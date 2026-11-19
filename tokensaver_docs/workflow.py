# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Shared, versioned first-run conversion preferences across plugin hosts.

The mode is stored once; conversions never silently change settings.
API credentials and external-consent secrets are never stored here.
"""
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit

from .storage import atomic_write, config_path

MODES = ('analyze', 'preserve', 'placeholder')
RUNTIMES = ('opencode', 'codex', 'claude', 'api', 'local')
LOCAL_PROVIDERS = ('ollama', 'lmstudio', 'openai_compatible')
EXTERNAL_PROVIDERS = ('openrouter', 'codex', 'claude')
ENDPOINTS = {'ollama': 'http://127.0.0.1:11434/v1',
             'lmstudio': 'http://127.0.0.1:1234/v1'}


def preferences_path() -> Path:
    path = config_path().with_name('conversion-preferences.json')
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('변환 설정의 심볼릭 링크는 허용하지 않습니다.')
    return path


def _trusted_endpoint(endpoint, policy):
    if not isinstance(endpoint, str) or len(endpoint) > 512:
        raise ValueError('로컬/내부망 모델 서버 주소를 확인하세요.')
    parts = urlsplit(endpoint)
    if (parts.scheme not in ('http', 'https') or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment
            or (parts.path not in ('', '/', '/v1', '/v1/'))):
        raise ValueError('지원되는 모델 API 기본 주소(/v1)만 사용할 수 있습니다.')
    try:
        address = ipaddress.ip_address(parts.hostname)
        port = parts.port
    except (ValueError, TypeError):
        raise ValueError('DNS 이름 대신 승인된 로컬 또는 사설 IP 주소를 지정하세요.') from None
    if port is not None and not (1 <= port <= 65535):
        raise ValueError('모델 서버 포트를 확인하세요.')
    if policy == 'local_only' and not address.is_loopback:
        raise ValueError('local_only는 루프백 주소만 허용합니다.')
    if policy == 'internal_only' and not (
        address.is_loopback or
        (address.version == 4 and
         (address in ipaddress.ip_network('10.0.0.0/8') or
          address in ipaddress.ip_network('172.16.0.0/12') or
          address in ipaddress.ip_network('192.168.0.0/16'))) or
        (address.version == 6 and address in ipaddress.ip_network('fc00::/7'))
    ):
        raise ValueError('internal_only는 로컬/사설망 IP만 허용합니다.')
    if policy == 'local_only' and parts.scheme != 'http' and not address.is_loopback:
        raise ValueError('로컬 서버 주소가 아닙니다.')
    return endpoint.rstrip('/')


def validate_preferences(value):
    if not isinstance(value, dict) or set(value) - {
        'version', 'image_mode', 'runtime', 'provider', 'model', 'endpoint',
        'network_policy', 'allow_external_images'}:
        raise ValueError('변환 설정 형식이 올바르지 않습니다.')
    if value.get('version') != 1 or value.get('image_mode') not in MODES:
        raise ValueError('변환 설정 버전 또는 이미지 처리 방식이 올바르지 않습니다.')
    mode = value['image_mode']
    if mode != 'analyze':
        if set(value) != {'version', 'image_mode'}:
            raise ValueError('이미지 분석하지 않는 설정은 모델/네트워크 선택이 필요 없습니다.')
        return value
    runtime, provider, model = (value.get(k) for k in ('runtime', 'provider', 'model'))
    if runtime not in RUNTIMES or not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError('이미지 분석 실행 플랫폼과 정확한 모델을 선택하세요.')
    if runtime == 'local':
        if provider not in LOCAL_PROVIDERS or value.get('allow_external_images'):
            raise ValueError('로컬 분석은 로컬 제공자만 사용하며 외부 전송 동의를 저장하지 않습니다.')
        policy = value.get('network_policy')
        if policy not in ('local_only', 'internal_only'):
            raise ValueError('로컬 분석은 local_only 또는 internal_only 정책이 필요합니다.')
        endpoint = _trusted_endpoint(value.get('endpoint') or ENDPOINTS.get(provider), policy)
        return {'version': 1, 'image_mode': mode, 'runtime': runtime,
                'provider': provider, 'model': model.strip(), 'endpoint': endpoint,
                'network_policy': policy, 'allow_external_images': False}
    if runtime == 'api' and provider != 'openrouter':
        raise ValueError('직접 API 연결은 현재 OpenRouter만 지원합니다. 지원되지 않는 엔드포인트로 전송하지 않습니다.')
    if runtime in ('codex', 'claude') and provider != runtime:
        raise ValueError('실행 플랫폼과 제공자가 일치하지 않습니다.')
    if runtime == 'opencode':
        raise ValueError('OpenCode 모델 실행은 아직 네이티브 이미지 분석 연결을 지원하지 않습니다.')
    if not value.get('allow_external_images') or value.get('network_policy') != 'external_allowed':
        raise ValueError('외부 분석은 전송 대상에 대한 명시적 지속 사용 동의가 필요합니다.')
    if 'endpoint' in value:
        raise ValueError('외부 API 엔드포인트를 임의로 지정할 수 없습니다.')
    return {'version': 1, 'image_mode': mode, 'runtime': runtime,
            'provider': provider, 'model': model.strip(), 'network_policy': 'external_allowed',
            'allow_external_images': True}


def load_preferences():
    path = preferences_path()
    if not path.exists():
        return None
    try:
        return validate_preferences(json.loads(path.read_text(encoding='utf-8')))
    except (ValueError, TypeError, OSError) as exc:
        raise ValueError('저장된 변환 설정을 읽을 수 없습니다. 원본 설정은 변경하지 않았습니다.') from exc


def configure_preferences(image_mode, *, runtime=None, provider=None, model=None,
                          endpoint=None, network_policy=None, allow_external_images=False):
    if image_mode not in MODES:
        raise ValueError('이미지 처리는 analyze / preserve / placeholder 중 선택하세요.')
    if type(allow_external_images) is not bool:
        raise ValueError('외부 전송 동의는 true 또는 false여야 합니다.')
    if image_mode == 'analyze':
        payload = {'version': 1, 'image_mode': image_mode,
                   'runtime': runtime, 'provider': provider, 'model': model,
                   'network_policy': network_policy, 'allow_external_images': allow_external_images}
        if endpoint is not None:
            payload['endpoint'] = endpoint
    else:
        if any(v is not None for v in (runtime, provider, model, endpoint, network_policy)) or allow_external_images:
            raise ValueError('이미지 분석하지 않는 방식에는 제공자 및 전송 동의를 설정하지 마세요.')
        payload = {'version': 1, 'image_mode': image_mode}
    saved = validate_preferences(payload)
    atomic_write(preferences_path(), json.dumps(saved, ensure_ascii=False, indent=2))
    return {'status': 'configured', 'preferences': saved}


def current_preferences():
    stored = load_preferences()
    return {'status': 'configured' if stored else 'setup_required',
            'preferences': stored, 'persistent': bool(stored)}
