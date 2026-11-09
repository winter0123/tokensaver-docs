import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from docx import Document
from openpyxl import Workbook
from openpyxl.drawing.image import Image as SheetImage
from PIL import Image

from file_to_md.context import document_context
from file_to_md.engine import convert
from file_to_md.storage import digest, load_state


class PlaceholderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / 'picture.png'
        Image.new('RGB', (20, 20), 'red').save(self.image)
        self.profiles = {'image': {'provider': 'codex', 'model': 'selected'}}

    def tearDown(self):
        self.temp.cleanup()

    def read(self, result):
        self.assertEqual(result[0]['image_mode'], 'placeholder')
        self.assertEqual(result[0]['ai_calls'], 0)
        self.assertEqual(result[0]['status'], '확인필요')
        text = Path(result[0]['output']).read_text()
        self.assertIn('[이미지]', text)
        self.assertNotIn('![', text)
        self.assertNotIn('이미지 속 글자', text)
        return text

    def test_standalone_placeholder_and_shared_reuse_do_not_restore_image_links(self):
        original = self.image.read_bytes()
        with patch('file_to_md.providers.generate') as call:
            for out in ('one', 'two'):
                result = convert(self.image, self.root/out, profiles=self.profiles, cache_dir=self.root/'cache', image_mode='placeholder')
                self.read(result)
            call.assert_not_called()
        self.assertEqual(self.image.read_bytes(), original)

    def test_placeholder_does_not_decode_standalone_image(self):
        self.image.write_bytes(b'not a decodable image')
        with patch('file_to_md.media.image_frames', side_effect=AssertionError('Do not decode')):
            result = convert(self.image, self.root/'out', image_mode='placeholder')
        self.read(result)

    def test_mode_switch_does_not_restore_prior_analysis_and_preserves_outputs(self):
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': 'SECRET', 'image_description': 'red image'})}) as call:
            analyzed = convert(self.image, self.root/'out', profiles=self.profiles, cache_dir=self.root/'cache', image_mode='analyze')
            before = Path(analyzed[0]['output']).read_bytes()
            skipped = convert(self.image, self.root/'out', profiles=self.profiles, cache_dir=self.root/'cache', image_mode='placeholder')
            self.assertNotIn('SECRET', self.read(skipped))
            preserved = convert(self.image, self.root/'out', cache_dir=self.root/'cache', image_mode='preserve')
            self.assertIn('![', Path(preserved[0]['output']).read_text())
            self.assertEqual(Path(analyzed[0]['output']).read_bytes(), before)
            self.assertEqual(call.call_count, 1)

    def test_legacy_flags_still_preserve_and_conflicting_selection_is_rejected(self):
        result = convert(self.image, self.root/'legacy', transcribe_images=False)
        self.assertIn('![', Path(result[0]['output']).read_text())
        for mode, old in [('placeholder', True), ('placeholder', False), ('analyze', False)]:
            with self.subTest(mode=mode, old=old), self.assertRaises(ValueError):
                convert(self.image, self.root/'bad', image_mode=mode, transcribe_images=old)
        with self.assertRaises(ValueError):
            convert(self.image, self.root/'bad', image_mode='invalid')

    def test_word_table_xlsx_and_scanned_pdf_keep_text_without_analyzing_images(self):
        doc = Document()
        doc.add_paragraph('Before image')
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.paragraphs[0].add_run().add_picture(str(self.image))
        doc.add_paragraph('After image')
        doc.save(self.root/'table.docx')
        book = Workbook()
        book.active['A1'] = 'Spreadsheet text'
        book.active.add_image(SheetImage(str(self.image)), 'B2')
        book.save(self.root/'sheet.xlsx')
        Image.new('RGB', (100, 100), 'blue').save(self.root/'scan.pdf', 'PDF')
        with patch('file_to_md.providers.generate') as call:
            for name in ('table.docx', 'sheet.xlsx', 'scan.pdf'):
                result = convert(self.root/name, self.root/'out', cache_dir=self.root/'cache', image_mode='placeholder')
                text = self.read(result)
                if name.endswith('docx'):
                    self.assertLess(text.index('Before image'), text.index('[이미지]'))
                    self.assertLess(text.index('[이미지]'), text.index('After image'))
                if name.endswith('xlsx'):
                    self.assertIn('Spreadsheet text', text)
                    self.assertIn('시트: Sheet / 이미지 B2', text)
            call.assert_not_called()

    def test_context_retains_placeholder_mode_and_edited_output_protection(self):
        with patch.dict(os.environ, FILE_TO_MD_CACHE_DIR=str(self.root/'cache')):
            result = convert(self.image, self.root/'out', cache_dir=self.root/'cache', image_mode='placeholder')
            with patch('file_to_md.providers.generate') as call:
                context = document_context(self.image, '이미지', self.root/'out')
                call.assert_not_called()
            self.assertEqual(context['status'], 'partial')
            self.assertTrue(context['excerpts'])
            state = load_state(self.root/'out')['records'][self.image.name+'.md']
            self.assertEqual(state['image_mode'], 'placeholder')
            output = Path(result[0]['output'])
            output.write_text(output.read_text()+'\nUSER EDIT')
            context = document_context(self.image, '이미지', self.root/'out')
            self.assertEqual(context['pending'][0]['status'], '충돌')
            self.assertEqual(context['excerpts'], [])
            self.assertIn('USER EDIT', output.read_text())

    def test_unknown_excel_anchor_keeps_text_and_original_review_warning(self):
        source = self.root/'broken-drawing.xlsx'
        book = Workbook()
        book.active['A1'] = 'Retained sheet text'
        book.active.add_image(SheetImage(str(self.image)), 'B2')
        book.save(source)
        with zipfile.ZipFile(source) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        drawing = next(name for name in entries if name.startswith('xl/drawings/drawing') and name.endswith('.xml'))
        entries[drawing] = b'<broken'
        with zipfile.ZipFile(source, 'w') as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        result = convert(source, self.root/'out', image_mode='placeholder')
        text = self.read(result)
        self.assertIn('Retained sheet text', text)
        self.assertIn('원본에서 확인', text)

    def test_explicit_image_model_key_keeps_other_models_cache_separate(self):
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': 'Words', 'image_description': 'red'})}) as call:
            for key, out in [('model-a', 'a'), ('model-b', 'b'), ('model-a', 'c')]:
                convert(self.image, self.root/out, profiles=self.profiles, cache_dir=self.root/'cache', image_mode='analyze', image_model_key=key)
            self.assertEqual(call.call_count, 2)

    def test_context_uses_current_selection_namespace_when_providers_are_enabled(self):
        selected = {'provider': 'codex', 'model': 'new-default'}
        key = digest(json.dumps(selected, sort_keys=True).encode())
        response = {'text': json.dumps({'image_text': 'Words', 'image_description': 'red'})}
        with patch.dict(os.environ, FILE_TO_MD_CACHE_DIR=str(self.root/'cache')):
            with patch('file_to_md.providers.generate', return_value=response):
                convert(self.image, self.root/'out', profiles=self.profiles, cache_dir=self.root/'cache', image_mode='analyze', image_model_key='previous-one-time')
            Image.new('RGB', (20, 20), 'blue').save(self.image)
            with patch('file_to_md.context.load_profiles', return_value={'image': {'provider': 'codex', 'model': 'legacy'}}), patch('file_to_md.model_setup.load_model_selection', return_value=selected), patch('file_to_md.providers.generate', return_value=response) as generate:
                document_context(self.image, 'Words', self.root/'out', use_configured_providers=True)
                self.assertEqual(generate.call_args.args[2], selected)
            state = load_state(self.root/'out')['records'][self.image.name+'.md']
            self.assertEqual(state['image_model_key'], key)


if __name__ == '__main__':
    unittest.main()
