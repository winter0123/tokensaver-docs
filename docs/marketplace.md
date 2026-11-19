# Tokensaver Marketplace — installation only, no manual MCP configuration

The independent [Tokensaver catalog](https://github.com/winter0123/Tokensaver) points at a small **skills + CLI** plugin package inside this repository. The original engine, caches, standalone release bundles, and native tools remain intact.

## Codex

```sh
codex plugin marketplace add winter0123/Tokensaver
```

Install `tokensaver-docs@tokensaver` in the Codex plugin manager. The catalog targets `marketplace-plugin/`, **not** the root of this repository. The new package contains `.codex-plugin/plugin.json` and a SKILL. No user-managed MCP server or PATH change is needed.

## Claude Code

```sh
claude plugin marketplace add winter0123/Tokensaver
claude plugin install tokensaver-docs@tokensaver
```

Uses the same `marketplace-plugin/` SKILL via its own `.claude-plugin/plugin.json`. It does not contain a `.mcp.json` file.

## OpenCode

OpenCode is not part of the Codex/Claude marketplace protocol. Install the independent OpenCode plugin via the host CLI:

```sh
opencode plugin add 'github:winter0123/tokensaver-docs#main::path:plugins/opencode'
```

The Git package includes its plugin JS, skill and startup runtime resolver. The bundled ZIP release installation path remains supported. The OpenCode plugin may use an **internally registered** local MCP server, but users do not install or configure one manually.

## Runtime behavior

The first actual document operation (or initial OpenCode plugin setup) automatically downloads the **v0.5.6** native release appropriate for macOS arm64/x64 or Windows x64, unless a verified runtime is already cached or bundled. The archive is checked against the GitHub release `checksums.txt` before being unpacked into user-local storage. This step requires GitHub network access and may require consent for download/command execution. The checksum manifest is published on the same origin; it is not a cryptographic release signature. No OS package manager, Python installation, global PATH modifications, manual MCP registration or separate server process setup is required by this marketplace package.

Linux does not have an official native release archive yet; follow the source-install instructions instead. Unsupported platforms must fail clearly rather than claim installation succeeded.

Existing `tokensaver-docs-marketplace` registrations are **not migrated or deleted**. Avoid enabling both legacy and Git-installed copies at once. Existing caches and user documents are not touched.

## Review and validation

Marketplace/plugin configuration is prepared on feature branches. The two PRs must be merged in dependency order before `main` resolves the new packages. Real macOS/Windows Codex, Claude Code, and OpenCode installs and first-run downloads remain to be verified; do not advertise production one-click support before these tests pass.
