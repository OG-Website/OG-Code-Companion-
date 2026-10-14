# OG Companion

<img src="og_companion_assets/OG%20Code%20Companion%20logo.png" width="180" alt="OG Companion logo">

Describe what you want to build, get editable starter code and guidance, explore library examples, and connect your own local models. OG Companion 2.2 uses three tabs, a smoothly scaled circular OG background and readable translucent controls.

## Download and start

Download **OG Companion.zip** from [Releases](https://github.com/OG-Website/OG-Code-Companion-/releases/latest). Extract it and open **OG Companion.exe** or **Start OG Companion.cmd**. Keep the complete folder together: Python and Qt are included in the Windows 64-bit package.

## Build code

Type a program description, choose a language and click **Get starter code / Update**. **Code** holds editable source and **How to build it** explains the approach. CSV-to-JSON and file-integrity foundations work without AI; matching reference snippets and real documentation examples are also available. Custom programs and expansion use a model you explicitly connect.

**New request** retains the editor. **Clear code** asks before discarding unsaved work. Updates include your current code, **Expand code** requests another addition, and **Undo update** restores the preceding source. Ctrl+Enter builds and Ctrl+S saves.

## Browse libraries

Explore seven package registries, the DevDocs catalogue and public repositories, or load a public source URL. Get examples from a selected library, browse further result pages, load complete collections and export source blocks with their attribution. Browsing and retrieval do not require AI.

The supplied content includes **31 teaching snippets across 14 languages**, two complete Python foundations, **244 documentation titles across 837 editions**, and **14 licensed collections containing 84,512 summed source blocks**. Editions are versions and documentation sets. Blocks include commands, configuration and transcripts; they are not a count of runnable programs. The global online total is unmeasured. The selector has 22 language/tool choices, including CMake. Source terms and provider availability apply.

## Local models

Discover the recipient's running Ollama, LM Studio or compatible localhost service, including recognised Windows services on non-default ports. Choose a model from the table and connect it explicitly. Add a service URL for another local endpoint. Optional service tokens stay in memory for the session; model weights and credentials are not shipped. Supported LM Studio native APIs list downloaded as well as loaded models. Embedding models are identified separately from code-capable language models.

A serving runtime must be available; the app does not directly open arbitrary weight files. Without AI, supplied/cached libraries, source retrieval, editing, copying and saving remain available. A local endpoint may itself use a remotely hosted model according to the recipient's service configuration.

## Run from source or build

```powershell
py -3 -m pip install -r requirements-build.txt
py -3 og_companion.py
py -3 -m unittest -v og_companion_tests.py
& '.\Build OG Companion.ps1'
```

Version 2.2 source passed **106 automated tests** on 14 October 2026. The packaged Windows executable passed the offline installation check for both foundations, tabs, clearing and undo. The interface was inspected at 1280 x 720 and 960 x 700 logical sizes. Recheck an extracted package with `OG Companion.exe --check-installation report.json`.

Model output is a draft. Python syntax, explicit no-prompts requests and update preservation are checked, but arbitrary behaviour still needs tests. Retrieved/generated code is never automatically executed. A clean second computer and live LM Studio remain separate checks. Runtime notices are in `og_companion_assets/runtime-licences`; collection terms are in `og_companion_assets/source-licences`.

The Read Me, technical specification and [portfolios](Portfolios/) explain operation, architecture and the commercial evidence boundary.

Built by Rob Johnston for OG Web.site.
