# TokenSaver Docs

**Turn PDF, Word, Excel, HTML, images, and audio into Markdown. Help AI agents waste fewer tokens reading documents.**

Convert once, reuse the Markdown, and retrieve only the passages you need. Plugins for Codex, Claude Code, and OpenCode are in development. Optionally include visible image text and descriptions using your chosen model.

[한국어](README.ko.md) · [Install](#install) · [Choose a model](#choose-or-change-a-model) · [Usage](#usage) · [Supported files](#supported-files)

> **Source CLI preview available.** The commands below do not automatically register an agent plugin. Downloadable plugin releases and official marketplace listings are still in preparation.

## Install

**Choose your operating system.** Requires Python 3.11+ and Git.

<details open>
<summary><strong>macOS / Linux — paste into your terminal</strong></summary>

```sh
python3 -m venv "$HOME/.tokensaver-docs/venv"
source "$HOME/.tokensaver-docs/venv/bin/activate"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

In a new terminal, run the second line again.

</details>

<details>
<summary><strong>Windows — paste into PowerShell</strong></summary>

```powershell
py -3 -m venv "$HOME\.tokensaver-docs\venv"
& "$HOME\.tokensaver-docs\venv\Scripts\Activate.ps1"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

In a new terminal, run the second line again. If activation is blocked, use `& "$HOME\.tokensaver-docs\venv\Scripts\tokensaver-docs.exe"` instead of `tokensaver-docs` below, without changing execution policy.

</details>

## Choose or change a model

**Choose one service if you want visible image text and descriptions.** Run commands in a terminal with the installed environment activated. Use the same command for initial setup and later changes; your model becomes the saved default.

<details>
<summary><strong>① Claude Code — use your signed-in CLI</strong></summary>

Install and sign in to the Claude Code CLI first. Run this, then **enter the exact model name available to your account**.

```sh
tokensaver-docs configure --kind image --provider claude
```

</details>

<details>
<summary><strong>② Codex — use your signed-in CLI</strong></summary>

Install and sign in to the Codex CLI first. Run this, then **enter the exact model name available to your account**.

```sh
tokensaver-docs configure --kind image --provider codex
```

</details>

<details>
<summary><strong>③ OpenCode + OpenRouter — choose from free model candidates</strong></summary>

Set the `OPENROUTER_API_KEY` environment variable first. Run this, then **choose a number from the free image-input model candidate list**. Actual availability depends on your account and the service. Do not share keys in agent chat.

```sh
tokensaver-docs configure --kind image --provider openrouter
```

OpenCode is the agent; OpenRouter is the model service. This does not change OpenCode's chat model. Claude Code and Codex users can also select OpenRouter as the conversion provider.

</details>

Plain document text needs no model or API key. These settings change the **image conversion model**, independently of your agent's chat model and audio model. Claude Code/Codex use their CLI authentication, usage limits, and billing conditions.

Check your model: `tokensaver-docs setup-model`

## Usage

Replace `./documents` with a file or folder. Results go into `./converted`. **Example: `policy.html` → `converted/policy.html.md`.**

**Extract text and mark image positions with `[이미지]`**

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode placeholder
```

**Include images, visible image text, and descriptions** — configure your model first. Images are sent to the selected provider.

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode analyze
```

Claude Code/Codex image support cannot be verified automatically. Add `--allow-unverified-model` only after checking image support yourself; known incompatible models remain blocked. Audio requires separate setup in the [advanced guide](docs/advanced-usage.md).

Existing Markdown and user edits are preserved. Identical documents and completed image analysis are reused from cache.

## Supported files

| File | Extensions | Markdown content |
| --- | --- | --- |
| PDF | `.pdf` | Text; image analysis of selected scanned pages |
| Word | `.docx` | Text, tables, embedded images |
| Excel | `.xlsx` | Sheets, cells, embedded images |
| HTML | `.html`, `.htm` | Body content, tables, embedded images |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif` | Preserved images, optional text and descriptions |
| Audio and video audio tracks | `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.mp4` | Speech converted to text; video frames are not analyzed |

Legacy `.doc`/`.xls` files are unsupported. Image/audio quality depends on the model. Token savings depend on the document and retrieved scope; see [benchmarks and limitations](benchmarks/README.md).

## More

[Agent connections, search, audio, development](docs/advanced-usage.md) · [Plugin installation and distribution](docs/distribution.md) · [Verification status](docs/current-status.md) · [Report an issue](https://github.com/winter0123/tokensaver-docs/issues) · [MIT license](LICENSE)
