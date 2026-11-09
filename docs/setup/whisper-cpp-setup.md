# 로컬 음성 인식 설치

사용자 승인: whisper.cpp 연결 및 실제 음성 검증. 무료 로컬 실행이며 유료 서비스·API 키를 사용하지 않는다.

- 실행 파일: Homebrew `whisper.cpp`, 명령은 `whisper-cli`.
- 모델: 공식 whisper.cpp 모델 저장소의 다국어 small, `~/.local/share/tokensaver-docs/models/ggml-small.bin`. 최초 다운로드 약 466MiB.
- 설치: `HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install whisper.cpp`.
- 실행 파일을 별도로 지정할 때는 `WHISPER_CPP_BINARY` 환경변수를 사용한다.
- 설정: `tokensaver-docs configure --kind audio --provider whisper.cpp --model ~/.local/share/tokensaver-docs/models/ggml-small.bin`.
- 음성은 기존 코드로 16kHz 모노 PCM WAV로 바꾼 뒤 로컬에서 인식한다. 원본과 다른 설정의 결과를 보존하고 모델·실행 파일 내용이 바뀌면 캐시를 갱신한다.


Homebrew 설치는 기존 의존성 버전을 갱신할 수 있다. 다른 운영체제의 설치 방법과 모델 선택은 [공식 안내](https://github.com/ggml-org/whisper.cpp)를 확인한다.
