"""Integration checks for an explicitly supplied built executable."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter
from PIL import Image


@unittest.skipUnless(os.environ.get('FILE_TO_MD_STANDALONE'), 'standalone executable not provided')
class StandaloneTests(unittest.TestCase):
    def test_visual_pdf_needs_no_external_renderer(self):
        executable = Path(os.environ['FILE_TO_MD_STANDALONE']).resolve()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (100, 200), 'red').save(root/'scan.pdf', 'PDF')
            env=dict(os.environ, PATH=str(root), FILE_TO_MD_CACHE_DIR=str(root/'cache'))
            result=subprocess.run([str(executable), 'convert', str(root/'scan.pdf'), '--output', str(root/'out'), '--no-configured-providers'], env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertIn('차단',result.stdout)
            self.assertNotIn('실패',result.stdout)
            self.assertIn('이미지 모델을 선택하세요', (root/'out/scan.pdf.md').read_text(encoding='utf-8'))

    def test_local_document_formats(self):
        executable = Path(os.environ['FILE_TO_MD_STANDALONE']).resolve()
        with tempfile.TemporaryDirectory(prefix='문서 ') as temp:
            root = Path(temp)
            source = root/'input'
            source.mkdir()
            doc = Document()
            doc.add_paragraph('환불은 수령 후 7일 이내')
            doc.save(source / 'sample.docx')
            book = Workbook()
            book.active['A1'] = '예외 조건'
            book.save(source / 'sample.xlsx')
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.write(source / 'sample.pdf')
            output = root / 'output'
            env=dict(os.environ, FILE_TO_MD_CACHE_DIR=str(root/'cache'))
            result = subprocess.run([str(executable), 'convert', str(source), '--output', str(output), '--no-configured-providers', '--refresh'], env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('환불은 수령 후 7일 이내', (output / 'sample.docx.md').read_text(encoding='utf-8'))
            self.assertIn('예외 조건', (output / 'sample.xlsx.md').read_text(encoding='utf-8'))
            self.assertTrue((output / 'sample.pdf.md').is_file())
