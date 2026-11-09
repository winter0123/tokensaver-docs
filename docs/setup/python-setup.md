# 설치 범위

이 프로젝트의 `.venv`에만 파이썬 의존성을 설치한다. 전역 파이썬 설정은 수정하지 않는다.
문서 처리에는 pypdf, python-docx, openpyxl, Pillow를 사용한다.
스캔 PDF 렌더링은 프로젝트 의존성 pypdfium2에 포함된 PDFium을 사용한다. 별도 pdftoppm 설치는 필요하지 않다. 오디오는 프로젝트에 포함된 ffmpeg를 사용한다.
전역 설치를 수정하지 않고 프로젝트 가상환경에 imageio-ffmpeg를 설치해 포함된 바이너리로 오디오를 정규화한다. WAV 구간 분할은 표준 라이브러리 wave로 처리한다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```
