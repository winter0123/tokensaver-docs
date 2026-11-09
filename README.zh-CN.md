<p align="center"><img src="assets/readme/hero-zh-CN.svg" width="960" alt="TokenSaver Docs — 将 PDF、Word、Excel、HTML、图片和音频转换为可重复使用的 Markdown，供 Codex、Claude Code 和 OpenCode 使用。" /></p>

<p align="center">Created by <a href="https://github.com/winter0123">winter0123</a> · <a href="https://github.com/winter0123/tokensaver-docs">Original repository</a> · <a href="AUTHORS.md">Authors</a> · <a href="LICENSE">MIT License</a></p>

<p align="center">
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-win32-x64.zip?download=1"><img src="assets/readme/download-windows.svg" width="260" alt="Download Windows x64 ZIP" /></a>
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-darwin-arm64.zip?download=1"><img src="assets/readme/download-macos.svg" width="260" alt="Download macOS Apple Silicon ZIP" /></a>
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-darwin-x64.zip?download=1"><img src="assets/readme/download-macos-intel.svg" width="260" alt="macOS Intel download" /></a>
</p>
<p align="center"><a href="#source-install">Linux · Source install</a> · <a href="https://github.com/winter0123/tokensaver-docs/releases">All releases</a></p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a></p>

**将 PDF、Word、Excel、HTML、图片和音频转换为可重复使用的 Markdown，供 Codex、Claude Code 和 OpenCode 使用。**

点击操作系统按钮即可下载，然后在安装程序中选择助手。

<a id="download"></a>

## 下载与安装 — v0.4.0

点击上方按钮会直接下载 ZIP。完整解压后运行安装程序，再选择 **1 Claude Code / 2 Codex / 3 OpenCode**。无需单独安装 Python。

macOS：双击 `install.command`，或在解压目录中运行 `sh install.command`。

Windows：在解压目录中打开 PowerShell，运行 `.\install.ps1`。如设备策略阻止执行，请遵循该策略；安装程序不会修改执行策略。

需要先安装所选助手的 CLI。安装后重启助手并发送 **“把这个 HTML 文件转成 Markdown：/文件路径/policy.html”**。更换模型时发送 **“更改 tokensaver-docs 的图片转换模型”**。

macOS arm64 统一安装已在本地验证。Windows／Intel Mac 二进制包已通过自动测试；新的 Windows 统一安装脚本及真实 Windows／Intel 助手安装仍属实验性支持。文件尚未签名或公证。Linux 目前仅提供源码安装。

<details>
<summary>高级：按助手下载单独 ZIP</summary>

| 操作系统 | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| macOS Apple Silicon | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-darwin-arm64.zip) |
| macOS Intel | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-darwin-x64.zip) |
| Windows x64 | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-win32-x64.zip) |

</details>

## 直接用自然语言提出请求

安装插件并重启助手后，像平时一样提出请求。无需每次输入插件名称或终端命令。

> 把这个 HTML 文件转成 Markdown：/文件路径/policy.html

> 把这个文件夹中的文档转成 Markdown：/文件夹路径

> 提取图片中的文字并添加图片说明，保存为 Markdown：/文件路径/photo.png

> 我想更换转换模型，请告诉我可选的方式。

助手会根据请求，从已安装的技能和工具中选择 TokenSaver Docs。如需首次模型设置或图片处理选择，请回答提示，并确认实际保存路径及部分完成、待检查等状态。

如果助手采用其他方式，可以补充“请用 tokensaver-docs 处理这项任务”。是否自动选择取决于助手，安装本身不能保证每次都会调用。

<a id="source-install"></a>

## 安装源码 CLI

需要 Python 3.11+ 和 Git。此安装不会自动注册助手插件。

<details>
<summary><strong>macOS / Linux</strong></summary>

```sh
python3 -m venv "$HOME/.tokensaver-docs/venv"
source "$HOME/.tokensaver-docs/venv/bin/activate"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

```powershell
py -3 -m venv "$HOME\.tokensaver-docs\venv"
& "$HOME\.tokensaver-docs\venv\Scripts\Activate.ps1"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

</details>

打开新终端后，请再次运行对应的第二行。若 PowerShell 阻止激活，可在后续命令中以 `& "$HOME\.tokensaver-docs\venv\Scripts\tokensaver-docs.exe"` 代替 `tokensaver-docs`，无需更改执行策略。

## 选择或更换图片模型

**以下命令供源码 CLI 用户使用；插件用户可直接向助手请求更换模型。** 在已激活安装环境的终端中选择一种方式，模型将保存为默认值。首次设置和更换使用同一命令。

**① Claude Code** — 先安装 CLI 并登录，运行后输入账号可用的准确模型名称。

```sh
tokensaver-docs configure --kind image --provider claude
```

**② Codex** — 先安装 CLI 并登录，运行后输入账号可用的准确模型名称。

```sh
tokensaver-docs configure --kind image --provider codex
```

**③ OpenCode + OpenRouter** — 设置 `OPENROUTER_API_KEY` 环境变量，运行后从免费图片输入模型候选列表中选择编号。实际可用性取决于账号与服务。不要在助手对话中发送 API 密钥。

```sh
tokensaver-docs configure --kind image --provider openrouter
```

OpenCode 是助手，OpenRouter 是模型服务；其他助手也能选择 OpenRouter 处理转换。此设置只影响图片转换模型，不会改变助手的聊天模型或音频模型。Claude Code/Codex 遵循各自 CLI 的登录、用量与计费条件。普通文档文字提取不需要模型或密钥。

查看当前模型：`tokensaver-docs setup-model`

## 转换文件或文件夹

将 `./documents` 替换为输入路径。例：`policy.html` → `converted/policy.html.md`。

**提取文字，并在图片位置保留 `[이미지]` 标记：**

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode placeholder
```

**加入图片、图片文字和说明：** 先设置模型与登录或 API 密钥。图片会发送到所选服务。

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode analyze
```

无法自动确认 Claude Code/Codex 的图片支持能力。只有自行确认支持图片后，才在命令末尾加上 `--allow-unverified-model`；已知不支持的模型仍会被阻止。音频需要单独设置，参见[英文详细指南](docs/advanced-usage.md)。

原文件及已有 Markdown 的人工修改会保留；相同文档和已完成的图片分析会从缓存复用。部分运行时提示和图片占位符仍使用韩语。

## 支持的文件

| 类型 | 扩展名 | 转换内容 |
| --- | --- | --- |
| PDF | `.pdf` | 文字；选定扫描页的图片分析 |
| Word | `.docx` | 文字、表格、内嵌图片 |
| Excel | `.xlsx` | 工作表、单元格、内嵌图片 |
| HTML | `.html`, `.htm` | 正文、表格、内嵌图片 |
| 图片 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif` | 保留原图，可选提取文字与图片说明 |
| 音频／视频音轨 | `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.mp4` | 语音转文字；不分析视频画面 |

不支持旧版 `.doc`、`.xls`。图片和音频质量因模型而异。Token 节省效果取决于文档与读取范围，详见[基准测试及限制](benchmarks/README.md)。

[详细使用说明（英文）](docs/advanced-usage.md) · [安装与发布（英文）](docs/distribution.md) · [验证状态（英文）](docs/current-status.md) · [反馈问题](https://github.com/winter0123/tokensaver-docs/issues) · [MIT 许可证](LICENSE)
