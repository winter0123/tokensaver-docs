<p align="center"><img src="assets/readme/hero-ja.svg" width="960" alt="TokenSaver Docs — PDF・Word・Excel・HTML・画像・音声を Markdown に変換し、Codex・Claude Code・OpenCode で再利用できます。" /></p>

<p align="center">
<a href="#download"><img src="assets/readme/download-windows.svg" width="260" alt="Windows x64 download options" /></a>
<a href="#download"><img src="assets/readme/download-macos.svg" width="260" alt="macOS Apple Silicon and Intel download options" /></a>
<a href="#source-install"><img src="assets/readme/download-linux.svg" width="260" alt="Linux source installation" /></a>
</p>
<p align="center"><a href="#download">macOS Intel</a> · <a href="https://github.com/winter0123/tokensaver-docs/releases">All releases</a></p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a></p>

**PDF・Word・Excel・HTML・画像・音声を Markdown に変換し、Codex・Claude Code・OpenCode で再利用できます。**

OS のボタンから進み、利用するエージェントの ZIP を選んでください。Linux は現在ソースからのインストールに対応しています。

<a id="download"></a>

## プラグインをダウンロード — v0.4.0 プレビュー

**OS・CPU・エージェントに合う ZIP を選んでください。Python の別途インストールは不要です。**

| OS | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| macOS Apple Silicon | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-darwin-arm64.zip) |
| macOS Intel | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-darwin-x64.zip) |
| Windows x64 | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-claude-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-codex-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.4.0/tokensaver-docs-opencode-win32-x64.zip) |

ZIP を展開し、**展開先のフォルダでターミナルを開いて**実行します。

```sh
./bin/tokensaver-docs install-plugin . --agent claude
```

Codex は `--agent codex`、OpenCode は `--agent opencode` を指定します。Windows PowerShell では実行ファイルを `.\bin\tokensaver-docs.exe` に変更してください。利用するエージェントの CLI が必要です。インストール後はエージェントを再起動します。

エージェントに **「tokensaver-docs でこのファイルを Markdown に変換して：/ファイルのパス」** と依頼します。モデル選択はプラグインが案内します。変更する場合は **「tokensaver-docs の画像変換モデルを変更して」** と依頼してください。

macOS arm64 はローカルでインストールを確認済みです。Intel Mac・Windows は自動バンドルテストに合格していますが、実際のエージェントへのインストールは実験的な対応です。バイナリは未署名・未公証です。Linux は以下のソースインストールを使用してください。公式マーケットへの掲載は GitHub リリースとは別です。

[リリースノート・チェックサム・インストーラ](https://github.com/winter0123/tokensaver-docs/releases/tag/v0.4.0)

<a id="source-install"></a>

## ソース CLI のインストール

Python 3.11 以上と Git が必要です。この手順ではエージェントにプラグインを自動登録しません。

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

新しいターミナルでは、該当する 2 行目を再実行してください。PowerShell で有効化がブロックされる場合は、後続の `tokensaver-docs` を `& "$HOME\.tokensaver-docs\venv\Scripts\tokensaver-docs.exe"` に置き換えられます。実行ポリシーの変更は不要です。

## 画像モデルの選択・変更

**以下はソース CLI ユーザー向けです。プラグインではエージェントにモデル変更を依頼できます。** インストール環境を有効化したターミナルで、いずれか 1 つを選びます。選択したモデルは既定値として保存されます。初回設定と変更は同じコマンドです。

**① Claude Code** — CLI をインストールしてログインし、実行後にアカウントで利用できる正確なモデル名を入力します。

```sh
tokensaver-docs configure --kind image --provider claude
```

**② Codex** — CLI をインストールしてログインし、実行後にアカウントで利用できる正確なモデル名を入力します。

```sh
tokensaver-docs configure --kind image --provider codex
```

**③ OpenCode + OpenRouter** — 環境変数 `OPENROUTER_API_KEY` を設定し、実行後に無料の画像入力対応モデル候補から番号を選びます。実際の利用可否はアカウントとサービスによって異なります。API キーをエージェントの会話に貼り付けないでください。

```sh
tokensaver-docs configure --kind image --provider openrouter
```

OpenCode はエージェント、OpenRouter はモデルサービスです。他のエージェントでも変換用に OpenRouter を選べます。この設定が変えるのは画像変換モデルのみで、会話モデルや音声モデルは別です。Claude Code/Codex は各 CLI の認証・利用上限・課金条件に従います。通常の文書テキスト抽出にモデルや API キーは不要です。

現在のモデルを確認：`tokensaver-docs setup-model`

## ファイル・フォルダの変換

`./documents` を入力パスに置き換えます。例：`policy.html` → `converted/policy.html.md`。

**文字を抽出し、画像の位置を `[이미지]` で表示：**

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode placeholder
```

**画像・画像内の文字・説明を追加：** モデルと CLI ログイン、または API キーを準備して実行します。画像は選択したサービスに送信されます。

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode analyze
```

Claude Code/Codex の画像対応は自動確認できません。自分で対応を確認した場合のみ、末尾に `--allow-unverified-model` を追加してください。既知の非対応モデルは引き続きブロックされます。音声は別途設定が必要です。[英語の詳細ガイド](docs/advanced-usage.md)をご覧ください。

元ファイルと手動編集した Markdown を保護し、同じ文書や完了済みの画像分析はキャッシュから再利用します。一部の実行時メッセージと画像プレースホルダーは韓国語です。

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
