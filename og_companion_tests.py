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
        from PySide6.QtTest import QTest
        self.ui=ui;self.QTest=QTest;self.app=ui.OGCompanion(discover_models=False)
        self.app.connected_model={'name':'test-coder','endpoint':'http://localhost:11434','provider':'Ollama'}
    def tearDown(self):self.app.dispose()
    def code(self):return self.app.output.toPlainText()
    def describe(self,text):self.app.description.setPlainText(text)
    def wait_request(self):
        deadline=time.monotonic()+4
        while self.app.busy and time.monotonic()<deadline:self.ui.application().processEvents();time.sleep(.01)
        self.assertFalse(self.app.busy,'Worker did not finish');self.ui.application().processEvents()
    def test_three_main_tabs(self):
        self.assertEqual([self.app.tabs.tabText(i) for i in range(3)],['Build code','Browse libraries','Models / API'])
    def test_clear_request_keeps_user_code(self):
        self.app.set_code('print("mine")','Python','My program');self.app.editor_dirty=True
        self.describe('CSV');self.app.keywords.setPlainText('csv');self.app.clear_search_button.click()
        self.assertEqual(self.code(),'print("mine")');self.assertTrue(self.app.editor_dirty)
        self.assertFalse(self.app.entries);self.assertFalse(self.app.description.toPlainText());self.assertFalse(self.app.keywords.toPlainText())
    def test_cleared_search_ignores_late_result(self):
        import threading
        event=threading.Event();self.app.worker('search',lambda:(event.wait(2),([], 'old result'))[1])
        self.app.clear_search_button.click();event.set();time.sleep(.04);self.app.poll()
        self.assertEqual(self.app.status.text(),'Request cleared. Your code is retained.');self.assertFalse(self.app.entries)
    def test_expansion_repeats_using_latest_code(self):
        old='print(1)';one=old+'\nprint(2)';two=one+'\nprint(3)'
        self.app.set_code(old,'Python','Test');self.describe('Add useful output')
        with patch.object(self.ui,'generate_snippet',side_effect=[one,two]) as generate:
            self.app.expand_button.click();self.wait_request();self.app.expand_button.click();self.wait_request()
        self.assertEqual([call.args[4] for call in generate.call_args_list],[old,one]);self.assertEqual(self.code(),two)
        self.assertTrue(generate.call_args.kwargs['additional_feature']);self.assertEqual(self.app.expansion_round,2)
    def test_changed_description_updates_existing_code(self):
        old='print(1)';self.app.set_code(old,'Python','Test');self.describe('Also display two')
        with patch.object(self.ui,'generate_snippet',return_value=old+'\nprint(2)') as generate:
            self.app.generate_button.click();self.wait_request()
        self.assertEqual(generate.call_args.args[4],old);self.assertEqual(generate.call_args.args[0],'Also display two')
    def test_undo_restores_preceding_update(self):
        self.app.set_code('print(1)','Python','Test');self.app.set_code('print(2)','Python','Updated',keep_undo=True)
        self.app.undo_button.click();self.assertEqual(self.code(),'print(1)')
    def test_library_selection_retains_code_and_origin(self):
        self.app.set_code('print("mine")','Python','Mine');origin=self.app.code_origin.text()
        self.app.show_results(search.task_libraries('csv','Python'),'results')
        self.assertEqual(self.code(),'print("mine")');self.assertEqual(self.app.code_origin.text(),origin)
    def test_empty_results_disable_stale_actions(self):
        self.app.examples=[{'code':'old'}];self.app.show_results([], 'nothing')
        self.assertFalse(self.app.examples);self.assertFalse(self.app.export_button.isEnabled());self.assertFalse(self.app.examples_button.isEnabled())
    def test_declined_replacement_preserves_unsaved_code(self):
        self.app.set_code('print(1)','Python','Test');self.app.editor_dirty=True
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.No):self.app.clear_code_button.click()
        self.assertEqual(self.code(),'print(1)')
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.Yes):self.app.clear_code_button.click()
        self.assertEqual(self.code(),'')
    def test_wrong_language_update_is_blocked(self):
        self.app.set_code('print(1)','Python','Test');self.app.language_box.setCurrentText('JavaScript');self.describe('Add output')
        with patch.object(self.ui,'generate_snippet') as generate:self.app.generate_button.click()
        generate.assert_not_called();self.assertEqual(self.code(),'print(1)')
    def test_missing_connection_retains_code(self):
        self.app.set_code('print(1)','Python','Test');self.app.connected_model=None;self.describe('Add output')
        with patch.object(self.ui,'discover_task_examples',return_value=([],[],'No matching source examples')) as discover:
            self.app.expand_button.click();self.wait_request()
        self.assertEqual(self.code(),'print(1)');discover.assert_called_once()
    def test_failed_model_response_retains_user_edits(self):
        self.app.set_code('print("mine")','Python','Test');self.app.editor_dirty=True;self.describe('Add output')
        with patch.object(self.ui,'generate_snippet',side_effect=RuntimeError('No code change')):
            self.app.expand_button.click();self.wait_request()
        self.assertEqual(self.code(),'print("mine")');self.assertTrue(self.app.editor_dirty)
    def test_newer_saved_edits_are_protected(self):
        self.app.set_code('print("newer")','Python','Test');self.app.generation_baseline='print("old")'
        self.app.results.put(('generate',True,('print("model")','Python','request',1)))
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.No):self.app.poll()
        self.assertEqual(self.code(),'print("newer")')
    def test_keyboard_input_and_main_button_produce_exact_user_starter(self):
        self.app.connected_model=None;self.QTest.keyClicks(self.app.description,'cybersecurity, file libraries, security considerations')
        self.app.generate_button.click();self.assertIn('def file_hash',self.code())
        self.assertIn('hashlib',[e['name'] for e in self.app.entries]);self.assertIn('Hashes detect changes',self.app.guidance.toPlainText())
    def test_discovery_does_not_block_typing_or_generation(self):
        import threading
        event=threading.Event()
        with patch.object(self.ui,'discover_models',side_effect=lambda endpoints:(event.wait(2),[])[1]):
            self.app.refresh_models();self.QTest.keyClicks(self.app.description,'I can still type')
            self.assertFalse(self.app.busy);self.assertTrue(self.app.generate_button.isEnabled());event.set()
            deadline=time.monotonic()+3
            while self.app.models_loading and time.monotonic()<deadline:self.ui.application().processEvents();time.sleep(.01)
        self.assertEqual(self.app.description.toPlainText(),'I can still type')
    def test_offline_documentation_reference_without_model(self):
        self.app.connected_model=None;self.describe('pytest fixtures');self.app.online.setChecked(False)
        example={'code':'def test_example():\n    assert 1 + 1 == 2','language':'Python','title':'Example','url':'https://devdocs.io/pytest','licence':'MIT'}
        with patch.object(self.ui,'discover_task_examples',return_value=([],[example],'Cached examples')):
            self.app.generate_button.click();self.wait_request()
        self.assertEqual(self.code(),'');self.assertIn('def test_example',self.app.preview_code.toPlainText());self.assertEqual(self.app.examples,[example])
        self.app.add_button.click();self.assertIn('def test_example',self.code())
    def test_discovery_lists_all_recipient_models_without_connecting(self):
        self.app.connected_model=None
        models=[{'name':'one','endpoint':'http://localhost:11434','provider':'Ollama'},{'name':'two','endpoint':'http://localhost:1234','provider':'LM Studio','loaded':False}]
        self.app.results.put(('models',True,models));self.app.poll()
        self.assertEqual(self.app.model_table.rowCount(),2);self.assertIsNone(self.app.connected_model)
    def test_explicit_connection_uses_selected_model(self):
        model={'name':'chosen','endpoint':'http://localhost:23123','provider':'Ollama'}
        self.app.results.put(('models',True,[model]));self.app.poll();self.app.connected_model=None
        with patch.object(self.ui,'connect_local_model',return_value=model) as connect:
            self.app.connect_button.click();deadline=time.monotonic()+3
            while self.app.connected_model is None and time.monotonic()<deadline:self.ui.application().processEvents();time.sleep(.01)
        connect.assert_called_once_with(model);self.assertEqual(self.app.connected_model,model)

    def test_window_is_brought_inside_the_preferred_work_area(self):
        screen=self.ui.application().primaryScreen();work=screen.availableGeometry()
        self.app.placement={'screen':screen.name()};self.app.resize(1280,900);self.app.move(work.left(),work.top()-1000)
        self.app.ensure_on_screen();frame=self.app.frameGeometry()
        self.assertTrue(work.contains(frame),(work,frame))

    def test_disconnected_preferred_monitor_falls_back_to_a_visible_screen(self):
        self.app.placement={'screen':'disconnected-monitor'};self.app.move(-5000,-5000);self.app.ensure_on_screen()
        self.assertTrue(any(s.availableGeometry().contains(self.app.frameGeometry()) for s in self.ui.application().screens()))


class TaskAndModelTests(unittest.TestCase):
    def test_exact_cybersecurity_request_has_code_and_libraries(self):
        task='cybersecurity, file libraries, security considerations'
        entries=search.task_libraries(task,'Python')
        self.assertIn('hashlib',[e['name'] for e in entries]);self.assertIn('pathlib',[e['name'] for e in entries])
        code,name=search.starter_program(task,'Python');ast.parse(code)
        self.assertIn('def compare',code);self.assertIn('Hashes detect changes',search.task_guidance(task,'Python',entries))

    def test_security_starter_does_not_silently_drop_gui_request(self):
        self.assertIsNone(search.starter_program('cybersecurity file monitor with GUI','Python'))

    def test_integrity_starter_records_and_detects_actual_file_changes(self):
        code,_=search.starter_program('cybersecurity file libraries security considerations','Python')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);data=root/'data';data.mkdir();(data/'a.txt').write_text('one')
            script=root/'integrity.py';script.write_text(code,encoding='utf-8');manifest=root/'manifest.json'
            baseline=subprocess.run([sys.executable,str(script),'baseline',str(data),str(manifest)],capture_output=True,text=True)
            self.assertEqual(baseline.returncode,0,baseline.stdout+baseline.stderr)
            (data/'a.txt').write_text('two');(data/'b.txt').write_text('new')
            result=subprocess.run([sys.executable,str(script),'check',str(data),str(manifest)],capture_output=True,text=True)
            self.assertIn('"a.txt"',result.stdout);self.assertIn('"b.txt"',result.stdout)
            second=subprocess.run([sys.executable,str(script),'baseline',str(data),str(manifest)],capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0)
            self.assertEqual(json.loads(manifest.read_text())['hashes']['a.txt'],__import__('hashlib').sha256(b'one').hexdigest())

    def test_custom_ollama_port_is_used(self):
        with patch.object(search,'fetch_json',return_value={'models':[{'name':'recipient-model'}]}) as fetch:
            rows=search.models_at('http://127.0.0.1:23001')
        self.assertEqual(rows[0]['name'],'recipient-model');self.assertEqual(fetch.call_args.args[0],'http://127.0.0.1:23001/api/tags')

    def test_discovery_includes_all_services_and_does_not_connect(self):
        with patch.object(search,'model_endpoints',return_value=['http://localhost:1111']),patch.object(search,'models_at',side_effect=lambda endpoint:[{'name':'model-'+endpoint,'endpoint':endpoint,'provider':'Ollama'}]),patch.object(search,'connect_local_model') as connect:
            rows=search.discover_models(['http://localhost:2222'])
        self.assertEqual(len(rows),2);connect.assert_not_called()

    def test_unreachable_service_does_not_hide_reachable_recipient_models(self):
        def available(endpoint):
            if endpoint.endswith('1111'):raise URLError('offline')
            return [{'name':'mine','endpoint':endpoint,'provider':'Ollama'}]
        with patch.object(search,'model_endpoints',return_value=['http://localhost:1111','http://localhost:2222']),patch.object(search,'models_at',side_effect=available):
            self.assertEqual(search.discover_models()[0]['name'],'mine')

    def test_lm_studio_lists_downloaded_and_loaded_models(self):
        def api(url,**kwargs):
            if url.endswith('/api/tags'):raise URLError('not Ollama')
            return {'models':[{'key':'downloaded','type':'llm','loaded_instances':[]},{'key':'loaded','type':'llm','loaded_instances':[{'id':'instance'}]},{'key':'embedding','type':'embedding'}]}
        with patch.object(search,'fetch_json',side_effect=api):rows=search.models_at('http://localhost:1234')
        self.assertEqual(len(rows),3);self.assertFalse(rows[0]['loaded']);self.assertTrue(rows[1]['loaded'])

    def test_lm_studio_connection_loads_only_explicit_selection(self):
        model={'name':'downloaded','endpoint':'http://localhost:1234','provider':'LM Studio','kind':'llm','loaded':False}
        with patch.object(search,'models_at',return_value=[model]),patch.object(search,'fetch_json',return_value={'instance_id':'loaded-instance'}) as fetch:
            connected=search.connect_local_model(model)
        self.assertEqual(connected['inference_name'],'loaded-instance');self.assertEqual(fetch.call_args.kwargs['payload'],{'model':'downloaded'})

    def test_embedding_model_is_listed_but_not_used_for_code(self):
        model={'name':'embedding','endpoint':'http://localhost:1234','provider':'LM Studio','kind':'embedding'}
        with patch.object(search,'models_at',return_value=[model]),patch.object(search,'fetch_json') as fetch:
            with self.assertRaisesRegex(RuntimeError,'Choose a language model'):search.connect_local_model(model)
        fetch.assert_not_called()

    def test_remote_service_urls_are_rejected(self):
        for endpoint in ('https://example.com','http://user:secret@localhost:1234','file:///tmp/model','http://127.0.0.1:1234/?key=secret'):
            with self.assertRaises(ValueError):search.local_endpoint(endpoint)

    def test_generation_uses_connected_recipient_endpoint(self):
        with patch.object(search,'fetch_json',return_value={'response':'print(1)'}) as fetch:
            search.generate_snippet('Print one','Python','recipient',endpoint='http://localhost:23123')
        self.assertEqual(fetch.call_args.args[0],'http://localhost:23123/api/generate')

    def test_openai_compatible_local_model_generates_code(self):
        with patch.object(search,'fetch_json',return_value={'choices':[{'message':{'content':'print(1)'},'finish_reason':'stop'}]}) as fetch:
            code=search.generate_snippet('Print one','Python','recipient',endpoint='http://localhost:1234',provider='LM Studio')
        self.assertEqual(code,'print(1)');self.assertEqual(fetch.call_args.args[0],'http://localhost:1234/v1/chat/completions')

    def test_reusable_module_rejects_unrequested_interactive_prompts(self):
        with patch.object(search,'fetch_json',side_effect=[{'response':'value = input("Name: ")'},{'response':'def value():\n    return 1'}]) as fetch:
            code=search.generate_snippet('A reusable module without a CLI or input prompts','Python','local')
        self.assertIn('def value',code);self.assertEqual(fetch.call_count,2)

    def test_legacy_lm_studio_includes_downloaded_models(self):
        def api(url,**kwargs):
            if url.endswith(('/api/tags','/api/v1/models')):raise URLError('not this API')
            return {'data':[{'id':'downloaded','type':'llm','state':'not-loaded'},{'id':'loaded','type':'llm','state':'loaded'}]}
        with patch.object(search,'fetch_json',side_effect=api):rows=search.models_at('http://localhost:1234')
        self.assertEqual(len(rows),2);self.assertFalse(rows[0]['loaded']);self.assertTrue(rows[1]['loaded'])

    def test_service_token_used_only_for_local_model_requests(self):
        with patch.dict(search.MODEL_TOKENS,{},clear=True),patch.object(search,'fetch_json',return_value={}) as fetch:
            search.set_service_token('http://localhost:1234','controlled-test-token')
            search.model_json('http://localhost:1234','/v1/models')
            self.assertEqual(fetch.call_args.kwargs['headers_extra'],{'Authorization':'Bearer controlled-test-token'})
            with self.assertRaises(ValueError):search.model_json('https://example.com','/v1/models')
            self.assertEqual(fetch.call_count,1)

    def test_removing_service_token_clears_it_from_memory(self):
        with patch.dict(search.MODEL_TOKENS,{},clear=True):
            search.set_service_token('http://localhost:1234','test');search.set_service_token('http://localhost:1234','')
            self.assertFalse(search.MODEL_TOKENS)

    def test_common_openai_base_url_does_not_duplicate_api_paths(self):
        self.assertEqual(search.local_endpoint('http://localhost:1234/v1'),'http://localhost:1234')
        with patch.object(search,'fetch_json',return_value={'models':[{'name':'recipient'}]}) as fetch:
            search.models_at('http://localhost:1234/v1')
        self.assertEqual(fetch.call_args.args[0],'http://localhost:1234/api/tags')


class CompleteCollectionTests(unittest.TestCase):
    def test_complete_database_reads_all_pages_and_deduplicates(self):
        doc={'name':'Test','slug':'test','mtime':12,'attribution':'Original author; MIT','type':'python'}
        data={str(i):'<pre data-language="python">print('+str(i)+')</pre>' for i in range(87)}
        data['duplicate']=data['0']
        with tempfile.TemporaryDirectory() as folder,patch.object(sources,'fetch_text',return_value=(json.dumps(data),'url','application/json')):
            rows,status=sources.collection_examples(doc,cache_dir=folder)
        self.assertEqual(len(rows),87);self.assertIn('88 pages',status);self.assertIn('MIT',rows[0]['licence'])
        self.assertTrue(all(e['url'].startswith('https://devdocs.io/test/') for e in rows))

    def test_complete_collection_cache_is_usable_offline(self):
        doc={'name':'Test','slug':'test','mtime':12}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sources,'fetch_text',return_value=('{"index":"<pre>code</pre>"}','url','application/json')):
                sources.collection_examples(doc,cache_dir=folder)
            with patch.object(sources,'fetch_text') as network:
                rows,_=sources.collection_examples(doc,cache_dir=folder,online=False)
            self.assertEqual(len(rows),1);network.assert_not_called()

    def test_matching_library_uses_entire_manifest_and_preserves_language(self):
        docs=[{'name':'Requests','slug':'requests'},{'name':'scikit-learn','slug':'scikit_learn','alias':'sklearn'}]
        with patch.object(sources,'documentation_catalogue',return_value=docs):
            self.assertEqual(sources.matching_documentation({'name':'sklearn','language':'Python'})['slug'],'scikit_learn')
            self.assertIsNone(sources.matching_documentation({'name':'requests','language':'JavaScript'}))

    def test_library_matching_full_collection_replaces_single_teaching_example(self):
        doc={'name':'NumPy','slug':'numpy~2.5'}
        entry=search.package_result('numpy','Python','Starter library','','','https://numpy.org','pip install numpy')
        entry['snippet']='import numpy'
        with patch.object(sources,'matching_documentation',return_value=doc),patch.object(sources,'collection_examples',return_value=([{'code':'full'}],'full collection')) as load:
            rows,_=sources.library_examples(entry)
        load.assert_called_once();self.assertEqual(rows,[{'code':'full'}])

    def test_invalid_collection_slug_rejected(self):
        with self.assertRaises(ValueError):sources.collection_examples({'slug':'../private'})

    def test_unexpected_database_does_not_cache_a_false_success(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(sources,'fetch_text',return_value=('{"index":4}','url','application/json')):
            with self.assertRaises(ValueError):sources.collection_examples({'name':'Test','slug':'test'},cache_dir=folder)
            self.assertFalse(list(Path(folder).glob('*.gz')))

    def test_github_library_name_is_not_changed_to_a_task_synonym(self):
        with patch.object(sources,'fetch_json',return_value={'items':[],'total_count':0}) as fetch:
            sources.github_search('requests','Python')
        self.assertIn('q=requests+',fetch.call_args.args[0]);self.assertNotIn('q=http+',fetch.call_args.args[0])

    def test_cmake_file_loads_as_actual_source_not_repository_readme(self):
        with patch.object(sources,'public_url'),patch.object(sources,'cached_document',return_value=('cmake_minimum_required(VERSION 3.20)','https://raw.githubusercontent.com/a/b/main/CMakeLists.txt','text/plain','Live')),patch.object(sources,'repository_readme') as readme:
            rows,_=sources.url_examples('https://github.com/a/b/blob/main/CMakeLists.txt','CMake')
        readme.assert_not_called();self.assertEqual(rows[0]['language'],'CMake');self.assertIn('cmake_minimum',rows[0]['code'])

    def test_cmake_selector_and_save_extension(self):
        self.assertIn('CMake',search.LANGUAGES);self.assertEqual(search.EXTENSIONS['CMake'],'.cmake')


class IncrementalWorkbenchTests(unittest.TestCase):
    setUp=WorkbenchControlTests.setUp
    tearDown=WorkbenchControlTests.tearDown
    code=WorkbenchControlTests.code
    describe=WorkbenchControlTests.describe
    def example(self,code,language='Python',title='Test example'):
        return {'code':code,'language':language,'title':title,'url':'https://example.com/docs','licence':'Test fixture'}
    def test_wrong_language_source_never_enters_editor(self):
        self.app.language_box.setCurrentText('JavaScript');self.app.set_code('console.log("mine")','JavaScript','Mine')
        self.app.show_examples([self.example('import click','Python')],'Click collection')
        self.assertFalse(self.app.examples);self.assertEqual(self.code(),'console.log("mine")');self.assertIn('No matching JavaScript',self.app.status.text())
    def test_preview_preserves_saved_and_unsaved_code(self):
        self.app.set_code('print("mine")','Python','Mine');self.app.editor_dirty=True
        self.app.show_examples([self.example('print("new")')],'Results')
        self.assertEqual(self.code(),'print("mine")');self.assertTrue(self.app.editor_dirty)
        self.assertEqual(self.app.preview_code.toPlainText(),'print("new")')
    def test_two_additions_and_undo_preserve_code_and_teaching(self):
        self.app.set_code('value = 10','Python','Mine');self.app.set_guidance('Original explanation')
        self.app.show_examples([self.example('value += 2'),self.example('print(value)')],'Results')
        self.app.add_button.click();one=self.code();guide=self.app.guidance.toPlainText()
        self.app.select_example(1);self.app.add_button.click();two=self.code()
        self.assertTrue(two.startswith('value = 10'));self.assertIn('value += 2',two);self.assertIn('print(value)',two)
        result=subprocess.run([sys.executable,'-c',two],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout.strip(),'12')
        self.app.undo_button.click();self.assertEqual(self.code(),one);self.assertEqual(self.app.guidance.toPlainText(),guide)
    def test_source_explanation_has_usage_syntax_and_provenance(self):
        self.app.show_examples([self.example('def double(value):\n    return value * 2')],'Results')
        text=self.app.preview_explanation.toPlainText()
        for phrase in ('Purpose','Setup','How to use','What the code does','double(value)','Expected result','Syntax','How to extend','https://example.com/docs'):
            self.assertIn(phrase,text)
    def test_python_syntax_error_explained_at_line(self):
        self.app.set_code('if True\n    print(1)','Python','Mine');self.app.check_button.click()
        text=self.app.run_output.toPlainText();self.assertIn('line 1',text);self.assertIn('colon',text);self.assertIsNone(self.app.run_process)
    def wait_run(self):
        deadline=time.monotonic()+8
        while self.app.run_process is not None and time.monotonic()<deadline:
            self.ui.application().processEvents();time.sleep(.01)
        self.assertIsNone(self.app.run_process,'Run did not finish')
    def test_actual_python_run_and_runtime_error_explanation(self):
        self.app.set_code('print(6 * 7)','Python','Mine')
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.Yes):self.app.run_button.click()
        self.wait_run();self.assertIn('42',self.app.run_output.toPlainText());self.assertIn('exit code 0',self.app.run_output.toPlainText())
        self.app.set_code('print(unknown_name)','Python','Mine')
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.Yes):self.app.run_button.click()
        self.wait_run();self.assertIn('NameError',self.app.run_output.toPlainText());self.assertIn('definition order',self.app.run_output.toPlainText())
    def test_actual_node_syntax_error_and_python_comparison(self):
        import shutil
        if not shutil.which('node'):self.skipTest('Node.js is not installed')
        self.app.set_code('const count = ;','JavaScript','Mine');self.app.check_button.click();self.wait_run()
        text=self.app.run_output.toPlainText();self.assertIn('SyntaxError',text);self.assertIn('Compared with Python',text);self.assertIn('Unexpected token',text)
    def test_run_rejection_does_not_execute(self):
        self.app.set_code('print(1)','Python','Mine')
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.No):self.app.run_button.click()
        self.assertIsNone(self.app.run_process)
    def test_run_stop_keeps_editor(self):
        code='while True:\n    pass';self.app.set_code(code,'Python','Mine')
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.Yes):self.app.run_button.click()
        self.app.stop_button.click();self.wait_run();self.assertEqual(self.code(),code);self.assertIn('did not pass',self.app.run_output.toPlainText())
    def test_project_roundtrip_retains_explanations_and_request(self):
        self.app.set_code('print("saved")','Python','Mine');self.app.set_guidance('My explanation and source');self.describe('My request')
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'project.json')
            with patch.object(self.ui.QFileDialog,'getSaveFileName',return_value=(path,'')):self.app.save_project()
            self.app.set_code('','Python','Empty');self.app.set_guidance('')
            with patch.object(self.ui.QFileDialog,'getOpenFileName',return_value=(path,'')):self.app.open_project()
        self.assertEqual(self.code(),'print("saved")');self.assertEqual(self.app.guidance.toPlainText(),'My explanation and source');self.assertEqual(self.app.description.toPlainText(),'My request')
    def test_dom_button_preview_does_not_use_node(self):
        self.app.language_box.setCurrentText('JavaScript');self.app.connected_model=None;self.describe('age click me button')
        self.app.generate_button.click();self.assertIn('createElement',self.app.preview_code.toPlainText());self.assertEqual(self.code(),'')
        self.app.add_button.click()
        with patch.object(self.ui.QMessageBox,'question',return_value=self.ui.QMessageBox.StandardButton.Yes),patch.object(self.ui.webbrowser,'open',return_value=True) as opened:
            self.app.run_button.click()
        self.assertIsNone(self.app.run_process);self.assertTrue(opened.call_args.args[0].startswith('file:'));self.assertIn('Browser preview',self.app.run_output.toPlainText())


class LanguageAndExplanationTests(unittest.TestCase):
    def test_click_cannot_match_javascript_task(self):
        docs=sources.documentation_catalogue(online=False)
        matches=sources.task_docsets('age click me button','JavaScript',docs)
        self.assertTrue(matches);self.assertEqual(matches[0]['slug'],'dom');self.assertNotIn('click',[d['slug'] for d in matches])
    def test_every_language_has_teaching_and_python_comparison(self):
        import og_companion_workbench as workbench
        for language in search.LANGUAGES:
            self.assertIn(language,workbench.LANGUAGE_GUIDES)
            self.assertTrue(workbench.syntax_comparison(language))
            if language!='Python':self.assertIn('Python',workbench.syntax_comparison(language))
    def test_html_and_markdown_keep_publisher_context(self):
        for text in ('<h2>Double values</h2><p>Call double with an integer.</p><pre data-language="python">def double(x):\n    return x * 2</pre>',
                     '# Double values\nCall double with an integer.\n```python\ndef double(x):\n    return x * 2\n```'):
            rows=sources.extract_examples(text,'https://example.com','Python');self.assertIn('Call double with an integer',rows[0]['source_context'])
    def test_missing_runtime_and_shell_metacharacters_are_not_executed(self):
        import og_companion_workbench as workbench
        exe,args,error=workbench.runtime_plan('JavaScript','console.log(1)','x & y',find=lambda name:None)
        self.assertIsNone(exe);self.assertIn('not available',error)
        exe,args,error=workbench.runtime_plan('JavaScript','console.log(1)','x & y',find=lambda name:'node')
        self.assertEqual(exe,'node');self.assertEqual(len(args),1);self.assertIn('x & y',args[0])
    def test_arbitrary_package_examples_reachable_without_ai(self):
        package=search.package_result('external-tool','JavaScript','npm','A package outside the teaching catalogue','1','https://example.com','npm install external-tool')
        block={'code':'console.log("external")','language':'JavaScript','title':'Usage','url':'https://example.com'}
        with patch.object(search,'search_libraries',return_value=([package],'Live registry')),patch.object(sources,'library_examples',return_value=([block],'Live source')):
            entries,blocks,status=sources.discover_task_examples('external-tool','JavaScript',catalogue=[])
        self.assertEqual([b['code'] for b in blocks],[block['code']]);self.assertEqual(blocks[0]['library']['name'],'external-tool');self.assertEqual(entries,[package]);self.assertIn('1 matching JavaScript',status)


class BasicLanguageTests(unittest.TestCase):
    def test_all_selector_languages_have_a_complete_basic_example(self):
        for language in search.LANGUAGES:
            rows=search.basic_libraries(language)
            self.assertTrue(rows,language)
            baseline=next(e for e in rows if e.get('baseline_for')==language)
            for field in ('snippet','description','install','expected_output','usage'):
                self.assertTrue(baseline[field],(language,field))
    def test_python_javascript_sql_and_powershell_basics_execute(self):
        import shutil,sqlite3
        rows=search.load_catalogue()
        baseline=lambda lang:next(e for e in rows if e.get('baseline_for')==lang)
        python=subprocess.run([sys.executable,'-c',baseline('Python')['snippet']],capture_output=True,text=True,timeout=5)
        self.assertEqual(python.returncode,0);self.assertEqual(python.stdout.strip(),'Total: 12')
        from contextlib import closing
        with closing(sqlite3.connect(':memory:')) as db:self.assertEqual(db.execute(baseline('SQL')['snippet']).fetchone(),(12,))
        for language,command in [('JavaScript','node'),('PowerShell','pwsh')]:
            exe=shutil.which(command)
            if exe:
                args=[exe,'-e',baseline(language)['snippet']] if language=='JavaScript' else [exe,'-NoProfile','-Command',baseline(language)['snippet']]
                result=subprocess.run(args,capture_output=True,text=True,timeout=8)
                self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'Total: 12')
    def test_switching_language_refreshes_basics_without_replacing_code(self):
        import og_companion as ui
        app=ui.OGCompanion(discover_models=False)
        try:
            app.set_code('print("keep")','Python','Mine');app.language_box.setCurrentText('C')
            self.assertTrue(app.entries);self.assertTrue(all(e['language']=='C' for e in app.entries));self.assertIn('C stdio.h',[e['name'] for e in app.entries])
            self.assertEqual(app.output.toPlainText(),'print("keep")')
            app.keywords.clear();app.description.clear();app.search_button.click();self.assertTrue(app.entries)
        finally:app.dispose()


class HostedProviderTests(unittest.TestCase):
    def setUp(self):
        import og_companion_providers as api
        self.api=api;self.records=[];self.key='fixture-secret-never-real'
    def tearDown(self):
        for record in self.records:self.api.forget_hosted(record)
    def record(self,provider='Custom (OpenAI-compatible)',auth='Bearer'):
        row=self.api.configure_hosted(provider,self.api.PRESETS[provider][0] or 'https://example.com/v1','test-model',self.key,auth);self.records.append(row);return row
    def request(self,record,response):
        from unittest.mock import MagicMock
        opened=MagicMock();opened.__enter__.return_value.read.return_value=json.dumps(response).encode()
        with patch.object(self.api,'build_opener') as factory:
            factory.return_value.open.return_value=opened
            result=self.api.hosted_generate(record,'System instructions','User source and task',1800)
            request=factory.return_value.open.call_args.args[0]
        return result,request
    def test_openai_responses_request_and_text_extraction(self):
        result,request=self.request(self.record('OpenAI (Responses)'),{'status':'completed','output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':'print(42)'}]}]})
        payload=json.loads(request.data);self.assertEqual(request.full_url,'https://api.openai.com/v1/responses');self.assertFalse(payload['store']);self.assertEqual(payload['max_output_tokens'],1800)
        self.assertEqual(result['response'],'print(42)');self.assertEqual(request.get_header('Authorization'),'Bearer '+self.key)
    def test_anthropic_uses_native_messages_and_version_header(self):
        result,request=self.request(self.record('Anthropic (Messages)'),{'content':[{'type':'text','text':'print(42)'}],'stop_reason':'end_turn'})
        payload=json.loads(request.data);self.assertTrue(request.full_url.endswith('/v1/messages'));self.assertEqual(payload['system'],'System instructions');self.assertEqual(request.get_header('X-api-key'),self.key);self.assertTrue(request.get_header('Anthropic-version'))
    def test_gemini_and_custom_chat_compatible_endpoints(self):
        for name in ('Gemini (OpenAI-compatible)','Custom (OpenAI-compatible)'):
            result,request=self.request(self.record(name),{'choices':[{'message':{'content':'print(42)'},'finish_reason':'stop'}]})
            self.assertTrue(request.full_url.endswith('/chat/completions'));self.assertIn('messages',json.loads(request.data));self.assertEqual(result['response'],'print(42)')
    def test_custom_api_key_header(self):
        _,request=self.request(self.record(auth='api-key'),{'choices':[{'message':{'content':'print(42)'}}]})
        self.assertEqual(request.get_header('Api-key'),self.key);self.assertIsNone(request.get_header('Authorization'))
    def test_credentials_are_absent_from_records_and_removed_on_forget(self):
        row=self.record();self.assertNotIn(self.key,json.dumps(row));self.api.forget_hosted(row)
        with self.assertRaisesRegex(RuntimeError,'no longer available'):self.api.hosted_generate(row,'system','prompt',1)
    def test_invalid_urls_and_header_injection_rejected(self):
        for endpoint in ('http://example.com/v1','https://user:password@example.com','https://example.com/?key=secret','https://127.0.0.1/v1'):
            with self.assertRaises(ValueError):self.api.configure_hosted('Custom (OpenAI-compatible)',endpoint,'model',self.key)
        with self.assertRaises(ValueError):self.api.configure_hosted('Custom (OpenAI-compatible)','https://example.com','model','secret\nInjected: header')
    def test_redirects_never_forward_credentials(self):
        with self.assertRaisesRegex(RuntimeError,'not forwarded'):
            self.api.NoRedirects().redirect_request(None,None,302,'Found',{},'https://other.example')
    def test_http_error_does_not_echo_server_body_or_key(self):
        from io import BytesIO
        from urllib.error import HTTPError
        row=self.record()
        with patch.object(self.api,'build_opener') as factory:
            factory.return_value.open.side_effect=HTTPError(row['endpoint'],401,'Unauthorised',{},BytesIO(self.key.encode()))
            with self.assertRaises(RuntimeError) as caught:self.api.hosted_generate(row,'system','prompt',1)
        self.assertIn('401',str(caught.exception));self.assertNotIn(self.key,str(caught.exception));self.assertEqual(factory.return_value.open.call_count,1)
    def test_truncated_response_is_rejected_by_generation_gate(self):
        row=self.record('OpenAI (Responses)')
        with patch.object(self.api,'hosted_generate',return_value={'response':'print(42)','done_reason':'length'}):
            with self.assertRaisesRegex(RuntimeError,'output limit'):search.generate_snippet('Print 42','Python','test-model',hosted_connection=row)
    def test_cloud_expansion_keeps_existing_code_context(self):
        row=self.record()
        with patch.object(self.api,'hosted_generate',return_value={'response':'print(1)\nprint(2)','done_reason':'stop'}) as generate:
            code=search.generate_snippet('Also print two','Python','test-model',existing_code='print(1)',hosted_connection=row)
        self.assertIn('print(1)',generate.call_args.args[2]);self.assertIn('print(2)',code)
    def test_api_configuration_does_not_contact_provider_and_refresh_keeps_it(self):
        import og_companion as ui
        app=ui.OGCompanion(discover_models=False)
        try:
            row=self.record()
            with patch.object(self.api,'build_opener') as network:app.add_api_record(row)
            network.assert_not_called();self.assertTrue(app.connected_model['hosted']);self.assertIn('Not contacted yet',app.model_note.text())
            app.results.put(('models',True,[]));app.poll();self.assertEqual(app.model_records,[row])
            app.forget_api_models();self.assertFalse(app.api_models);self.assertIsNone(app.connected_model)
        finally:app.dispose()


if __name__=='__main__':unittest.main()
