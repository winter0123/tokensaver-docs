# Plugin installation and distribution

No service or remote MCP server is needed. The tools run on the user's computer.
The planned distribution uses GitHub for source and versioned release archives.
PyPI, npm and official plugin directories are separate distribution channels.

Source repository: [winter0123/tokensaver-docs](https://github.com/winter0123/tokensaver-docs). **No public binary release has been published yet.** The commands below
are templates for a trusted repository after its release has been published.
Replace `winter0123/tokensaver-docs` with its real GitHub name. Do not execute placeholders.

## Availability and discovery

The current bundles are local previews. Installing one does not submit it to a
public plugin directory, and file-to-md is not currently listed for public
name-based discovery.

| Agent | Current preview installation | Public discovery status |
| --- | --- | --- |
| Codex | The installer registers the bundled local marketplace with the Codex CLI. | Public directory submission and review are separate. OpenAI's [desktop-only submission guidance](https://developers.openai.com/plugins/deploy/desktop-only) says local MCP submissions require an approved partner and allowlisting; its desktop-only listings are installed from the ChatGPT desktop app. Eligibility for this project has not been established. |
| Claude Code | The installer registers the bundled local marketplace with the Claude CLI. | The [plugin browser](https://code.claude.com/docs/en/discover-plugins) searches configured marketplaces; registering a local marketplace does not list this project in Anthropic's marketplace. |
| OpenCode | The installer adds a managed local loader for the detected OpenCode major version. | No npm package or public listing has been published. OpenCode documents [local and npm plugins](https://opencode.ai/docs/plugins/) and [v2 plugins](https://opencode.ai/v2/docs/plugins). Version 2.1.3 has been exercised locally on macOS arm64. |

Actual Codex and Claude Code conversations using this preview have not been
verified. OpenCode v1 was checked with a synthetic HTML example and v2.1.3 with
local HTML documents; this does not establish compatibility with all workflows.
See [the current status](current-status.md) for the recorded checks.

## Release installer templates

The package build targets are macOS Apple Silicon, macOS Intel and Windows x64.
Only macOS Apple Silicon has been exercised locally so far; Windows and Intel
Mac installations have not been verified. Linux has source tests only and no
release installer in this preview.

### macOS

```sh
repo='winter0123/tokensaver-docs'
version='v0.3.4'
curl -fL --proto '=https' "https://github.com/$repo/releases/download/$version/install.sh" -o file-to-md-install.sh
sh file-to-md-install.sh --repo "$repo" --version "$version" --agent claude
```

Use `--agent codex` or `--agent opencode` for the other agents.

### Windows PowerShell

```powershell
$Repo = 'winter0123/tokensaver-docs'
$Version = 'v0.3.4'
Invoke-WebRequest "https://github.com/$Repo/releases/download/$Version/install.ps1" -OutFile file-to-md-install.ps1
& .\file-to-md-install.ps1 -Repo $Repo -Version $Version -Agent claude
```

Use `-Agent codex` or `-Agent opencode`. If local execution policy blocks the
script, review it and your machine's policy; do not change system-wide policy
just to install the plugin. These preview binaries are not signed/notarized;
OS trust checks may require additional review.

The scripts choose the correct archive, check its SHA-256 hash, and pass the
requested version to the native installer. The installer checks individual files,
the agent/OS/CPU and executable version before registration. Checksums detect
corruption; they do not replace trust in the repository or sign its releases.

No separate Python, Poppler, npm or Bun installation is needed by these bundles.
Your chosen coding agent must already be installed. Claude Code and Codex must
provide their plugin CLI commands. OpenCode uses a managed local loader in its
configuration directory. No new account or API key is required for text document
extraction or cached evidence retrieval.

## After installing

Restart the agent. Ask it to use file-to-md on a **local file or folder path**,
for example: "Use file-to-md to find the refund deadline and exceptions in
./documents. Reuse existing conversions."

Text PDF, Word, Excel and HTML are extracted locally. Scanned PDF pages are rendered
using bundled PDFium. First use offers model selection or deferral; document text
does not require an AI model. The plugin conversion model is separate from the host
chat model, and unknown host settings are not guessed. Use `setup_conversion_model`
(OpenCode v1: `file_to_md_setup_model`) or CLI `setup-model` to inspect a selection.
Use `setup-model --defer` to choose later. A request-only model selection leaves the
default unchanged; `--save-as-default --confirmed` saves it after explicit consent.

For images, the tool distinguishes image support from price and lookup errors.
If the selected model cannot read images, it asks whether to change models or
continue with `[이미지]` at each known image position. Continuing adds no image
link, image text or description. With a supported model, choose images with visible
text and a description or images only. CLI modes are `--image-mode analyze`,
`--image-mode preserve` and `--image-mode placeholder`. Legacy transcription flags
retain their analyze/preserve meanings.

`prepare --model-provider PROVIDER --model MODEL_ID` applies a model for that
request only. `--allow-unverified-model` is only for a manually confirmed model
whose image capability is unknown; it does not bypass known incompatibility,
lookup errors or free-price checks. Image analysis may send images to the selected
provider; image preservation and placeholders stay local. No local OCR fallback
or automatic provider/model switch is performed. Preparation tools return the
questions to the agent; the host controls how those questions appear to the user.
Local audio includes Whisper's executable, but the user must select and download
a tiny/base/small multilingual model first. Its size is displayed before download.

Same-content files reuse the local user's cache across agents and sessions.
Changing agents, moving a file, changing output folders or reinstalling does not
require another successful image analysis when the image and analysis policy match.
Image modes are kept separate, and explicit model selection in the new preparation
path uses a model-specific cache identity. Prior text-only image results are not
complete descriptions. Explicit refresh creates
a new result and preserves existing outputs. Important image text and descriptions
still need accuracy checks.

## Update and removal

To update, download the installer from the **new version's release** and run the
same installation command with that version. Updates retain configuration,
document conversions and previous runtimes. Restart the agent after updating.
This is a user-initiated update, not an automatic background updater.

Remove Claude Code/Codex plugins with the host's plugin manager. For OpenCode,
remove only the managed `file-to-md.js` loader in its `plugins` configuration
folder (normally `~/.config/opencode/plugins`); do not remove the entire folder.
Document caches and model files remain until explicitly removed by their owner.

If installation fails, report OS/CPU, agent version, release tag, and the error
message through GitHub Issues. Never attach API keys or private documents. A
bundle may also be unpacked manually and installed with its `bin/file-to-md`
(`bin/file-to-md.exe` on Windows) `install-plugin` command.

## Maintainer release steps

1. Review the source to publish. Exclude `qa`, `.env`, cached documents, personal
   interview data and internal work logs. Package exclusions do not remove files
   from Git history; inspect the actual files selected for Git publication.
2. Keep Python, OpenCode package and CLI versions consistent. Choose a version
   tag matching `v` plus `file_to_md.__version__`; do not reuse a published tag.
3. After source/tag publication is authorized, run **Prepare draft release** in
   GitHub Actions with that existing tag. The workflow builds Windows x64 and both
   Mac CPU targets, runs tests against each executable, and collects nine plugin
   archives. It refuses missing/duplicate archives, wrong versions and damaged
   archive contents. The combined checksum list covers all nine archives.
4. The workflow creates a **draft prerelease** only. Review its files, CI results,
   third-party notices, unsigned-binary experience and actual agent installation
   on each target before manually publishing it.
5. Test the published release URL on a clean machine. Add the real installation
   commands to README only after the release is accessible. Then pursue official
   directory submissions separately; a Release is not an official listing.

Ordinary pushes run the source test workflow. Heavy native builds are manual or
called by the draft-release workflow. No workflow publishes to PyPI/npm. Running
remote CI can consume the repository's Actions allowance; review account limits
before triggering it. This checkout has not run those remote workflows.

To build one platform manually, follow [plugin build instructions](plugin-preview.md).
To validate archives downloaded from all three build jobs locally:

```sh
python scripts/prepare_release.py --artifacts downloaded-artifacts --output dist/complete-release --tag v0.3.4
```

Build on each actual target OS/CPU; renaming a Mac binary never makes a Windows
binary. Linux source tests remain in CI, but there is no Linux release installer
or official package support in this first release scope.
