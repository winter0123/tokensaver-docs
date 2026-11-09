# Changelog

## 0.4.1

- Fix GitHub Actions checkout shallow clone so release tag resolves in CI builds
- Add winter0123 as copyright holder in LICENSE, AUTHORS.md, and NOTICE
- Add SPDX license header and author attribution to Python sources and OpenCode plugin
- Bundle LICENSE, NOTICE, AUTHORS.md in plugin and release artifacts

## 0.4.0

- Rename package, CLI, MCP server, skills, plugin IDs, tool names, environment variables, cache paths, and release assets to TokenSaver Docs. Install using `tokensaver-docs`; Python imports use `tokensaver_docs`.
- This is a breaking rename: existing installations must reinstall. Existing Markdown is preserved; choose a fresh output folder for conversions created by earlier versions.
- Disconnect child CLI stdin from the MCP protocol pipe.

- Public project branding: TokenSaver Docs; legacy command and plugin IDs remain compatible.
- Require Pillow 13 or newer after the pre-publication dependency audit.

## 0.3.4 — local preview

- Handle both OpenCode v1 `filePath` and v2 `path` read arguments; verified first-use and placeholder choices in an actual v2 host.

- Offer first-use conversion model selection or deferral, with request-only selection and explicitly confirmed default saving.
- Distinguish image support, free pricing and lookup failures; ask users to change unsupported models or continue with `[이미지]` placeholders.
- Separate image analysis, image preservation and placeholders in conversion/cache state while retaining legacy flag meanings.
- Expose the choice flow through CLI, MCP and OpenCode tools; automatic HTML reads no longer choose image preservation silently.

## 0.3.3 — local preview

- Let users choose image-only preservation or image text extraction plus a visual description, with reusable analysis for standalone and embedded images.
- Keep image and audio provider choices separate during image preparation, preserve edited Markdown, and report incomplete image analysis.
- Support OpenCode v1 and v2 plugin loading and document the limits of local preview testing.

## 0.3.2 — local preview

- Return matching passages and nearby context from long sections within the requested budget.
- Invalidate obsolete extraction results while reusing available media transcripts, and continue after an oversized input.
- Warn when HTML may contain CSS background images, and report damaged embedded images.
- Prepare embedded-image HTML in the user cache in OpenCode, including read-only source folders.
- Add a reproducible synthetic HTML token comparison and clarify distribution status.

## 0.3.1 — local preview

- Deterministic HTML extraction with preserved photos, original order and Markdown tables.
- English asset names, local resource checks, image-change detection and explicit optional transcription.
- One-call offline preparation tools and concise tool-first skills for small/free models.
- OpenCode v1 native-read redirection for embedded-image HTML; no model-generated conversion scripts.
- HTML structure and image transcription reuse without overwriting edited outputs or photos.

## 0.3.0 — local preview, not yet published

- Shared complete conversions and media units across output folders and agents.
- Cross-output partial resume, unit reuse after source changes, explicit refresh,
  integrity checks and process-level deduplication.
- One-call document context with bounded JSON evidence and continuation metadata.
- Checksum-verified local plugin installation and self-contained OpenCode JS.
- Bundled CPU whisper-cli builds and explicit multilingual model setup.
- macOS and Windows release installer scripts and build/archive workflows.
- Preserved source files, edited outputs and verifiable legacy conversion results.
- Bundled PDFium rendering and upstream/dependency notices; no external Poppler required.
- Version-matched release installation, registration rollback and a manual draft-release workflow.
- Combined multi-platform archive verification and documented GitHub Releases installation/updates.

## 0.2.0

- CLI, optional MCP, skills, extraction/transcription, bounded read/search,
  standalone packaging and initial synthetic comparison.
