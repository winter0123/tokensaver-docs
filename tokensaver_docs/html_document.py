# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Deterministic local HTML preparation; models never need to read raw HTML."""
import base64
import io
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from markdownify import markdownify
from PIL import Image

from . import media, providers
from .storage import atomic_write, digest, file_hash, load_state, publish_bytes, publish_new, save_state
from .shared_cache import shared_lock, UnitStore
from .image_analysis import analyze_image

LIMIT = 100 * 1024 * 1024
HTML_VERSION = 3
FORMATS = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp', 'GIF': '.gif', 'BMP': '.bmp', 'TIFF': '.tiff'}


def checked_folder(path, boundary):
    path = Path(path).absolute()
    boundary = Path(boundary).absolute()
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(boundary)):
        raise ValueError('이미지·캐시 폴더에 심볼릭 링크를 사용할 수 없습니다.')
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_label(item, source, number):
    candidates = [item['alt'], Path(unquote(urlsplit(item['ref']).path)).stem, source.stem]
    for candidate in candidates:
        words = re.findall(r'[A-Za-z][A-Za-z0-9]*', candidate)
        words = [w.lower() for w in words if w.lower() not in ('data', 'image', 'img', 'png', 'jpg', 'jpeg', 'screenshot')]
        if words:
            label = '-'.join(words)[:50].strip('-')
            if label.upper() not in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
                return label + f'-image-{number+1:02d}'
    return f'document-image-{number+1:02d}'


def store_image(folder, data, label=None):
    if len(data) > LIMIT:
        raise ValueError('이미지가 100MiB를 초과합니다.')
    with Image.open(io.BytesIO(data)) as image:
        suffix = FORMATS.get(image.format)
        if not suffix:
            raise ValueError('지원하지 않는 이미지 형식입니다.')
        try:
            image.verify()
        except SyntaxError as error:
            raise ValueError('이미지 파일이 손상됐습니다.') from error
    name = label + '-' + digest(data)[:12] if label else digest(data)
    path = folder / (name + suffix)
    if path.is_symlink():
        raise ValueError('이미지 경로가 올바르지 않습니다.')
    if path.is_file() and file_hash(path) == digest(data):
        return path
    return publish_bytes(path, data)


def decode_html(data):
    if data.startswith(b'\xef\xbb\xbf'):
        return data.decode('utf-8-sig')
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    meta = re.search(br'<meta\b[^>]*charset\s*=\s*[\"\x27]?\s*([a-zA-Z0-9_-]+)', data[:8192], re.I)
    encoding = meta.group(1).decode('ascii') if meta else 'utf-8'
    try:
        return data.decode(encoding)
    except (LookupError, UnicodeError):
        raise ValueError('HTML 인코딩을 확인할 수 없습니다. UTF-8 사본을 사용하세요.') from None


def parse_html(data, blobs, *, preserve_images=True):
    soup = BeautifulSoup(decode_html(data), 'html.parser')
    warnings = []
    if soup.find(['script', 'iframe', 'canvas', 'svg']):
        warnings.append('스크립트·동적 또는 외부 콘텐츠는 실행하지 않았습니다.')
    styles = [node.decode_contents() for node in soup.find_all('style')]
    styles.extend(node['style'] for node in soup.find_all(style=True))
    if soup.find('link', rel=lambda value: value and 'stylesheet' in value) or any(
        re.search(r'@import\b|(?<![\w-])background(?:-image)?\s*:', style, re.I) for style in styles
    ):
        warnings.append('CSS 배경 이미지가 포함될 수 있으나 추출하지 않았습니다. 원본을 확인하세요.')
    if soup.find(attrs={'colspan': True}) or soup.find(attrs={'rowspan': True}):
        warnings.append('병합 셀의 정확한 배치는 원본에서 확인하세요.')
    base = soup.find('base')
    base_href = base.get('href', '') if base else ''
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    for node in soup.find_all(['script', 'style', 'template', 'head', 'colgroup']):
        node.decompose()
    resources = []
    prefix = 'FTMDIMAGE' + digest(data)[:16]
    for index, node in enumerate(soup.find_all('img')):
        token = prefix + str(index) + 'END'
        src = str(node.get('src', ''))
        item = {'token': token, 'alt': str(node.get('alt', '')), 'ref': src}
        if src.lower().startswith('data:'):
            item['ref'] = '내장 이미지'
            if preserve_images:
                try:
                    head, payload = src.split(',', 1)
                    if not re.fullmatch(r'data:image/(?:png|jpeg|jpg|webp|gif|bmp|tiff);base64', head, re.I):
                        raise ValueError()
                    data_image = base64.b64decode(payload, validate=True)
                    item['blob'] = store_image(blobs, data_image).name
                    item['hash'] = digest(data_image)
                except (ValueError, OSError, Image.DecompressionBombError):
                    item['error'] = '내장 이미지 형식·크기를 확인하세요.'
        resources.append(item)
        node.replace_with('\n\n' + token + '\n\n')
    for node in soup.find_all('a', href=True):
        if urlsplit(node['href'].strip()).scheme.lower() not in ('', 'http', 'https', 'mailto'):
            node.attrs.pop('href', None)
    text = markdownify(str(soup), heading_style='ATX', bs4_options='html.parser').strip()
    if title:
        text = '# ' + title + '\n\n' + text
    if not text:
        if warnings:
            text = '(정적 본문이 없습니다. 원본을 확인하세요.)'
        else:
            raise ValueError('추출할 HTML 본문이 없습니다.')
    return {'text': text, 'resources': resources, 'base': base_href, 'warnings': warnings}


def local_image(source, ref, base):
    parts = urlsplit(ref)
    if base or parts.scheme or parts.netloc or not parts.path or '\\' in parts.path:
        raise ValueError('외부·절대 주소 또는 base 경로의 이미지는 자동으로 읽지 않습니다.')
    path = Path(unquote(parts.path))
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('HTML 폴더 밖의 이미지는 자동으로 읽지 않습니다.')
    candidate = source.parent / path
    if any(p.is_symlink() for p in (candidate, *candidate.parents) if p != source.parent and p.is_relative_to(source.parent)):
        raise ValueError('이미지 심볼릭 링크는 따라가지 않습니다.')
    if not candidate.resolve().is_relative_to(source.parent.resolve()) or not candidate.is_file():
        raise ValueError('연결된 로컬 이미지가 없습니다.')
    if candidate.stat().st_size > LIMIT:
        raise ValueError('이미지가 100MiB를 초과합니다.')
    return candidate.read_bytes()


def convert_html(source, output, *, cache_dir, source_root, profiles=None, transcribe_images=False, refresh=False, failed_units=None, refreshed_units=None, image_mode=None, image_model_key=None):
    if image_mode not in (None, 'analyze', 'preserve', 'placeholder'):
        raise ValueError('이미지 처리 방식은 analyze, preserve, placeholder 중에서 선택하세요.')
    mode = image_mode or ('analyze' if transcribe_images else 'preserve')
    transcribe_images = mode == 'analyze'
    source, output, cache_dir = Path(source).resolve(), Path(output).absolute(), Path(cache_dir).absolute()
    if output.is_symlink() or cache_dir.is_symlink() or source == output or source.is_relative_to(output.resolve()):
        raise ValueError('HTML 출력·캐시 경로를 확인하세요.')
    if source.stat().st_size > LIMIT:
        raise ValueError('HTML이 100MiB를 초과합니다.')
    folder = checked_folder(cache_dir / 'html', cache_dir)
    blobs = checked_folder(folder / 'images', cache_dir)
    data = source.read_bytes()
    key = digest(data)
    structure_policy = f'html-{HTML_VERSION}' + ('-placeholder' if mode == 'placeholder' else '')
    structure = checked_folder(folder / digest(f'{structure_policy}:'.encode() + data), cache_dir)
    relative = str(source.relative_to(Path(source_root).resolve())) + '.md'
    with shared_lock(structure):
        parsed_path = structure / 'parsed.json'
        if parsed_path.is_symlink():
            raise ValueError('HTML 캐시 경로가 올바르지 않습니다.')
        reused = parsed_path.exists() and not refresh
        if reused:
            try:
                entry = json.loads(parsed_path.read_text(encoding='utf-8'))
                parsed = entry['document']
                if entry['hash'] != digest(json.dumps(parsed, sort_keys=True).encode()) or not isinstance(parsed['text'], str) or not isinstance(parsed['resources'], list):
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise ValueError('HTML 캐시 무결성 확인 실패. 명시적으로 재변환하세요.') from None
        else:
            parsed = parse_html(data, blobs, preserve_images=mode != 'placeholder')
            atomic_write(parsed_path, json.dumps({'document': parsed, 'hash': digest(json.dumps(parsed, sort_keys=True).encode())}, ensure_ascii=False))
        # Lock order matches the other converters: source, output, then media unit.
        with shared_lock(output):
            target = output / relative
            if target.is_symlink() or not target.resolve().is_relative_to(output.resolve()):
                raise ValueError('HTML 출력 경로가 올바르지 않습니다.')
            assets = checked_folder(output / 'assets', output) if mode != 'placeholder' else None
            store_options = {'image_model_key': image_model_key} if image_model_key is not None else {}
            store = UnitStore(cache_dir, refresh=refresh, failures=failed_units, successes=refreshed_units, **store_options) if transcribe_images else None
            warnings = list(parsed['warnings'])
            text = parsed['text']
            calls = 0
            def count_call():
                nonlocal calls
                calls += 1
            total = 0
            failed = False
            configuration_required = False
            image_errors = 0
            completed_images = 0
            with tempfile.TemporaryDirectory(prefix='tokensaver-docs-html-') as tmp:
                for number, item in enumerate(parsed['resources']):
                    if mode == 'placeholder':
                        text = text.replace(item['token'], '[이미지]', 1)
                        warnings.append('이미지 내용은 정리하지 않고 [이미지]로 표시했습니다.')
                        continue
                    message = ''
                    replacement = '[이미지 확인 필요]\n\n'
                    try:
                        if item.get('error'):
                            raise ValueError(item['error'])
                        if 'blob' in item:
                            blob = blobs / item['blob']
                            if blob.is_symlink() or not blob.resolve().is_relative_to(blobs.resolve()):
                                raise ValueError('내장 이미지 캐시 경로가 올바르지 않습니다.')
                            image_data = blob.read_bytes()
                            if digest(image_data) != item['hash']:
                                raise ValueError('내장 이미지 캐시가 변경됐습니다.')
                        else:
                            image_data = local_image(source, item['ref'], parsed['base'])
                        total += len(image_data)
                        if total > LIMIT:
                            raise ValueError('문서 이미지 합계가 100MiB를 초과합니다.')
                        saved = store_image(assets, image_data, image_label(item, source, number))
                        link = Path(os.path.relpath(saved, target.parent)).as_posix()
                        alt = item['alt'].replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ') or '이미지'
                        replacement = f'![{alt}]({link})\n\n'
                        if not transcribe_images:
                            message = '이미지 내용 정리 안 함. 내용을 정리하려면 해당 옵션을 선택하세요.'
                            replacement += '> ' + message
                            warnings.append(message)
                        else:
                            image_failed = False
                            for frame, count, image in media.image_frames(saved, Path(tmp)):
                                try:
                                    normalized = media.normalize_image(image, Path(tmp) / f'{number}-{frame}.png')
                                    record, _ = analyze_image(normalized, (profiles or {}).get('image'), store, on_call=count_call)
                                    label = f'프레임 {frame}/{count}\n\n' if count > 1 else ''
                                    replacement += label + record['text'] + '\n\n'
                                except (ValueError, OSError, RuntimeError, Image.DecompressionBombError, providers.ConversionError) as error:
                                    image_failed = failed = True
                                    if isinstance(error, providers.ProviderRequired):
                                        configuration_required = True
                                    else:
                                        image_errors += 1
                                    message = str(error) if isinstance(error, (ValueError, providers.ConversionError)) else '이미지 처리 실패. 원본을 확인하세요.'
                                    label = f'프레임 {frame}/{count}: ' if count > 1 else ''
                                    replacement += '> ' + label + message + '\n\n'
                                    warnings.append(message)
                            if not image_failed:
                                completed_images += 1
                    except (ValueError, OSError, RuntimeError, Image.DecompressionBombError, providers.ConversionError) as error:
                        if isinstance(error, providers.ProviderRequired):
                            configuration_required = True
                        else:
                            image_errors += 1
                        message = str(error) if isinstance(error, (ValueError, providers.ConversionError)) else '이미지 처리 실패. 원본을 확인하세요.'
                        if transcribe_images:
                            failed = True
                        replacement += '> ' + message
                        warnings.append(message)
                    text = text.replace(item['token'], replacement, 1)
            if file_hash(source) != key:
                raise ValueError('변환 중 HTML 원본이 변경됐습니다.')
            status = '부분완료' if failed else '확인필요' if warnings else '완료'
            body = '## HTML 본문\n\n' + ''.join('> 확인 필요: ' + w + '\n\n' for w in parsed['warnings']) + text + '\n'
            signature_data = {'body': body, 'image_mode': mode, 'image_model_key': image_model_key}
            signature = digest(json.dumps(signature_data, sort_keys=True).encode())
            state = load_state(output)
            previous = state['records'].get(relative, {})
            current = output / previous.get('current_output', relative)
            if current.is_symlink() or not current.resolve().is_relative_to(output.resolve()):
                raise ValueError('HTML 상태의 출력 경로가 올바르지 않습니다.')
            if previous.get('source') not in (None, str(source)) and previous.get('source_hash') != key:
                return {'file': str(source), 'status': '충돌', 'ai_calls': calls}
            if not refresh and previous.get('source') == str(source) and previous.get('signature') == signature and current.is_file() and previous.get('output_hash') == file_hash(current):
                if previous.get('image_analysis') is not bool(transcribe_images) or previous.get('image_errors') != image_errors or previous.get('image_mode') != mode:
                    previous.update(image_analysis=bool(transcribe_images), image_errors=image_errors, image_mode=mode, image_model_key=image_model_key)
                    save_state(output, state)
                return {'file': str(source), 'output': str(current), 'status': status, 'cached': True, 'structure_cached': reused, 'ai_calls': calls, 'images': len(parsed['resources']), 'untranscribed_images': len(parsed['resources'])-completed_images, 'image_configuration_required': configuration_required, 'image_errors': image_errors, 'image_mode': mode}
            header = f'# {source.name}\n\n원본: {source}\n\n상태: {status}\n\n'
            published = publish_new(target, header + body)
            history = list(previous.get('output_history', []))
            if previous.get('current_output'):
                history.append(previous['current_output'])
            state['records'][relative] = {'source': str(source), 'source_hash': key, 'signature': signature, 'current_output': str(published.relative_to(output)), 'output_history': history, 'output_hash': file_hash(published), 'status': status, 'warnings': list(dict.fromkeys(warnings)), 'units': {}, 'ai_calls': calls, 'image_analysis': bool(transcribe_images), 'image_errors': image_errors, 'image_mode': mode, 'image_model_key': image_model_key}
            save_state(output, state)
            return {'file': str(source), 'output': str(published), 'status': status, 'structure_cached': reused, 'ai_calls': calls, 'images': len(parsed['resources']), 'untranscribed_images': len(parsed['resources'])-completed_images, 'image_configuration_required': configuration_required, 'image_errors': image_errors, 'image_mode': mode}
