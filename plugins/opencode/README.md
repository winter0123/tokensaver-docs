# TokenSaver Docs for OpenCode

This package adds local document preparation and bounded search to OpenCode.
The platform-specific release includes the `tokensaver-docs` executable. The
OpenCode v2 tools can analyze images with an explicitly selected model after the
user approves image analysis; no image is sent for analysis without that choice.

## OpenCode v2

The bundle exposes a v2 plugin definition alongside the compatibility MCP server.
It registers these native tools before connecting MCP:

- `tokensaver_docs_prepare`
- `tokensaver_docs_setup_model`
- `tokensaver_docs_setup_audio`
- `tokensaver_docs_convert_audio`
- `tokensaver_docs_read`

Use `tokensaver_docs_setup_model` for model inspection/selection or deferral; the
native v2 tool is not named `setup_conversion_model`. The installer selects the
v1 or v2 loader from `opencode --version`; reinstall after changing major version.
The v2 path has been exercised with OpenCode 2.1.3 on macOS arm64.

The v2 tool guard permits only these read-only MCP tools
`tokensaver-docs_list_free_models`, `tokensaver-docs_outline_document`,
`tokensaver-docs_search_documents`, and `tokensaver-docs_read_document`. Other
MCP conversion and settings methods are not available through the v2 plugin.

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
