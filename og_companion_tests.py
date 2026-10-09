"""Repeatable checks of discovery, cached indexes and generation boundaries."""
import ast
import gzip
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from urllib.error import URLError

import og_companion_search as search
import og_companion_sources as sources


class DiscoveryTests(unittest.TestCase):
    def test_csv_task_suggests_stdlib_and_dataframe(self):
        rows=search.local_search('Read CSV rows as dictionaries','Python')
        self.assertEqual(rows[0]['name'],'csv')
        self.assertIn('pandas',[r['name'] for r in rows])

    def test_language_filter_prevents_java_code_in_kotlin(self):
        self.assertEqual(search.local_search('HTTP request','Kotlin'),[])
        self.assertIn('java.net.http',[e['name'] for e in search.local_search('HTTP request','Java')])

    def test_task_synonym_finds_image_tool(self):
        self.assertEqual(search.local_search('Resize pictures','Python')[0]['name'],'Pillow')

    def test_offline_never_calls_registry(self):
        with patch.object(search,'registry_search') as remote:
            rows,status=search.search_libraries('CSV','Python',online=False)
        remote.assert_not_called();self.assertTrue(rows);self.assertIn('Offline',status)

    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError):search.search_libraries(' ','Python')

    def test_registry_failure_retains_starters(self):
        with patch.object(search,'registry_search',side_effect=URLError('offline')):
            rows,status=search.search_libraries('json','Python')
        self.assertTrue(rows);self.assertIn('failed',status)

    def test_fresh_full_index_cache_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            with gzip.open(Path(folder)/'pypi-index.json.gz','wt') as file:
                json.dump({'names':['a','library-not-in-starters'],'fetched_at':time.time()},file)
            with patch.object(search,'fetch_json') as http:
                names,status=search.pypi_names(folder)
            self.assertIn('library-not-in-starters',names);http.assert_not_called()

    def test_index_download_and_atomic_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(search,'fetch_json',return_value={'projects':[{'name':'new-package'}]}):
                names,status=search.pypi_names(folder)
            self.assertEqual(names,['new-package'])
            self.assertTrue((Path(folder)/'pypi-index.json.gz').is_file())
            self.assertFalse((Path(folder)/'pypi-index.json.tmp').exists())

    def test_stale_cache_kept_when_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            with gzip.open(Path(folder)/'pypi-index.json.gz','wt') as f:
                json.dump({'names':['retained'],'fetched_at':time.time()-90000},f)
            with patch.object(search,'fetch_json',side_effect=URLError('offline')):
                names,status=search.pypi_names(folder)
            self.assertEqual(names,['retained']);self.assertIn('Offline',status)

    def test_full_index_search_finds_nonstarter_package(self):
        with patch.object(search,'pypi_names',return_value=(['not-a-match','a-new-niche-library'],'Test full index')):
            rows,status=search.registry_search('niche','Python')
        self.assertEqual(rows[0]['name'],'a-new-niche-library')

    def test_pypi_selection_loads_actual_metadata(self):
        entry=search.package_result('package','Python','PyPI','','Select to load','https://pypi.org/project/package/','python -m pip install package')
        with patch.object(search,'fetch_json',return_value={'info':{'summary':'Real summary','version':'2.1','project_urls':{'Documentation':'https://example.com/docs'}}}):
            value=search.hydrate_python(entry)
        self.assertEqual(value['version'],'2.1');self.assertEqual(value['description'],'Real summary')

    def test_npm_scoped_name_retained(self):
        payload={'objects':[{'package':{'name':'@scope/tool','version':'1.0','description':'Useful tool','links':{'npm':'https://npmjs.com/package/@scope/tool'}}}]}
        with patch.object(search,'fetch_json',return_value=payload):
            rows,status=search.registry_search('tool','TypeScript')
        self.assertEqual(rows[0]['install'],'npm install @scope/tool')

    def test_other_languages_use_public_repository_discovery(self):
        with patch.object(sources,'github_search',return_value=([], 'GitHub live results')) as http:
            rows,status=search.registry_search('json','Go')
        self.assertFalse(rows);self.assertIn('GitHub',status);http.assert_called_once_with('json','Go',page=1)

    def test_malformed_nuget_service_rejected(self):
        with patch.object(search,'fetch_json',return_value={'resources':[{'@type':'SearchQueryService','@id':'http://other.example/query'}]}):
            with self.assertRaises(ValueError):search.registry_search('json','C#')

    def test_python_starters_parse_as_editable_code(self):
        for row in search.load_catalogue():
            if 'Python' in row['languages']:
                with self.subTest(library=row['name']):ast.parse(row['snippet'])

    def test_catalogue_links_and_language_metadata(self):
        for row in search.load_catalogue():
            self.assertTrue(row['docs'].startswith('https://'));self.assertTrue(row['snippet'].strip())
            self.assertTrue(set(row['languages']).issubset(search.LANGUAGES))


class GenerationTests(unittest.TestCase):
    def test_supported_foundation_selected_from_natural_request(self):
        task='I want a program that reads a CSV file, checks for missing values, shows the valid rows and saves them as JSON.'
        code,name=search.starter_program(task,'Python')
        self.assertEqual(name,'csv');ast.parse(code)

    def test_foundation_does_not_claim_unimplemented_gui_or_other_language(self):
        self.assertIsNone(search.starter_program('Read CSV and save JSON with a tkinter GUI','Python'))
        self.assertIsNone(search.starter_program('Read CSV and save JSON','Java'))

    def test_starter_mode_requests_all_features_and_program_structure(self):
        with patch.object(search,'fetch_json',return_value={'response':json.dumps({'code':'print(1)'})}) as http:
            search.generate_snippet('Load CSV, validate and save JSON','Python','local',program_mode=True)
        payload=http.call_args.kwargs['payload']
        self.assertIn('EACH requested feature',payload['prompt'])
        self.assertIn('main entry point',payload['prompt'])
        self.assertIn('Load CSV, validate and save JSON',payload['prompt'])
        self.assertEqual(payload['options']['num_predict'],3200)

    def test_blank_task_rejected_before_network(self):
        with self.assertRaises(ValueError):search.generate_snippet(' ','Python','model')

    def test_model_discovery_prefers_installed_coder(self):
        with patch.object(search,'fetch_json',return_value={'models':[{'name':'chat:1b'},{'name':'qwen-coder:1b'}]}):
            self.assertEqual(search.installed_models()[0],'qwen-coder:1b')

    def test_verified_model_preferred_when_available(self):
        with patch.object(search,'fetch_json',return_value={'models':[{'name':'qwen2.5-coder:1.5b'},{'name':'qwen2.5:3b'}]}):
            self.assertEqual(search.installed_models()[0],'qwen2.5:3b')

    def test_generation_context_and_fences(self):
        with patch.object(search,'fetch_json',return_value={'response':'```python\nprint(1)\n```'}) as http:
            code=search.generate_snippet('print','Python','local',{'name':'json'},'print(0)')
        self.assertEqual(code,'print(1)');payload=http.call_args.kwargs['payload']
        self.assertIn('print(0)',payload['prompt']);self.assertIn('json',payload['prompt']);self.assertFalse(payload['stream'])

    def test_fenced_source_extracted_without_surrounding_prose(self):
        response='Here is the program:\n```python\nprint("OG")\n```\nThis displays the name.'
        with patch.object(search,'fetch_json',return_value={'response':response}):
            self.assertEqual(search.generate_snippet('print','Python','local'),'print("OG")')

    def test_empty_model_response_is_failure(self):
        with patch.object(search,'fetch_json',return_value={'response':''}):
            with self.assertRaises(RuntimeError):search.generate_snippet('print','Python','model')

    def test_structured_code_is_extracted(self):
        with patch.object(search,'fetch_json',return_value={'response':json.dumps({'code':'print(1)'})}):
            self.assertEqual(search.generate_snippet('print','Python','model'),'print(1)')

    def test_invalid_python_response_is_rejected(self):
        with patch.object(search,'fetch_json',return_value={'response':json.dumps({'code':'- Python 3.x'})}):
            with self.assertRaisesRegex(RuntimeError,'invalid Python syntax'):search.generate_snippet('print','Python','model')

    def test_python_syntax_gets_one_correction_attempt(self):
        responses=[{'response':json.dumps({'code':'print("broken)'})},{'response':json.dumps({'code':'print("fixed")'})}]
        with patch.object(search,'fetch_json',side_effect=responses) as http:
            self.assertEqual(search.generate_snippet('print','Python','model'),'print("fixed")')
        self.assertEqual(http.call_count,2)
        self.assertIn('Correct the Python syntax',http.call_args.kwargs['payload']['prompt'])

    def test_incomplete_structured_response_is_rejected(self):
        with patch.object(search,'fetch_json',return_value={'response':'{"code":'}):
            with self.assertRaisesRegex(RuntimeError,'complete code response'):search.generate_snippet('print','Python','model')

    def test_offline_ai_error_explains_starters(self):
        with patch.object(search,'fetch_json',side_effect=URLError('offline')):
            with self.assertRaisesRegex(RuntimeError,'starter snippets'):search.generate_snippet('print','Python','model')

    def test_nested_entry_guard_rejected_before_it_can_recurse(self):
        with self.assertRaisesRegex(SyntaxError,'recursively'):
            search.validate_python('def main():\n    if __name__ == "__main__":\n        main()\n')

    def test_module_entry_guard_accepted(self):
        search.validate_python('def main():\n    print("OG")\nif __name__ == "__main__":\n    main()\n')

    def test_truncated_model_response_does_not_enter_editor_as_finished_code(self):
        with patch.object(search,'fetch_json',return_value={'response':'print(1)','done_reason':'length'}):
            with self.assertRaisesRegex(RuntimeError,'output limit'):search.generate_snippet('print','Python','model')


class StarterRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.folder=Path(self.directory.name)
        self.program=self.folder/'starter.py'
        self.program.write_text(search.starter_program('Read CSV and save JSON','Python')[0],encoding='utf-8')

    def run_starter(self,source,output):
        return subprocess.run([sys.executable,str(self.program),str(source),str(output)],capture_output=True,text=True,timeout=15)

    def test_valid_rows_displayed_and_saved_with_rejection_counts(self):
        source=self.folder/'journeys.csv';output=self.folder/'valid.json'
        source.write_text('driver,destination\nRob Johnston,London\nGillian Drake,Manchester\nAlex Richards,\nAli,   \nMissing\n',encoding='utf-8')
        result=self.run_starter(source,output)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(output.read_text()),[{'driver':'Rob Johnston','destination':'London'},{'driver':'Gillian Drake','destination':'Manchester'}])
        self.assertIn('Rob Johnston',result.stdout);self.assertIn('Valid rows: 2; rejected rows: 3',result.stdout)

    def test_input_cannot_be_overwritten(self):
        source=self.folder/'input.csv';source.write_text('value\nkept\n')
        result=self.run_starter(source,source)
        self.assertNotEqual(result.returncode,0);self.assertEqual(source.read_text(),'value\nkept\n')

    def test_missing_file_reported_without_traceback_or_output(self):
        output=self.folder/'output.json'
        result=self.run_starter(self.folder/'absent.csv',output)
        self.assertNotEqual(result.returncode,0);self.assertIn('Could not process',result.stderr)
        self.assertNotIn('Traceback',result.stderr);self.assertFalse(output.exists())

    def test_empty_csv_reported_without_creating_output(self):
        source=self.folder/'empty.csv';source.write_text('');output=self.folder/'output.json'
        result=self.run_starter(source,output)
        self.assertNotEqual(result.returncode,0);self.assertIn('header row',result.stderr);self.assertFalse(output.exists())


class SourceBrowserTests(unittest.TestCase):
    def test_pypi_page_two_reaches_packages_after_first_fifty(self):
        names=['library-'+str(i).zfill(3) for i in range(135)]
        with patch.object(search,'pypi_names',return_value=(names,'Index')):
            first,_=search.registry_search('library','Python')
            second,_=search.registry_search('library','Python',page=2)
            third,_=search.registry_search('library','Python',page=3)
        self.assertEqual(len(first),50);self.assertEqual(len(second),50);self.assertEqual(len(third),35)
        self.assertFalse({r['name'] for r in first}&{r['name'] for r in second})

    def test_npm_page_offset_sent_to_provider(self):
        with patch.object(search,'fetch_json',return_value={'objects':[]}) as http:
            search.registry_search('csv','JavaScript',page=3)
        self.assertIn('from=100',http.call_args.args[0])

    def test_sonatype_compatibility_endpoint_uses_page_index(self):
        with patch.object(search,'fetch_json',return_value={'response':{'docs':[]}}) as http:
            search.registry_search('json','Java',page=2)
        self.assertIn('start=1',http.call_args.args[0]);self.assertNotIn('start=50',http.call_args.args[0])

    def test_standard_module_without_curated_snippet_is_found(self):
        rows,_=search.search_libraries('heapq','Python',online=False)
        self.assertIn('heapq',[r['name'] for r in rows])

    def test_every_markdown_code_block_retained_beyond_thirty(self):
        text='\n'.join('## Sample '+str(i)+'\n```python\nprint('+str(i)+')\n```\n' for i in range(83))
        rows=sources.extract_examples(text,'https://example.org/docs','Python')
        self.assertEqual(len(rows),83);self.assertEqual(rows[-1]['code'],'print(82)')
        self.assertTrue(all(r['url']=='https://example.org/docs' for r in rows))

    def test_code_and_configuration_languages_kept_separate(self):
        text='```bash\nnpm install tool\n```\n```ts\nconst n: number = 1;\n```\n```json\n{"a": 1}\n```\n'
        rows=sources.extract_examples(text,'https://example.org','JavaScript')
        self.assertEqual([r['language'] for r in rows],['Bash','TypeScript','JSON'])

    def test_html_entities_and_nested_code_preserve_original(self):
        text='<h2>Filtering</h2><pre data-language="python"><code>if x &lt; 3:\n    print("OG")</code></pre>'
        rows=sources.extract_examples(text,'https://example.org','Python')
        self.assertEqual(rows[0]['code'],'if x < 3:\n    print("OG")')
        self.assertIn('Filtering',rows[0]['title'])

    def test_python_transcripts_are_not_claimed_as_executable_scripts(self):
        rows=sources.extract_examples('<pre>&gt;&gt;&gt; 1 + 1\n2</pre>','https://example.org','Python')
        self.assertEqual(rows[0]['language'],'Python transcript');self.assertIn('>>>',rows[0]['code'])

    def test_rst_code_block_extracted(self):
        text='.. code-block:: python\n\n    print("OG")\n\nOutside prose\n'
        rows=sources.extract_examples(text,'https://example.org','Python')
        self.assertEqual(rows[0]['code'],'print("OG")')

    def test_private_and_non_https_sources_rejected(self):
        for url in ('http://example.org','https://127.0.0.1/a','https://192.168.1.1','https://localhost',
                    'file:///secret','https://user:password@example.org','https://example.org:1234'):
            with self.subTest(url=url),self.assertRaises(ValueError):sources.public_url(url,resolve=False)

    def test_public_hostname_resolving_to_private_ip_rejected(self):
        with patch.object(sources.socket,'getaddrinfo',return_value=[(2,1,6,'',('10.0.0.1',443))]):
            with self.assertRaises(ValueError):sources.public_url('https://example.org')

    def test_downloaded_document_available_offline_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sources,'fetch_text',return_value=('```python\nprint(1)\n```','https://example.org','text/plain')):
                sources.cached_document('https://example.org',cache_dir=folder)
            with patch.object(sources,'fetch_text') as http:
                text,_,_,status=sources.cached_document('https://example.org',online=False,cache_dir=folder)
            http.assert_not_called();self.assertIn('print(1)',text);self.assertIn('Cached',status)

    def test_missing_cache_does_not_silently_go_online(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(sources,'fetch_text') as http:
            with self.assertRaises(RuntimeError):sources.cached_document('https://example.org',online=False,cache_dir=folder)
            http.assert_not_called()

    def test_entire_documentation_index_browsable_across_pages(self):
        doc={'slug':'python~3.14','name':'Python','type':'python','version':'3.14'}
        index=json.dumps({'entries':[{'name':'API '+str(i).zfill(3),'path':'library/a'+str(i),'type':'Library'} for i in range(205)]})
        with patch.object(sources,'cached_document',return_value=(index,'url','application/json','Cached')):
            rows,status=sources.documentation_search(doc,page=3,online=False)
        self.assertEqual(len(rows),5);self.assertIn('205',status)
        self.assertEqual(rows[0]['name'],'API 200')

    def test_no_code_page_returns_empty_collection_honestly(self):
        with patch.object(sources,'public_url'),patch.object(sources,'repository_readme',return_value=None),patch.object(sources,'cached_document',return_value=('<p>No examples</p>','https://example.org','text/html','Live')):
            rows,status=sources.url_examples('https://example.org','Python')
        self.assertEqual(rows,[]);self.assertIn('0 code examples',status)

    def test_pypi_readme_code_available_for_arbitrary_package(self):
        entry=search.package_result('not-in-offline-catalogue','Python','PyPI','','1','', 'pip install test','https://pypi.org/project/test/')
        info={'info':{'description':'```python\nimport new_library\nnew_library.example()\n```','license_expression':'MIT'}}
        with patch.object(sources,'cached_document',return_value=(json.dumps(info),'url','application/json','Live')):
            rows,status=sources.library_examples(entry)
        self.assertEqual(rows[0]['code'],'import new_library\nnew_library.example()')
        self.assertEqual(rows[0]['licence'],'MIT')


class ExpansionBoundaryTests(unittest.TestCase):
    def test_identical_and_comment_only_python_changes_rejected(self):
        for code in ('print(1)', '# extra comment\nprint(1)'):
            with self.subTest(code=code),self.assertRaises(ValueError):
                search.validate_expansion('print(1)',code,'Python')

    def test_missing_named_component_rejected(self):
        with self.assertRaises(ValueError):
            search.validate_expansion('def greet():\n    return "hi"','print("added")','Python')

    def test_no_change_model_result_retried_then_rejected(self):
        with patch.object(search,'fetch_json',return_value={'response':'print(1)'}) as http:
            with self.assertRaises(RuntimeError):search.generate_snippet('expand','Python','local',existing_code='print(1)')
        self.assertEqual(http.call_count,2)

    def test_full_context_round_and_previous_requirement_sent(self):
        old='def greet():\n    return "hi"\n'
        with patch.object(search,'fetch_json',return_value={'response':old+'print(greet())'}) as http:
            search.generate_snippet('display greeting','Python','local',existing_code=old,expansion_round=2,previous_description='make a greeting')
        prompt=http.call_args.kwargs['payload']['prompt']
        self.assertIn(old,prompt);self.assertIn('make a greeting',prompt);self.assertIn('2',prompt)

    def test_oversized_existing_code_rejected_without_network_or_truncation(self):
        with patch.object(search,'fetch_json') as http:
            with self.assertRaises(ValueError):search.generate_snippet('expand','Python','local',existing_code='#'+('a'*24001))
        http.assert_not_called()

    def test_expand_intent_follows_current_code_in_prompt(self):
        with patch.object(search,'fetch_json',return_value={'response':'print(1)\nprint(2)'}) as http:
            search.generate_snippet('print one','Python','local',existing_code='print(1)',additional_feature=True)
        prompt=http.call_args.kwargs['payload']['prompt']
        self.assertGreater(prompt.index('EXPAND button request'),prompt.index('CURRENT SOURCE'))

    def test_timeout_reports_timeout_instead_of_missing_service(self):
        with patch.object(search,'fetch_json',side_effect=TimeoutError('slow')):
            with self.assertRaisesRegex(RuntimeError,'timed out after 300 seconds'):
                search.generate_snippet('print','Python','local')


class WorkbenchControlTests(unittest.TestCase):
    def setUp(self):
        import og_companion as ui
        self.ui=ui;self.app=ui.OGCompanion(discover_models=False);self.app.withdraw();self.app.update()
        self.app.model.set('test-coder')

    def tearDown(self):self.app.destroy()

    def code(self):return self.app.output.get('1.0','end-1c')

    def wait_request(self):
        deadline=time.monotonic()+4
        while self.app.busy and time.monotonic()<deadline:self.app.update();time.sleep(.01)
        self.assertFalse(self.app.busy,'Worker did not finish');self.app.update()

    def describe(self,text):self.app.description.delete('1.0','end');self.app.description.insert('1.0',text)

    def test_clear_search_button_clears_results_and_keeps_code(self):
        self.app.set_code('print("keep me")','Python','Test');self.app.editor_dirty=True
        self.app.keywords.set('csv');self.app.clear_search_button.invoke();self.app.update()
        self.assertEqual(self.code(),'print("keep me")');self.assertTrue(self.app.editor_dirty)
        self.assertFalse(self.app.description.get('1.0','end-1c'));self.assertFalse(self.app.keywords.get())
        self.assertFalse(self.app.entries);self.assertFalse(self.app.library_tree.get_children())
        self.assertIsNone(self.app.selected_library);self.assertIsNone(self.app.search_context)

    def test_cleared_search_ignores_late_result_and_progress(self):
        import threading
        event=threading.Event()
        self.app.worker('search',lambda:(event.wait(2),([], 'old results'))[1])
        epoch=self.app.work_epoch;self.app.clear_search_button.invoke();event.set()
        self.app.results.put(('progress',True,(epoch,'old progress')))
        time.sleep(.04);self.app.poll()
        self.assertFalse(self.app.entries);self.assertEqual(self.app.status.get(),'Search cleared. Your code is retained.')

    def test_expansion_button_repeats_using_latest_code(self):
        old='print(1)';one='print(1)\nprint(2)';two=one+'\nprint(3)'
        self.app.set_code(old,'Python','Test');self.describe('Add useful output')
        with patch.object(self.ui,'generate_snippet',side_effect=[one,two]) as generate:
            self.app.expand_button.invoke();self.wait_request()
            self.app.expand_button.invoke();self.wait_request()
        self.assertEqual([call.args[4] for call in generate.call_args_list],[old,one])
        self.assertEqual(self.code(),two);self.assertEqual(self.app.expansion_round,2)
        self.assertTrue(generate.call_args.kwargs['additional_feature'])
        self.assertEqual(generate.call_args.kwargs['previous_description'],'Add useful output')

    def test_changed_description_updates_existing_code_without_reset(self):
        old='print(1)';new=old+'\nprint(2)';self.app.set_code(old,'Python','Test')
        self.describe('Also display two')
        with patch.object(self.ui,'generate_snippet',return_value=new) as generate:
            self.app.generate_button.invoke();self.wait_request()
        self.assertEqual(generate.call_args.args[0],'Also display two');self.assertEqual(generate.call_args.args[4],old)
        self.assertEqual(self.code(),new)

    def test_undo_restores_code_before_update(self):
        self.app.set_code('print(1)','Python','Test')
        self.app.set_code('print(1)\nprint(2)','Python','Test',keep_undo=True)
        self.app.undo_button.invoke();self.assertEqual(self.code(),'print(1)')

    def test_search_selection_does_not_overwrite_code_or_origin(self):
        self.app.set_code('print("mine")','Python','My program')
        origin=self.app.code_origin.get();self.app.show_results(search.local_search('csv','Python'),'results');self.app.update()
        self.assertEqual(self.code(),'print("mine")');self.assertEqual(self.app.code_origin.get(),origin)

    def test_empty_search_disables_stale_example_actions(self):
        self.app.examples=[{'code':'old'}];self.app.export_button.configure(state='normal')
        self.app.show_results([], 'nothing')
        self.assertFalse(self.app.examples);self.assertIn('disabled',self.app.export_button.state())
        self.assertIn('disabled',self.app.examples_button.state())

    def test_clear_code_respects_declined_confirmation(self):
        self.app.set_code('print(1)','Python','Test');self.app.editor_dirty=True
        with patch.object(self.ui.messagebox,'askyesno',return_value=False):self.app.clear_code_button.invoke()
        self.assertEqual(self.code(),'print(1)')
        with patch.object(self.ui.messagebox,'askyesno',return_value=True):self.app.clear_code_button.invoke()
        self.assertEqual(self.code(),'');self.assertEqual(self.app.expansion_round,0)

    def test_language_switch_does_not_send_wrong_language_code(self):
        self.app.set_code('print(1)','Python','Test');self.app.language.set('JavaScript')
        with patch.object(self.ui,'generate_snippet') as generate:self.app.generate_button.invoke()
        generate.assert_not_called();self.assertEqual(self.code(),'print(1)');self.assertIn('Choose that language',self.app.status.get())

    def test_missing_model_detected_and_code_preserved(self):
        self.app.set_code('print(1)','Python','Test');self.app.model.set('')
        with patch.object(self.ui,'installed_models',return_value=[]):
            self.app.expand_button.invoke();self.wait_request()
        self.assertEqual(self.code(),'print(1)');self.assertIn('need Ollama',self.app.status.get())

    def test_failed_generation_retains_current_edits(self):
        self.app.set_code('print("mine")','Python','Test');self.app.editor_dirty=True
        with patch.object(self.ui,'generate_snippet',side_effect=RuntimeError('No code change')):
            self.app.expand_button.invoke();self.wait_request()
        self.assertEqual(self.code(),'print("mine")');self.assertTrue(self.app.editor_dirty)

    def test_saved_newer_edits_still_need_confirmation_before_replacement(self):
        self.app.set_code('print("newer saved")','Python','Test');self.app.editor_dirty=False
        self.app.generation_baseline='print("older")'
        self.app.results.put(('generate',True,('print("response")','Python','request',1,'test')))
        with patch.object(self.ui.messagebox,'askyesno',return_value=False) as confirm:self.app.poll()
        confirm.assert_called_once();self.assertEqual(self.code(),'print("newer saved")')


if __name__=='__main__':unittest.main()
