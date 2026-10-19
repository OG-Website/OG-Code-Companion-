"""Public documentation, repository examples and on-demand documentation indexes.

Content is reference data: nothing downloaded here is installed or executed.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import ipaddress
import gzip
import json
from pathlib import Path
import re
import socket
import tempfile
import time
from urllib.parse import quote, urlencode, urlparse, urljoin
from urllib.request import Request, HTTPRedirectHandler, build_opener

from og_companion_search import BASE, fetch_json, package_result, tokens

ALIASES = {'py': 'Python', 'python': 'Python', 'python3': 'Python', 'pycon': 'Python',
           'js': 'JavaScript', 'javascript': 'JavaScript', 'jsx': 'JavaScript',
           'ts': 'TypeScript', 'typescript': 'TypeScript', 'tsx': 'TypeScript',
           'cs': 'C#', 'csharp': 'C#', 'c#': 'C#', 'fsharp': 'F#',
           'java': 'Java', 'kotlin': 'Kotlin', 'scala': 'Scala', 'rs': 'Rust', 'rust': 'Rust',
           'php': 'PHP', 'rb': 'Ruby', 'ruby': 'Ruby', 'go': 'Go', 'golang': 'Go',
           'cpp': 'C++', 'c++': 'C++', 'c': 'C', 'sql': 'SQL', 'sh': 'Bash',
           'bash': 'Bash', 'shell': 'Bash', 'powershell': 'PowerShell', 'ps1': 'PowerShell',
           'r': 'R', 'swift': 'Swift', 'dart': 'Dart', 'html': 'HTML / CSS', 'css': 'HTML / CSS',
           'json': 'JSON', 'yaml': 'YAML', 'yml': 'YAML', 'console': 'Console', 'text': 'Text',
           'toml': 'TOML', 'xml': 'XML', 'ini': 'INI', 'http': 'HTTP'}
DOC_DEFAULTS = {'Python': 'python~3.14', 'JavaScript': 'javascript', 'TypeScript': 'typescript',
                'C#': 'dotnet', 'F#': 'dotnet', 'Java': 'openjdk~21', 'Kotlin': 'kotlin~2.2',
                'Scala': 'scala~2.13', 'Rust': 'rust', 'PHP': 'php', 'Ruby': 'ruby~3.4',
                'Go': 'go', 'C++': 'cpp', 'C': 'c', 'SQL': 'sqlite', 'Bash': 'bash',
                'PowerShell': 'powershell', 'R': 'r', 'Swift': 'swift', 'Dart': 'dart',
                'HTML / CSS': 'html','CMake':'cmake'}


def public_url(url, *, resolve=True):
    """Only public HTTPS pages, including every redirect, can be retrieved."""
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Use a public HTTPS documentation or repository URL.')
    host = parsed.hostname.casefold()
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Local and private addresses cannot be used as documentation sources.')
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = [ipaddress.ip_address(row[4][0]) for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)] if resolve else []
    if any(not address.is_global for address in addresses):
        raise ValueError('Local and private addresses cannot be used as documentation sources.')
    return url


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_text(url, *, limit=8_000_000):
    public_url(url)
    request = Request(url, headers={'User-Agent': 'OG-Companion/2.0 (documentation browser)',
                                   'Accept': 'text/html,text/plain,application/json'})
    with build_opener(PublicRedirects()).open(request, timeout=25) as response:
        content_type = response.headers.get_content_type()
        if content_type not in ('text/html', 'text/plain', 'application/json', 'application/octet-stream', 'text/markdown'):
            raise ValueError('This address does not supply text documentation.')
        raw = response.read(limit + 1)
        encoding = response.headers.get_content_charset() or 'utf-8'
        final_url = response.url
    if len(raw) > limit:
        raise ValueError('The document is too large. Open a specific documentation page instead.')
    return raw.decode(encoding, errors='replace'), final_url, content_type


def cached_document(url, *, online=True, cache_dir=None):
    folder = Path(cache_dir) if cache_dir else Path.home() / '.og-companion' / 'documents'
    file = folder / (sha256(url.encode()).hexdigest() + '.json')
    cached = None
    if file.exists():
        try:
            cached = json.loads(file.read_text(encoding='utf-8'))
            if not isinstance(cached.get('text'), str): cached = None
        except (OSError, ValueError): pass
    if cached and (not online or time.time() - cached['fetched_at'] < 86400):
        return cached['text'], cached['url'], cached['type'], 'Cached document'
    if not online:
        raise RuntimeError('This document is not cached yet. Enable online access to load it once.')
    try:
        text, final_url, content_type = fetch_text(url)
    except (OSError, ValueError):
        if cached: return cached['text'], cached['url'], cached['type'], 'Offline cached document'
        raise
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder, delete=False, suffix='.tmp') as stream:
        json.dump({'text': text, 'url': final_url, 'type': content_type, 'fetched_at': time.time()}, stream)
        temporary=Path(stream.name)
    try: temporary.replace(file)
    finally: temporary.unlink(missing_ok=True)
    return text, final_url, content_type, 'Live document'


class CodeHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []; self.parts = []; self.depth = 0
        self.language = ''; self.heading = ''; self.heading_parts = None
        self.prose=[];self.contexts=[];self.hidden=0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script','style'):self.hidden+=1
        if tag in ('p','li','h1','h2','h3','h4','h5','h6') and not self.depth:self.prose.append('\n')
        if re.fullmatch('h[1-6]', tag) and not self.depth: self.heading_parts = []
        if tag == 'pre':
            if not self.depth:
                self.parts = []; self.language = attrs.get('data-language', '')
                self.contexts.append(''.join(self.prose).strip()[-1800:]);self.prose=[]
            self.depth += 1
        if self.depth:
            classes = attrs.get('class', '')
            match = re.search(r'(?:language-|lang-|highlight\s+)([\w+#-]+)', classes)
            if match: self.language = match[1]
            self.language = attrs.get('data-language', self.language)
            if tag == 'br': self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if re.fullmatch('h[1-6]', tag) and self.heading_parts is not None:
            self.heading = ''.join(self.heading_parts).strip(); self.heading_parts = None
        if tag == 'pre' and self.depth:
            self.depth -= 1
            if not self.depth:
                self.blocks.append((self.heading, self.language, ''.join(self.parts).strip()))
    def handle_data(self, data):
        if self.depth: self.parts.append(data)
        elif not self.hidden:self.prose.append(data)
        if self.heading_parts is not None: self.heading_parts.append(data)


def infer_language(code, default):
    if re.search(r'^\s*(?:>>> |from \w+ import |def \w+\(|import (?:os|sys|re|json|numpy|pandas))', code, re.M): return 'Python'
    if re.search(r'^\s*(?:npm |pip |python -m pip|cargo |gem |composer |\$ )', code, re.M): return 'Bash'
    if re.search(r'\b(?:require\(|console\.log\()', code): return 'JavaScript'
    return default


def extract_examples(text, url, language, *, attribution='', licence='See source terms'):
    """Return every code block in the loaded page, retaining its provenance."""
    raw = [];contexts=[]
    if '<pre' in text.casefold():
        parser = CodeHTML(); parser.feed(text); raw.extend(parser.blocks);contexts=parser.contexts
    else:
        fence = re.compile(r'^\s*(`{3,}|~{3,})([^\n]*)\n(.*?)^\s*\1\s*$', re.M | re.S)
        for match in fence.finditer(text):
            headings = re.findall(r'^#{1,6}\s+(.+)$', text[:match.start()], re.M)
            raw.append((headings[-1] if headings else 'Example', match[2].strip().split(' ')[0], match[3].strip()))
            prefix=text[:match.start()];previous=list(fence.finditer(prefix));start=previous[-1].end() if previous else 0
            contexts.append(prefix[start:].strip()[-1800:])
        if not raw:
            # reStructuredText is used in many PyPI descriptions.
            for match in re.finditer(r'^\.\. code(?:-block)?::\s*(\w*)\s*\n((?:[ \t]+[^\n]*\n|\n)+)', text, re.M):
                import textwrap
                raw.append(('Example', match[1], textwrap.dedent(match[2]).strip()))
    rows = []; seen = set()
    for raw_index,(title, hint, code) in enumerate(raw):
        if not code or code in seen: continue
        seen.add(code)
        hint=hint.split(',')[0].strip('{}.')
        actual_language = ALIASES.get(hint.casefold(), hint or infer_language(code, language))
        # Interactive prompts and printed results stay visible as transcript examples.
        if re.search(r'^>>> ', code, re.M): actual_language = 'Python transcript'
        rows.append({'title': f'{len(rows)+1}. {title[:95] or "Example"}', 'code': code,
                     'language': actual_language, 'url': url, 'attribution': attribution,
                     'licence': licence, 'source_context':contexts[raw_index] if raw_index<len(contexts) else '',
                     'retrieved_at': datetime.now(timezone.utc).isoformat()})
    return rows


def documentation_catalogue(online=True):
    try:
        text, _, _, _ = cached_document('https://devdocs.io/docs.json', online=online)
        data = json.loads(text)
        if not isinstance(data,list) or not all(isinstance(row,dict) and isinstance(row.get('slug'),str) for row in data):
            raise ValueError('Unexpected documentation catalogue format.')
    except (OSError, ValueError, RuntimeError):
        data = json.loads((BASE / 'og_companion_assets' / 'documentation-index.json').read_text(encoding='utf-8'))
    return [row for row in data if re.fullmatch(r'[a-zA-Z0-9_.~+-]+', row['slug'])]


def documentation_language(docset, fallback='Text'):
    family=docset['slug'].split('~')[0]
    if family in ('python','numpy','pandas','scipy','scikit-learn','scikit_learn','django','django_rest_framework','flask','fastapi','requests','pytest','tensorflow','pytorch','sphinx','matplotlib','seaborn','statsmodels','click','bottle','celery','falcon','polars','pygame','scikit_image','trio','wagtail','werkzeug','saltstack'):return 'Python'
    if family in ('javascript','node','express','react','react_native','vue','vueuse','angular','jquery','lodash','underscore','nextjs','svelte','d3','moment','rxjs','backbone','dom','web_extensions','angularjs','astro','async','axios','babel','bluebird','bun','chai','codeceptjs','cordova','cypress','date_fns','deno','dojo','electron','ember','enzyme','es_toolkit','esbuild','eslint','flow','fluture','grunt','hapi','htmx','immutable','jasmine','jest','joi','jquerymobile','jqueryui','jsdoc','knockout','koa','leaflet','lit','maplibre_gl','marionette','meteor','mocha','modernizr','moment_timezone','mongoose','npm','openlayers','phaser','playwright','prettier','puppeteer','qunit','ramda','react_bootstrap','react_router','redux','relay','requirejs','sanctuary','sanctuary_def','sanctuary_type_classes','sequelize','sinon','socketio','threejs','valibot','vite','vitest','vue_router','vuex','webpack','yarn'):return 'JavaScript'
    if family in ('sqlite','mysql','mariadb','postgresql'):return 'SQL'
    if family=='cpp':return 'C++'
    if family.startswith('openjdk'):return 'Java'
    if family=='dotnet':return 'C#'
    if family in ('cakephp','codeception','codeigniter','composer','drupal','laravel','phalcon','phpunit','symfony','twig','wordpress','yii'):return 'PHP'
    if family in ('jekyll','nokogiri','padrino','minitest','rack','rails','vagrant'):return 'Ruby'
    if family in ('eigen3','point_cloud_library','qt','tensorflow_cpp'):return 'C++'
    if family in ('spring_boot','vertx'):return 'Java'
    if family=='tokio':return 'Rust'
    if family=='cmake':return 'CMake'
    return ALIASES.get(family,fallback)


def compatible_examples(examples, language):
    """Never silently substitute another language, commands or transcripts."""
    return [e for e in examples if e.get('language') == language]


def task_docsets(description, language, catalogue):
    """Rank library names only within a known language family."""
    words=tokens(description);ranked=[];seen=set()
    browser=language=='JavaScript' and bool(words & {'button','click','dom','element','page','browser','html','event'})
    for doc in catalogue:
        family=doc['slug'].split('~')[0]
        if family in seen or documentation_language(doc)!=language:continue
        name=doc['name'].casefold();names=tokens(name+' '+family)
        score=20*len(words & names)+(100 if name==description.strip().casefold() else 0)
        if browser and family=='dom':score+=80
        if family==DOC_DEFAULTS.get(language,'').split('~')[0]:score+=1
        if score:ranked.append((score,doc));seen.add(family)
    return [doc for _,doc in sorted(ranked,key=lambda pair:-pair[0])]


def discover_task_examples(description, language, *, online=True, catalogue=None, page=1):
    """Search matching documentation and real package sources without a model."""
    from og_companion_search import search_libraries, task_libraries, task_terms
    catalogue=documentation_catalogue(online=False) if catalogue is None else catalogue
    entries=[];examples=[];issues=[];seen=set()
    def keep(blocks,entry=None):
        for block in compatible_examples(blocks,language):
            key=(block['code'],block['language'])
            if key not in seen:
                seen.add(key);block=dict(block)
                if entry:block['library']={k:entry[k] for k in ('name','description','install','docs') if k in entry}
                examples.append(block)
    query=' '.join(sorted(task_terms(description)))
    for doc in task_docsets(description,language,catalogue)[:3]:
        try:
            rows,_=documentation_search(doc,query,page=page,online=online,language=language,page_size=30)
            entries.extend(rows)
            for entry in rows[:3]:
                blocks,_=library_examples(entry,online=online,complete=False);keep(blocks,entry)
            if not rows or not examples:
                blocks,_=collection_examples(doc,online=online)
                ranked=sorted(blocks,key=lambda e:-len(tokens(e.get('title','')+' '+e.get('topic','')+' '+e['code']) & tokens(query)))
                keep([e for e in ranked if tokens(e.get('title','')+' '+e.get('topic','')+' '+e['code']) & tokens(query)])
                if not rows:
                    entries.append(package_result(doc['name'],language,'Documentation collection','Published reference examples; inspect their source context.',doc.get('version') or 'Current','https://devdocs.io/'+doc['slug'],'See source documentation'))
        except (OSError,ValueError,KeyError,RuntimeError) as error:issues.append(str(error))
    # Package discovery is not limited to the supplied teaching catalogue.
    try:
        packages,status=search_libraries(description,language,online,page=page) if online else (task_libraries(description,language),'Supplied/offline packages')
        entries.extend(packages)
        for entry in packages[:3]:
            try:
                blocks,_=library_examples(entry,online=online,complete=False);keep(blocks,entry)
            except (OSError,ValueError,KeyError,RuntimeError) as error:issues.append(str(error))
    except (OSError,ValueError,KeyError,RuntimeError) as error:issues.append(str(error))
    unique_entries=[];keys=set()
    for entry in entries:
        key=(entry['name'],entry['docs'])
        if key not in keys:keys.add(key);unique_entries.append(entry)
    status=f'{len(examples)} matching {language} examples · {len(unique_entries)} library/API results · '+('online/cached sources' if online else 'offline sources')
    if issues:status+=' · '+str(len(issues))+' source checks unavailable'
    if not examples:status+='. No suitable source block found; try an exact library/API name or another result page. Your code is retained.'
    return unique_entries,examples,status


def documentation_search(docset, query='', *, page=1, online=True, page_size=100, language=None):
    slug = docset['slug']
    if not re.fullmatch(r'[a-zA-Z0-9_.~+-]+', slug): raise ValueError('Invalid documentation edition.')
    url = 'https://documents.devdocs.io/' + quote(slug) + '/index.json?' + str(docset.get('mtime', ''))
    text, _, _, cache_status = cached_document(url, online=online)
    entries = json.loads(text)['entries']; words = tokens(query)
    ranked = []
    for item in entries:
        name = item['name'].casefold(); hay = name + ' ' + item.get('type', '').casefold()
        score = sum(5 if word in name else 1 for word in words if word in hay)
        if not words or score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['name'].casefold()))
    rows = []
    for _, item in ranked[(page-1)*page_size:page*page_size]:
        row = package_result(item['name'], documentation_language(docset),
                             'DevDocs', item.get('type','')+' · '+docset['name'], docset.get('version') or 'Current edition',
                             'https://devdocs.io/'+quote(slug)+'/'+item['path'], 'See library documentation')
        row.update(docset=docset, path=item['path'], attribution=unescape(re.sub('<[^>]+>', ' ', docset.get('attribution',''))).strip())
        rows.append(row)
    return rows, f'DevDocs · {docset["name"]} {docset.get("version", "")} · {len(ranked):,} matching API topics · page {page} · {cache_status}'


def github_search(query, language, *, page=1):
    lang = {'HTML / CSS':'HTML', 'Bash':'Shell'}.get(language, language)
    meaningful = query.strip()
    data = fetch_json('https://api.github.com/search/repositories?' + urlencode(
        {'q': meaningful+' language:"'+lang+'" archived:false', 'per_page':50, 'page':page}))
    rows = []
    for repo in data['items']:
        row = package_result(repo['full_name'], language, 'GitHub', repo.get('description'),
                             repo.get('updated_at','')[:10], repo['html_url'], 'See repository documentation')
        row.update(repository=repo['html_url'], licence=(repo.get('license') or {}).get('spdx_id') or 'See repository licence')
        rows.append(row)
    return rows, f'GitHub · {data["total_count"]:,} matching public repositories · page {page} (provider search limits apply)'


def github_repo(url):
    parsed = urlparse(url.replace('git+https://','https://').removesuffix('.git'))
    if parsed.hostname not in ('github.com','www.github.com'): return None
    parts = parsed.path.strip('/').split('/')
    if len(parts)>=2 and all(re.fullmatch(r'[\w.-]+', part) for part in parts[:2]): return '/'.join(parts[:2])
    return None


def repository_readme(url, online=True):
    repo = github_repo(url)
    if not repo: return None
    api = 'https://api.github.com/repos/'+repo+'/readme'
    text, _, _, _ = cached_document(api, online=online)
    data = json.loads(text)
    if not data.get('download_url'): return None
    # The raw file avoids executable scripts and navigation noise in GitHub HTML.
    text, _, _, _ = cached_document(data['download_url'], online=online)
    return text, data['html_url']


def matching_documentation(entry):
    """Resolve a library against the entire edition manifest, not a snippet list."""
    normal=lambda value:re.sub(r'[^a-z0-9]','',str(value).casefold())
    wanted={normal(entry['name']),normal(entry['name'].split('/')[-1].split(':')[-1])}
    wanted.discard('')
    for doc in documentation_catalogue(online=False):
        names={normal(doc['name']),normal(doc['slug'].split('~')[0]),normal(doc.get('alias') or '')}
        if wanted & names and documentation_language(doc)==entry['language']:
            return doc
    return None


def collection_examples(docset, *, online=True, cache_dir=None, progress=lambda message:None):
    """Extract every distinct block in a published documentation database."""
    slug=docset['slug']
    if not re.fullmatch(r'[a-zA-Z0-9_.~+-]+',slug):raise ValueError('Invalid documentation edition.')
    folder=Path(cache_dir) if cache_dir else Path.home()/'.og-companion'/'collections'
    file=folder/(slug+'.json.gz');cached=None
    supplied=BASE/'og_companion_assets'/'example-collections'/(slug+'.json.gz')
    if supplied.exists() and not file.exists():file=supplied
    if file.exists():
        try:
            with gzip.open(file,'rt',encoding='utf-8') as stream:cached=json.load(stream)
            if cached.get('slug')!=slug or not isinstance(cached.get('examples'),list):cached=None
        except (OSError,ValueError,EOFError):cached=None
    if cached and (not online or cached.get('mtime')==docset.get('mtime')):
        return cached['examples'],f"{len(cached['examples']):,} distinct source blocks · {docset['name']} complete collection · cached"
    if not online:raise RuntimeError('This complete collection is not downloaded yet. Enable online access to load it once.')
    url='https://documents.devdocs.io/'+quote(slug)+'/db.json'
    progress('Downloading the complete '+docset['name']+' documentation collection…')
    try:
        text,_,_=fetch_text(url,limit=160_000_000)
        database=json.loads(text)
        if not isinstance(database,dict) or not all(isinstance(value,str) for value in database.values()):
            raise ValueError('The documentation database has an unexpected format.')
    except (OSError,ValueError):
        if cached:return cached['examples'],f"{len(cached['examples']):,} distinct source blocks · retained collection after refresh failure"
        raise
    examples=[];seen=set();attribution=unescape(re.sub('<[^>]+>',' ',docset.get('attribution',''))).strip()
    language=documentation_language(docset,docset['name'])
    for path,html in database.items():
        source='https://devdocs.io/'+quote(slug)+'/'+quote(path,safe='/')
        for row in extract_examples(html,source,language,attribution='DevDocs · '+attribution,licence=attribution or 'See original documentation terms'):
            key=(row['code'],row['language'])
            if key not in seen:
                seen.add(key);row.update(collection=docset['name'],edition=slug,topic=path)
                examples.append(row)
    folder.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder,delete=False,suffix='.tmp') as stream:temporary=Path(stream.name)
    try:
        with gzip.open(temporary,'wt',encoding='utf-8') as stream:
            json.dump({'slug':slug,'mtime':docset.get('mtime'),'pages':len(database),'fetched_at':time.time(),'examples':examples},stream,ensure_ascii=False)
        temporary.replace(folder/(slug+'.json.gz'))
    finally:temporary.unlink(missing_ok=True)
    return examples,f'{len(examples):,} distinct source blocks · {len(database):,} pages · {docset["name"]} complete collection'


def library_examples(entry, *, online=True, complete=True):
    """Read source examples from arbitrary selected packages, not just supplied entries."""
    language = entry['language']; blocks = []; issues = []; documents = []; licence = entry.get('licence','See source terms')
    if entry['source']=='DevDocs':
        slug = entry['docset']['slug']; path = entry['path'].split('#')[0]
        if '..' in path.split('/') or urlparse(path).scheme: raise ValueError('Invalid documentation path.')
        url = 'https://documents.devdocs.io/'+quote(slug)+'/'+quote(path,safe='/')+'.html'
        text, _, _, status = cached_document(url, online=online)
        rows = extract_examples(text, entry['docs'], language, attribution=entry.get('attribution','DevDocs'), licence=entry.get('attribution','See documentation terms'))
        return rows, status+' · DevDocs · '+str(len(rows))+' code examples from this topic'
    docset=matching_documentation(entry) if complete else None
    if docset:
        try:return collection_examples(docset,online=online)
        except (OSError,ValueError,RuntimeError) as error:issues.append('Complete collection unavailable: '+str(error))
    if entry.get('snippet'):
        blocks.append({'title':'Supplied offline example', 'code':entry['snippet'], 'language':language,
                       'url':entry['docs'], 'attribution':'OG Code Companion teaching example', 'licence':'OG Web.site teaching example'})
    if entry['source']=='PyPI':
        api = 'https://pypi.org/pypi/'+quote(entry['name'],safe='')+'/json'
        try:
            text, _, _, _ = cached_document(api, online=online); info=json.loads(text)['info']
            licence = info.get('license_expression') or info.get('license') or licence
            licence = licence[:200]
            blocks.extend(extract_examples(info.get('description',''), entry['registry_url'], language, licence=licence))
            urls = info.get('project_urls') or {}
            documents += [v for k,v in urls.items() if any(word in k.casefold() for word in ('source','repo','doc','homepage'))]
        except (OSError,ValueError,RuntimeError,KeyError) as error: issues.append(str(error))
    elif entry['source']=='npm':
        try:
            text, _, _, _ = cached_document('https://registry.npmjs.org/'+quote(entry['name'],safe='@'), online=online)
            info=json.loads(text); licence=info.get('license') or licence
            if not isinstance(licence,str): licence=str(licence)
            blocks.extend(extract_examples(info.get('readme',''), entry['registry_url'], language, licence=licence))
            repo=info.get('repository') or {}; repo=repo.get('url') if isinstance(repo,dict) else repo
            if repo: documents.append(repo)
        except (OSError,ValueError,RuntimeError,KeyError) as error: issues.append(str(error))
    elif entry['source']=='crates.io':
        try:
            text, _, _, _ = cached_document('https://crates.io/api/v1/crates/'+quote(entry['name']),online=online)
            info=json.loads(text)['crate']
            if info.get('repository'): documents.append(info['repository'])
        except (OSError,ValueError,RuntimeError,KeyError) as error: issues.append(str(error))
    elif entry['source']=='RubyGems':
        try:
            text, _, _, _ = cached_document('https://rubygems.org/api/v1/gems/'+quote(entry['name'])+'.json',online=online)
            info=json.loads(text)
            documents += [info[key] for key in ('source_code_uri','documentation_uri','homepage_uri') if info.get(key)]
            licence=', '.join(info.get('licenses') or []) or licence
        except (OSError,ValueError,RuntimeError,KeyError) as error: issues.append(str(error))
    documents += [entry.get('repository'),entry.get('docs')]
    documents = list(dict.fromkeys(str(url) for url in documents if url))[:4]
    def read(url):
        try:
            readme = repository_readme(url,online)
            if readme: text,source = readme
            else: text,source,_,_ = cached_document(url,online=online)
            return extract_examples(text,source,language,licence=licence),''
        except (OSError,ValueError,RuntimeError,KeyError) as error: return [],str(error)
    with ThreadPoolExecutor(max_workers=3) as workers:
        for rows,error in workers.map(read,documents):
            blocks.extend(rows)
            if error: issues.append(error)
    if not blocks and online and entry['source']!='GitHub':
        try:
            repositories,_=github_search(entry['name'],language)
            if repositories:
                readme=repository_readme(repositories[0]['docs'],online=True)
                if readme:
                    text,source=readme
                    blocks.extend(extract_examples(text,source,language,licence=repositories[0].get('licence','See repository terms')))
        except (OSError,ValueError,RuntimeError,KeyError) as error:issues.append('Repository discovery unavailable: '+str(error))
    seen=set();unique=[]
    for block in blocks:
        if block['code'] not in seen: seen.add(block['code']);unique.append(block)
    status=f'{len(unique)} source examples · '+('online or cached documentation' if online else 'cached/offline documentation')
    if issues: status += ' · '+str(len(issues))+' source(s) unavailable'
    return unique,status


def url_examples(url, language, *, online=True):
    public_url(url,resolve=online)
    parsed=urlparse(url)
    if parsed.hostname in ('github.com','www.github.com') and '/blob/' in parsed.path:
        owner,repo,_,rest=parsed.path.strip('/').split('/',3)
        url='https://raw.githubusercontent.com/'+owner+'/'+repo+'/'+rest
    suffix=Path(urlparse(url).path).suffix
    raw_languages={'.py':'Python','.js':'JavaScript','.ts':'TypeScript','.cs':'C#','.cpp':'C++','.c':'C',
                   '.java':'Java','.rs':'Rust','.go':'Go','.php':'PHP','.rb':'Ruby','.cmake':'CMake',
                   '.swift':'Swift','.dart':'Dart','.sh':'Bash','.ps1':'PowerShell','.r':'R','.sql':'SQL'}
    extra_sources={'.zig','.ex','.exs','.erl','.hs','.scala','.kt','.fs','.lua','.jl','.f90','.m','.pl','.clj','.rkt','.groovy','.v','.sv','.vb'}
    if suffix.casefold() in raw_languages or suffix.casefold() in extra_sources or urlparse(url).path.endswith('/CMakeLists.txt'):
        text,source,_,_=cached_document(url,online=online)
        if text.lstrip().casefold().startswith(('<!doctype html','<html')):raise ValueError('This source address returned a webpage rather than source code.')
        return [{'title':Path(urlparse(source).path).name,'code':text,'language':raw_languages.get(suffix.casefold(),'CMake' if urlparse(source).path.endswith('/CMakeLists.txt') else language),
                 'url':source,'attribution':'Original source file','licence':'See the original repository licence'}],'1 complete source file · source retained verbatim'
    readme = repository_readme(url,online)
    if readme: text,source=readme
    else: text,source,_,_=cached_document(url,online=online)
    examples=extract_examples(text,source,language)
    return examples, f'{len(examples)} code examples from the supplied source'
