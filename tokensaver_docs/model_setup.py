# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""First-use model selection without changing legacy provider settings."""
import json

from .providers import inspect_image_model, validate_image_profile
from .storage import atomic_write, config_path, load_profiles


def _path():
    path = config_path().with_name('model-choice.json')
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('모델 선택 설정의 심볼릭 링크는 허용하지 않습니다.')
    return path


def _load():
    path = _path()
    if not path.exists():
        return {'version': 1, 'deferred': False}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(state, dict) or set(state) - {'version', 'deferred', 'profile'}
                or state.get('version') != 1 or type(state.get('deferred')) is not bool):
            raise ValueError()
        if 'profile' in state:
            state['profile'] = validate_image_profile(state['profile'])
        return state
    except (ValueError, TypeError):
        raise ValueError('모델 선택 설정 형식을 확인하세요. 기존 설정은 보존했습니다.') from None


def load_model_selection(*, legacy_profiles=None):
    state = _load()
    if state.get('profile'):
        return state['profile']
    return (load_profiles() if legacy_profiles is None else legacy_profiles).get('image')


def setup_status():
    state = _load()
    profile = state.get('profile') or load_profiles().get('image')
    if profile:
        return {'status': 'configured', 'model': profile}
    return {'status': 'deferred' if state['deferred'] else 'setup_required'}


def select_model(provider=None, model=None, *, defer=False, save_as_default=False, confirmed=False):
    if any(type(value) is not bool for value in (defer, save_as_default, confirmed)):
        raise ValueError('모델 선택과 저장 동의는 true 또는 false여야 합니다.')
    if defer:
        if provider is not None or model is not None or save_as_default:
            raise ValueError('나중에 선택하기와 모델 선택을 함께 지정할 수 없습니다.')
        state = _load()
        state['deferred'] = True
        atomic_write(_path(), json.dumps(state, ensure_ascii=False, indent=2))
        return setup_status()
    if provider is None and model is None and not save_as_default:
        return setup_status()
    profile = validate_image_profile({'provider': provider, 'model': model})
    if save_as_default and not confirmed:
        return {'status': 'confirmation_required', 'profile': profile,
                'next': '기본 모델로 저장할지 사용자에게 확인하세요. 이번에만 사용하려면 save_as_default=false를 지정하세요.'}
    inspection = inspect_image_model(profile)
    if save_as_default:
        _load()
        atomic_write(_path(), json.dumps({'version': 1, 'deferred': False, 'profile': profile}, ensure_ascii=False, indent=2))
    return {'status': 'configured' if save_as_default else 'selection_ready', 'profile': profile, 'inspection': inspection}
