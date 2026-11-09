"""Prepare documents and report an explicit image-content choice."""
import json
import tempfile
from pathlib import Path
from .engine import DOCUMENTS, IMAGES, convert, discover
from .shared_cache import cache_root
from .storage import load_profiles, digest


def _needs_image_choice(source, output):
    for path in discover(Path(source), Path(output)):
        if path.suffix.lower() in ('.html', '.htm'):
            from bs4 import BeautifulSoup
            from .html_document import LIMIT, decode_html
            if path.stat().st_size > LIMIT:
                return True
            try:
                document = BeautifulSoup(decode_html(path.read_bytes()), 'html.parser')
                if document.find(['img', 'picture', 'canvas', 'svg', 'iframe', 'script']):
                    return True
            except (OSError, ValueError):
                return True
        elif path.suffix.lower() in IMAGES:
            return True
        elif path.suffix.lower() in DOCUMENTS:
            from .extractors import extract
            try:
                with tempfile.TemporaryDirectory(prefix='file-to-md-inspect-') as temp:
                    for unit in extract(path, Path(temp)):
                        if unit.get('kind') == 'image' or any(word in unit.get('warning', '') for word in ('이미지', '그림', '차트', '도형', '개체')):
                            return True
            except Exception:
                # Unknown content must not be assumed to contain no images.
                return True
    return False


_UNSET = object()


def _choice(status, question, details, **metadata):
    return {'status': status, 'question': question,
            'choices': [d['label'] for d in details], 'choice_details': details,
            'ai_calls': 0, **metadata,
            'next': 'Ask the user using question and choice_details. Do not choose or send images on their behalf. Retry with their explicit image_mode/model choice. Never request API keys in chat.'}


def _model_choice(status, question, **metadata):
    return _choice(status, question, [
        {'label': '모델 바꾸기', 'action': 'select_model', 'description': '이미지 지원 모델을 선택해 이미지·이미지 속 글자·설명을 MD에 넣어요. 외부 서비스를 사용하면 이미지가 전송돼요.'},
        {'label': '현재 모델로 계속하기', 'image_mode': 'placeholder', 'description': '일반 글자는 변환하고 이미지가 있던 위치에는 [이미지]만 표시해요. 이미지 속 글자·설명·이미지 링크는 넣지 않아요.'},
    ], **metadata)


def prepare_documents(source, output='converted', *, transcribe_images=_UNSET,
                      image_mode=None, model_provider=None, model=None,
                      allow_unverified_model=False, onboarding=False):
    strict = onboarding or image_mode is not None or model_provider is not None or model is not None
    if transcribe_images is _UNSET:
        transcribe_images = None if strict else False
    if transcribe_images is not None and type(transcribe_images) is not bool:
        raise ValueError('이미지 내용 정리 선택은 true 또는 false여야 합니다.')
    if type(allow_unverified_model) is not bool or type(onboarding) is not bool:
        raise ValueError('확인되지 않은 모델 사용과 최초 안내는 true 또는 false여야 합니다.')
    if image_mode not in (None, 'analyze', 'preserve', 'placeholder'):
        raise ValueError('이미지 처리 방식은 analyze, preserve, placeholder 중 선택하세요.')
    legacy_mode = None if transcribe_images is None else 'analyze' if transcribe_images else 'preserve'
    if image_mode is not None and legacy_mode is not None and image_mode != legacy_mode:
        raise ValueError('이미지 처리 선택이 서로 다릅니다.')
    mode = image_mode or legacy_mode
    if bool(model_provider) != bool(model):
        raise ValueError('이번에 사용할 제공자와 모델을 함께 지정하세요.')
    override = None
    if model_provider is not None or model is not None:
        from .model_setup import validate_image_profile
        override = validate_image_profile({'provider': model_provider, 'model': model})
    selected = None
    if strict:
        from .model_setup import load_model_selection, setup_status
        selected = override or load_model_selection()
        if mode is None and not selected and setup_status()['status'] == 'setup_required':
            return _choice('setup_required', '변환에 사용할 모델을 선택할까요? 일반 문서의 글자는 모델을 선택하지 않아도 추출할 수 있어요.', [
                {'label': '모델 선택하기', 'action': 'select_model', 'description': '플러그인의 변환 모델을 선택해요. 대화 중인 모델과 다를 수 있어요.'},
                {'label': '나중에 선택하기', 'action': 'defer', 'description': '모델 설정을 미뤄요. 이미지가 있으면 처리 방법을 따로 물어봐요.'},
            ])
        has_images = _needs_image_choice(source, output)
        if has_images and mode in (None, 'analyze'):
            if not selected:
                return _model_choice('configuration_required', '이미지 처리 모델이 아직 선택되지 않았어요. 모델을 선택하거나 이미지 위치에 [이미지]만 표시할 수 있어요.')
            from .providers import inspect_image_model
            report = inspect_image_model(selected)
            metadata = {'model': selected, 'model_support': report}
            if report['capability'] == 'unsupported':
                return _model_choice('model_incompatible', '선택한 모델은 이미지를 읽을 수 없어요. 이미지 속 글자와 내용을 MD에 담으려면 이미지 지원 모델이 필요해요. 모델을 바꿀까요?', **metadata)
            if report.get('reason') == 'lookup_failed':
                return _model_choice('model_lookup_failed', '모델 정보를 조회하지 못했어요. 이미지 지원 여부를 확인한 뒤 모델을 선택하거나 [이미지]로 표시하고 계속할 수 있어요.', **metadata)
            if report['capability'] == 'unknown' and not allow_unverified_model:
                return _model_choice('model_support_unknown', '선택한 모델의 이미지 지원 여부를 확인할 수 없어요. 확인 가능한 모델로 바꾸거나 [이미지]로 표시하고 계속할 수 있어요.', **metadata)
            if selected['provider'] == 'openrouter' and report['price'] != 'free':
                return _model_choice('model_price_unverified', '선택한 모델의 무료 이용 조건이 확인되지 않아 이미지 전송을 중단했어요. 무료 이미지 모델로 바꾸거나 [이미지]로 표시하고 계속할 수 있어요.', **metadata)
        if mode is None:
            if has_images:
                return _choice('choice_required', '이미지를 MD에 어떻게 담을까요?', [
                    {'label': '이미지·글자·설명 넣기', 'image_mode': 'analyze', 'description': '원본 이미지와 이미지 속 글자, 사진·그림·도표의 설명을 넣어요. 선택한 서비스에 이미지가 전송될 수 있어요.'},
                    {'label': '이미지만 넣기', 'image_mode': 'preserve', 'description': '원본 이미지가 MD에 표시돼요. 이미지 속 글자와 설명은 별도로 적지 않고 분석 모델을 호출하지 않아요.'},
                ], model=selected)
            mode = 'preserve'
        profiles = {'image': selected} if mode == 'analyze' and selected else {}
        options = {'image_mode': mode}
        if mode == 'analyze' and selected:
            options['image_model_key'] = digest(json.dumps(selected, sort_keys=True).encode())
    else:
        if mode is None:
            if _needs_image_choice(source, output):
                return _choice('choice_required', '이미지를 MD에 어떻게 담을까요?', [
                    {'label': '이미지·글자·설명 넣기', 'image_mode': 'analyze', 'description': '이미지와 글자·설명을 넣어요. 선택한 서비스에 이미지가 전송될 수 있어요.'},
                    {'label': '이미지만 넣기', 'image_mode': 'preserve', 'description': '이미지만 표시하고 글자와 설명은 만들지 않아요.'},
                ])
            transcribe_images = False
        configured = load_profiles() if transcribe_images else {}
        profiles = {'image': configured['image']} if configured.get('image') else {}
        options = {'transcribe_images': transcribe_images}
    transcribe_images = mode == 'analyze' if strict else transcribe_images
    records = convert(Path(source), Path(output), profiles=profiles, cache_dir=cache_root(), **options)
    status = 'no_files' if not records else 'partial' if any(r['status'] not in ('완료', '확인필요') for r in records) else 'needs_review' if any(r['status']=='확인필요' for r in records) else 'ready'
    missing_model = bool(transcribe_images and any(r.get('image_configuration_required', False) for r in records))
    has_errors = any(r.get('image_errors', False) or r['status'] in ('실패', '충돌') for r in records)
    if missing_model and not has_errors:
        status = 'configuration_required'
    result = {'status': status, 'total': len(records), 'files': [], 'truncated': False,
              'ai_calls': sum(r.get('ai_calls', 0) for r in records),
              'next': ('Ask the user to choose an image provider and model, then retry with the same paths. Never request API keys in chat.' if missing_model else 'Return output paths and status. For questions use context_documents on the same source/output. Never read raw HTML/Base64 or write a converter.')}
    if has_errors and missing_model:
        result['next'] += ' Some images also failed for other reasons; check file warnings.'
    for record in records:
        result['files'].append(record)
        if len(json.dumps(result, ensure_ascii=False)) > 6000:
            result['files'].pop()
            result['truncated'] = True
            result['next'] += ' The file list is truncated; use status with the output directory to see all recorded results.'
            break
    return result
