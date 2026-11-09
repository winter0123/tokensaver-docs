"""결과와 진행 상태를 원자적으로 저장한다."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.tokensaver-docs-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def publish_new(path: Path, text: str) -> Path:
    return publish_bytes(path, text.encode('utf-8'))


def publish_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.tokensaver-docs-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        number = 1
        while True:
            candidate = path if number == 1 else path.with_name(f'{path.stem}.{number}{path.suffix}')
            try:
                os.link(temporary, candidate)
                return candidate
            except FileExistsError:
                number += 1
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_state(output: Path) -> dict:
    path = output / '.tokensaver-docs' / 'state.json'
    if not path.exists():
        return {'version': 1, 'records': {}}
    if path.is_symlink() or not path.is_file():
        raise ValueError('상태 파일 경로가 올바르지 않습니다.')
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('version') != 1 or not isinstance(state.get('records'), dict):
        raise ValueError('알 수 없는 상태 파일 형식입니다. 다른 출력 폴더를 사용하세요.')
    return state


def save_state(output: Path, state: dict) -> None:
    folder = output / '.tokensaver-docs'
    if folder.is_symlink():
        raise ValueError('캐시 경로에 심볼릭 링크를 사용할 수 없습니다.')
    atomic_write(folder / 'state.json', json.dumps(state, ensure_ascii=False, indent=2))


def config_path() -> Path:
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'tokensaver-docs' / 'config.json'


def load_profiles(path: Path | None = None) -> dict:
    path = path or config_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('설정 형식이 올바르지 않습니다.')
    for kind, profile in data.items():
        if kind not in ('image', 'audio') or not isinstance(profile, dict):
            raise ValueError('이미지·오디오 설정만 저장할 수 있습니다.')
        if set(profile) != {'provider', 'model'}:
            raise ValueError('설정에는 제공자와 모델만 저장하세요. 키는 환경변수를 사용합니다.')
        if profile['provider'] not in ('openrouter', 'codex', 'claude', 'whisper.cpp') or not isinstance(profile['model'], str) or not profile['model'].strip():
            raise ValueError('제공자 또는 모델 설정을 확인하세요.')
        if profile['provider'] == 'whisper.cpp' and kind != 'audio':
            raise ValueError('whisper.cpp는 오디오 설정에만 사용할 수 있습니다.')
    return data
