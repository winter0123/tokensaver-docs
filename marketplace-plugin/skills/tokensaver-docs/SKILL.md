---
name: tokensaver-docs
description: Prepare local documents, images and audio as reusable Markdown; answer focused questions with bounded context.
---

# TokenSaver Docs — marketplace package

This Git-sourced package is a **SKILL + CLI** plugin for Codex and Claude Code. Do not ask the user to install or configure an MCP server. The existing TokenSaver Docs conversion engine and caches are unchanged.

Locate this installed `SKILL.md` and resolve the plugin root as its grandparent directory (`skills/tokensaver-docs/SKILL.md` → plugin root). Do not assume the current working directory.

- macOS: `sh "<plugin-root>/scripts/run.sh" COMMAND [ARGS...]`
- Windows: `powershell.exe -NoProfile -File "<plugin-root>\scripts\run.ps1" COMMAND [ARGS...]`

The first invocation downloads the pinned `v0.5.6` native archive from the official TokenSaver Docs GitHub Release, verifies its SHA-256 against the published checksums, and stores the binary in per-user cache. **Inform the user before first download and obtain approval when necessary.** No manual MCP registration or runtime PATH setup is needed. A new version requires updating the pinned release in the launchers. Supported binaries: macOS arm64/x64 and Windows x64. Linux is not covered by binary bootstrap. Network access, execution policy and download size can affect first use.

## First-run conversion preferences

Before the first image-bearing conversion, inspect the common native preference store with `preferences`. If the status is `setup_required`, show the image modes exactly once. Save the user's choice with `preferences --set-mode preserve` or `preferences --set-mode placeholder`; future `prepare INPUT` calls automatically reuse it without asking again, across projects and agent hosts. Only change saved preferences on the user's explicit request. Both modes run locally without a model.

For image analysis, first let the user select Codex, Claude Code, OpenRouter API or a local Ollama/LM Studio/OpenAI-compatible service and then an exact supported model. For a local model run `list-image-models --provider ollama`, followed by `preferences --set-mode analyze --runtime local --provider ollama --model MODEL --network-policy local_only`. With user-approved private IP endpoints use `internal_only`. With external APIs, name the provider/model and ask for explicit **persistent future image transmission** approval before storing `--allow-external-images --network-policy external_allowed`. Never transfer images to an unapproved external service, ask for API keys in chat, or silently change models. OpenCode's chat-model invocation is not yet wired into the native image engine: do not claim it works.

## Conversion

When asked to convert a supported local file/folder, run `prepare INPUT`. Only specify `--output DIR` if the output folder was given. Interpret the returned JSON status and questions; never assume model selection or consent. For images, ask whether to analyze (image + text/description; may send to a provider), preserve (images only), or use placeholder (text-only placeholder). Run `prepare INPUT --image-mode analyze|preserve|placeholder` with model flags only after the user chooses. Do not read raw binaries into context, invent image descriptions, choose providers automatically or overwrite originals.

For document questions use `context INPUT "focused query" --max-tokens 1200` first, reusing the cached Markdown. Cite returned path and line ranges. Limit evidence rather than dumping entire documents.

For archived research use `knowledge search PROJECT "query" --max-tokens 500`. Activating project capture with `knowledge enable PROJECT` requires explicit user approval: do not add hooks silently.

If the command fails, report the precise cause; do not fall back to unverified downloading or executing code. Installing this marketplace package does not modify legacy `tokensaver-docs-marketplace` entries. Avoid enabling both legacy and new plugin copies at once.
