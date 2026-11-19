# Tokensaver marketplace integration

The [Tokensaver marketplace](https://github.com/winter0123/Tokensaver) is a lightweight catalog; **the Git-sourced plugin contains the skill and MCP metadata, but not the operating-system-specific native executable**.

## Requirements

1. Install the TokenSaver Docs native runtime using the release installer described in [distribution.md](distribution.md). Alternatively, build/install the Python package in a suitable environment.
2. Make the `tokensaver-docs` command available on `PATH` for the Codex/Claude Code process, and verify `tokensaver-docs --help` succeeds. The current release bundle installer stores its runtime in per-user versioned storage and **does not guarantee a global PATH command**, so merely running that installer is not sufficient for this Git-sourced MCP configuration.
3. Register the shared marketplace: `codex plugin marketplace add winter0123/Tokensaver` or `claude plugin marketplace add winter0123/Tokensaver`.
4. Install `tokensaver-docs@tokensaver` using the host plugin manager. Confirm MCP tools respond before relying on the plugin.

The standalone native release bundles remain the supported self-contained alternative. Their local plugin registration currently uses `tokensaver-docs-marketplace` until a separate validated migration is implemented. Do **not** remove that marketplace or delete its data automatically. If both sources are installed, disable one copy to avoid duplicate MCP registrations.

The root `plugin.json`/`mcp.json` and `.claude-plugin/plugin.json`/`.mcp.json` support the Git-backed catalog. They do not replace the OS-specific release artifacts. Windows and macOS live-host installation has not been verified for this new path; GitHub catalog registration and plugin launch should be tested on each host.
