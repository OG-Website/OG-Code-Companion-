# OG Companion

OG Web.site's Windows coding workbench: find libraries, explore public documentation examples and build on editable code.

## Download and start

Download **OG Companion.zip** from [Releases](https://github.com/OG-Website/OG-Code-Companion-/releases/latest). Extract it, open the OG Companion folder and double-click **OG Companion.exe** or **Start OG Companion.cmd**. Keep the complete folder together. Python and Tcl/Tk are bundled in the Windows package.

## Build on your code

**Clear search** clears the description, keywords, results and example selection while retaining the editor. **Clear code** separately starts a new workbench and asks before discarding unsaved changes.

**Build / update code** builds from an empty editor or sends your current code with a changed requirement. **Expand code** starts a new request immediately. Click it again after completion to request a further useful addition to the latest code. **Undo update** restores the preceding code change. Searches and library selections retain the code until you explicitly load another example.

Custom building and expansion require a separately installed [Ollama](https://ollama.com/) service and local model. The supplied CSV-to-JSON foundation and teaching examples work without AI. Model output is a draft: unchanged responses are rejected, Python syntax is checked and existing top-level Python function/class names must remain, but these checks do not prove that every requirement or behaviour is correct. Test saved code before using it. OG Companion does not execute generated or retrieved code.

## Content and sources

The included snapshot contains **30 editable teaching snippets across 14 languages**, one complete CSV-to-JSON foundation and **244 documentation collection titles across 837 editions**. Editions include versions, languages, tools and frameworks; they are not 837 unique libraries. The language selector has 21 choices and seven package-registry connectors cover 11 choices directly. Other languages can use public repository discovery and source URLs.

Online examples are retrieved on demand, beyond the bundled catalogue. The total across online sources is unmeasured. Each loaded collection reports its actual distinct block count; commands, configuration, transcripts and API declarations are distinguished from executable source. The guide and `og_companion_assets/content-inventory.json` contain the checked counts and dates. Third-party source and licence terms apply.

## Source and verification

Run with Python 3 and Tcl/Tk:

```powershell
py -3 og_companion.py
py -3 -m unittest -v og_companion_tests.py
```

The portable build was checked with Python 3.14.0 and PyInstaller 6.17.0 on Windows 64-bit. To build from this repository:

```powershell
py -3 -m pip install -r requirements-build.txt
& '.\Build OG Companion.ps1'
```

The build script runs the source tests, bundles the interpreter and resources, checks the executable and creates the complete ZIP. Source files are editable; an existing executable needs rebuilding to include source changes.

The Read Me and technical specification cover discovery, source retrieval, caching, controls, generation and recipient checks. A clean second computer and other operating systems remain recipient/platform checks.

Built by Rob Johnston for OG Web.site.
