import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from docx import Document
from openpyxl import Workbook
from PIL import Image

from file_to_md.engine import convert


class PlannedFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.out = self.root / 'out'
        self.profile = {'image': {'provider': 'codex', 'model': 'chosen'}}

    def tearDown(self):
        self.temp.cleanup()

    def test_file_created_during_conversion_is_preserved(self):
        path = self.root / 'image.png'
        Image.new('RGB', (4, 4)).save(path)
        def generate(*args):
            (self.out / 'image.png.md').write_text('사용자 파일')
            return {'text': json.dumps({'image_text': '전사', 'image_description': 'fixture image'})}
        with patch('file_to_md.providers.generate', side_effect=generate):
            result = convert(path, self.out, profiles=self.profile)
        self.assertEqual((self.out / 'image.png.md').read_text(), '사용자 파일')
        self.assertIn('전사', Path(result[0]['output']).read_text())
        self.assertTrue(result[0]['output'].endswith('image.png.2.md'))

    def test_xlsx_missing_dimensions(self):
        path = self.root / 'book.xlsx'
        book = Workbook(write_only=True)
        sheet = book.create_sheet('가격')
        sheet.append(['수박', '=1+2'])
        book.create_sheet('빈 시트')
        book.save(path)
        result = convert(path, self.out)
        self.assertEqual(result[0]['status'], '완료', result)
        text = Path(result[0]['output']).read_text()
        self.assertIn('수박', text)
        self.assertIn('계산값 없음', text)
        self.assertIn('빈 시트', text)

    def test_large_sparse_sheet_is_rejected(self):
        path = self.root / 'large.xlsx'
        book = Workbook()
        book.active['ZZ10000'] = '끝'
        book.save(path)
        result = convert(path, self.out)
        self.assertEqual(result[0]['status'], '실패')
        self.assertIn('너무 큽니다', result[0]['detail'])

    def test_existing_result_changed_during_request_is_preserved(self):
        path = self.root / 'image.png'
        Image.new('RGB', (4, 4)).save(path)
        old = self.out / 'image.png.md'
        self.out.mkdir()
        old.write_text('이전 결과')
        def generate(*args):
            old.write_text('변환 중 편집')
            return {'text': json.dumps({'image_text': '전사', 'image_description': 'fixture image'})}
        with patch('file_to_md.providers.generate', side_effect=generate):
            result = convert(path, self.out, profiles=self.profile)
        self.assertEqual(old.read_text(), '변환 중 편집')
        self.assertEqual(Path(result[0]['output']).name, 'image.png.2.md')

    def test_result_publication_interrupted_then_cached_units_resume(self):
        from file_to_md import engine
        path = self.root / 'image.png'
        Image.new('RGB', (4, 4)).save(path)
        real_publish = engine.publish_new
        def publish_then_interrupt(target, text):
            real_publish(target, text)
            raise KeyboardInterrupt()
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '저장된 전사', 'image_description': 'fixture image'})}) as ai:
            with patch('file_to_md.engine.publish_new', side_effect=publish_then_interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    convert(path, self.out, profiles=self.profile)
            result = convert(path, self.out, profiles=self.profile)
        self.assertEqual(ai.call_count, 1)
        self.assertTrue((self.out / 'image.png.md').exists())
        self.assertEqual(Path(result[0]['output']).name, 'image.png.2.md')
        state = json.loads((self.out / '.file-to-md' / 'state.json').read_text())
        self.assertEqual(state['records']['image.png.md']['current_output'], 'image.png.2.md')
        with patch('file_to_md.providers.generate', side_effect=AssertionError('불필요한 AI 호출')):
            again = convert(path, self.out, profiles=self.profile)
        self.assertEqual(again[0]['output'], result[0]['output'])

    def test_output_lock_is_released(self):
        from file_to_md.engine import output_lock
        with output_lock(self.out):
            with self.assertRaisesRegex(ValueError, '다른 변환'):
                with output_lock(self.out):
                    pass
        with output_lock(self.out):
            pass

    def test_word_images_stay_in_position_and_are_reused(self):
        image = self.root / 'image.png'
        Image.new('RGB', (8, 8), 'red').save(image)
        path = self.root / 'doc.docx'
        doc = Document()
        doc.add_paragraph('앞')
        doc.add_picture(str(image))
        doc.add_paragraph('뒤')
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.paragraphs[0].add_run().add_picture(str(image))
        cell.add_paragraph('셀 뒤')
        doc.save(path)
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '그림 전사', 'image_description': 'fixture image'})}) as ai:
            result = convert(path, self.out, profiles=self.profile)
        self.assertEqual(result[0]['status'], '완료', result)
        text = Path(result[0]['output']).read_text()
        self.assertLess(text.index('앞'), text.index('그림 전사'))
        self.assertLess(text.index('그림 전사'), text.index('뒤'))
        self.assertEqual(text.count('그림 전사'), 2)
        self.assertLess(text.rindex('그림 전사'), text.index('셀 뒤'))
        self.assertEqual(ai.call_count, 1)

    def test_word_nested_and_header_images_resume(self):
        image1, image2 = self.root / 'one.png', self.root / 'two.png'
        Image.new('RGB', (8, 8), 'red').save(image1)
        Image.new('RGB', (8, 8), 'blue').save(image2)
        path = self.root / 'nested.docx'
        doc = Document()
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        nested = cell.add_table(rows=1, cols=1).cell(0, 0)
        nested.paragraphs[0].add_run('앞').add_picture(str(image1))
        nested.add_paragraph('뒤')
        doc.sections[0].header.paragraphs[0].add_run().add_picture(str(image2))
        doc.save(path)
        with patch('file_to_md.providers.generate', side_effect=[{'text': json.dumps({'image_text': '첫 그림', 'image_description': 'fixture image'})}, RuntimeError('실패')]) as ai:
            first = convert(path, self.out, profiles=self.profile)
        self.assertEqual(first[0]['status'], '부분완료')
        self.assertEqual(ai.call_count, 2)
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '머리 그림', 'image_description': 'fixture image'})}) as ai:
            result = convert(path, self.out, profiles=self.profile)
        self.assertEqual(ai.call_count, 1)
        text = Path(result[0]['output']).read_text()
        self.assertLess(text.index('앞'), text.index('첫 그림'))
        self.assertLess(text.index('첫 그림'), text.index('뒤'))
        self.assertIn('머리글', text)
        self.assertIn('머리 그림', text)
