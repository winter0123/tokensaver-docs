"""Analyze one normalized image frame and reuse verified results."""
import json

from . import providers


def analyze_image(asset, profile, store, on_call=None):
    def produce():
        if not profile:
            raise providers.ProviderRequired('이미지 내용을 정리하려면 이미지 모델을 선택하세요.')
        if on_call:
            on_call()
        result = providers.generate(asset, 'image', profile)
        try:
            parsed = json.loads(providers.checked_text(result.get('text')))
            if not isinstance(parsed, dict) or set(parsed) != {'image_text', 'image_description'}:
                raise ValueError()
            image_text, description = parsed['image_text'], parsed['image_description']
            if not all(isinstance(value, str) and value.strip() and len(value) <= 1_000_000
                       for value in (image_text, description)):
                raise ValueError()
            image_text, description = image_text.strip(), description.strip()
        except (ValueError, KeyError, TypeError):
            raise providers.ConversionError('이미지 분석 결과에 글자 또는 설명이 없습니다. 다시 시도하세요.') from None
        return {'image_text': image_text, 'image_description': description,
                'text': f'**이미지 속 글자**\n\n{image_text}\n\n**이미지 설명**\n\n{description}',
                'provider': profile['provider'], 'model': profile['model'], 'usage': result.get('usage', {})}

    if store is None:
        return produce(), False
    return store.obtain(asset, 'image', produce)
