<p align="center"><img src="assets/readme/hero-zh-CN.svg" width="960" alt="TokenSaver Docs — 将 PDF、Word、Excel、HTML、图片和音频转换为可重复使用的 Markdown，供 Codex、Claude Code 和 OpenCode 使用。" /></p>

<p align="center">
<a href="#download"><img src="assets/readme/download-windows.svg" width="260" alt="Windows x64 download options" /></a>
<a href="#download"><img src="assets/readme/download-macos.svg" width="260" alt="macOS Apple Silicon and Intel download options" /></a>
<a href="#source-install"><img src="assets/readme/download-linux.svg" width="260" alt="Linux source installation" /></a>
</p>
<p align="center"><a href="#download">macOS Intel</a> · <a href="https://github.com/winter0123/tokensaver-docs/releases">All releases</a></p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a></p>

**将 PDF、Word、Excel、HTML、图片和音频转换为可重复使用的 Markdown，供 Codex、Claude Code 和 OpenCode 使用。**

点击操作系统按钮，再选择对应 AI 助手的 ZIP。Linux 目前提供源码安装。

<a id="download"></a>

## 下载插件 — v0.4.0 预览版

**选择与操作系统、CPU 和 AI 助手匹配的 ZIP。无需单独安装 Python。**

| 操作系统 | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| macOS Apple Silicon | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-darwin-arm64.zip) |
| macOS Intel | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-darwin-x64.zip) |
| Windows x64 | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-win32-x64.zip) |

解压后，在**解压目录中打开终端**，运行安装命令：

```sh
./bin/tokensaver-docs install-plugin . --agent claude
```

Codex 使用 `--agent codex`，OpenCode 使用 `--agent opencode`。Windows PowerShell 中，将可执行文件改为 `.\bin\tokensaver-docs.exe`。需要先安装对应助手的 CLI；安装后重启助手。

向助手发送：**“用 tokensaver-docs 将这个文件转换为 Markdown：/文件路径”**。插件会引导你选择模型。更换模型时发送：**“更改 tokensaver-docs 的图片转换模型”**。

macOS arm64 已在本地验证安装。Intel Mac 和 Windows 已通过自动打包测试，实际助手安装仍属实验性支持。二进制文件尚未签名或公证。Linux 使用下方源码安装。GitHub 发布与官方插件市场收录是不同流程。

[发布说明、校验和与安装脚本](https://github.com/winter0123/tokensaver-docs/releases/tag/v0.4.0)

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
