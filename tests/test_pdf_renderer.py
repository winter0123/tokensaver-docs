import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from file_to_md.media import pdf_image


class PdfRendererTests(unittest.TestCase):
    def test_renders_selected_page_without_external_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'scan.pdf'
            Image.new('RGB', (200, 100), 'red').save(
                source, 'PDF', save_all=True, append_images=[Image.new('RGB', (200, 100), 'blue')])
            with patch('file_to_md.media.run_command', side_effect=AssertionError('external renderer')):
                rendered = pdf_image(source, 2, root)
            with Image.open(rendered) as image:
                self.assertEqual(image.size, (2400, 1200))
                r, g, b = image.convert('RGB').getpixel((100, 100))
                self.assertGreater(b, r + 100)

    def test_bad_pages_and_damaged_pdf_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'scan.pdf'
            Image.new('RGB', (100, 200), 'white').save(source, 'PDF')
            for page in (0, -1, 2):
                with self.subTest(page=page), self.assertRaises(ValueError):
                    pdf_image(source, page, root)
            source.write_bytes(b'not a pdf')
            with self.assertRaises(ValueError):
                pdf_image(source, 1, root)
