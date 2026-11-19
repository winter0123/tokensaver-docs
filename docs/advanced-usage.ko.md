# 상세 사용법

[빠른 시작으로 돌아가기](../README.ko.md) · [최신 검증 상태](current-status.md)

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
tokensaver-docs read ~/Documents/변환결과/규정.pdf.md --start-line 20 --lines 40
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

`python benchmarks/token_demo.py`는 합성 문서 한 건의 전문과 검색 응답을 `cl100k_base`로 비교하고 알려진 근거가 검색되는지 확인한다. 실전 절감률이나 여러 도구의 우열을 보장하는 수치는 아니다. 영어 안내: [README.en.md](../README.en.md).

QMD BM25와 같은 합성 문서·질문으로 비교하는 재현 스크립트도 제공한다. 결과 및 한계: [benchmarks/README.md](../benchmarks/README.md). 세 질문의 작은 예제이므로 실전 전반의 우열이나 정확도를 뜻하지 않는다.


## 프로젝트 조사 자료 자동 보관

아래 기능은 v0.5.1 프리뷰와 최신 소스에서 사용할 수 있습니다.

플러그인 ZIP으로 설치했다면 설치기가 출력한 전체 활성화 명령을 프로젝트에서 한 번
실행합니다. 소스 CLI를 설치했다면 `tokensaver-docs knowledge enable .`을 사용합니다. 이 명령은
`docs/research/inbox/`와 `docs/tokensaver-docs/`를 만들고 두 경로를 Git 무시 목록에
추가합니다. 이미 Git이 추적하는 파일은 무시 규칙의 적용을 받지 않습니다.
`tokensaver-docs knowledge disable .`은 자동 처리만 끕니다.

Codex·Claude Code 자동 수집은 설치기가 안내하는 프로젝트별 훅을 사용합니다.
소스 CLI에서는 각각 `--codex-project-hooks`, `--claude-project-hooks`를 활성화
명령에 추가합니다. Codex에서는 등록된 훅을 검토하고 신뢰를 선택합니다. OpenCode v1과
v2는 프로젝트가 켜진 경우 파일 저장과 작업 종료 이벤트로 수집합니다. 수동 처리는
`tokensaver-docs knowledge sync .`을 사용합니다. 프로젝트를 다른 경로로 옮기면
다시 활성화합니다. 비활성화하면 TokenSaver가 등록한 프로젝트 훅과 자동화 승인만
제거하고 자료는 보존합니다.

예를 들어 “반품 정책 찾아보고 프로젝트에 정리해줘”라고 요청합니다. 수집 대상은
조사 과정에서 `docs/research/inbox/`에 실제로 저장된 파일입니다. 원본과 연결된 로컬 이미지는
버전별로 보관합니다. 연구 초안은 `<topic>.research.json`에 저장하며, 파일명과
`topic`은 같은 ASCII 소문자 슬러그를 사용합니다. 예시는 아래와 같습니다.

```json
{
  "topic": "refunds",
  "title": "환불 규정",
  "conclusion": "배송 후 7일 이내 반품할 수 있다.",
  "impact": "환불 가능 기간을 구현한다.",
  "unknowns": "예외의 적용 범위를 확인해야 한다.",
  "evidence": [
    {"source": "docs/research/inbox/policy.md", "quote": "Returns within seven days."}
  ],
  "references": ["https://example.org/policy"]
}
```

`docs/tokensaver-docs/index.md`에서 보관 상태와 보고서 목록을 확인합니다.
개별 보고서는 `docs/tokensaver-docs/reports/<topic>/summary.md`에서 읽습니다. 출처 파일을
확보한 인용은 변환본의 줄 범위와 보관 원본에 연결합니다. URL만 있는 항목은
`REFERENCE_ONLY`이고, 인용을 확인하지 못한 항목과 결론은 검토가 필요합니다.
일반 텍스트(`.txt`)는 원본 그대로 보관하고 검색용 Markdown을 별도로 만듭니다. 인용 링크는 보관된 파일에 해당 문구가 있음을 보여줍니다. 에이전트가 추가한 조건은 중요한 결론에 쓰기 전에 원출처와 대조하세요.
자료가 뒤늦게 등록되면 미해결 인용을 다시 확인합니다. 이미 연결한 인용은 당시
원본과 변환본을 계속 가리킵니다.
초안이 없다면 `reports/inbox/summary.md`에 최근 파일의 미검토 발췌를 제공합니다.
사람이 편집한 보고서는 보존하고 새 자동 요약은 `summary.pending-*.md`에 저장합니다.

후속 세션에서는 MCP의 `search_research`, OpenCode의
`tokensaver_docs_search_research` 또는
`tokensaver-docs knowledge search . "환불 예외" --max-tokens 500`으로 등록 자료의
근거만 읽습니다. 도구에 절대 프로젝트 경로와 핵심 검색어를 전달합니다.
`source_index`는 응답의 `sources`에 담긴 프로젝트 기준 Markdown 경로를 가리킵니다.
긴 줄의 일부를 반환해도 원래 줄 번호를 함께 표시합니다. 검색은 원본·변환 결과의
무결성을 확인하며 로컬에서 실행합니다. 승인받아 이미지 분석이나 전사를 이미 완료했다면
`tokensaver-docs knowledge attach . docs/research/inbox/audio.wav converted`로
원본 해시와 결과 해시가 일치하는 기존 변환본을 붙일 수 있습니다.
특정 시점의 전사를 다시 검색하려면 보고서에 나온 원본 버전과 변환본 ID를
`--version-id`와 `--conversion-id`로 함께 지정합니다. MCP에서는 `version_id`와
`conversion_id`를 전달합니다.


### 웹 원문과 미디어 자동 처리 선택

다음 옵션은 각각 기본값이 꺼져 있고, 현재 컴퓨터의 사용자 설정에 프로젝트별로
저장합니다. 같은 경로에 새 프로젝트를 만들거나 이전 형식의 승인을 사용했다면
옵션을 다시 지정해야 합니다. 플러그인 ZIP을 설치했다면 설치기가 출력한 전체 활성화 명령에 필요한
옵션을 덧붙입니다.

| 옵션 | 처리 범위 |
| --- | --- |
| `--snapshot-domain docs.example.org` | 연구 초안의 `references`에 포함된 해당 호스트의 공개 HTTPS HTML을 원문으로 보관합니다. 호스트는 정확히 일치해야 합니다. 여러 호스트를 허용하려면 옵션을 반복합니다. 주소에 쿼리나 자격 증명이 있거나 응답이 리디렉션이면 기존 링크만 남깁니다. HTML 응답 상한은 2 MiB이며 이미 보관한 URL은 다시 받지 않습니다. |
| `--auto-audio` | 공통 CLI에 설정한 로컬 `whisper.cpp` 모델로 받은 음성을 전사합니다. OpenCode 전용 설정에서 받은 모델 파일도 공통 CLI의 `configure --kind audio --provider whisper.cpp --model 경로`로 지정할 수 있습니다. |
| `--auto-image-analysis` | 현재 선택한 이미지 제공자와 모델로 수집 폴더의 독립 이미지 파일을 분석합니다. 이 옵션은 해당 제공자로 이미지를 자동 전송하고 요금이 발생할 수 있다는 동의를 뜻합니다. 문서 안에 삽입된 이미지는 기존 보존 방식으로 처리합니다. |
| `--clear-automation` | 웹과 미디어 자동 처리 승인을 모두 해제합니다. 원본 보관과 기존 분석 결과 검색은 계속 가능합니다. |

동기화 한 번에 미디어 한 파일을 분석합니다. 중단된 로컬 전사는 다음 동기화에서
한 번 재시도합니다. 중단된 외부 이미지 분석은 재전송하지 않으며, 확인할 작업은
`index.md`에 표시합니다. 실패한 자료는 기존 변환 명령으로 처리한 뒤
`knowledge attach`로 연결할 수 있습니다. 처리 시간 때문에 미룬 웹 자료가 있으면
동기화 결과에 `pending`을 표시합니다.
