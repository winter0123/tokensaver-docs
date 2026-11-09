# PDFium 개발 의존성

스캔 PDF 페이지를 이미지로 만들 때 외부 Poppler 설치가 필요하지 않도록 `pypdfium2>=5,<6`을 프로젝트 가상환경에 추가한다. OCR이나 AI 모델은 포함하지 않는다.

설치 범위는 이 저장소의 `.venv`이며 시스템 Python이나 전역 설정을 변경하지 않는다.

```sh
.venv/bin/python -m pip install 'pypdfium2>=5,<6'
```

소스 설치 사용자는 프로젝트 의존성으로 받고, 플러그인 사용자는 네이티브 실행 파일에 포함된 PDFium을 사용한다. PDFium은 동시에 여러 스레드에서 호출하지 않도록 직렬화한다.

공식 API: https://pypdfium2.readthedocs.io/en/stable/python_api.html
재배포 안내: https://github.com/pypdfium2-team/pypdfium2#licensing
