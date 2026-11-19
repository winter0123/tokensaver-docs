# TokenSaver Docs for OpenCode

This package adds local document preparation and bounded search to OpenCode.
The platform-specific release includes the `tokensaver-docs` executable. The
OpenCode v2 tools can analyze images with an explicitly selected model after the
user approves image analysis; no image is sent for analysis without that choice.

## Git-installed OpenCode 2 plugin startup

For the GitHub `::path:plugins/opencode` package, **server plugin activation does not download the native runtime**. The V2 plugin registers its native document tools immediately and only checks for a previously bundled/cached CLI. The first actual `tokensaver_docs_prepare` or other native document tool call then downloads the pinned release into the per-user cache, verifying its published SHA-256, and executes it. If that runtime exists at the next OpenCode service startup, the optional internal local MCP bridge is registered automatically. Users do not configure MCP themselves.

The original ZIP bundle carries its own executable, so its previous activation and internal MCP behavior are preserved. This fix does not modify other plugins in `~/.opencode/plugins/`; errors about unrelated local plugins exporting an invalid default V2 definition need separate diagnosis.

## OpenCode v2

The bundle exposes a v2 plugin definition alongside the compatibility MCP server.
It registers these native tools before connecting MCP:

- `tokensaver_docs_prepare`
- `tokensaver_docs_setup_model`
- `tokensaver_docs_setup_audio`
- `tokensaver_docs_convert_audio`
- `tokensaver_docs_read`
- `tokensaver_docs_context`
- `tokensaver_docs_search_research`

Use `tokensaver_docs_setup_model` for model inspection/selection or deferral; the
native v2 tool is not named `setup_conversion_model`. The installer selects the
v1 or v2 loader from `opencode --version`; reinstall after changing major version.
The v2 path has been exercised with OpenCode 2.1.3 on macOS arm64.

The v2 tool guard permits only these read-only MCP tools
`tokensaver-docs_list_free_models`, `tokensaver-docs_outline_document`,
`tokensaver-docs_search_documents`, `tokensaver-docs_read_document`, and
`tokensaver-docs_search_research`. Other
MCP conversion and settings methods are not available through the v2 plugin.

## Project research archive

With the updated bundle, run the activation command printed by the installer
from the project directory. OpenCode v1 and v2 register research files saved to
`docs/research/inbox/` during file-write or session events. Use
`docs/tokensaver-docs/index.md` to find the Markdown reports. Run
`knowledge sync .` with the installed executable for a manual sync.


The archive preserves Markdown and plain-text (`.txt`) originals, including any details an agent added while writing a file. Check important claims against the underlying source.

For follow-up questions, use `tokensaver_docs_search_research` with the absolute
project path and focused keywords. It returns bounded excerpts with line numbers
and project-relative Markdown paths. The default response budget is 500 tokens.
Use `version_id` and `conversion_id` together to retrieve evidence from a
specific attached conversion.

## Model and image choices

The conversion model is separate from OpenCode's chat model. Image support is
not inferred from the host. For image analysis, use `analyze` only after the
user explicitly approves sending the image to the selected model. `preserve`
adds image links without image text or descriptions; `placeholder` writes only
`[이미지]` at image positions. No model or service is switched automatically.

The executable's CLI supports `prepare --image-mode analyze|preserve|placeholder`.
The older boolean/CLI transcription flags continue to mean analyze/preserve. Raw
HTML reads containing embedded images wait for explicit choices; use the
preparation tool and read its returned Markdown path. The host renders the
question UI; the plugin supplies structured choices.

## Audio

The v2 native audio path asks the user to choose `tiny`, `base`, or `small`, shows
the exact download size, and waits for a separate download confirmation. Audio
conversion asks for a second, separate local transcription choice. It accepts
one user-named supported audio file and uses only the plugin's configured local
`whisper.cpp` profile; folders, mixed inputs, external audio providers, and the
compatibility MCP audio mutation methods remain blocked. The standalone CLI
continues to support its broader configured audio-provider workflow.
