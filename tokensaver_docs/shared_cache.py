"""User-local reusable conversion results. No remote cache or automatic uploads."""
import copy
import json
import os
import sys
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .storage import atomic_write, digest, file_hash, load_state, publish_new, save_state


@contextmanager
def shared_lock(folder, timeout=240):
    from .engine import output_lock
    deadline = time.monotonic() + timeout
    while True:
        manager = output_lock(folder)
        try:
            manager.__enter__()
            break
        except ValueError as error:
            if str(error) != '같은 출력 폴더에서 다른 변환이 실행 중입니다.' or time.monotonic() >= deadline:
                raise
            time.sleep(0.1)
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


def cache_root() -> Path:
    if os.environ.get('TOKENSAVER_DOCS_CACHE_DIR'):
        return Path(os.environ['TOKENSAVER_DOCS_CACHE_DIR'])
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    return base / 'tokensaver-docs/cache'


def convert_shared(source, output, *, cache_dir, refresh, profiles, vision_pages, chunk_seconds, transcribe_images=False, source_root=None, image_mode=None, image_model_key=None):
    from .engine import _convert_local, discover, format_version, output_lock, image_link, IMAGES, AUDIO
    from .providers import IMAGE_PROMPT_VERSION
    source, output, cache_dir = Path(source).absolute(), Path(output).absolute(), Path(cache_dir).absolute()
    if source.is_symlink() or output.is_symlink() or cache_dir.is_symlink():
        raise ValueError('입력·출력·공통 캐시의 심볼릭 링크는 허용하지 않습니다.')
    if source.resolve() == output.resolve() or source.resolve().is_relative_to(output.resolve()):
        raise ValueError('출력 폴더는 입력 파일 또는 그 상위 폴더와 달라야 합니다.')
    if not 1 < chunk_seconds <= 300:
        raise ValueError('오디오 구간은 2~300초로 지정하세요.')
    if cache_dir.resolve().is_relative_to(source.resolve()) and source.is_dir():
        raise ValueError('공통 캐시는 입력 폴더 밖에 두세요.')
    root = Path(source_root).absolute() if source_root is not None else (source if source.is_dir() else source.parent)
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    results = []
    failed_units = {}
    refreshed_units = {}
    for path in discover(source, output):
        if path.suffix.lower() in ('.html', '.htm'):
            from .html_document import convert_html
            try:
                results.append(convert_html(path, output, cache_dir=cache_dir, source_root=root, profiles=profiles, transcribe_images=transcribe_images, refresh=refresh, failed_units=failed_units, refreshed_units=refreshed_units, image_mode=image_mode, image_model_key=image_model_key))
            except (ValueError, OSError) as error:
                results.append({'file': str(path), 'status': '실패', 'detail': str(error)})
            continue
        if path.stat().st_size > 100 * 1024 * 1024:
            results.append({'file': str(path), 'status': '실패', 'detail': '원본이 100MiB를 초과합니다. 파일을 나눠 주세요.'})
            continue
        try:
            version = format_version(path)
        except (OSError, zipfile.BadZipFile):
            results.append({'file': str(path), 'status': '실패', 'detail': '파일 처리 실패. 원본과 형식을 확인하세요.'})
            continue
        source_hash = file_hash(path)
        identity = {'hash': source_hash, 'format': path.suffix.lower(), 'pages': sorted(vision_pages or []), 'chunk': chunk_seconds if path.suffix.lower() in {'.wav','.mp3','.m4a','.ogg','.flac','.aac','.mp4'} else None}
        if version > 1:
            identity['version'] = version
        if path.suffix.lower() not in AUDIO:
            identity['image_policy'] = IMAGE_PROMPT_VERSION
            if transcribe_images is not None:
                identity['image_analysis'] = transcribe_images
            if image_mode is not None:
                identity['image_mode'] = image_mode
            if image_model_key is not None:
                identity['image_model_key'] = image_model_key
        key = digest(json.dumps(identity, sort_keys=True).encode())
        folder = cache_dir / key
        if folder.is_symlink():
            raise ValueError('공통 캐시 객체에 심볼릭 링크를 사용할 수 없습니다.')
        folder.mkdir(exist_ok=True, mode=0o700)
        with shared_lock(folder):
            entry_path = folder / 'entry.json'
            if entry_path.is_symlink():
                raise ValueError('공통 캐시 파일에 심볼릭 링크를 사용할 수 없습니다.')
            entry = None
            if entry_path.exists() and not refresh:
                try:
                    entry = json.loads(entry_path.read_text(encoding='utf-8'))
                    if entry['identity'] != identity or entry['body_hash'] != digest(entry['body'].encode()) or entry['record']['status'] not in ('완료', '확인필요'):
                        raise ValueError()
                    if image_mode != 'placeholder' and identity['format'] == '.pdf' and any(
                        not {'provider', 'model'} <= entry['record']['units'].get(f'page-{page}', {}).keys()
                        for page in identity['pages']
                    ):
                        raise ValueError()
                    if identity['format'] in ('.docx', '.xlsx') and entry['record'].get('images', 0):
                        entry = None
                except (ValueError, KeyError, TypeError):
                    raise ValueError('공통 캐시 무결성을 확인할 수 없습니다. 기존 결과를 보존했습니다. 명시적으로 재변환하세요.') from None
            relative = str(path.relative_to(root)) + '.md'
            if entry:
                if file_hash(path) != source_hash:
                    raise ValueError('변환 확인 중 원본이 변경됐습니다. 다시 확인하세요.')
                with output_lock(output):
                    state = load_state(output)
                    previous = state['records'].get(relative, {})
                    current = output / previous.get('current_output', relative)
                    if current.is_symlink() or not current.resolve().is_relative_to(output.resolve()):
                        raise ValueError('기존 출력 경로가 올바르지 않습니다.')
                    if previous and previous.get('source') != str(path.resolve()):
                        results.append({'file': str(path), 'status': '충돌', 'detail': '기존 결과를 보존했습니다. 다른 출력 폴더를 선택하세요.'})
                        continue
                    original_link = image_link(path, output, output / relative) if path.suffix.lower() in IMAGES and image_mode != 'placeholder' else ''
                    if original_link and file_hash(path) != source_hash:
                        raise ValueError('변환 확인 중 원본이 변경됐습니다. 다시 확인하세요.')
                    if previous.get('shared_key') == key and current.is_file() and previous.get('output_hash') == file_hash(current) and (not original_link or original_link in current.read_text(encoding='utf-8')):
                        results.append({'file': str(path), 'output': str(current), 'status': previous['status'], 'cached': True, 'ai_calls': 0, **{k: previous[k] for k in ('images', 'untranscribed_images', 'image_configuration_required', 'image_errors', 'image_mode') if k in previous}})
                        continue
                    record = copy.deepcopy(entry['record'])
                    header = f"# {path.name}\n\n원본: {path.resolve()}\n\n상태: {record['status']}\n"
                    provenance = sorted({u['provider'] + '/' + u['model'] for u in record.get('units', {}).values() if 'provider' in u and 'model' in u})
                    if provenance:
                        header += '\n전사 설정: ' + ', '.join(provenance) + '\n'
                    header += ''.join('\n> ' + w + '\n' for w in record.get('warnings', []))
                    body = entry['body']
                    if path.suffix.lower() in IMAGES and image_mode != 'placeholder':
                        _, marker, rest = body.partition('\n## ')
                        if not marker or not body.startswith('## 원본 이미지\n'):
                            raise ValueError('이미지 결과 캐시 형식을 확인할 수 없습니다.')
                        body = '## 원본 이미지\n\n' + original_link + '\n## ' + rest
                    published = publish_new(output / relative, header + '\n' + body)
                    history = list(previous.get('output_history', []))
                    if previous.get('current_output'):
                        history.append(previous['current_output'])
                    record.update(source=str(path.resolve()), shared_key=key, current_output=str(published.relative_to(output)), output_hash=file_hash(published), output_history=history, ai_calls=0)
                    state['records'][relative] = record
                    save_state(output, state)
                    results.append({'file': str(path), 'output': str(published), 'status': record['status'], 'cached': True, 'ai_calls': 0, **{k: record[k] for k in ('images', 'untranscribed_images', 'image_configuration_required', 'image_errors', 'image_mode') if k in record}})
            else:
                # Keep the existing per-output resume and file protection implementation.
                local = _convert_local(path, output, profiles=profiles, vision_pages=vision_pages, chunk_seconds=chunk_seconds, source_root=root, refresh=refresh, unit_store=UnitStore(cache_dir, refresh, failures=failed_units, successes=refreshed_units, image_model_key=image_model_key), shared_key=key, transcribe_images=transcribe_images, image_mode=image_mode, image_model_key=image_model_key)
                results.extend(local)
                if local and file_hash(path) != source_hash:
                    local[0].update(status='충돌', detail='변환 중 원본이 변경됐습니다. 생성 결과를 공통 캐시에 등록하지 않았습니다.')
                    continue
                if local and local[0]['status'] in ('완료','확인필요') and file_hash(path) == source_hash and not (path.suffix.lower() in ('.docx', '.xlsx') and local[0].get('images', 0)):
                    generated = Path(local[0]['output'])
                    with output_lock(output):
                        state = load_state(output)
                        record = copy.deepcopy(state['records'][relative])
                        content = generated.read_bytes()
                        if digest(content) != record.get('output_hash'):
                            local[0]['detail'] = '결과가 편집되어 공통 캐시에 등록하지 않았습니다.'
                            continue
                        for field in ('source', 'current_output', 'output_hash', 'output_history'):
                            record.pop(field, None)
                        text = content.decode('utf-8')
                        body = text[text.index('\n## ') + 1:]
                        atomic_write(entry_path, json.dumps({'identity':identity, 'body':body, 'body_hash':digest(body.encode()), 'record':record}, ensure_ascii=False))
                        state['records'][relative]['shared_key'] = key
                        save_state(output, state)
    return results


class UnitStore:
    """Content-addressed successful media units shared by different source files."""
    def __init__(self, root, refresh=False, failures=None, successes=None, image_model_key=None):
        self.root = Path(root) / 'units'
        if self.root.is_symlink():
            raise ValueError('구간 캐시 심볼릭 링크는 허용하지 않습니다.')
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.refresh = refresh
        self.image_model_key = image_model_key
        self.failures = failures if failures is not None else {}
        self.successes = successes if successes is not None else {}

    def obtain(self, asset, kind, producer):
        from .engine import output_lock
        from .providers import PROMPT_VERSION, IMAGE_PROMPT_VERSION
        policy = IMAGE_PROMPT_VERSION if kind == 'image' else PROMPT_VERSION
        identity = {'asset':file_hash(asset), 'kind':kind, 'policy':policy}
        if kind == 'image' and self.image_model_key is not None:
            identity['image_model_key'] = self.image_model_key
        key = digest(json.dumps(identity, sort_keys=True).encode())
        if key in self.failures:
            raise self.failures[key]
        folder = self.root / key
        if folder.is_symlink():
            raise ValueError('구간 캐시 경로가 올바르지 않습니다.')
        folder.mkdir(exist_ok=True, mode=0o700)
        with shared_lock(folder):
            if key in self.failures:
                raise self.failures[key]
            if self.refresh and key in self.successes:
                return self.successes[key], True
            path = folder / 'unit.json'
            if path.is_symlink():
                raise ValueError('구간 캐시 파일이 올바르지 않습니다.')
            if path.exists() and not self.refresh:
                entry = json.loads(path.read_text(encoding='utf-8'))
                record = entry['record']
                if entry['hash'] != digest(json.dumps(record, sort_keys=True).encode()):
                    raise ValueError('구간 캐시 무결성 확인 실패. 명시적으로 재변환하세요.')
                return record, True
            try:
                record = producer()
            except Exception as error:
                self.failures[key] = error
                raise
            atomic_write(path, json.dumps({'record':record, 'hash':digest(json.dumps(record, sort_keys=True).encode())}, ensure_ascii=False))
            if self.refresh:
                self.successes[key] = record
            return record, False
