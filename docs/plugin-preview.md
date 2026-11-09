# Self-contained plugin preview (0.3.3)

This checkout can build local plugin bundles. GitHub, npm/PyPI and official directory
publication have not occurred. Do not paste a fictitious owner/repository into an
installation command and expect a published release to exist.

The chosen distribution is GitHub source plus GitHub Releases, with no hosted
server or required PyPI/npm publication. See [release installation and updates](distribution.md).

## Build (maintainers only)

```sh
python -m pip install '.[mcp,tokens]' 'pyinstaller>=6,<7' 'cmake>=3.26,<5'
bun install --cwd plugins/opencode --frozen-lockfile
python scripts/build_whisper.py --output dist/whisper
python scripts/build_standalone.py --output dist/standalone --whisper dist/whisper
python scripts/package_plugins.py --binary dist/standalone/tokensaver-docs --output dist/plugins --bundle-opencode
python scripts/archive_plugins.py --plugins dist/plugins --output dist/release
```

On Windows use `tokensaver-docs.exe`. Build on the actual target OS/CPU; do not label a
Mac executable as a Windows release. Build commands refuse to overwrite output.
The audio CPU runtime is built from pinned whisper.cpp sources and has a bundled
upstream license. Review third-party redistribution requirements before publishing.
PDFium and its upstream/dependency license texts are included in the executable
and its `third-party` companion directory. Keep this directory with the binary
when running `package_plugins.py`; no separate Poppler installation is needed.

## Install a built bundle (end users)

The executable includes Python, document libraries and the optional compiled audio
runtime. The bundled OpenCode JavaScript contains its SDK dependencies. End users
need their coding agent, but do not need separate Python/npm/Bun installations.

```sh
./bin/tokensaver-docs install-plugin /path/to/unpacked/bundle --agent claude
# Alternatively: --agent codex or --agent opencode
```

Windows uses `.\bin\tokensaver-docs.exe`. The installer verifies all listed files,
checks OS/CPU/agent compatibility, copies a versioned runtime into user storage and
registers only this plugin. No sudo or administrator installation is required.
Claude/Codex registration uses their own CLI. OpenCode gets a small managed plugin
loader; arbitrary existing user plugins are not overwritten. Install failures
leave the old runtime available. Update by installing another verified bundle.
Remove the plugin through the host's plugin controls; do not delete shared document
caches unless you explicitly want to lose conversion reuse.

After a repository release exists, `scripts/install.sh` and `scripts/install.ps1`
can fetch a versioned platform archive and verify the release checksum list.
They require an actual trusted repository and version. They have not been tested
against a published release here. PowerShell has not been run on Windows locally.

## Shared conversions

CLI, MCP and OpenCode use the same per-user cache. `TOKENSAVER_DOCS_CACHE_DIR` can
select another location outside the input folder. Source content, format and
requested coverage identify completed results. Renaming or moving a source does
not cause another transcription. Media units are independently content-addressed,
so completed units survive source changes and partial failure in another output
folder. Models are not automatically changed or retried against paid alternatives.

`convert --refresh` explicitly creates new results while keeping existing output.
Verified legacy results can be imported. Unverifiable legacy mappings are preserved
and reported instead of automatically retranscribed. Damaged cache files are not
silently trusted. A process crash after a remote request but before its response
is saved can still require a repeated request: exactly-once external calls cannot
be guaranteed in that situation.

## Audio and context

`setup-audio --model small` displays model size without downloading. After the user
chooses, `--download` resumes/downloads the pinned model and verifies its checksum.
Tiny/base/small are multilingual. Existing verified model files can be reused.
Local transcription sends no audio outside the computer, but recognition accuracy
still needs human checks for important names and numbers.

`context INPUT QUERY --output converted --max-tokens 1200` prepares missing local
content and returns original evidence with source lines. A token limit covers
serialized result JSON with cl100k_base, excluding host protocol/tool schemas.
Incomplete/truncated results are explicit. Search is lexical; distant exceptions
or synonyms can still require follow-up reading.

macOS arm64 has local checks. Other OS/CPU build jobs are configured but remote CI
and actual Windows/Intel Mac installation are not verified in this checkout.
Heavy native builds run manually or as part of the manual draft-release workflow.
The draft workflow requires all nine Windows/macOS agent archives and never
automatically publishes a public release. Linux has source tests only.
