import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tokensaver_docs.html_document import convert_html
from tokensaver_docs.storage import load_state


class HtmlPlaceholderTests(unittest.TestCase):
    def run_html(self, source, root, **options):
        return convert_html(source, root/'out', cache_dir=root/'cache', source_root=source.parent, **options)

    def test_placeholder_keeps_each_position_without_opening_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'page.html'
            source.write_text('<p>Before</p><img alt="secret alt" src="missing.png"><p>Between</p>'
                              '<img src="https://example.invalid/image.png"><img src="data:image/png;base64,invalid">'
                              '<p>After</p>', encoding='utf-8')
            with patch('tokensaver_docs.html_document.local_image', side_effect=AssertionError('must not open images')), \
                    patch('tokensaver_docs.html_document.store_image', side_effect=AssertionError('must not store images')), \
                    patch('tokensaver_docs.providers.generate', side_effect=AssertionError('must not call provider')):
                result = self.run_html(source, root, image_mode='placeholder')
                repeated = self.run_html(source, root, image_mode='placeholder')
            text = Path(result['output']).read_text(encoding='utf-8')
            self.assertLess(text.index('Before'), text.index('[이미지]'))
            self.assertLess(text.index('[이미지]'), text.index('Between'))
            self.assertLess(text.index('Between'), text.rindex('[이미지]'))
            self.assertLess(text.rindex('[이미지]'), text.index('After'))
            self.assertEqual(text.count('[이미지]'), 3)
            self.assertNotIn('![', text)
            self.assertNotIn('secret alt', text)
            self.assertNotIn('https://', text)
            self.assertEqual(result['images'], 3)
            self.assertEqual(result['untranscribed_images'], 3)
            self.assertEqual(result['image_mode'], 'placeholder')
            self.assertEqual(result['ai_calls'], 0)
            self.assertTrue(repeated['cached'])
            self.assertEqual(load_state(root/'out')['records']['page.html.md']['image_mode'], 'placeholder')

    def test_placeholder_does_not_reuse_preserved_or_analyzed_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'page.html'
            source.write_text('<p>Text</p><img src="image.png">')
            Image.new('RGB', (8, 9), 'blue').save(root/'image.png')
            preserved = self.run_html(source, root)
            original_md = Path(preserved['output']).read_bytes()
            response = {'text': json.dumps({'image_text': 'secret words', 'image_description': 'secret description'})}
            with patch('tokensaver_docs.providers.generate', return_value=response):
                analyzed = self.run_html(source, root, transcribe_images=True, profiles={'image': {'provider': 'codex', 'model': 'fixture'}})
            self.assertIn('secret description', Path(analyzed['output']).read_text())
            with patch('tokensaver_docs.providers.generate', side_effect=AssertionError('no analysis')):
                placeholder = self.run_html(source, root, image_mode='placeholder')
            self.assertEqual(Path(preserved['output']).read_bytes(), original_md)
            self.assertTrue(Path(analyzed['output']).is_file())
            text = Path(placeholder['output']).read_text()
            self.assertNotIn('secret', text)
            self.assertNotIn('![', text)
            self.assertEqual(text.count('[이미지]'), 1)
            self.assertNotEqual(placeholder['output'], preserved['output'])
            self.assertTrue(list((root/'out/assets').glob('*.png')))

    def test_explicit_model_key_is_forwarded_and_separates_output_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'page.html'
            source.write_text('<img src="image.png">')
            Image.new('RGB', (8, 9), 'blue').save(root/'image.png')
            with patch('tokensaver_docs.html_document.UnitStore') as store, \
                    patch('tokensaver_docs.html_document.analyze_image', return_value=({'text': 'same text'}, False)):
                first = self.run_html(source, root, image_mode='analyze', image_model_key='model-a')
                second = self.run_html(source, root, image_mode='analyze', image_model_key='model-b')
            self.assertEqual(store.call_args.kwargs['image_model_key'], 'model-b')
            self.assertNotEqual(first['output'], second['output'])
            self.assertEqual(load_state(root/'out')['records']['page.html.md']['image_model_key'], 'model-b')
