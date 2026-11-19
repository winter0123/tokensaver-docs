<p align="center"><img src="assets/readme/hero-ja.svg" width="960" alt="TokenSaver Docs — PDF・Word・Excel・HTML・画像・音声を Markdown に変換し、Codex・Claude Code・OpenCode で再利用できます。" /></p>

<p align="center">Created by <a href="https://github.com/winter0123">winter0123</a> · <a href="https://github.com/winter0123/tokensaver-docs">Original repository</a> · <a href="AUTHORS.md">Authors</a> · <a href="LICENSE">MIT License</a></p>

<p align="center">
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-win32-x64.zip?download=1"><img src="assets/readme/download-windows.svg" width="260" alt="Download Windows x64 ZIP" /></a>
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-darwin-arm64.zip?download=1"><img src="assets/readme/download-macos.svg" width="260" alt="Download macOS Apple Silicon ZIP" /></a>
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-darwin-x64.zip?download=1"><img src="assets/readme/download-macos-intel.svg" width="260" alt="macOS Intel download" /></a>
</p>
<p align="center"><a href="https://github.com/winter0123/tokensaver-docs/releases">All releases</a></p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a></p>

**PDF・Word・Excel・HTML・画像・音声を Markdown に変換し、Codex・Claude Code・OpenCode で再利用できます。更新されたソースでは、調査資料をプロジェクト内に保存し、必要な根拠だけを検索できます。**

OS ボタンを押すと直接ダウンロードされ、インストーラでエージェントを選択できます。

<a id="download"></a>

## ダウンロードとインストール — v0.5.5

ZIP をすべて展開してインストーラーを一度実行すると、検出された Codex・Claude Code・OpenCode から登録先を選べます。Python の別途インストールは不要です。

macOS：`install.command` をダブルクリックするか、展開先で `sh install.command` を実行します。

Windows：展開先で PowerShell を開き、`.\install.ps1` を実行します。端末のポリシーでブロックされる場合は、そのポリシーに従ってください。インストーラは実行ポリシーを変更しません。

利用するエージェントの CLI を先に用意し、プラグインのインストール後にエージェントを再起動してください。

macOS arm64 の統合インストールはローカルで確認済みです。Windows・Intel Mac のバイナリは自動テスト済みですが、新しい Windows 統合インストーラと実際の Windows・Intel エージェントへのインストールは実験的です。バイナリは未署名・未公証です。Linux は現在ソースインストールのみです。

### ターミナルからプラグインをインストール

OS に合ったコマンドを実行します。ダウンロードと検証の後、検出したエージェントが表示されます。Tab または矢印キーで移動し、Space でチェックします。Enter でチェックした項目だけをインストールします。選択したエージェントにプラグインが登録されます。

**macOS**

```sh
curl -fsSL --proto '=https' 'https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/install.sh' -o tokensaver-docs-install.sh && sh tokensaver-docs-install.sh --repo winter0123/tokensaver-docs --version v0.5.5
```

**Windows PowerShell**

```powershell
& { $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest 'https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/install.ps1' -OutFile tokensaver-docs-install.ps1 -ErrorAction Stop; & .\tokensaver-docs-install.ps1 -Repo winter0123/tokensaver-docs -Version v0.5.5 }
```

<details>
<summary>詳細：エージェント別の ZIP</summary>

| OS | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| macOS Apple Silicon | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-claude-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-codex-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-opencode-darwin-arm64.zip) |
| macOS Intel | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-claude-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-codex-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-opencode-darwin-x64.zip) |
| Windows x64 | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-claude-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-codex-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.5/tokensaver-docs-opencode-win32-x64.zip) |

</details>

## ファイルを添付して依頼する

チャットにファイルや画像を添付し、普段どおりに依頼できます。

> このファイルを Markdown にして。

> この画像の文字と説明を Markdown にまとめて。

エージェントが添付ファイルを開ければ、元のファイル名と既定の保存先を使って Markdown を作成し、保存先を知らせます。画像モデルの初期設定や分析の同意が必要な場合は、表示された質問に答えてください。

## プロジェクトの調査資料を自動保存する

v0.5.5 から、インストーラーに表示されるコマンドをプロジェクトで一度実行すると、自動保存を有効にできます。

> 返品条件を調べてプロジェクトにまとめて。

有効なエージェントが調査資料を保存すると、**バージョン付きの原本、検索用 Markdown、人が読む要約**がプロジェクトに残ります。要約には確認できる原本と根拠の行番号が付きます。URL のみ取得できた資料は参照リンクとして記録します。別のセッションで調査内容を尋ねると、既定の 500 トークン予算内で関連する根拠を検索できます。

許可した公開サイトの原文保存、ローカル音声の文字起こし、画像の自動分析はプロジェクトごとに有効にできます。[設定と詳細な使い方](docs/advanced-usage.md#project-research-archive) · [検証結果](docs/current-status.md#v051-public-preview)

## 画像モデルの選択・変更

画像モデルを変更するには、エージェントに「画像変換モデルを変えて」と依頼してください。

## 対応ファイル

| 種類 | 拡張子 | 変換内容 |
| --- | --- | --- |
| PDF | `.pdf` | テキスト・選択したスキャンページの画像分析 |
| Word | `.docx` | テキスト・表・埋め込み画像 |
| Excel | `.xlsx` | シート・セル・埋め込み画像 |
| HTML | `.html`, `.htm` | 本文・表・埋め込み画像 |
| 画像 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif` | 画像の保存、任意で文字と説明を追加 |
| 音声・動画の音声トラック | `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.mp4` | 音声を文字に変換。動画フレームは解析しません |

旧形式の `.doc`・`.xls` は非対応です。画像・音声の品質はモデルによって異なります。トークン節約効果は文書と読み取る範囲に依存します。[ベンチマークと制限](benchmarks/README.md)をご確認ください。

[詳細ガイド（英語）](docs/advanced-usage.md) · [インストールと配布（英語）](docs/distribution.md) · [検証状況（英語）](docs/current-status.md) · [問題を報告](https://github.com/winter0123/tokensaver-docs/issues) · [MIT ライセンス](LICENSE)
