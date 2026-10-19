# OG Code Companion

<img src="og_companion_assets/OG%20Code%20Companion%20logo.png" width="180" alt="OG Code Companion logo">

Describe what you want to build, assemble editable code with detailed guidance, explore library examples, and connect your own local models. OG Code Companion 2.4 uses three tabs, a smoothly scaled circular OG background and readable translucent controls.

## Download and start

Download the Windows **OG Code Companion.zip** from [GitHub Releases](https://github.com/OG-Website/OG-Code-Companion-/releases/latest), or build it locally with **Build OG Code Companion.ps1**. Extract it and open **OG Code Companion.exe** or **Start OG Code Companion.cmd**. For published packages, see [Releases](https://github.com/OG-Website/OG-Code-Companion-/releases/latest) and check the version and asset name; existing releases can describe an earlier build. Keep the complete folder together: Python and Qt are included in the Windows 64-bit package.

**First time using local AI? Follow the [full setup guide below](#local-ai-setup-guide).** It includes official downloads, model installation, connecting to OG Code Companion and troubleshooting. You can start using the supplied code and libraries straight away while you decide whether to add a model.

## Build code

Choose a language and describe a feature or library. **Find code / Update** offers a supported starter or a matching reference. **Find more snippets** searches documentation topics, package sources and cached collections without AI. Selecting JavaScript cannot silently load Python Click examples.

Retrieved examples open in **Snippet preview** alongside an explanation of their purpose, setup, operations, use, expected results where supplied, extension points, source and licence. Source context is retained when available. Unknown behaviour and dependencies are identified rather than invented. Each of the 22 language/tool choices has a syntax guide and a comparison with Python where relevant.

Choose **Add snippet to code** to append it to the existing program. Repeat with another example or edit the assembled source directly. **Replace code with snippet** is separate and protects unsaved edits. **Undo update** restores the previous code and explanation. Adding a fragment does not automatically connect its variables, dependencies or entry points to the rest of a program.

**Check syntax** reports Python parser locations and explanations. Installed Node.js, Ruby, PHP, Bash and TypeScript tools provide their own syntax diagnostics where configured; TypeScript also checks types. Explanations describe likely causes and language differences without silently rewriting source. A syntax pass does not prove correct behaviour.

**Run code** executes only after an explicit review confirmation. Python, Node.js JavaScript, Ruby, PHP, PowerShell, Bash, R, Go, Dart, Swift and F# have runtime adapters when their tools are installed on PATH. Browser JavaScript that uses document/window opens a web preview; HTML/CSS also use a browser. Other languages receive their project/compiler instructions. Missing runtimes are reported; none is installed automatically. The app's bundled desktop runtime does not replace the language runtimes required for learners' programs.

**Run output** shows output, errors and explanations. Set a working folder for input files, supply arguments as a JSON string list, send standard input or stop the child process. Local child runs have a 30-second time limit and 1 MB output limit. The run uses the user's file and network permissions and is not a sandbox. Browser previews run separately and are not subject to the child-process limits.

Use **Project → Save project with explanations** to retain the assembled code, explanations, request and source references in one editable JSON project; **Open project** restores them without executing anything. **Save code** exports source only. **New request** retains code, while **Clear code** asks before discarding unsaved work. Custom AI updates remain optional through a local or hosted API model you explicitly configure. Selecting a language immediately refreshes its supplied examples. An empty package search restores that language's basics; the main languages and every other selector choice have a built-in baseline, so no model is needed to begin.

## Browse libraries

Explore seven package registries, the DevDocs catalogue and public repositories, or load a public source URL. Get examples from a selected library, browse further result pages, load complete collections and export source blocks with their attribution. Browsing and retrieval do not require AI.

The supplied content includes **55 teaching snippets across all 22 language/tool choices**, two complete Python foundations, **244 documentation titles across 837 editions**, and **14 licensed collections containing 84,512 summed source blocks**. Editions are versions and documentation sets. Blocks include commands, configuration and transcripts; they are not a count of runnable programs. The global online total is unmeasured. The selector has 22 language/tool choices, including CMake. Source terms and provider availability apply.

## Models / API

Use **Add API model** for OpenAI Responses, Anthropic Messages, Gemini's OpenAI-compatible API, or another service implementing OpenAI-compatible Chat Completions/Responses. Enter the provider, API base URL, exact model ID and your API key. Custom compatible services can use Bearer, api-key or x-api-key authentication. Compatibility depends on the chosen protocol, endpoint, model and account; this is not a claim that every proprietary API is supported.

Keys remain in memory for the session, are excluded from settings/projects/packages and can be removed using **Forget API keys**. Adding a configuration makes no network request and labels it unverified. When you explicitly request generation or expansion, the task and current code go to that provider under its billing and data policies. Hosted requests require HTTPS and reject redirects rather than forwarding credentials. Basic examples, browsing and manual snippet assembly remain available without any model account.

Provider adapters are covered by request/response fixtures and generation regression tests. No live hosted generation was performed with a real provider key. Use your own account and model ID to verify account access and generation quality.

The adapter schemas follow [OpenAI text generation](https://developers.openai.com/api/docs/guides/text), [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create) and [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).


Discover the recipient's running Ollama, LM Studio or compatible localhost service, including recognised Windows services on non-default ports. Choose a model from the table and connect it explicitly. Add a service URL for another local endpoint. Optional service tokens stay in memory for the session; model weights and credentials are not shipped. Supported LM Studio native APIs list downloaded as well as loaded models. Embedding models are identified separately from code-capable language models.

A serving runtime must be available; the app does not directly open arbitrary weight files. Without AI, supplied/cached libraries, source retrieval, editing, copying and saving remain available. A local endpoint may itself use a remotely hosted model according to the recipient's service configuration.

## Local AI setup guide

### What you need

Use the Windows 64-bit OG Code Companion release on a compatible computer. Install a model runner, download a language model into it, then connect OG Code Companion to that runner's local server. The runner manages the model files and memory; OG Code Companion provides the coding workbench. Choose either the Ollama route or the LM Studio route below. You can connect more services later.

Internet access is needed for the initial downloads. Leave space for the runner and model files, and check the runner's hardware requirements. Model download size is different from the RAM or graphics memory required to run it. A larger context also uses more memory. See [Ollama hardware support](https://docs.ollama.com/gpu) or [LM Studio system requirements](https://lmstudio.ai/docs/app/system-requirements). LM Studio currently recommends at least 16 GB RAM and 4 GB dedicated VRAM on Windows, with AVX2 required for x64 CPUs; these are its recommendations, not a promise that every model will fit.

### Route 1: Ollama

#### Install the runner and a model

1. Open the official [Ollama Windows download page](https://ollama.com/download/windows), choose the manual installer and install it. The [Windows guide](https://docs.ollama.com/windows) lists supported Windows versions and explains model storage.
2. Start Ollama from the Windows Start menu. The normal Windows installation runs its server in the background at `http://localhost:11434`.
3. Open a **new PowerShell window** after installation. Download a model with this command and wait for it to finish:

   ```powershell
   ollama pull qwen2.5-coder:3b
   ```

4. Check that the download appears in the installed model list:

   ```powershell
   ollama ls
   ```

The [Qwen2.5-Coder model page](https://ollama.com/library/qwen2.5-coder) offers several sizes. These are example downloads to try, rather than a guarantee of performance on your computer:

| Model tag | Approximate download size | Download command |
| --- | --- | --- |
| `qwen2.5-coder:1.5b` | 986 MB | `ollama pull qwen2.5-coder:1.5b` |
| `qwen2.5-coder:3b` | 1.9 GB | `ollama pull qwen2.5-coder:3b` |
| `qwen2.5-coder:7b` | 4.7 GB | `ollama pull qwen2.5-coder:7b` |

Smaller models are an option when resources are limited, but their answers still need checking. In OG Code Companion's controlled checks, a 1.5b model failed an explicit reusable-module request. A separate [general Qwen2.5 3b model](https://ollama.com/library/qwen2.5:3b) produced one tested file-count module. You can download that particular model with `ollama pull qwen2.5:3b`; it is a different model from `qwen2.5-coder:3b`. The table's sizes describe downloaded weights, not total runtime memory, and can change.

#### Connect it to OG Code Companion

1. Keep Ollama running and open **OG Code Companion**.
2. Open **Models / API** and choose **Refresh models**.
3. Select the downloaded model in the table, checking its provider and endpoint.
4. Click **Connect selected model** and wait for the connection message.
5. Open **Build code**, choose **Python**, enter a request and click **Find code / Update**.

For a first custom request, try: “Write a reusable Python function called count_regular_files(folder). Return the number of regular files directly inside the folder, exclude subfolders, and raise ValueError if the folder does not exist. Do not use input(). Include pathlib.” Review the source in **Code** and the explanation in **How to build it**, then save your version. Use Check syntax and explicitly choose Run code after reviewing it; the app never runs generated code automatically.

You can also check the model directly in PowerShell with `ollama run qwen2.5-coder:3b`. Type `/bye` to leave that chat, as shown in the [official quickstart](https://docs.ollama.com/quickstart). The [Ollama CLI reference](https://docs.ollama.com/cli) covers downloading, listing and stopping models.

### Route 2: LM Studio

1. Download the Windows installer from the official [LM Studio download page](https://lmstudio.ai/download) and install it.
2. Open LM Studio's **Discover** tab (`Ctrl+2`). Search for a coding language model, such as **Qwen2.5-Coder**, and inspect the publisher, model size and download options. Its [model download guide](https://lmstudio.ai/docs/app/basics/download-model) explains these choices. A quantised model stores weights at lower precision to reduce size; choose a supported Windows GGUF download that fits your machine. A 4-bit option such as Q4_K_M is a starting option to assess, not a universal hardware guarantee.
3. Complete the model download. Load it in LM Studio and try a short chat there first; this checks that the runner can actually use it.
4. Open LM Studio's **Developer** tab and turn on **Start server**. Use its displayed localhost address and port. The usual address is `http://localhost:1234`. Follow the [official server guide](https://lmstudio.ai/docs/developer/core/server) if the controls differ in your version.
5. Open OG Code Companion's **Models / API** tab, choose **Refresh models**, select the language model and click **Connect selected model**.
6. If LM Studio uses another port, click **Add service URL**, enter its base address, for example `http://127.0.0.1:1234`, and refresh again. Continue in **Build code** as described above.

Supported LM Studio native APIs expose downloaded models and their loaded instances. OG Code Companion can load the selected downloaded language model through that API. With older or generic compatible APIs, load the model in the runner first. Embedding models produce representations for search and are unsuitable for this code-generation action. See LM Studio's [model-list API](https://lmstudio.ai/docs/developer/rest/list).

If you enable LM Studio authentication, create a token through **Developer > Server Settings > Manage Tokens**, using its [authentication guide](https://lmstudio.ai/docs/developer/core/authentication). In OG Code Companion, choose **Service token**, enter the matching localhost base URL, then paste the token into the password field. Refresh and connect. OG Code Companion retains this token only for that session; enter it again after restarting. Keep tokens out of shared files and screenshots.

### Existing models and other local servers

Use models already installed in your runner by starting its server, refreshing the table and connecting the selected model. A model file sitting in a downloads folder needs to be imported into a compatible runner before OG Code Companion can discover it.

For another OpenAI-compatible local server, enable its `/v1/models` and `/v1/chat/completions` endpoints. Enter the **base URL** through **Add service URL**, such as `http://127.0.0.1:8080`, then refresh and connect. An `/v1` suffix is accepted and normalised. This release accepts localhost addresses (`localhost`, `127.0.0.1` or `::1`); remote addresses need a separate integration. The table shows the models that the running server exposes, which may differ from the files on disk.

For local inference, select downloaded local weights in the runner. Cloud-backed models can send requests beyond your computer even when the API address is localhost. Check the runner's configuration and the chosen model before submitting private code.

### When something does not work

| What you see | What to check |
| --- | --- |
| `ollama` is not recognised | Finish installation and open a new PowerShell window so it receives the updated PATH. |
| Empty model table | Start the runner, finish downloading a language model, enable its API server and refresh. For Ollama, check `ollama ls`. For another port, use **Add service URL**. |
| Ollama connection refused | Start Ollama from the Start menu. For a CLI-only installation, `ollama serve` starts the server; keep that terminal open. If the port is already in use, check the existing service rather than starting another copy. |
| LM Studio chat works but no model appears | Enable **Start server** in the Developer tab and check its displayed port. Try loading the model manually, then refresh. |
| Authentication error or protected server missing from the table | Enter a valid token through **Service token** for the same base URL. Refresh after adding it. |
| Loading fails or generation is very slow | Try a smaller model or a shorter request/context, and close other memory-heavy applications. Check the runner's logs and hardware guidance. |
| Response is rejected | Read the message, simplify the request or try another model. The app retains your existing code when validation fails; a connected model can still produce unsuitable code. |
| A saved program will not run | Install that program's own language runtime and dependencies. The runtime inside OG Code Companion supports the workbench itself. |

For an Ollama endpoint check in PowerShell:

```powershell
(Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags').models |
    Select-Object name
```

This checks the runner's [installed-model API](https://docs.ollama.com/api/tags). Replace the port with your configured port when necessary. An empty list means no models are listed by that service; a connection error means the service is unavailable at that address.

### Using OG Code Companion without a model

Open **Build code**, choose **Python** and enter “cybersecurity, file libraries, security considerations” to load the supplied local file-integrity foundation. The CSV-to-JSON foundation is also supplied. **Browse libraries** retrieves public examples independently of AI. Supplied and cached material remains available with **Online sources** switched off; material not yet downloaded requires internet access.

To run Python source you save, install Python separately from the [official Windows downloads](https://www.python.org/downloads/windows/) and follow its [Windows setup guide](https://docs.python.org/3/using/windows.html). In PowerShell, open the folder containing your saved program and run `py -3 your_program.py`, replacing the filename. Install additional packages only when that program needs them. Other languages need their corresponding runtimes or build tools.

The runner links and commands above were checked against official documentation on **14/10/2026**. Ollama has been exercised locally with OG Code Companion; a live LM Studio installation and a clean second Windows computer remain separate verification steps. Model downloads and their licences belong to their publishers and are not included in the OG Code Companion ZIP.

## Run from source or build

```powershell
py -3 -m pip install -r requirements-build.txt
py -3 og_companion.py
py -3 -m unittest -v og_companion_tests.py
& '.\Build OG Code Companion.ps1'
```

Version 2.4 source passed **136 automated tests** on 19 October 2026, including language filtering, successive additions, project saving/loading, Python execution and Node.js syntax diagnostics. The rebuilt Windows executable passed its offline installation check for both foundations, preview preservation, assembly, syntax explanations, the JavaScript button reference and correct branding. Recheck an extracted package with `OG Code Companion.exe --check-installation report.json`. Live source retrieval returned 106 matching JavaScript examples for Axios and four CMake examples. Retrieval is distinct from executing those examples. The supplied browser-button example was checked through two clicks in a browser.

Model output is a draft. Python syntax, explicit no-prompts requests and update preservation are checked, but arbitrary behaviour still needs tests. Retrieved/generated code is never automatically executed. A clean second computer and live LM Studio remain separate checks. Runtime notices are in `og_companion_assets/runtime-licences`; collection terms are in `og_companion_assets/source-licences`.

The Read Me and technical specification describe version 2.4. The [product and investor portfolios](Portfolios/) describe version 2.2 and need revision to include these changes before being used as current feature summaries.

Built by Rob Johnston for OG Web.site.
