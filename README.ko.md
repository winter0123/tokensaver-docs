# TokenSaver Docs

**문서는 한 번 준비하고, AI에는 필요한 근거만 전달하세요.**

Codex · Claude Code · OpenCode를 위한 문서 컨텍스트 플러그인입니다.

플러그인 단독 설치를 위한 시험 빌드와 현재 제한은 [플러그인 미리보기 안내](docs/plugin-preview.md)를 참고하세요. 공식 마켓에는 아직 등록되지 않았습니다.

Convert files once and give coding agents bounded, line-numbered evidence. [English guide](README.en.md) · 한국어 안내는 아래를 확인하세요.

## 빠른 시작

**설치는 컴퓨터 기준으로, 모델 선택은 사용할 서비스 기준으로 고르세요.**

| 단계 | 선택 기준 | 골라야 할 항목 |
| --- | --- | --- |
| 1. 프로그램 설치 | 내 컴퓨터의 운영체제 | macOS·Linux / Windows 중 하나 |
| 2. 변환 모델 선택 | 이미지 변환에 사용할 서비스 | Claude Code / Codex / OpenCode에서 사용할 OpenRouter 중 하나 |
| 3. 파일 변환 | 결과에 이미지를 어떻게 넣을지 | 이미지 위치만 표시 / 이미지 속 글자·설명도 추가 |

예: **Windows에서 Claude Code를 사용한다면 → 1-B로 설치 → 2-A로 모델 선택 → 3단계로 변환**합니다. 설치 명령은 운영체제에 따라 다르고, 모델 선택 명령은 모든 운영체제에서 같습니다.

### 1단계. 프로그램 설치 — 운영체제별로 선택

현재 바로 사용할 수 있는 **소스 버전 설치**입니다. Python 3.11 이상과 Git이 필요합니다. 에이전트에 등록되는 플러그인 설치와는 별개이며, 공개 플러그인 설치 파일은 아직 배포 전입니다.

#### 1-A. macOS / Linux

터미널에 아래 세 줄을 붙여넣으세요.

```sh
python3 -m venv "$HOME/.tokensaver-docs/venv"
source "$HOME/.tokensaver-docs/venv/bin/activate"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

#### 1-B. Windows

PowerShell에 아래 세 줄을 붙여넣으세요.

```powershell
py -3 -m venv "$HOME\.tokensaver-docs\venv"
& "$HOME\.tokensaver-docs\venv\Scripts\Activate.ps1"
python -m pip install 'tokensaver-docs[mcp,tokens] @ git+https://github.com/winter0123/tokensaver-docs.git'
```

새 터미널에서는 위의 두 번째 줄로 다시 활성화하세요. PowerShell에서 활성화가 차단되면 정책을 바꾸는 대신 `& "$HOME\.tokensaver-docs\venv\Scripts\tokensaver-docs.exe"`를 `tokensaver-docs` 대신 사용하세요.

### 2단계. 변환 모델 선택·변경 — 서비스별로 선택

**아래 세 가지 중 사용할 방식 하나만 선택하세요.** 명령은 에이전트 대화창이 아닌, 1단계에서 설치한 환경을 활성화한 터미널에 입력합니다.

OpenCode는 에이전트이고 OpenRouter는 모델 제공 서비스입니다. 아래 2-C는 OpenCode와 함께 사용할 변환 제공자로 OpenRouter를 선택하는 예입니다. 변환 제공자는 사용하는 에이전트와 별개라서, Claude Code나 Codex에서도 OpenRouter를 선택할 수 있습니다.

 처음 설정할 때와 모델을 변경할 때 같은 명령을 사용합니다. 선택한 모델은 다음 이미지 변환에도 사용할 기본값으로 저장됩니다.

#### 2-A. Claude Code 모델 사용

Claude Code CLI가 설치되어 있고 로그인되어 있어야 합니다. 아래 명령을 실행한 뒤, **해당 계정에서 사용할 모델 이름을 입력**하세요. 모델 목록을 번호로 고르는 방식은 아닙니다.

```sh
tokensaver-docs configure --kind image --provider claude
```

#### 2-B. Codex 모델 사용

Codex CLI가 설치되어 있고 로그인되어 있어야 합니다. 아래 명령을 실행한 뒤, **해당 계정에서 사용할 모델 이름을 입력**하세요. 모델 목록을 번호로 고르는 방식은 아닙니다.

```sh
tokensaver-docs configure --kind image --provider codex
```

Claude Code와 Codex는 각각 실행되는 CLI의 로그인·사용량 한도·과금 조건을 따릅니다. 현재 대화 모델을 자동으로 가져오지 않습니다. 이 플러그인은 두 CLI의 모델 목록·이미지 지원 여부를 자동 조회하지 못하므로, 이미지 입력을 지원하는 모델인지 확인하고 선택하세요.

#### 2-C. OpenCode에서 OpenRouter 무료 모델 사용

`OPENROUTER_API_KEY` 환경변수를 설정한 뒤 아래 명령을 실행하세요. **무료 이미지 입력 지원 후보 목록에서 모델 번호를 입력**하면 됩니다. 실제 사용 가능 여부는 계정과 서비스 상태에 따라 달라질 수 있습니다.

```sh
tokensaver-docs configure --kind image --provider openrouter
```

키는 에이전트 대화에 입력하지 마세요.

위 명령은 **문서 속 이미지를 처리할 모델**을 바꿉니다. 에이전트의 대화 모델이나 음성 모델은 바꾸지 않습니다. 이미지 없는 문서의 텍스트 추출에는 모델·API 키가 필요하지 않습니다.

#### 공통: 현재 선택한 모델 확인

```sh
tokensaver-docs setup-model
```

### 3단계. 파일 또는 폴더 변환 — 모든 환경 공통

`./documents`를 변환할 파일이나 폴더 경로로 바꾸세요. 경로에 공백이 있으면 따옴표로 감싸세요.

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode placeholder
```

위 명령은 글자를 추출하고 이미지 위치에 `[이미지]`를 남깁니다. **이미지 속 글자와 설명도 넣으려면**, 선택한 방식의 모델과 로그인 또는 API 키를 준비한 뒤 아래 명령을 사용하세요. 이미지가 선택한 제공자로 전송됩니다.
Claude Code·Codex처럼 이미지 지원 여부가 자동 확인되지 않는 모델은, 지원 여부를 직접 확인한 경우에만 아래 명령 끝에 `--allow-unverified-model`을 추가하세요. 이 옵션은 이미지 미지원으로 확인된 모델을 허용하지 않습니다.

```sh
tokensaver-docs prepare "./documents" --output "./converted" --image-mode analyze
```

## PDF·Word·Excel·HTML·이미지·음성을 Markdown으로 변환

| 종류 | 지원 확장자 | 변환 내용 |
| --- | --- | --- |
| PDF | `.pdf` | 텍스트 추출, 선택한 스캔 페이지의 이미지 내용 정리 |
| Word | `.docx` | 문서 텍스트·표·포함 이미지 |
| Excel | `.xlsx` | 시트·셀·포함 이미지 |
| HTML | `.html`, `.htm` | 본문·표·포함 이미지 |
| 이미지 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif` | 원본 이미지 보존, 선택한 모델로 글자와 이미지 설명 추가 |
| 음성·동영상의 음성 | `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.mp4` | 음성을 글자로 변환; 동영상 화면은 분석하지 않음 |

이미지 내용 정리와 음성의 글자 변환에는 별도 모델 설정과 사용자 선택이 필요합니다. 이전 Word·Excel 형식인 `.doc`, `.xls`는 지원하지 않습니다.

텍스트 문서는 로컬에서 직접 추출한다. 이미지가 있으면 이미지·글자·설명을 넣을지, 이미지만 넣을지 사람이 선택한다. 선택한 모델이 이미지를 읽지 못하면 모델을 바꾸거나 해당 위치에 `[이미지]`만 표시하고 계속할 수 있다. 이미지 내용 정리는 사용자가 선택한 모델로 처리하며, 음성은 별도로 선택한다. 화면 메시지와 안내는 한국어다.

명령어·플러그인 ID·설치 경로는 `tokensaver-docs`, Python 패키지는 `tokensaver_docs`를 사용합니다.

## 개발자용: 체크아웃한 소스에서 실행

일반 사용자는 위의 빠른 시작을 따르면 됩니다. 아래는 저장소를 직접 체크아웃한 개발자를 위한 macOS·Linux 예시입니다. Python 3.11 이상이 필요합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/tokensaver-docs --help
```

스캔 PDF의 페이지 렌더링은 포함된 PDFium으로 처리하므로 Poppler나 `pdftoppm` 설치가 필요하지 않다. 페이지 이미지의 내용을 정리할 제공자·모델은 사람이 선택한다. 오디오 정규화는 프로젝트 의존성 `imageio-ffmpeg`에 포함된 바이너리를 사용하고 구간 분할은 파이썬이 수행한다. 시스템 ffmpeg/ffprobe를 설치하거나 수정하지 않는다. OCR 엔진은 사용하지 않는다. 음성은 선택에 따라 whisper.cpp로 로컬 인식할 수 있다.

```sh
tokensaver-docs inspect ~/Documents/자료 --output ~/Documents/변환결과
tokensaver-docs convert ~/Documents/자료 --output ~/Documents/변환결과
tokensaver-docs status --output ~/Documents/변환결과
tokensaver-docs search "환불 기한" --output ~/Documents/변환결과
tokensaver-docs read ~/Documents/변환결과/규정.pdf.md --page 4
```

폴더는 자동 재귀 처리하며 출력·캐시·가상환경·심볼릭 링크는 제외한다. 단일 파일도 입력할 수 있다. 결과는 원본의 상대경로와 확장자를 보존해 `규정.pdf.md`처럼 저장한다. 기본 출력 폴더는 실행한 위치의 `converted`다.

## 모델 선택

처음 `prepare`를 사용하면 **모델 선택하기 / 나중에 선택하기**를 안내한다. 일반 문서의 글자는 모델 없이도 추출할 수 있다. 플러그인의 변환 모델은 현재 대화 모델과 별개이며, 호스트 모델 정보를 확인할 수 없으면 추측하지 않는다.

```sh
tokensaver-docs setup-model
tokensaver-docs setup-model --defer
# 사용자가 고른 모델의 지원 여부 확인: 기본값은 바뀌지 않음
tokensaver-docs setup-model --provider openrouter --model MODEL_ID
# 사용자가 기본 모델 저장을 선택한 뒤 실행
tokensaver-docs setup-model --provider openrouter --model MODEL_ID --save-as-default --confirmed
```

이미지 입력 지원 여부와 무료 여부는 따로 확인한다. 미지원, 확인 불가, 목록 조회 실패, 무료 가격 미확인은 서로 다른 상태로 안내한다. 코덱스·클로드 CLI에서 이미지 지원을 확인하지 못한 경우 사용자가 직접 지원·계정 조건을 확인하고 동의한 뒤 `--allow-unverified-model`을 사용할 수 있다. 이 옵션은 확인된 미지원이나 오픈라우터의 가격 검사·조회 실패를 우회하지 않는다.

모델이 이미지를 읽을 수 없으면 다음 두 선택을 제공한다.

- **모델 바꾸기**: 이미지 지원 모델을 선택해 이미지·이미지 속 글자·설명을 MD에 넣는다. 이번 작업에만 사용하거나 기본 모델로 저장할 수 있다.
- **현재 모델로 계속하기**: 일반 글자는 변환하고 이미지가 있던 확인 가능한 위치에 `[이미지]`만 남긴다. 이미지 링크·이미지 속 글자·설명은 넣지 않는다.

지원 모델일 때의 `이미지만 넣기`는 실제 이미지를 MD에 연결하는 기존 기능이다. `[이미지]`만 표시하는 선택과 결과가 다르다. 로컬 OCR이나 글자만 추출하는 새 모드는 추가하지 않았다.

```sh
tokensaver-docs prepare 자료 --output 결과 --image-mode placeholder
tokensaver-docs prepare 자료 --output 결과 --image-mode preserve
tokensaver-docs prepare 자료 --output 결과 --image-mode analyze --model-provider openrouter --model MODEL_ID
```

`analyze`는 이미지·글자·설명, `preserve`는 이미지만, `placeholder`는 위치 표시만 뜻한다. `--model-provider`와 `--model`은 이번 요청에만 적용하며 저장된 기본값을 바꾸지 않는다. 외부 분석 제공자를 선택하면 이미지가 전송될 수 있으므로 처리 전에 동의한다. 음성 제공자는 함께 활성화하지 않는다.

`configure`를 실행하면 사람이 입력 종류, 제공자, 모델을 선택한다. 이미지와 오디오를 따로 설정한다. 로컬 음성은 `configure --kind audio --provider whisper.cpp --model /모델경로/ggml-small.bin`으로 선택한다. 실행 파일은 `whisper-cli`이며 `WHISPER_CPP_BINARY`로 경로를 지정할 수 있다. 오픈라우터 무료 후보는 `models --kind image` 또는 `models --kind audio`로 조회한다. 목록 조회는 추론을 호출하지 않는다.

```sh
tokensaver-docs configure
tokensaver-docs configure --kind image --provider codex --model <계정에서_사용할_모델>
tokensaver-docs configure --kind audio --provider openrouter --model <직접_선택한_무료모델>
```

오픈라우터 키는 `OPENROUTER_API_KEY` 환경변수로만 전달한다. 명령줄 인자로 키를 받거나 설정 파일에 저장하지 않는다. 기존 제공자 설정은 `~/.config/tokensaver-docs/config.json`, 최초 선택과 새 기본 변환 모델은 같은 폴더의 `model-choice.json`에 저장한다. `XDG_CONFIG_HOME`을 지정하면 그 아래를 사용한다. 기존 `configure --config`는 해당 제공자 파일 위치를 바꾸는 옵션이다.

| 연결 | 이미지 | 오디오 | 사용량 |
| --- | --- | --- | --- |
| whisper.cpp | 미지원 | 다국어 로컬 인식 | API 요금·외부 전송 없음 |
| 오픈라우터 | 현재 무료 입력 지원 모델만 | 일반 오디오 입력 모델만, 실제 지원 여부 확인 필요 | 무료 가격을 확인한 모델만 호출, 요청 한도 존재 |
| 코덱스 CLI | 선택 모델·계정에서 지원 필요 | 직접 입력 미지원 | 기존 CLI 로그인 계정의 조건 적용 |
| 클로드 코드 CLI | 선택 모델·계정에서 지원 필요 | 직접 입력 미지원 | 기존 CLI 로그인 계정의 조건 적용 |

세 연결 모두 모델·제공자 자동 변경과 유료 대체를 하지 않는다. 코덱스·클로드 코드 사용은 무료를 보장하지 않는다. 기존 계정의 실제 인증 방식과 한도를 확인한 뒤 사용한다. CLI 버전과 로그인·모델 가용성에 따라 실행이 차단될 수 있다. 불필요한 사용자 설정·도구 로딩을 줄여 별도의 일회성 작업으로 실행한다.

## 파일별 동작과 한계

- PDF: 페이지별 직접 추출. 텍스트 추출이 안 되면서 이미지·벡터 도형·추출 불가 텍스트가 있는 페이지는 이미지 내용 정리 대상이며, 모델 미설정 시 차단한다. 실제 빈 페이지와 구분한다. 그림과 글이 함께 있는 페이지는 직접 추출 후 경고한다. `convert 규정.pdf --vision-pages 1,3-5 --output 결과`로 특정 페이지 전체를 AI에 보낼 수 있다. 암호화 파일은 해제한 사본이 필요하다.
- DOCX: 본문·표·중첩 표의 이미지 위치를 보존하고 머리글·바닥글을 구분한다. 같은 이미지와 처리 정책의 완료된 분석 결과는 재사용한다. 텍스트 상자·변경 추적·위치 미확인 개체 등은 경고하며 완전한 재현을 보장하지 않는다. 실제 페이지 번호는 추측하지 않는다.
- XLSX: 시트·셀 주소·수식·저장 계산값을 기록한다. 수식을 계산하거나 매크로를 실행하지 않는다. 숨김 시트도 표시한다. 내장 이미지는 AI 대상이며 차트·도형은 원본 확인을 안내한다.
- 이미지: 원본을 보존하고 MD에서 연결한다. 내용 정리를 선택하면 PNG/JPEG/WEBP/BMP/TIFF/GIF를 PNG로 정규화한 사본을 선택한 AI에 전달해 보이는 글자와 이미지 설명을 함께 작성한다. 투명 배경은 흰색에 합성하며, 다중 TIFF와 GIF 등은 프레임별로 처리한다. 큰 이미지는 전체와 겹치는 확대 조각을 한 요청에 함께 보내 작은 글자를 읽도록 한다. 확대 조각 포함 15MiB 또는 16조각을 넘으면 분할을 안내한다. 원본은 수정하지 않는다.
- 오디오: WAV/MP3/M4A/OGG/FLAC/AAC/MP4를 WAV 구간으로 변환한다. 기본 60초, 1초 겹침이다. `--chunk-seconds 30`으로 줄일 수 있다. 시간은 원본의 구간 기준이며 화자·단어별 시각은 보장하지 않는다. 겹침 중복은 임의로 삭제하지 않는다. 오픈라우터는 일반 오디오 입력용 `/chat/completions` 경로를 사용하며 전사 전용 `/audio/transcriptions` 경로는 지원하지 않는다. 후보 목록에 나타나도 실제 모델의 경로 지원은 별도 확인이 필요하다.
- 구형 DOC/XLS는 미지원이다. 최신 형식으로 저장한 사본을 사용한다.

whisper.cpp는 16kHz 모노 WAV를 로컬에서 인식하고 언어를 자동 감지한다. 다국어 모델을 선택해야 하며 영어 전용 `.en` 모델은 거부한다. 설치는 `docs/setup/whisper-cpp-setup.md`를 참고한다. 기존 전사는 재사용하며 명시적으로 재변환할 수 있다.

이미지 내용 정리는 보이는 글자와 별도의 이미지 설명을 요청한다. 읽기 어려운 부분은 표시하도록 요청하지만 모델의 누락·잘못된 설명을 완전히 검출할 수는 없다. 금액·날짜·도표의 방향 등 중요한 사실은 원본과 대조한다.

원본은 파일당 100MiB, AI 전송 사본은 15MiB, 일반 이미지는 4천만 화소까지 처리한다. PDF 페이지는 긴 변 2,400픽셀로 렌더링하므로 작은 글씨는 원본과 대조한다. 큰 문서는 필요한 페이지·구간으로 나눠 사용한다. 이 도구는 문서 전체 시각 배치를 재현하는 편집기가 아니다.

## 캐시·재개·보존

결과 폴더의 `.tokensaver-docs/state.json`에 원본 해시, 설정·모델·지시문 버전, 완료 구간, 추출 내용, 제공된 사용량을 저장한다. 인증값은 저장하지 않는다. 추출 내용은 민감정보를 포함할 수 있으므로 결과 폴더도 원본과 동일하게 관리한다.

같은 내용의 파일과 완료한 AI 구간은 공통 캐시에서 재사용한다. 이미지 분석·이미지 보존·위치 표시는 서로 구분한다. 새 준비 경로에서 분석 모델을 명시적으로 선택하면 모델별 캐시를 사용해 다른 모델의 결과를 선택 모델의 결과처럼 표시하지 않는다. 결과 MD만 삭제한 경우 캐시에서 복원하고, 실패한 구간은 같은 명령으로 재개한다. 기존 `convert`의 모델 설정만 변경해도 완료된 결과는 유지하며, 새 모델로 다시 처리하려면 `--refresh`를 명시한다. 원본이 바뀌면 달라진 내용을 다시 처리한다.

누락 문제 수정 때문에 과거 PDF·DOCX·이미지와 내장 이미지가 있는 XLSX 캐시 중 이전 형식은 재사용하지 않는다. 해당 원본을 다시 변환하면 선택한 AI가 다시 호출될 수 있다. 오디오와 내장 이미지 없는 XLSX 캐시는 유지한다.

기존 결과나 사람이 편집한 MD는 덮어쓰지 않는다. 새 변환이 필요하면 `사진.png.2.md`, `.3.md`처럼 저장하며, 변환·상태 명령에 실제 경로를 표시한다. 검색은 기록된 이전 버전을 제외하며 `--all-versions`로 포함할 수 있다. 이전 형식의 상태에 기록되지 않은 과거 버전은 일반 MD처럼 검색될 수 있다. 동일 이름의 다른 원본은 충돌로 처리한다. 출력 폴더는 동시에 한 변환만 사용할 수 있다. 완료 구간 저장 전에 강제 종료되면 해당 AI 요청은 다시 필요할 수 있다. 파일시스템이 하드링크를 지원하지 않으면 결과를 덮어쓰지 않고 실패한다.

종료 코드: 0은 완료 또는 원본 확인 경고, 2는 차단·실패·충돌·부분완료, 130은 사용자 중단이다. 경고가 있는 문서는 상태가 `확인필요`다. 경고와 모델의 자기평가를 검증된 정확도로 표현하지 않는다.

## 스킬

`skills/tokensaver-docs/SKILL.md` 한 개를 코덱스·클로드 코드가 함께 사용한다. 사용자 스킬 폴더에 연결하면 어느 프로젝트에서든 변환·검색·부분 읽기 절차를 사용할 수 있다. 스킬 본문에 대회 자료나 인증값을 넣지 않는다.

## 검증

```sh
.venv/bin/python -m unittest discover -s tests -v
```

자동 테스트는 생성한 작은 문서와 가짜 제공자 응답을 사용한다. 실 API·구독 모델 호출을 테스트 성공으로 가장하지 않는다.

문서 제목과 원본 결과 파일의 줄 번호는 `tokensaver-docs outline 결과.md`로 확인한다. 검색할 때 `--context 2`를 지정하면 일치한 줄 앞뒤의 문맥을 함께 확인할 수 있다. 결과는 기본적으로 글자 수로 제한되며 실제 토큰 수와 같지는 않다.

## 에이전트와 토큰 예산

공개 저장소의 체크아웃에서 다음처럼 설치한다. 현재 PyPI 등록은 하지 않았다.

```sh
python -m pip install '.[mcp,tokens]'
tokensaver-docs doctor
tokensaver-docs install-skill --agent codex
# 또는 tokensaver-docs install-skill --agent claude
```

`install-skill`은 기본적으로 해당 에이전트의 사용자 스킬 폴더를 사용하고, 기존 스킬 내용이 다르면 덮어쓰지 않는다. `--destination`으로 별도 상위 폴더를 지정할 수 있다. Orca에서는 Orca가 실행하는 에이전트의 CLI·스킬 설정을 사용한다.

```sh
tokensaver-docs outline 결과/규정.pdf.md
tokensaver-docs search "환불" --output 결과 --context 2 --max-tokens 300
tokensaver-docs read 결과/규정.pdf.md --start-line 20 --max-tokens 300
tokensaver-docs count-tokens 결과/규정.pdf.md --encoding cl100k_base
```

`--max-tokens`는 검색 결과의 경로·줄 번호와 본문 또는 읽기 결과의 줄 번호와 본문에 적용하며 상태 메시지나 에이전트 프로토콜 부가 내용은 포함하지 않는다. `count-tokens`와 검색은 선택한 인코딩 기준이므로 실제 다른 모델의 청구 토큰과 다를 수 있다. `tiktoken` 어휘 파일은 최초 사용 시 다운로드가 필요할 수 있다. 전체 정답과 예외를 확인할 수 있을 만큼 문맥을 읽어야 하며 짧은 검색 결과만으로 정확도를 보장하지 않는다.

MCP는 선택 설치 후 `tokensaver-docs-mcp`를 stdio 서버로 실행한다. 설치가 클라이언트 설정을 자동 변경하지는 않는다. 선택한 에이전트의 명령에서 등록할 수 있다.

```sh
codex mcp add tokensaver-docs -- tokensaver-docs-mcp
claude mcp add tokensaver-docs -- tokensaver-docs-mcp
```

MCP 변환 도구는 기본적으로 설정된 외부 제공자를 사용하지 않고 상태와 경로만 반환한다. `convert_documents`의 `use_configured_providers=true`는 이미지 제공자를, `use_configured_audio_provider=true`는 음성 제공자를 각각 활성화한다. `context_documents`의 `use_configured_providers=true`는 이미지와 음성 제공자를 모두 활성화하므로 두 입력 종류에 대한 동의가 필요하다. 활성화한 입력은 해당 서비스로 전송될 수 있다. MCP 검색과 읽기는 제한된 근거를 반환하며 선택적으로 `max_tokens`를 받을 수 있다. 여러 검색어는 정확한 문구를 먼저 찾고, 같은 줄에 모든 단어가 있는 결과를 그 다음에 출력한다.

기존 `convert` 명령은 설정된 제공자를 그대로 사용한다. `--transcribe-images` 또는 `--vision-pages`를 지정한 경우 음성 제공자는 제외하며, 함께 사용하려면 `--use-configured-audio-provider`를 추가한다.

`python benchmarks/token_demo.py`는 합성 문서 한 건의 전문과 검색 응답을 `cl100k_base`로 비교하고 알려진 근거가 검색되는지 확인한다. 실전 절감률이나 여러 도구의 우열을 보장하는 수치는 아니다. 영어 안내: [README.en.md](README.en.md).

QMD BM25와 같은 합성 문서·질문으로 비교하는 재현 스크립트도 제공한다. 결과 및 한계: [benchmarks/README.md](benchmarks/README.md). 세 질문의 작은 예제이므로 실전 전반의 우열이나 정확도를 뜻하지 않는다.

## 0.3.0 로컬 미리보기 변경

동일 파일과 이미지·음성 구간을 공통 캐시로 재사용하고, `context` 명령으로
변환 준비와 근거 조회를 한 번에 수행합니다. 새 설치 패키지에는 Python과
Whisper 실행 파일, OpenCode JavaScript 의존성이 포함됩니다. 음성 모델은
`setup-audio --model small`로 용량을 확인한 뒤 사용자가 선택해 다운로드합니다.
검증된 패키지는 `install-plugin 패키지경로 --agent claude|codex|opencode`로
연결합니다. 실제로 선택할 때는 세 이름 중 하나만 지정합니다.

상세 안내는 [설치 문서](docs/plugin-preview.md)를 확인하세요. GitHub와 공식
디렉터리 게시, Windows와 Intel Mac의 실제 실행은 아직 완료되지 않았습니다.


HTML과 이미지는 `tokensaver-docs prepare <입력> --output <결과>`로 준비합니다. 반환된 최초 설정·모델 지원·이미지 처리 질문에 사용자가 답한 뒤 계속합니다. 기존 `--transcribe-images`는 `analyze`, `--skip-image-transcription`은 `preserve`와 같은 의미입니다. `[이미지]`만 남기려면 `--image-mode placeholder`를 선택합니다. 결과 상태에서 누락·실패를 확인하세요. 모델에게 원문 HTML을 읽히거나 변환기를 작성시키지 마세요. 0.4.0의 새 흐름을 세 호스트의 실제 모델 호출로 검증한 상태는 아니며 최신 기록은 [검증 상태](docs/current-status.md)를 확인하세요.
