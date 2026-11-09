"""구간 단위 변환, 충돌 방지, 중단 후 재개."""

import json
import os
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

from . import media, providers
from .extractors import extract, image_units
from .storage import digest, file_hash, load_state, save_state, publish_new

IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
AUDIO = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac', '.mp4'}
DOCUMENTS = {'.pdf', '.docx', '.xlsx', '.html', '.htm'}
SUPPORTED = IMAGES | AUDIO | DOCUMENTS
EXCLUDED = {'.git', '.venv', '.worker-context', '__pycache__', '.file-to-md', 'node_modules'}


def discover(source: Path, output: Path, *, include_markdown: bool = False) -> list[Path]:
    source, output = Path(source).absolute(), Path(output).resolve()
    if source.is_symlink():
        raise ValueError('입력 심볼릭 링크는 따라가지 않습니다.')
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise ValueError('입력 파일 또는 폴더가 없습니다.')
    import os
    found = []
    for directory, dirs, files in os.walk(source, followlinks=False):
        base = Path(directory)
        dirs[:] = [d for d in dirs if d not in EXCLUDED and not d.startswith('.') and not (base / d).is_symlink() and not (base / d).resolve().is_relative_to(output)]
        for name in files:
            p = base / name
            if not p.is_symlink() and (p.suffix.lower() in SUPPORTED or (include_markdown and p.suffix.lower() == '.md')) and not p.resolve().is_relative_to(output):
                found.append(p)
    return sorted(found)


@contextmanager
def output_lock(output: Path):
    import os
    output.mkdir(parents=True, exist_ok=True)
    cache = output / '.file-to-md'
    if cache.is_symlink():
        raise ValueError('캐시 폴더 심볼릭 링크는 허용하지 않습니다.')
    cache.mkdir(exist_ok=True)
    lock = cache / 'lock'
    if lock.is_symlink():
        raise ValueError('잠금 파일 심볼릭 링크는 허용하지 않습니다.')
    with lock.open('a+b') as f:
        try:
            if os.name == 'nt':
                import msvcrt
                f.seek(0, 2)
                if f.tell() == 0:
                    f.write(b'\0')
                    f.flush()
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            raise ValueError('같은 출력 폴더에서 다른 변환이 실행 중입니다.') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def units(path: Path, folder: Path, vision_pages: set[int], chunk_seconds: int):
    suffix = path.suffix.lower()
    if suffix in DOCUMENTS:
        yield from extract(path, folder, vision_pages)
    elif suffix in IMAGES:
        yield from image_units('image', '이미지 전사', path, folder)
    elif suffix in AUDIO:
        pcm = media.pcm_audio(path, folder / '원본.wav')
        for i, (start, end) in enumerate(media.intervals(media.duration(pcm), chunk_seconds, 1)):
            yield {'id': f'audio-{i}', 'title': f'오디오 {start:.3f}–{end:.3f}초', 'kind': 'audio', 'path': pcm, 'start': start, 'end': end}
    else:
        raise ValueError('지원하지 않는 형식입니다. .doc/.xls는 .docx/.xlsx로 저장한 사본을 사용하세요.')


def resolve_image_mode(image_mode, transcribe_images):
    if transcribe_images is not None and type(transcribe_images) is not bool:
        raise ValueError('이미지 내용 정리 선택은 true 또는 false여야 합니다.')
    if image_mode is not None:
        if image_mode not in ('analyze', 'preserve', 'placeholder'):
            raise ValueError('이미지 처리 방식이 올바르지 않습니다.')
        legacy = 'analyze' if transcribe_images else 'preserve'
        if transcribe_images is not None and image_mode != legacy:
            raise ValueError('이미지 처리 방식과 기존 이미지 선택이 서로 다릅니다.')
    return image_mode


def convert(source: Path, output: Path, *, profiles: dict | None = None,
            vision_pages: set[int] | None = None, chunk_seconds: int = 60,
            cache_dir: Path | None = None, refresh: bool = False,
            transcribe_images: bool | None = None, source_root: Path | None = None,
            image_mode: str | None = None, image_model_key: str | None = None) -> list[dict]:
    image_mode = resolve_image_mode(image_mode, transcribe_images)
    if image_mode is not None:
        transcribe_images = image_mode == 'analyze'
    if cache_dir is not None:
        from .shared_cache import convert_shared
        return convert_shared(source, output, cache_dir=cache_dir, refresh=refresh,
                              profiles=profiles, vision_pages=vision_pages, chunk_seconds=chunk_seconds, transcribe_images=transcribe_images, source_root=source_root, image_mode=image_mode, image_model_key=image_model_key)
    source, output = Path(source), Path(output)
    if any(p.suffix.lower() in ('.html', '.htm') for p in discover(source, output)):
        from .html_document import convert_html, checked_folder
        from .shared_cache import UnitStore
        root = Path(source_root) if source_root is not None else (source if source.is_dir() else source.parent)
        results = []
        failed_units, refreshed_units = {}, {}
        image_store = None
        if transcribe_images:
            if source.is_symlink() or output.is_symlink() or source.resolve().is_relative_to(output.resolve()):
                raise ValueError('입력·출력 경로를 확인하세요.')
            cache = checked_folder(output / '.file-to-md/html-cache', output)
            image_store = UnitStore(cache, refresh=refresh, failures=failed_units, successes=refreshed_units, image_model_key=image_model_key)
        for path in discover(source, output):
            if path.suffix.lower() in ('.html', '.htm'):
                try:
                    results.append(convert_html(path, output, cache_dir=output/'.file-to-md/html-cache', source_root=root, profiles=profiles, transcribe_images=transcribe_images, refresh=refresh, failed_units=failed_units, refreshed_units=refreshed_units, image_mode=image_mode, image_model_key=image_model_key))
                except (ValueError, OSError) as error:
                    results.append({'file': str(path), 'status': '실패', 'detail': str(error)})
            else:
                results.extend(_convert_local(path, output, source_root=root, profiles=profiles, vision_pages=vision_pages, chunk_seconds=chunk_seconds, refresh=refresh, transcribe_images=transcribe_images, image_store=image_store, image_mode=image_mode, image_model_key=image_model_key))
        return results
    return _convert_local(source, output, profiles=profiles, vision_pages=vision_pages, chunk_seconds=chunk_seconds, refresh=refresh, transcribe_images=transcribe_images, source_root=source_root, image_mode=image_mode, image_model_key=image_model_key)


def format_version(path: Path) -> int:
    if path.suffix.lower() == '.docx':
        return 3
    if path.suffix.lower() in IMAGES | {'.pdf'}:
        return 2
    if path.suffix.lower() == '.xlsx':
        with zipfile.ZipFile(path) as archive:
            if any(name.startswith('xl/media/') for name in archive.namelist()):
                return 3
    return 1


def image_link(source: Path, output: Path, target: Path) -> str:
    from .html_document import checked_folder, store_image
    assets = checked_folder(output / 'assets', output)
    saved = store_image(assets, source.read_bytes())
    alt = source.name.replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ').replace('\r', ' ')
    return '![' + alt + '](' + Path(os.path.relpath(saved, target.parent)).as_posix() + ')\n\n'


def _convert_local(source: Path, output: Path, *, profiles: dict | None = None,
                   vision_pages: set[int] | None = None, chunk_seconds: int = 60,
                   source_root: Path | None = None, refresh: bool = False, unit_store=None,
                   shared_key: str | None = None, transcribe_images: bool | None = None,
                   image_store=None, image_mode: str | None = None, image_model_key: str | None = None) -> list[dict]:
    if Path(source).is_symlink():
        raise ValueError('입력 심볼릭 링크는 따라가지 않습니다.')
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.is_symlink():
        raise ValueError('출력 폴더 심볼릭 링크는 허용하지 않습니다.')
    output = output.resolve()
    if source == output or source.is_relative_to(output):
        raise ValueError('출력 폴더는 입력 파일 또는 그 상위 폴더와 달라야 합니다.')
    if chunk_seconds <= 1 or chunk_seconds > 300:
        raise ValueError('오디오 구간은 2~300초로 지정하세요.')
    files = discover(source, output)
    root = source_root.resolve() if source_root is not None else (source if source.is_dir() else source.parent)
    profiles, vision_pages = profiles or {}, vision_pages or set()
    results = []
    with output_lock(output):
        state = load_state(output)
        for path in files:
            relative = str(path.relative_to(root)) + '.md'
            target = output / relative
            previous = state['records'].get(relative)
            current = output / (previous.get('current_output', relative) if previous else relative)
            conflict = (target.is_symlink() or not target.resolve().is_relative_to(output)
                        or current.is_symlink() or not current.resolve().is_relative_to(output)
                        or (previous and previous.get('source') != str(path)))
            if conflict:
                results.append({'file': str(path), 'output': str(target), 'status': '충돌', 'detail': '기존 결과 또는 사용자 편집을 보존했습니다. 다른 출력 폴더를 선택하세요.'})
                continue
            try:
                if path.stat().st_size > 100 * 1024 * 1024:
                    raise ValueError('원본이 100MiB를 초과합니다. 파일을 나눠 주세요.')
                kind = 'audio' if path.suffix.lower() in AUDIO else 'image'
                effective = {kind: profiles[kind]} if kind in profiles else {}
                source_image_link = ''
                if path.suffix.lower() in IMAGES and image_mode != 'placeholder':
                    source_image_link = image_link(path, output, target)
                local_files = None
                if kind == 'audio' and effective.get(kind, {}).get('provider') == 'whisper.cpp':
                    model_path, binary = providers.whisper_paths(effective[kind]['model'])
                    local_files = {'model': file_hash(model_path), 'binary': file_hash(Path(binary))}
                # 수정 대상 형식의 과거 누락 결과만 무효화하고 오디오·엑셀 캐시는 보존한다.
                signature_data = {'source': file_hash(path), 'profiles': effective, 'pages': sorted(vision_pages) if path.suffix.lower() == '.pdf' else [], 'chunk': chunk_seconds if kind == 'audio' else None, 'version': format_version(path), 'prompt': providers.PROMPT_VERSION}
                if kind == 'image':
                    signature_data['image_policy'] = providers.IMAGE_PROMPT_VERSION
                    if transcribe_images is not None:
                        signature_data['image_analysis'] = transcribe_images
                    if image_mode is not None:
                        signature_data['image_mode'] = image_mode
                    if image_model_key is not None:
                        signature_data['image_model_key'] = image_model_key
                if local_files:
                    signature_data['local_files'] = local_files
                signature = digest(json.dumps(signature_data, sort_keys=True).encode())
                reassemble_assets = bool(path.suffix.lower() in ('.docx', '.xlsx') and previous and previous.get('images', 0))
                if unit_store is not None and not reassemble_assets and not refresh and previous and previous.get('status') in ('완료','확인필요') and current.is_file() and previous.get('output_hash') == file_hash(current):
                    if previous.get('signature') == signature or (shared_key and previous.get('shared_key') == shared_key):
                        results.append({'file':str(path), 'output':str(current), 'status':previous['status'], 'ai_calls':0, 'cached':True, **{k: previous[k] for k in ('images', 'untranscribed_images', 'image_configuration_required', 'image_errors', 'image_mode') if k in previous}})
                        continue
                    if not previous.get('shared_key') and ('source_hash' not in previous or previous['source_hash'] == signature_data['source']):
                        results.append({'file':str(path), 'output':str(current), 'status':'차단', 'detail':'이전 원본 연결을 검증할 수 없습니다. 결과를 보존했습니다. 필요하면 --refresh로 다시 변환하세요.'})
                        continue
                if not refresh and not reassemble_assets and previous and previous.get('signature') == signature and previous.get('status') in ('완료', '확인필요') and current.is_file() and previous.get('output_hash') == file_hash(current):
                    results.append({'file': str(path), 'output': str(current), 'status': previous['status'], 'ai_calls': 0, 'cached': True, **{k: previous[k] for k in ('images', 'untranscribed_images', 'image_configuration_required', 'image_errors', 'image_mode') if k in previous}})
                    continue
                record = previous if not refresh and previous and previous.get('signature') == signature else {'source': str(path), 'signature': signature, 'units': {}, 'output_hash': previous.get('output_hash') if previous else None, 'output_history': list(previous.get('output_history', [])) if previous else []}
                if previous and 'current_output' not in record:
                    record['current_output'] = previous.get('current_output', relative)
                state['records'][relative] = record
                record['source_hash'] = signature_data['source']
                parts, failures, warnings, ai_calls = [], [], [], 0
                images = untranscribed = image_errors = 0
                image_configuration_required = False
                if source_image_link:
                    parts.append('## 원본 이미지\n\n' + source_image_link)
                with tempfile.TemporaryDirectory(prefix='file-to-md-media-') as temporary:
                    folder = Path(temporary)
                    conversion_units = ([{'id': 'image', 'title': '이미지', 'kind': 'image'}]
                                        if image_mode == 'placeholder' and path.suffix.lower() in IMAGES
                                        else units(path, folder, vision_pages, chunk_seconds))
                    for unit in conversion_units:
                        key = unit['id']
                        unit_link = ''
                        if unit.get('kind') == 'image':
                            images += 1
                            if image_mode != 'placeholder' and path.suffix.lower() in ('.docx', '.xlsx') and unit.get('original_image'):
                                unit_link = image_link(unit['original_image'], output, target)
                            if image_mode == 'placeholder':
                                untranscribed += 1
                                warnings.append('이미지 내용 정리 안 함: 이미지 위치만 표시했습니다.')
                                parts.append(f"## {unit['title']}\n\n[이미지]\n")
                                continue
                            if transcribe_images is False:
                                untranscribed += 1
                                warnings.append('이미지 내용 정리 안 함')
                                parts.append(f"## {unit['title']}\n\n{unit_link}[이미지 내용 정리 안 함]\n")
                                continue
                        stored = record['units'].get(key)
                        warning = unit.get('warning', '')
                        if warning:
                            warnings.append(warning)
                        if stored:
                            text = stored['text']
                        elif 'text' in unit:
                            text = unit['text']
                            record['units'][key] = {'text': text}
                            save_state(output, state)
                        else:
                            kind = unit['kind']
                            profile = profiles.get(kind)
                            if not profile and unit_store is None:
                                if kind == 'image':
                                    untranscribed += 1
                                    image_configuration_required = True
                                failures.append('차단')
                                parts.append(f"## {unit['title']}\n\n{unit_link}[차단: {kind} 제공자와 모델을 설정하세요.]\n")
                                continue
                            try:
                                if kind == 'audio':
                                    if profile and profile.get('provider') in ('codex', 'claude'):
                                        raise providers.ConversionError('이 명령줄 연결은 오디오 직접 입력을 지원하지 않습니다.')
                                    asset = media.audio_chunk(unit['path'], unit['start'], unit['end'], folder / f'{key}.wav')
                                elif 'pdf_page' in unit:
                                    asset = media.pdf_image(path, unit['pdf_page'], folder)
                                else:
                                    asset = media.normalize_image(unit['path'], folder / f'{key}.png')
                                image_key = file_hash(asset) if kind == 'image' and path.suffix.lower() in ('.docx', '.xlsx') else None
                                cached_image = record.get('image_cache', {}).get(image_key) if image_key else None
                                if cached_image:
                                    record['units'][key] = cached_image
                                else:
                                    def generate_unit():
                                        nonlocal ai_calls
                                        if not profile:
                                            raise providers.ProviderRequired('제공자와 모델을 설정하세요. 완료된 구간은 보존됩니다.')
                                        ai_calls += 1
                                        result = providers.generate(asset, kind, profile)
                                        return {'text': providers.checked_text(result.get('text')), 'usage': result.get('usage', {}), 'provider': profile['provider'], 'model': profile['model']}
                                    if kind == 'image':
                                        from .image_analysis import analyze_image
                                        def count_call():
                                            nonlocal ai_calls
                                            ai_calls += 1
                                        record['units'][key], _ = analyze_image(asset, profile, image_store or unit_store, on_call=count_call)
                                    elif unit_store is not None:
                                        record['units'][key], _ = unit_store.obtain(asset, kind, generate_unit)
                                    else:
                                        record['units'][key] = generate_unit()
                                    if image_key:
                                        record.setdefault('image_cache', {})[image_key] = record['units'][key]
                                text = record['units'][key]['text']
                                save_state(output, state)
                            except (providers.ConversionError, ValueError, RuntimeError, OSError) as error:
                                if kind == 'image':
                                    untranscribed += 1
                                    if isinstance(error, providers.ProviderRequired):
                                        image_configuration_required = True
                                    else:
                                        image_errors += 1
                                message = str(error) if isinstance(error, (providers.ConversionError, ValueError)) else '해당 구간 처리 실패. 다시 실행하면 미완료 구간부터 처리합니다.'
                                failures.append('차단' if isinstance(error, providers.ProviderRequired) else '실패')
                                parts.append(f"## {unit['title']}\n\n{unit_link}[확인 필요: {message}]\n")
                                continue
                        part = f"## {unit['title']}\n\n{unit_link}{text}\n"
                        if warning:
                            part += '\n> 확인 필요: ' + warning + '\n'
                        parts.append(part)
                if not parts:
                    raise ValueError('추출할 내용이 없습니다. 원본을 확인하세요.')
                if path.suffix.lower() in AUDIO:
                    warnings.append('오디오 구간은 1초 겹칩니다. 경계의 반복 전사는 자동 삭제하지 않습니다. 표기 시간은 구간 기준입니다.')
                status = '부분완료' if failures and record['units'] else ('차단' if failures and all(f == '차단' for f in failures) else '실패' if failures else '확인필요' if warnings else '완료')
                header = f'# {path.name}\n\n원본: {path}\n\n상태: {status}\n'
                if effective:
                    header += '\n선택 설정: ' + ', '.join(f"{k}={v['provider']}/{v['model']}" for k, v in effective.items()) + '\n'
                text = header + ''.join('\n> ' + w + '\n' for w in dict.fromkeys(warnings)) + '\n' + '\n'.join(parts)
                if reassemble_assets and not refresh and previous.get('output_hash') and current.is_file() and previous['output_hash'] == file_hash(current) and current.read_text(encoding='utf-8') == text:
                    published = current
                else:
                    published = publish_new(target, text)
                if previous and current.exists() and published != current:
                    old = str(current.relative_to(output))
                    if old not in record.setdefault('output_history', []):
                        record['output_history'].append(old)
                record.update(current_output=str(published.relative_to(output)), output_hash=file_hash(published), status=status, warnings=list(dict.fromkeys(warnings)), ai_calls=ai_calls)
                if path.suffix.lower() not in AUDIO:
                    record.update(images=images, untranscribed_images=untranscribed, image_configuration_required=image_configuration_required, image_errors=image_errors, image_analysis=transcribe_images)
                    if image_mode is not None:
                        record['image_mode'] = image_mode
                    if image_model_key is not None:
                        record['image_model_key'] = image_model_key
                save_state(output, state)
                result = {'file': str(path), 'output': str(published), 'status': status, 'ai_calls': ai_calls}
                if kind != 'audio':
                    result.update(images=images, untranscribed_images=untranscribed, image_configuration_required=image_configuration_required, image_errors=image_errors)
                    if image_mode is not None:
                        result['image_mode'] = image_mode
                if images and not ai_calls and not untranscribed:
                    result['cached'] = True
                results.append(result)
            except (Exception, KeyboardInterrupt) as error:
                if isinstance(error, KeyboardInterrupt):
                    save_state(output, state)
                    raise
                message = str(error) if isinstance(error, (ValueError, providers.ConversionError)) else f'파일 처리 실패 ({type(error).__name__}). 원본과 형식을 확인하세요.'
                failed_record = state['records'].get(relative)
                if failed_record:
                    failed_record['status'] = '실패'
                    failed_record['detail'] = message
                    save_state(output, state)
                results.append({'file': str(path), 'status': '실패', 'detail': message})
    return results
