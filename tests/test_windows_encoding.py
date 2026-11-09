"""The CLI must print Korean even when Windows starts with an ANSI pipe."""
import io
import unittest
from unittest.mock import patch
from tokensaver_docs.cli import main


class WindowsEncodingTests(unittest.TestCase):
    def test_help_is_utf8_on_redirected_windows_stdout(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='cp1252')
        with patch('tokensaver_docs.cli.sys.platform', 'win32'), patch('tokensaver_docs.cli.sys.stdout', stream):
            with self.assertRaises(SystemExit) as result:
                main(['--help'])
        stream.flush()
        self.assertEqual(result.exception.code, 0)
        self.assertIn('이미지', buffer.getvalue().decode('utf-8'))
