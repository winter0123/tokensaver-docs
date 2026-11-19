# Advanced usage

[Back to quick start](../README.md) · [Verification status](current-status.md)

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
The [synthetic HTML comparison](../benchmarks/README.md#html-예제) includes a small
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

[Contributing](../CONTRIBUTING.md) · [Changelog](../CHANGELOG.md) · [MIT License](../LICENSE)

CLI diagnostic and status messages currently include Korean; plugin tool names and schemas are in English.

## Project research archive (unreleased)

The updated source and plugin builds support a local research archive. The
published v0.4.2 download predates this feature. From your project directory,
run the activation command printed by the updated plugin installer. With a
source CLI installed with the `tokens` extra, run:

```sh
tokensaver-docs knowledge enable .
```

Activation creates `docs/research/inbox/` and `docs/tokensaver-docs/` and adds
both paths to the project's Git ignore rules. Git continues to track files
already committed. Project activation is bound to the project's absolute path.
Run activation again after moving the project. `knowledge disable .` turns off
capture, removes managed project hooks and clears optional automation approvals. The archive remains available for search.

| Host | How to capture |
| --- | --- |
| Codex | Run the printed activation command and review the project hooks in `/hooks`. With the source CLI, add `--codex-project-hooks`. |
| Claude Code | Run the printed activation command. With the source CLI, add `--claude-project-hooks` to register local project settings. |
| OpenCode v1/v2 | The plugin uses session and file-write hooks when the project is enabled. |
| Manual | Run `tokensaver-docs knowledge sync .` with the installed executable path if needed. |

For example, ask “Look up the refund policy and summarize it in this project.”
The archive preserves plain-text (`.txt`) originals and creates separate Markdown copies for search. A citation links to the submitted file. For agent-authored material, check important claims against the underlying source.

The capture workflow processes supported files the agent saves in the inbox.
It preserves original bytes and versions, prepares searchable Markdown and links
summaries to the evidence. Links without a saved source are marked
`REFERENCE_ONLY`. For a topic report, the agent can also save a
[`<topic>.research.json` draft](advanced-usage.ko.md#프로젝트-조사-자료-자동-보관)
with source paths and exact quotes.

Open `docs/tokensaver-docs/index.md` to find reports, then
`docs/tokensaver-docs/reports/<topic>/summary.md` for a topic summary.
Without a draft, the inbox report shows recent excerpts. If new evidence
arrives, sync rechecks unresolved citations. Already linked evidence stays
pinned, and summary edits stay intact. Generated updates to an edited summary
appear in a separate `summary.pending-*.md` file.

For a later question, use `search_research` over MCP or
`tokensaver_docs_search_research` in OpenCode. Pass the absolute project path
and focused keywords. Each `source_index` refers to the corresponding
project-relative Markdown path in `sources`. When a line is clipped, the
response still identifies its original line. CLI equivalents:

```sh
tokensaver-docs knowledge search . "refund exceptions" --max-tokens 500
tokensaver-docs knowledge search . "refund exceptions" --version-id VERSION_ID --conversion-id CONVERSION_ID
```

Archiving uses local conversion. To reuse an approved, already completed image
analysis or transcription of a self-contained source, first sync the source,
then attach that conversion. The third argument is the earlier conversion's
output folder, relative to the project. The attachment checks the source and
conversion hashes.

```sh
tokensaver-docs knowledge attach . docs/research/inbox/interview.wav converted
```


### Optional website and media processing

Add these flags to the activation command to authorize processing for this
project on this machine. The approvals are stored in user settings. Re-enable
the options when replacing a project at the same path or migrating old approvals.

- `--snapshot-domain docs.example.org` captures exact-host public HTTPS HTML
  referenced in a research draft. Repeat it for multiple hosts. Each response
  is limited to 2 MiB. URLs with queries or credentials, redirects and blocked
  responses remain references.
- `--auto-audio` transcribes inbox audio through the configured local Whisper
  profile.
- `--auto-image-analysis` authorizes sending standalone inbox images to the
  currently selected provider and model. Provider charges may apply.
  Images embedded in other documents are preserved in ordinary conversion.
- `--clear-automation` clears these optional approvals.

Sync processes one approved media file at a time and keeps earlier conversions
available. An interrupted local transcription gets one retry. An interrupted
external image analysis requires review before resending. The archive index
shows items that need attention. You can run the ordinary conversion commands
and attach their result to the source. Web work deferred by the time budget
reports `pending`.
