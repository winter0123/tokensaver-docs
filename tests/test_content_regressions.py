import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from file_to_md.engine import convert
from file_to_md.media import normalize_image
from file_to_md.providers import PROMPT_VERSION
from file_to_md.storage import digest, file_hash, save_state


class ContentRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / '결과'
        self.profiles = {'image': {'provider': 'codex', 'model': '사용자선택'}}

    def tearDown(self):
        self.temp.cleanup()

    def vector_pdf(self, path):
        writer = PdfWriter()
        page = writer.add_blank_page(width=100, height=100)
        stream = DecodedStreamObject()
        stream.set_data(b'0 0 0 rg 10 10 50 50 re f')
        page[NameObject('/Contents')] = writer._add_object(stream)
        with path.open('wb') as f:
            writer.write(f)

    def test_nested_word_tables_preserve_text_order_and_amounts(self):
        path = self.root / '중첩표.docx'
        doc = Document()
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.text = '본문 앞'
        inner = cell.add_table(rows=1, cols=2)
        inner.cell(0, 0).text = '환불액 12345원'
        inner.cell(0, 1).text = '다음 열'
        inner.cell(0, 0).add_table(rows=1, cols=1).cell(0, 0).text = '깊은 표 678원'
        cell.add_paragraph('본문 뒤')
        doc.sections[0].header.add_table(rows=1, cols=1, width=100).cell(0, 0).text = '머리글 표'
        doc.save(path)
        with patch('file_to_md.providers.generate', side_effect=AssertionError('AI 호출 금지')):
            result = convert(path, self.output)
        text = (self.output / (path.name + '.md')).read_text()
        for expected in ('환불액 12345원', '깊은 표 678원', '다음 열', '머리글 표'):
            self.assertIn(expected, text)
        self.assertLess(text.index('본문 앞'), text.index('환불액 12345원'))
        self.assertLess(text.index('환불액 12345원'), text.index('본문 뒤'))
        self.assertEqual(result[0]['status'], '완료')

    def test_vector_pdf_is_blocked_without_model_instead_of_declared_empty(self):
        path = self.root / '벡터.pdf'
        self.vector_pdf(path)
        with patch('file_to_md.providers.generate', side_effect=AssertionError('모델 미설정')):
            result = convert(path, self.output)
        self.assertEqual(result[0]['status'], '차단')
        self.assertNotIn('(빈 페이지)', (self.output / (path.name + '.md')).read_text())

    def test_vector_pdf_uses_selected_image_model_and_empty_page_does_not(self):
        path = self.root / '벡터.pdf'
        self.vector_pdf(path)
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '검은 도형', 'image_description': 'fixture image'}), 'usage': {}}) as ai:
            result = convert(path, self.output, profiles=self.profiles)
        self.assertEqual(ai.call_count, 1)
        self.assertEqual(result[0]['status'], '완료')
        self.assertIn('검은 도형', (self.output / (path.name + '.md')).read_text())
        blank = self.root / '빈문서.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with blank.open('wb') as f:
            writer.write(f)
        with patch('file_to_md.providers.generate', side_effect=AssertionError('빈 페이지 AI 낭비')):
            result = convert(blank, self.output, profiles=self.profiles)
        self.assertEqual(result[0]['status'], '완료')
        self.assertIn('(빈 페이지)', (self.output / (blank.name + '.md')).read_text())

    def test_transparent_pixels_are_composited_on_white_without_losing_text(self):
        for mode in ('RGBA', 'LA', 'P'):
            with self.subTest(mode=mode):
                source = self.root / f'{mode}.png'
                target = self.root / f'{mode}-처리.png'
                if mode == 'RGBA':
                    im = Image.new(mode, (5, 5), (0, 0, 0, 0))
                    im.putpixel((2, 2), (0, 0, 0, 255))
                elif mode == 'LA':
                    im = Image.new(mode, (5, 5), (0, 0))
                    im.putpixel((2, 2), (0, 255))
                else:
                    im = Image.new(mode, (5, 5), 0)
                    im.putpalette([0, 0, 0, 0, 0, 0] + [0] * 762)
                    im.putpixel((2, 2), 1)
                    im.info['transparency'] = 0
                im.save(source)
                original_hash = file_hash(source)
                normalize_image(source, target)
                with Image.open(target) as result:
                    self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
                    self.assertEqual(result.getpixel((2, 2)), (0, 0, 0))
                self.assertEqual(file_hash(source), original_hash)

    def test_multiframe_tiff_transcribes_each_frame_and_reuses_cache(self):
        path = self.root / '여러장.tiff'
        Image.new('RGB', (20, 20), 'red').save(path, save_all=True, append_images=[Image.new('RGB', (20, 20), 'blue')])
        seen = []

        def transcribe(image, kind, profile):
            with Image.open(image) as im:
                seen.append(im.getpixel((0, 0)))
            return {'text': json.dumps({'image_text': f'{len(seen)}번째 전사', 'image_description': 'fixture image'}), 'usage': {}}

        with patch('file_to_md.providers.generate', side_effect=transcribe):
            result = convert(path, self.output, profiles=self.profiles)
            convert(path, self.output, profiles=self.profiles)
        self.assertEqual(seen, [(255, 0, 0), (0, 0, 255)])
        self.assertEqual(result[0]['status'], '완료')
        text = (self.output / (path.name + '.md')).read_text()
        self.assertIn('프레임 1/2', text)
        self.assertIn('프레임 2/2', text)
        self.assertLess(text.index('1번째 전사'), text.index('2번째 전사'))

    def test_multiframe_tiff_resume_only_failed_frame(self):
        path = self.root / '재개.tiff'
        Image.new('RGB', (20, 20), 'red').save(path, save_all=True, append_images=[Image.new('RGB', (20, 20), 'blue')])
        with patch('file_to_md.providers.generate', side_effect=[{'text': json.dumps({'image_text': '앞장', 'image_description': 'fixture image'}), 'usage': {}}, RuntimeError('실패')]) as ai:
            result = convert(path, self.output, profiles=self.profiles)
        self.assertEqual(ai.call_count, 2)
        self.assertEqual(result[0]['status'], '부분완료')
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '뒷장', 'image_description': 'fixture image'}), 'usage': {}}) as ai:
            result = convert(path, self.output, profiles=self.profiles)
        self.assertEqual(ai.call_count, 1)
        self.assertEqual(result[0]['status'], '완료')

    def test_old_incorrect_image_cache_is_not_reused(self):
        path = self.root / '과거.png'
        Image.new('RGBA', (5, 5), (0, 0, 0, 0)).save(path)
        self.output.mkdir()
        target = self.output / (path.name + '.md')
        target.write_text('과거의 잘못된 전사')
        legacy_signature = digest(json.dumps({'source': file_hash(path), 'profiles': self.profiles,
                                             'pages': [], 'chunk': None, 'version': 1,
                                             'prompt': PROMPT_VERSION}, sort_keys=True).encode())
        save_state(self.output, {'version': 1, 'records': {target.name: {
            'source': str(path.resolve()), 'signature': legacy_signature,
            'output_hash': file_hash(target), 'status': '완료',
            'units': {'image': {'text': '과거의 잘못된 전사'}},
        }}})
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '수정된 전사', 'image_description': 'fixture image'}), 'usage': {}}) as ai:
            result = convert(path, self.output, profiles=self.profiles)
        self.assertEqual(ai.call_count, 1)
        self.assertEqual(result[0]['status'], '완료')
        self.assertEqual(target.read_text(), '과거의 잘못된 전사')
        self.assertIn('수정된 전사', Path(result[0]['output']).read_text())

    def test_old_xlsx_embedded_image_cache_is_invalidated(self):
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as SheetImage
        image = self.root / '내장.png'
        Image.new('RGBA', (5, 5), (0, 0, 0, 0)).save(image)
        path = self.root / '내장이미지.xlsx'
        book = Workbook()
        book.active.add_image(SheetImage(str(image)))
        book.save(path)
        self.output.mkdir()
        target = self.output / (path.name + '.md')
        target.write_text('과거 이미지 전사')
        legacy = digest(json.dumps({'source': file_hash(path), 'profiles': self.profiles,
                                   'pages': [], 'chunk': None, 'version': 1,
                                   'prompt': PROMPT_VERSION}, sort_keys=True).encode())
        save_state(self.output, {'version': 1, 'records': {target.name: {
            'source': str(path.resolve()), 'signature': legacy, 'status': '확인필요',
            'output_hash': file_hash(target), 'units': {},
        }}})
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '새 이미지 전사', 'image_description': 'fixture image'}), 'usage': {}}) as ai:
            result = convert(path, self.output, profiles=self.profiles)
        self.assertEqual(ai.call_count, 1)
        self.assertEqual(target.read_text(), '과거 이미지 전사')
        self.assertIn('새 이미지 전사', Path(result[0]['output']).read_text())


if __name__ == '__main__':
    unittest.main()
