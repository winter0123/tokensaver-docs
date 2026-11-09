# 검색 토큰 비교

이미지의 글자·설명·도형 관계를 사람 기준과 대조하는 합성 자료는
[이미지 평가 안내](image-eval/README.md)를 참고한다. 모델 사용량과 품질은
실제로 측정한 경우에만 기록한다.

## HTML 예제

```sh
python benchmarks/html_policy_demo.py
```

재배포 가능한 합성 HTML 한 건으로 원본, 변환 MD, 근거 JSON의
`cl100k_base` 추정 토큰 수를 비교한다. 선택 의존성 `tiktoken`과 로컬에
캐시된 인코딩 데이터가 필요하다. 표·이미지와 환불 기한·예외 보존,
재사용 시 전사 호출 0회를 확인한다. 작은 문서에서는 근거 응답의 메타데이터가
전문보다 클 수 있다. 실제 모델 사용량이나 일반적인 절감률은 측정하지 않는다.

`token_demo.py`는 합성 문서 한 건에서 전문과 `tokensaver-docs search` 응답을 비교한다. `compare_qmd.py`는 직접 생성한 한국어·영어 합성 문서 세 건과 질문 세 개로 전문, tokensaver-docs 검색, QMD 2.8.3의 BM25 검색 결과를 비교한다. 두 스크립트 모두 tiktoken 선택 의존성이 필요하며 `cl100k_base`를 사용한다.

QMD 비교에는 Bun과 `bunx`가 필요하며, 최초 실행 시 공개 npm 패키지를 다운로드한다. 색인과 설정은 임시 디렉터리에 생성되고 기존 QMD 설정을 변경하지 않는다. 임베딩·외부 LLM·유료 API는 사용하지 않는다.

```sh
python -m pip install '.[tokens]'
python benchmarks/token_demo.py
python benchmarks/compare_qmd.py
```

`results/synthetic-qmd-2026-11-05.json`은 해당 날짜의 한 번의 실행 결과다. 같은 예제에서 정답 문자열 포함 여부와 출력 토큰 수만 확인했다. 경로 길이·패키지 버전·인코딩에 따라 값이 달라질 수 있다. QMD는 JSON, tokensaver-docs는 줄 번호가 있는 텍스트로 출력했으므로 토큰 수에는 표현 형식 차이도 반영된다. 이는 실전 절감률, 최종 모델 답변의 정확도, 속도 우위 또는 전반적 도구 우열을 의미하지 않는다. 실전 판단에는 다양한 재배포 가능한 문서·질문, 누락·오답, 변환과 외부 전사 비용, 모델의 실제 사용량을 별도로 측정해야 한다.

## Shared-cache and context demonstration

```sh
python benchmarks/reuse_demo.py
```

This creates a disposable synthetic Word document and a mock image transcription.
It asserts that repeated image use in another output directory makes zero new
mock provider calls and that retrieved evidence retains the designated exception.
The token counts compare full generated Markdown with serialized context JSON
using cl100k_base. This is not a paid model usage comparison, an image accuracy
test or a real-world savings percentage.
