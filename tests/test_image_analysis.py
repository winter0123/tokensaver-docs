import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from tokensaver_docs.image_analysis import analyze_image
from tokensaver_docs.providers import ConversionError, ProviderRequired
from tokensaver_docs.shared_cache import UnitStore


class ImageAnalysisTests(unittest.TestCase):
    def test_result_contains_text_and_description_and_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = root / 'image.png'
            Image.new('RGB', (8, 8), 'red').save(asset)
            profile = {'provider': 'openrouter', 'model': 'chosen:free'}
            store = UnitStore(root)
            with patch('tokensaver_docs.image_analysis.providers.generate', return_value={'text': json.dumps({'image_text': '확인되는 글자 없음', 'image_description': '빨간 사각형.'}), 'usage': {'input_tokens': 7}}) as generate:
                calls = []
                record, cached = analyze_image(asset, profile, store, on_call=lambda: calls.append(1))
                reused, cached_again = analyze_image(asset, None, store, on_call=lambda: calls.append(1))
            self.assertFalse(cached)
            self.assertTrue(cached_again)
            self.assertEqual(record, reused)
            self.assertEqual(len(calls), 1)
            self.assertEqual(generate.call_count, 1)
            self.assertIn('**이미지 속 글자**\n\n확인되는 글자 없음', record['text'])
            self.assertIn('**이미지 설명**\n\n빨간 사각형.', record['text'])
            self.assertEqual(record['usage']['input_tokens'], 7)

    def test_missing_invalid_or_partial_output_is_not_cached(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = root / 'image.png'
            Image.new('RGB', (8, 8)).save(asset)
            store = UnitStore(root)
            with self.assertRaises(ProviderRequired):
                analyze_image(asset, None, store)
            for output in ('not json', '{}', '{"image_text":"x","image_description":""}', '{"image_text":[],"image_description":"photo"}'):
                with patch('tokensaver_docs.image_analysis.providers.generate', return_value={'text': output}):
                    with self.assertRaises(ConversionError):
                        analyze_image(asset, {'provider':'openrouter','model':'selected:free'}, store)
            self.assertFalse(list((root / 'units').glob('*/unit.json')))
