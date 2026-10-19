"""Source-grounded teaching, incremental assembly and explicit local test plans."""
import ast
import re
import shutil
from pathlib import Path

from og_companion_search import EXTENSIONS

LANGUAGE_GUIDES = {
    'Python': ('Indentation defines blocks; a colon starts a block. Names are case sensitive. Imports make modules available.', 'python', 'python og-starter.py'),
    'JavaScript': ('Braces delimit blocks. const and let declare variables; === compares without type coercion. Functions can be event handlers.', 'node', 'node og-starter.js; DOM code needs an HTML page in a browser'),
    'TypeScript': ('JavaScript syntax with type annotations and interfaces. Types are checked before execution and are removed when compiled.', 'tsc', 'tsc og-starter.ts, then node og-starter.js; browser APIs need a browser'),
    'C#': ('Braces delimit blocks; declarations specify types. Most statements end with a semicolon. Code normally belongs in a .NET project.', 'dotnet', 'dotnet run from the project directory'),
    'F#': ('Indentation groups expressions; let binds values. Types are often inferred. Immutable values are the default.', 'dotnet', 'dotnet fsi og-starter.fsx'),
    'Java': ('Braces delimit blocks; variables have declared types. A public class must match its filename; statements usually end with a semicolon.', 'java', 'java ClassName.java with a JDK that supports source-file launch'),
    'Kotlin': ('val declares a read-only binding and var a mutable one. Types are inferred; nullable types use ?. Blocks use braces.', 'kotlinc', 'kotlinc og-starter.kt -include-runtime -d starter.jar, then java -jar starter.jar'),
    'Scala': ('val binds immutable values and var mutable values. Types are inferred; block syntax depends on the Scala edition.', 'scala', 'scala og-starter.scala'),
    'Rust': ('let binds values; mut enables mutation. Ownership and borrowing control access to memory. Result represents recoverable errors.', 'rustc', 'rustc og-starter.rs, then run the compiled program; crates normally use Cargo'),
    'PHP': ('Variables start with $. Statements normally end with a semicolon. PHP source begins with <?php; web handlers require a server.', 'php', 'php og-starter.php'),
    'Ruby': ('end closes many blocks. Methods use def; blocks use do/end or braces. Symbols such as :name differ from strings.', 'ruby', 'ruby og-starter.rb'),
    'Go': ('package identifies a package; func declares a function. Braces delimit blocks, and := declares and initialises a variable.', 'go', 'go run og-starter.go; external modules need go.mod'),
    'C++': ('Braces delimit blocks; types are declared. #include provides declarations. Compile and link before running; object lifetimes matter.', 'g++', 'g++ og-starter.cpp -o starter, then run starter'),
    'C': ('Braces delimit blocks; types are declared. Pointers hold addresses. Compile and link before running; memory ownership needs explicit care.', 'gcc', 'gcc og-starter.c -o starter, then run starter'),
    'SQL': ('SQL describes operations on database tables. SELECT returns rows; WHERE filters them. Single quotes delimit string literals.', 'sqlite3', 'Run in the database engine documented by the source; dialects differ'),
    'Bash': ('Commands use space-separated arguments. $name expands a variable; quoting controls splitting. if blocks end with fi.', 'bash', 'bash og-starter.sh'),
    'PowerShell': ('Variables start with $. The pipeline passes objects. Cmdlets often use Verb-Noun names; blocks use braces.', 'pwsh', 'pwsh -NoProfile -File og-starter.ps1'),
    'R': ('<- commonly assigns values; vectors are central. Indexes normally start at 1. NA marks missing data.', 'Rscript', 'Rscript og-starter.R'),
    'Swift': ('let declares a constant and var a variable. Types are inferred; optionals explicitly represent missing values.', 'swift', 'swift og-starter.swift; platform frameworks require the matching platform'),
    'Dart': ('Braces delimit blocks and statements end with semicolons. final binds once; async/await handles futures.', 'dart', 'dart run og-starter.dart; Flutter examples need a Flutter project'),
    'HTML / CSS': ('HTML describes document structure; CSS selects elements and styles them. Neither uses Python statements or indentation to execute logic.', None, 'Save an .html document and open it in a browser; CSS needs a style element or stylesheet'),
    'CMake': ('Commands use name(arguments). ${name} expands variables. CMake configures a build; it is not the C/C++ program being compiled.', 'cmake', 'Save as CMakeLists.txt and run cmake -S . -B build, then cmake --build build'),
}


def syntax_comparison(language):
    guide = LANGUAGE_GUIDES.get(language)
    if not guide:
        return 'Consult the source documentation for this language or format; it has no configured teaching guide.'
    if language == 'Python':
        return guide[0] + '\nExample: if ready:\n    print("Ready")\nKeep the indented statement inside the block; inconsistent indentation is an error.'
    contrast = {
        'JavaScript': 'Python uses if ready: followed by indentation; JavaScript uses if (ready) { ... }. Python None/True/False correspond roughly to null/true/false. Lists and dictionaries have different methods from arrays and objects. Browser document is not a Python or Node.js global.',
        'TypeScript': 'Python annotations do not normally enforce types at runtime. TypeScript checks types before producing JavaScript. A Python def becomes function or an arrow function; braces replace indentation for blocks.',
        'SQL': 'A Python loop visits items step by step; SELECT describes the rows to retrieve. SQL NULL and its comparisons differ from Python None. Do not concatenate user input into queries; use the driver\'s parameters.',
        'HTML / CSS': 'Python executes statements. HTML creates elements and CSS styles them; JavaScript adds browser behaviour. A CSS colon separates a property from a value, rather than starting a Python block.',
        'CMake': 'Python runs a general-purpose program. CMake generates a build system; project(), add_executable() and target_link_libraries() describe the build. Indentation is for readability, not Python block scope.',
        'Ruby': 'Python closes blocks by dedenting; Ruby commonly uses end. Python None is nil in Ruby. Ruby arrays and hashes have their own methods.',
        'R': 'Python indexes lists from 0; R normally indexes vectors from 1. Python None and R NA have different meanings. R vector operations can act on all elements at once.',
        'PowerShell': 'Python usually passes values through function calls; PowerShell pipelines pass objects between commands. $name replaces Python name, and braces delimit blocks.',
        'Bash': 'Python variables are expressions; Bash expands $name into command arguments. Spaces around = are not allowed in a simple Bash assignment. Quoting is essential to avoid unintended argument splitting.',
    }.get(language, 'Python uses dynamic typing and indentation. This language has its own declaration, block, type and runtime rules; Python code cannot be pasted into it unchanged. ' + LANGUAGE_GUIDES[language][0])
    return guide[0] + '\n\nCompared with Python: ' + contrast


def code_facts(code, language):
    facts=[]
    if language == 'Python':
        try:
            tree=ast.parse(code)
        except SyntaxError:
            return ['This block is not currently valid standalone Python; use Check syntax for the exact location.']
        imports=[]
        for node in tree.body:
            if isinstance(node, ast.Import): imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or '(relative module)')
            elif isinstance(node, (ast.FunctionDef,ast.AsyncFunctionDef)):
                args=', '.join(a.arg for a in node.args.args)
                facts.append(f'Line {node.lineno}: {node.name}({args}) defines a reusable function. Its body runs when called; defining it alone produces no output.')
            elif isinstance(node, ast.ClassDef): facts.append(f'Line {node.lineno}: class {node.name} defines a type; inspect its constructor before creating instances.')
        if imports:facts.insert(0,'Imports used: '+', '.join(dict.fromkeys(imports))+'. Standard-library modules come with Python; third-party modules need their documented installation.')
    rules = [
        (r'\baddEventListener\b','Registers a browser event handler: the callback runs when the named event occurs, rather than immediately.'),
        (r'\bdocument\.createElement\b','Creates a browser element in memory; append it to the document before expecting it to appear.'),
        (r'\b(?:querySelector|getElementById)\b','Looks up an existing HTML element. Ensure the markup exists before this line runs; an unmatched lookup can return null.'),
        (r'\bfetch\s*\(','Starts an HTTP request. Await the response, check its status and handle network failures; browsers also enforce cross-origin rules.'),
        (r'\b(?:open\s*\(|read_text\s*\(|readFile|read_csv\s*\()','Reads or opens data. Replace example paths with a real test file and check the working directory and encoding.'),
        (r'\b(?:write_text|writeFile|to_csv)\s*\(','Writes data. Choose a test output path and check it does not overwrite an input you need.'),
        (r'\b(?:print\s*\(|console\.log\s*\(|Console\.WriteLine\s*\()','Displays a value in the run output or console. Compare the displayed value with your expected result.'),
        (r'\b(?:input\s*\(|ReadLine\s*\(|readline\s*\()','Waits for input. Use the Run output input field, or run in a terminal when interactive behaviour is required.'),
        (r'\b(?:import|require|using|#include)\b','Uses a module, package or header. Check its version, installation and runtime against the linked source before running.'),
        (r'\b(?:async|await)\b','Uses asynchronous work. await suspends the surrounding async operation until its result is available; errors still need handling.'),
        (r'\b(?:SELECT|select)\s','Queries a database. Check the schema, connection and SQL dialect; a documentation fragment may depend on tables created earlier.'),
    ]
    facts.extend(note for pattern,note in rules if re.search(pattern,code))
    return facts or ['This is a reference fragment. Its topic and source describe the intended context; no reliable behavioural explanation could be inferred from its syntax alone.']


def explain_example(example, entry=None):
    entry=example.get('library') or entry or {};code=example['code'];language=example['language']
    title=example.get('title','Reference example');topic=example.get('topic',title)
    purpose=example.get('explanation') or entry.get('explanation') or entry.get('description') or ('The publisher groups this block under '+str(topic)+'. A topic label is not proof that this block is a complete program.')
    if example.get('source_context'):purpose+='\n\nPublisher context (excerpt; may refer to earlier material):\n'+example['source_context']
    setup=entry.get('install') or 'Use the publisher\'s installation and version instructions. No dependencies are installed automatically.'
    steps=example.get('usage') or entry.get('usage') or ('1. Read the linked source, including surrounding definitions, required input and version.\n'
        '2. Review the imports and operations described below. Replace example names, paths and values with your own test inputs.\n'
        '3. Preview the block, then use Add snippet. Existing code remains editable; place definitions before their first use.\n'
        '4. Check syntax on the assembled program, then run it with the required runtime and dependencies.\n'
        '5. Compare the actual output with an expected result, try empty/invalid inputs and inspect any reported error before adding another block.')
    expected=example.get('expected_output') or entry.get('expected_output') or 'No verified expected output is supplied for this block. Function definitions may produce no visible output until called; fragments may depend on earlier source code.'
    return (f'{title}\n\nPurpose and when to use it\n{purpose}\n\nSetup and dependencies\n{setup}\n\n'
        f'How to use it\n{steps}\n\nWhat the code does and why\n'+'\n'.join(code_facts(code,language))+
        f'\n\nExpected result and checks\n{expected}\n\nSyntax and Python comparison\n{syntax_comparison(language)}\n\n'
        f'How to extend it\nAdd one feature at a time. Reuse existing variables and functions instead of redefining them. '
        'An appended block is not automatically integrated: check names, types, execution order and any existing main entry point. '
        'Use Undo update to remove the last addition, or edit the combined program directly.\n\n'
        f'Source: {example.get("url",entry.get("docs","Not supplied"))}\n'
        f'Attribution: {example.get("attribution","Not supplied")}\nTerms: {example.get("licence","Check source terms")}')


def append_snippet(existing, addition, language):
    """Append source without editing any existing text."""
    if not addition.strip():raise ValueError('The selected snippet is empty.')
    if existing.strip()==addition.strip():raise ValueError('This is already the complete code in your workbench.')
    return existing + ('\n\n' if existing and not existing.endswith('\n\n') else '') + addition.rstrip() + '\n'


def python_syntax(code):
    try:ast.parse(code)
    except SyntaxError as error:
        message=error.msg;line=error.lineno or 1;column=error.offset or 1
        reason='Python could not parse this statement. Check the highlighted position and the preceding line; the cause can begin earlier.'
        if 'expected \':\'' in message:reason='A compound statement such as if, for, def or class needs a colon before its indented body. Add : at the end of the header.'
        elif 'indent' in message or isinstance(error,IndentationError):reason='Python uses indentation to group statements. Indent the body consistently, normally four spaces, and do not mix tabs and spaces.'
        elif 'never closed' in message or 'unmatched' in message:reason='An opening bracket needs a matching closing bracket. Check (), [] and {} in this statement and the preceding lines.'
        elif 'unterminated' in message:reason='A quoted string is missing its closing quote, or crosses a line without valid multiline quoting. Match the quote style and escape embedded quotes.'
        elif re.search(r'\b(const|let|function)\b|===|&&|\|\|',code):reason='This looks like JavaScript syntax in a Python editor. Python uses assignments without let/const, def for functions, == for equality and and/or for Boolean operators.'
        text=(error.text or '').rstrip()
        return False,f'Python syntax error at line {line}, column {column}: {message}\n{text}\n'+(' '*(column-1))+'^\n\nWhy and how to correct it\n'+reason+'\n\n'+syntax_comparison('Python')
    return True,'Python syntax check passed. This checks grammar only; imports, values, missing files and program behaviour still need a run.'


def runtime_plan(language, code, folder, *, check=False, find=shutil.which):
    """Build argument vectors, never a shell command; no implicit installation."""
    folder=Path(folder)
    if language=='JavaScript' and re.search(r'\b(?:document|window|HTMLElement)\b',code) and not check:
        return None,[], 'Browser JavaScript uses the web preview, not Node.js.'
    runtime={ 'Python':'python','JavaScript':'node','Ruby':'ruby','PHP':'php','PowerShell':'pwsh','Bash':'bash','R':'Rscript','Go':'go','Dart':'dart','Swift':'swift','F#':'dotnet','TypeScript':'tsc' }.get(language)
    if not runtime:return None,[],LANGUAGE_GUIDES.get(language,('',None,'Use the documented project toolchain'))[2]+'. This language needs its project/compiler workflow; no built-in run adapter is configured.'
    exe=find(runtime)
    if not exe:return None,[],f'{runtime} is not available on PATH. Install/select the required runtime, then restart OG Code Companion. '+LANGUAGE_GUIDES[language][2]
    ext='.fsx' if language=='F#' else EXTENSIONS.get(language,'.txt');file=folder/('og-starter'+ext)
    if runtime=='tsc' and str(exe).lower().endswith(('.cmd','.bat')):
        # Invoke the installed compiler JS directly, avoiding cmd.exe quoting.
        compiler=Path(exe).parent/'node_modules/typescript/bin/tsc';node=find('node')
        if not compiler.is_file() or not node:return None,[],'TypeScript needs Node.js and the TypeScript compiler installed together. No shell wrapper is executed.'
        exe=node;prefix=[str(compiler)]
    else:prefix=[]
    if check:
        options={'Python':['-m','py_compile',str(file)],'JavaScript':['--check',str(file)],'Ruby':['-c',str(file)],'PHP':['-l',str(file)],'Bash':['-n',str(file)],'TypeScript':['--noEmit','--pretty','false',str(file)]}
        if language not in options:return None,[],'No syntax-only adapter is configured for '+language+'. '+syntax_comparison(language)
        args=options[language]
    else:
        args={'Python':['-u',str(file)],'JavaScript':[str(file)],'Ruby':[str(file)],'PHP':[str(file)],'PowerShell':['-NoProfile','-File',str(file)],'Bash':[str(file)],'R':[str(file)],'Go':['run',str(file)],'Dart':['run',str(file)],'Swift':[str(file)],'F#':['fsi',str(file)],'TypeScript':[]}[language]
        if language=='TypeScript':return None,[],'Check syntax compiles TypeScript types without execution. Compile it in your project before running the resulting JavaScript.'
    return str(exe),prefix+args,''


def diagnostic_explanation(language, output):
    details=[]
    rules=[('SyntaxError','The parser rejected the grammar before the program could run. Inspect the reported line and the preceding statement.'),
        ('Unexpected token','A token is not valid at this position. Check matching braces, parentheses, commas and the language selected.'),
        ('Unexpected end','The source ended while a string, expression or block was still open. Check closing quotes, parentheses and braces.'),
        ('is not defined','A name was used before a value or declaration was available. Check spelling, scope, imports and definition order.'),
        ('Cannot find module','The runtime could not resolve an imported package or file. Check the dependency installation and module path.'),
        ('ModuleNotFoundError','Python cannot import that module in the selected interpreter. Check the spelling and install the documented dependency in that interpreter.'),
        ('document is not defined','document belongs to a browser page. Use Web preview for DOM code; Node.js does not supply an HTML document.'),
        ('FileNotFoundError','The requested file was not found. Choose a working folder containing it or use the correct absolute path.'),
        ('TypeError','The operation received a value of an unsuitable type. Inspect the values passed at the reported line; valid syntax does not guarantee valid runtime values.'),
        ('IndentationError','Python block indentation is inconsistent or missing. Align statements within each block using spaces consistently.'),
        ('error TS','TypeScript reported a syntax or type-check failure. Use its file, line and column to check declarations, assignments and imports.')]
    for token,text in rules:
        if token in output:details.append(text)
    if not details:details=['Read the original diagnostic above. The installed runtime supplies the exact error; no automatic correction has been applied.']
    return '\n\nWhy it failed and what to check\n'+'\n'.join(dict.fromkeys(details))+'\n\n'+syntax_comparison(language)
