# TokenSaver Docs

**Prepare documents once. Give your AI only what it needs.**

A document context plugin for Codex, Claude Code, and OpenCode. Convert documents once,
reuse the Markdown across sessions and agents, and read only the evidence you need.

[한국어 안내](README.ko.md) · [Local plugin builds](docs/plugin-preview.md) · [Benchmarks](benchmarks/README.md)

Text PDF, Word, Excel and HTML are extracted locally. The user chooses images with
visible text and descriptions, images only, or `[이미지]` placeholders at known
image positions. Image analysis
uses a provider and model chosen by the user; multilingual audio can run locally with bundled whisper.cpp.
No separate OCR engine is used. Existing files and user edits are preserved.

## Quick start

### 1. Install

This installs the **source CLI**, not an agent plugin. Requires Python 3.11+ and Git. Public plugin release archives are not available yet.

**macOS / Linux**

```sh
python3 -m venv "$HOME/.tokensaver-docs/venv"
source "$HOME/.tokensaver-docs/venv/bin/activate"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

**Windows PowerShell**

```powershell
py -3 -m venv "$HOME\.tokensaver-docs\venv"
& "$HOME\.tokensaver-docs\venv\Scripts\Activate.ps1"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

In a new terminal, activate the environment again using the second line. If PowerShell blocks activation, use `& "$HOME\.tokensaver-docs\venv\Scripts\tokensaver-docs.exe"` instead of `tokensaver-docs`, without changing execution policy.

### 2. Choose or change the conversion model

Run this in your terminal, then **enter a model number from the list**. The selected model becomes the default for future image conversions. Use the same command to change it later.

```sh
tokensaver-docs configure --kind image --provider openrouter
```

OpenRouter image analysis needs the `OPENROUTER_API_KEY` environment variable. Do not share keys in agent chat. This changes the document image model, not your coding agent's chat model or audio model. Plain document text extraction needs no model or API key.

Check the current model:

```sh
tokensaver-docs setup-model
```

### 3. Convert a file or folder

Replace `./documents` with your input path. This extracts text and marks image positions with `[이미지]`, without image analysis:

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode placeholder
```

To include visible image text and descriptions, configure your model/key first, then run this. Images are sent to the selected provider:

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode analyze
```

## Supported file formats

| Type | Extensions | Markdown content |
| --- | --- | --- |
| PDF | `.pdf` | Extracted text; image analysis of selected scanned pages |
| Word | `.docx` | Document text, tables, and embedded images |
| Excel | `.xlsx` | Sheets, cells, and embedded images |
| HTML | `.html`, `.htm` | Body content, tables, and embedded images |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif` | Preserved images, with optional visible text and image descriptions |
| Audio and video audio tracks | `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.mp4` | Speech converted to text; video frames are not analyzed |

Image analysis and speech-to-text require separate model setup and user choices.
Legacy `.doc` and `.xls` files are not supported.

The CLI command, Python package, plugin IDs, and installation paths use `tokensaver-docs` (`tokensaver_docs` in Python).

## Current status

0.4.0 is a local preview, not a published registry or official directory release.
Source CI passes on macOS, Windows, and Linux with Python 3.11 and 3.13.
The macOS arm64 executable and bundled OpenCode integration are tested locally.
Windows and Intel Mac native installers have not been verified.

## Install a plugin

The distribution path is **GitHub Releases → platform archive → local plugin**.
No hosted server is needed. Choose Claude Code, Codex or OpenCode and run the
release installer for Windows x64, macOS Apple Silicon or macOS Intel.
See [installation, updates and release preparation](docs/distribution.md).

The bundles include Python, PDFium and the audio runtime. Users do not need
separate Python, Poppler, npm or Bun. Image providers and audio models are chosen
on first use. Public release URLs will be added after publication; a checkout
alone is not a published plugin installer.

## Use from a checkout

```sh
python -m pip install '.[mcp,tokens]'
tokensaver-docs prepare ./documents --output ./converted --skip-image-transcription
tokensaver-docs convert ./documents --output ./converted --no-configured-providers
tokensaver-docs context ./documents 'refund deadline' --output ./converted --max-tokens 1200
tokensaver-docs read ./converted/policy.pdf.md --start-line 20 --lines 40
```

The installed plugin bundles contain the Python runtime and libraries. The
checkout installation above is for Python users; end users of a built plugin
bundle do not need Python, npm or Bun. See [plugin installation](docs/plugin-preview.md).

## Convert once

For agents, start with `prepare_documents` (OpenCode v1: `tokensaver_docs_prepare`;
v2: native `tokensaver_docs_prepare`). First use offers model selection or
deferral. The plugin's conversion model can differ from the host chat model;
the plugin does not infer a host model it cannot verify. Ordinary document text
needs no AI model. For images, the tool checks the selected model's image support
and reports free pricing separately from image support and lookup errors.
If the model cannot read images, choose **change model** or **continue with
`[이미지]` only**. Continuing extracts ordinary document text and marks each known
image position with `[이미지]`; it adds no image link, image text or description.
Supported models offer images with visible text and descriptions, or images only.
An external analysis provider receives the images after the user's selection.
The tool returns output paths/status, not raw HTML or Base64. Questions use
`context_documents` for bounded evidence.

For CLI use, inspect first-use setup or defer it:

```sh
tokensaver-docs setup-model
tokensaver-docs setup-model --defer
# Inspect a user-selected model without saving it:
tokensaver-docs setup-model --provider openrouter --model MODEL_ID
# Only after the user chooses to save this default:
tokensaver-docs setup-model --provider openrouter --model MODEL_ID --save-as-default --confirmed
```

`prepare INPUT --output OUTPUT --image-mode analyze` includes images, visible text
and descriptions; `preserve` includes images only; `placeholder` writes `[이미지]`
only. `--model-provider PROVIDER --model MODEL_ID` chooses a model for that request
without changing the default. API keys belong in environment variables, never
these model arguments. Unknown image support requires explicit manual consent
with `--allow-unverified-model`; this does not bypass confirmed incompatibility,
lookup failures or OpenRouter's free-price checks. No separate local OCR is added.
The existing `--transcribe-images` and `--skip-image-transcription` flags retain
their analyze/preserve meanings. Check status for pending choices, missing models,
unreadable images or incomplete analysis.

Image preparation does not enable an audio provider. For MCP `convert_documents`,
`use_configured_providers=true` selects the image provider and
`use_configured_audio_provider=true` separately selects audio. The optional
`context_documents` provider switch enables both and needs consent for both.
The existing CLI `convert` command uses configured providers by default; when
`--transcribe-images` or `--vision-pages` is specified, audio is excluded unless
`--use-configured-audio-provider` is also supplied.

The OpenCode read hook intercepts HTML with a literal embedded-image data URI.
It directs the agent to preparation when a model/image choice is needed rather
than silently choosing a mode; prepared Markdown reads are capped at 40 lines.
HTML entities in the URI can evade detection; shell commands and other host tools
are also outside that hook. Use `tokensaver_docs_prepare` for reliable preparation.

CLI, MCP and plugins use a common cache within the current user's application data.
Identical content can be reused after renaming or moving a file, changing the output
folder, or switching agents. Complete media units survive partial failure and can
be reused in another output folder or a changed document when the actual processed
unit is identical. Concurrent requests share per-source and per-unit locks.

Preparation separates analyze, preserve and placeholder caches. Explicitly choosing
a model for analysis uses that model's cache identity; a result from a different
model is not presented as its work. Legacy `convert` model-setting changes alone
do not automatically regenerate successful shared results. Prior text-only image
results are not complete image descriptions.
Request `convert --refresh` explicitly to make a new version. Existing
outputs are kept. Unverifiable old results are preserved rather than silently
reprocessed. Cache integrity failures are explicit.

## Media setup

The audio bundle includes a CPU whisper-cli. First show a model's download size:

```sh
tokensaver-docs setup-audio --model small
# After choosing the model and consenting to the download:
tokensaver-docs setup-audio --model small --download
```

The pinned multilingual model download is checksum-verified and shared across
agents. Local Whisper automatically detects the language; review its transcript
for recognition errors. No audio is uploaded for local transcription. For image analysis,
choose a supported provider and model; API keys belong in environment variables,
not documents, chat, configuration files or logs. No paid or alternate model is
automatically selected. Free API quotas and availability vary.

## What is measured

`context` returns original excerpts with paths, line ranges, pending items and
truncation/continuation information. Its token budget uses `cl100k_base` for the
serialized JSON response and excludes the host's protocol framing and tool schemas.
It is not a guarantee about the host model's billed usage. Existing search/read
commands retain their documented body-only budgets.

Our small synthetic QMD comparison is a reproducible example, not a ranking or a
real-world accuracy or savings claim. Converting to Markdown alone does not guarantee
lower tokens if the agent then reads the entire document repeatedly.
The [synthetic HTML comparison](benchmarks/README.md#html-예제) includes a small
case where the bounded response is larger than the full Markdown.

## Limits and privacy

Extracted text and image descriptions can contain errors, especially names,
numbers and diagram relationships. Compare important details with the original.
Audio transcripts can also contain errors.
Search is lexical, can miss synonyms or distant exceptions, and is not proof that
a fact is absent. Truncated or incomplete output is not a full-document review.
HTML CSS background images are not extracted; possible omissions are flagged for review.
Scanned and selected visual PDF pages use bundled PDFium to prepare image input;
transcription still requires a selected image provider and model.

Files already uploaded through the host's native attachment flow may already have
consumed tokens. Pass a file or folder path to the plugin before uploading raw
media when possible. Documents and caches stay local unless the user explicitly
selects an external transcription provider and allows the relevant media to be sent.
Caches contain document text: treat them as private and review any outputs before sharing.

[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [MIT License](LICENSE)

CLI diagnostic and status messages currently include Korean; plugin tool names and schemas are in English.
