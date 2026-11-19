<p align="center"><img src="assets/readme/hero-ko.svg" width="960" alt="TokenSaver Docs — PDF·Word·Excel·HTML·이미지·음성을 Markdown으로 바꿔 Codex·Claude Code·OpenCode에서 재사용하세요." /></p>

<p align="center">Created by <a href="https://github.com/winter0123">winter0123</a> · <a href="https://github.com/winter0123/tokensaver-docs">Original repository</a> · <a href="AUTHORS.md">Authors</a> · <a href="LICENSE">MIT License</a></p>

<p align="center">
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-win32-x64.zip?download=1"><img src="assets/readme/download-windows.svg" width="260" alt="Download Windows x64 ZIP" /></a>
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-darwin-arm64.zip?download=1"><img src="assets/readme/download-macos.svg" width="260" alt="Download macOS Apple Silicon ZIP" /></a>
<a href="https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-darwin-x64.zip?download=1"><img src="assets/readme/download-macos-intel.svg" width="260" alt="macOS Intel download" /></a>
</p>
<p align="center"><a href="https://github.com/winter0123/tokensaver-docs/releases">All releases</a></p>

<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a></p>

**Codex·Claude Code·OpenCode에서 문서·이미지·음성을 Markdown으로 변환하고 재사용하세요. 업데이트된 소스에서는 프로젝트 조사 자료를 원본과 함께 보관하고 필요한 근거만 검색할 수 있습니다.**

운영체제 버튼을 누르면 바로 다운로드되고, 설치 프로그램에서 사용할 에이전트를 선택합니다.

<a id="download"></a>

## 다운로드와 설치 — v0.5.3

ZIP 전체를 풀고 설치 프로그램을 한 번 실행하세요. 설치 화면에서 사용할 에이전트를 선택하세요. Python을 따로 설치할 필요가 없습니다.

macOS: `install.command`를 더블클릭하거나, 압축을 푼 폴더에서 `sh install.command`를 실행하세요.

Windows: 압축을 푼 폴더에서 PowerShell을 열고 `.\install.ps1`을 실행하세요. 기기 정책으로 차단되면 해당 정책을 따르세요. 설치 프로그램은 실행 정책을 바꾸지 않습니다.

설치할 에이전트의 CLI가 먼저 준비되어 있어야 합니다. 설치가 끝나면 에이전트를 재시작하세요.

macOS arm64 통합 설치는 로컬에서 확인했습니다. Windows·Intel Mac 바이너리 번들 검사는 통과했으나 새 Windows 통합 설치 프로그램과 실제 Windows·Intel 호스트 설치는 실험적입니다. 바이너리는 서명·공증 전입니다. Linux는 현재 소스 설치만 제공합니다.

### 터미널에서 플러그인 설치

운영체제에 맞는 명령을 터미널에 붙여 넣으세요. 설치기가 파일을 내려받아 검증하고 감지된 에이전트를 보여줍니다. 번호는 쉼표로 여러 개 입력할 수 있으며, Enter만 누르면 전체를 선택합니다. 선택한 에이전트에 플러그인으로 등록됩니다.

**macOS**

```sh
curl -fL --proto '=https' 'https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/install.sh' -o tokensaver-docs-install.sh && sh tokensaver-docs-install.sh --repo winter0123/tokensaver-docs --version v0.5.3
```

**Windows PowerShell**

```powershell
Invoke-WebRequest 'https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/install.ps1' -OutFile tokensaver-docs-install.ps1 -ErrorAction Stop; & .\tokensaver-docs-install.ps1 -Repo winter0123/tokensaver-docs -Version v0.5.3
```

<details>
<summary>고급: 에이전트별 개별 ZIP</summary>

| 운영체제 | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| macOS Apple Silicon | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-claude-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-codex-darwin-arm64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-opencode-darwin-arm64.zip) |
| macOS Intel | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-claude-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-codex-darwin-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-opencode-darwin-x64.zip) |
| Windows x64 | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-claude-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-codex-win32-x64.zip) | [ZIP](https://github.com/winter0123/tokensaver-docs/releases/download/v0.5.3/tokensaver-docs-opencode-win32-x64.zip) |

</details>

## 파일을 첨부하고 요청하기

파일이나 이미지를 채팅에 첨부하고 평소처럼 말하세요.

> 이 파일 MD 파일로 만들어줘.

> 이 이미지 글자랑 설명 MD 파일로 정리해줘.

에이전트가 첨부 파일을 열 수 있으면 기본 위치와 원본 이름을 사용해 Markdown을 저장하고 결과 위치를 알려줍니다. 이미지 분석을 처음 설정하거나 동의가 필요한 경우에는 화면에 나온 질문에 답하면 됩니다.

## 프로젝트 조사 자료 자동 보관

v0.5.3부터 설치기가 안내하는 명령을 작업 프로젝트에서 한 번 실행하면 자동 보관을 켤 수 있습니다. 이후에는 평소처럼 요청하세요.

> 반품 정책 찾아보고 프로젝트에 정리해줘.

자동 수집이 활성화된 에이전트가 조사 자료를 저장하면 **버전별 원본, 검색용 Markdown, 사람이 읽는 최종 요약**을 프로젝트에 남깁니다. 요약에는 확인할 수 있는 원본과 근거 줄 번호를 연결합니다. 링크만 확보한 자료는 출처 링크로 표시합니다. 새 세션에서 이전 조사 내용을 물으면 기본 500토큰 예산 안에서 관련 근거를 찾아줍니다.

승인한 사이트의 공개 웹 원문 저장, 로컬 음성 전사, 이미지 자동 분석은 프로젝트별로 선택할 수 있습니다. [프로젝트 설정과 상세 사용법](docs/advanced-usage.ko.md#프로젝트-조사-자료-자동-보관) · [검증 결과](docs/current-status.md#v051-public-preview)

## 모델 선택·변경

이미지 모델을 바꾸려면 에이전트에게 “이미지 변환 모델 바꿔줘”라고 요청하세요.

## 지원 파일

| 파일 | 확장자 | 변환 내용 |
| --- | --- | --- |
| PDF | `.pdf` | 텍스트, 선택한 스캔 페이지의 이미지 분석 |
| Word | `.docx` | 텍스트·표·포함 이미지 |
| Excel | `.xlsx` | 시트·셀·포함 이미지 |
| HTML | `.html`, `.htm` | 본문·표·포함 이미지 |
| 이미지 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif` | 이미지 보존, 선택한 모델로 글자·설명 추가 |
| 음성·동영상의 음성 | `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.mp4` | 음성을 글자로 변환; 동영상 화면은 분석하지 않음 |

`.doc`, `.xls`는 지원하지 않습니다. 이미지와 음성의 결과 품질은 모델에 따라 달라집니다. 토큰 절감 효과는 문서와 읽는 범위에 따라 달라지며, 측정 방법과 한계는 [벤치마크](benchmarks/README.md)를 참고하세요.

## 더 알아보기

[에이전트 연결·검색·음성·개발자 사용법](docs/advanced-usage.ko.md) · [플러그인 설치·배포](docs/distribution.md) · [검증 상태](docs/current-status.md) · [문제 신고](https://github.com/winter0123/tokensaver-docs/issues) · [MIT 라이선스](LICENSE)
