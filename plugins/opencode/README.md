# TokenSaver Docs for OpenCode

This package adds local document conversion and bounded search tools to OpenCode.
The platform-specific release includes the tokensaver-docs executable. External image
and audio transcription require explicit setup and are not enabled by these tools.
# OpenCode v2

The bundle also exposes a v2 plugin definition. It registers the bundled local
MCP server and its document tools. The installer selects the v1 or v2 loader
from the installed `opencode --version`; reinstall after changing major version.
The v2 path has been exercised with OpenCode 2.1.3 on macOS arm64.


## Model and image choices

Start with `tokensaver_docs_prepare` (v2: native `tokensaver_docs_prepare`). First use can ask
for a conversion model or let the user defer setup. `tokensaver_docs_setup_model`
(v2: `setup_conversion_model`; CLI: `setup-model`) inspects/selects a model.
One-time `model_provider`/`model` parameters do not change defaults; saving a
default needs the user's explicit choice and confirmation. The conversion model
is separate from the chat model; image support is not inferred from the host.

If a selected model cannot read images, ask whether to switch to an image model
or continue with normal text and literal `[이미지]` at image positions. The latter
contains no image text, description or Markdown image link. An unknown capability
is reported as unknown, not unsupported. Image analysis and audio consent remain
separate. No model or service is switched automatically.

`prepare --image-mode analyze` includes image links, visible text and descriptions;
`preserve` includes image links only; `placeholder` writes `[이미지]` only. The old
boolean/CLI transcription flags continue to mean analyze/preserve. Raw embedded
HTML reads wait for explicit choices rather than silently choosing image
preservation. Use the preparation tool and read its returned Markdown path.
The host renders the question UI; the plugin supplies structured choices.

The v2 entry point now registers native first-use tools (`tokensaver_docs_prepare`, `tokensaver_docs_setup_model`, `tokensaver_docs_read`) before contributing the compatibility MCP server. This avoids requiring an MCP tool discovery round-trip for preparation. Other MCP tools remain available after connection.
