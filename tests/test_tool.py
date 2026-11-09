import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CliSmoke(unittest.TestCase):
    def test_help_exposes_conversion_and_search(self):
        result = subprocess.run([sys.executable, '-m', 'file_to_md', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('convert', result.stdout)
        self.assertIn('search', result.stdout)

    def test_convert_scanned_pdf_without_profile_is_blocked(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'scan.pdf'
            Image.new('RGB', (100, 200), 'red').save(source, 'PDF')
            result = subprocess.run(
                [sys.executable, '-m', 'file_to_md', 'convert', str(source),
                 '--output', str(root / 'out'), '--no-configured-providers'],
                env=dict(os.environ, FILE_TO_MD_CACHE_DIR=str(root / 'cache')),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('차단', result.stdout)
            self.assertIn('이미지 모델을 선택하세요', (root / 'out' / 'scan.pdf.md').read_text())


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.src = self.root / '자료'
        self.src.mkdir()
        self.out = self.root / '출력'

    def tearDown(self):
        self.temp.cleanup()

    def convert(self, **kwargs):
        from file_to_md.engine import convert
        return convert(self.src, self.out, **kwargs)

    def image(self, name='사진.png'):
        from PIL import Image
        p = self.src / name
        Image.new('RGB', (80, 40), 'white').save(p)
        return p

    def test_docx_order_and_xlsx_formula_without_ai(self):
        from docx import Document
        from openpyxl import Workbook
        d = Document()
        d.add_paragraph('앞 문단')
        d.add_table(rows=1, cols=1).cell(0, 0).text = '가운데 표'
        d.add_paragraph('뒤 문단')
        d.save(self.src / '규정.docx')
        w = Workbook()
        w.active.title = '가격'
        w.active['A1'] = '수박'
        w.active['B1'] = '=10+20'
        w.save(self.src / '가격.xlsx')
        with patch('file_to_md.providers.generate', side_effect=AssertionError('AI 호출 금지')):
            result = self.convert()
        self.assertTrue(all(r['status'] == '완료' for r in result), result)
        text = (self.out / '규정.docx.md').read_text()
        self.assertLess(text.index('앞 문단'), text.index('가운데 표'))
        self.assertLess(text.index('가운데 표'), text.index('뒤 문단'))
        text = (self.out / '가격.xlsx.md').read_text()
        self.assertIn('B1', text)
        self.assertIn('=10+20', text)
        self.assertIn('계산값 없음', text)

    def test_image_cache_and_deleted_output_rebuild_without_request(self):
        self.image()
        profile = {'image': {'provider': 'openrouter', 'model': 'example:free'}}
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '원문 123', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}) as call:
            self.convert(profiles=profile)
            self.convert(profiles=profile)
            (self.out / '사진.png.md').unlink()
            self.convert(profiles=profile)
        self.assertEqual(call.call_count, 1)
        self.assertIn('원문 123', (self.out / '사진.png.md').read_text())

    def test_edited_output_is_preserved(self):
        self.image()
        p = {'image': {'provider': 'codex', 'model': 'chosen'}}
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '추출', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}):
            self.convert(profiles=p)
        target = self.out / '사진.png.md'
        target.write_text('사용자 직접 수정')
        with patch('file_to_md.providers.generate', side_effect=AssertionError('재호출 금지')):
            result = self.convert(profiles=p)
        self.assertEqual(target.read_text(), '사용자 직접 수정')
        self.assertEqual(result[0]['status'], '완료')
        self.assertIn('추출', Path(result[0]['output']).read_text())

    def test_missing_profile_blocks_image(self):
        self.image()
        with patch('file_to_md.providers.generate', side_effect=AssertionError('설정 없음')):
            r = self.convert()
        self.assertEqual(r[0]['status'], '차단')

    def test_direct_input_symlink_is_rejected(self):
        from file_to_md.engine import convert
        source = self.image()
        link = self.root / '연결.png'
        link.symlink_to(source)
        with self.assertRaisesRegex(ValueError, '심볼릭'):
            convert(link, self.out)

    def test_failed_new_settings_can_resume_without_output_conflict(self):
        source = self.image()
        p = {'image': {'provider': 'codex', 'model': 'first'}}
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '최초', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}):
            self.convert(profiles=p)
        p['image']['model'] = 'second'
        with patch('file_to_md.media.normalize_image', side_effect=ValueError('일시 준비 실패')):
            self.convert(profiles=p)
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '재개', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}):
            r = self.convert(profiles=p)
        self.assertEqual(r[0]['status'], '완료', r)
        self.assertIn('최초', (self.out / (source.name + '.md')).read_text())
        self.assertIn('재개', Path(r[0]['output']).read_text())

    def test_unrelated_audio_profile_does_not_reconvert_image(self):
        self.image()
        p = {'image': {'provider': 'codex', 'model': 'chosen'}}
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '전사', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}) as call:
            self.convert(profiles=p)
            p['audio'] = {'provider': 'openrouter', 'model': 'other:free'}
            self.convert(profiles=p)
        self.assertEqual(call.call_count, 1)

    def test_output_recursion_symlinks_and_other_root_collision(self):
        from file_to_md.engine import convert, discover
        self.image()
        nested = self.src / 'converted'
        nested.mkdir()
        (nested / 'again.png').write_bytes(b'ignored')
        (self.src / 'link.png').symlink_to(self.src / '사진.png')
        self.assertEqual([p.name for p in discover(self.src, nested)], ['사진.png'])
        p = {'image': {'provider': 'codex', 'model': 'chosen'}}
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '추출', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}):
            convert(self.src / '사진.png', self.out, profiles=p)
        other = self.root / '다른곳'
        other.mkdir()
        from PIL import Image
        Image.new('RGB', (20, 20)).save(other / '사진.png')
        with patch('file_to_md.providers.generate', side_effect=AssertionError('충돌')):
            result = convert(other / '사진.png', self.out, profiles=p)
        self.assertEqual(result[0]['status'], '충돌')

    def test_failed_pdf_page_resumes_only_missing_page(self):
        from pypdf import PdfWriter
        w = PdfWriter()
        w.add_blank_page(width=100, height=100)
        w.add_blank_page(width=100, height=100)
        with (self.src / '스캔.pdf').open('wb') as f:
            w.write(f)
        p = {'image': {'provider': 'codex', 'model': 'chosen'}}
        with patch('file_to_md.providers.generate', side_effect=[{'text': json.dumps({'image_text': '첫째', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}, RuntimeError('일시 실패')]) as c:
            r = self.convert(profiles=p, vision_pages={1, 2})
        self.assertEqual(c.call_count, 2)
        self.assertEqual(r[0]['status'], '부분완료')
        with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '둘째', 'image_description': '이미지 설명'}, ensure_ascii=False), 'usage': {}}) as c:
            r = self.convert(profiles=p, vision_pages={1, 2})
        self.assertEqual(c.call_count, 1)
        self.assertEqual(r[0]['status'], '완료')


class ProviderTests(unittest.TestCase):
    def test_price_and_modality_filter(self):
        from file_to_md.providers import eligible
        m = {'id': 'x:free', 'pricing': {'prompt': '0', 'completion': '0', 'request': '0'}, 'architecture': {'input_modalities': ['image', 'text']}}
        self.assertTrue(eligible(m, 'image'))
        self.assertFalse(eligible(m, 'audio'))
        m['pricing']['image'] = '0.01'
        self.assertFalse(eligible(m, 'image'))
        m['pricing'] = {}
        self.assertFalse(eligible(m, 'image'))

    def test_cli_audio_is_explicitly_unsupported(self):
        from file_to_md.providers import generate, ConversionError
        for provider in ('codex', 'claude'):
            with self.assertRaisesRegex(ConversionError, '오디오'):
                generate(Path('a.wav'), 'audio', {'provider': provider, 'model': 'chosen'})

    def test_openrouter_output_truncation_rejected(self):
        from file_to_md.providers import generate, ConversionError
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'a.png'
            Image.new('RGB', (5, 5)).save(p)
            m = {'id': 'x:free', 'pricing': {'prompt': '0', 'completion': '0'}, 'architecture': {'input_modalities': ['image']}}
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}), patch('file_to_md.providers.list_models', return_value=[m]), patch('file_to_md.providers.request_json', return_value={'choices': [{'finish_reason': 'length', 'message': {'content': '불완전'}}]}):
                with self.assertRaisesRegex(ConversionError, '잘림'):
                    generate(p, 'image', {'provider': 'openrouter', 'model': 'x:free'})

    def test_audio_segments_cover_original_duration(self):
        from file_to_md.media import intervals
        spans = list(intervals(125, 60, 1))
        self.assertEqual(spans, [(0, 60), (59, 119), (118, 125)])
        with self.assertRaises(ValueError):
            list(intervals(10, 1, 1))

    def test_real_wave_segment_without_system_ffmpeg(self):
        from file_to_md.media import audio_chunk, duration
        import wave
        with tempfile.TemporaryDirectory() as t:
            source, target = Path(t) / '원본.wav', Path(t) / '구간.wav'
            with wave.open(str(source), 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b'\0\0' * 16000 * 5)
            audio_chunk(source, 2, 5, target)
            self.assertAlmostEqual(duration(target), 3, places=2)

    def test_openrouter_audio_payload_and_completed_text(self):
        from file_to_md.providers import generate
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'a.wav'
            p.write_bytes(b'RIFF-test')
            m = {'id': 'x:free', 'pricing': {'prompt': '0', 'completion': '0'}, 'architecture': {'input_modalities': ['audio']}}
            response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '음성 전사'}}]}
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}), patch('file_to_md.providers.list_models', return_value=[m]), patch('file_to_md.providers.request_json', return_value=response) as request:
                r = generate(p, 'audio', {'provider': 'openrouter', 'model': 'x:free'})
            self.assertEqual(r['text'], '음성 전사')
            url, payload, _ = request.call_args.args
            self.assertTrue(url.endswith('/chat/completions'))
            self.assertEqual(payload['messages'][0]['content'][1]['input_audio']['format'], 'wav')

    def test_cli_provider_success_and_failure_parsing(self):
        from file_to_md.providers import generate, ConversionError
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'a.png'
            p.write_bytes(b'image')
            codex = '\n'.join(json.dumps(x) for x in [
                {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '이미지 전사'}},
                {'type': 'turn.completed', 'usage': {'input_tokens': 5}},
            ])
            for provider, stdout in [('codex', codex), ('claude', json.dumps({'subtype': 'success', 'is_error': False, 'result': '이미지 전사'}))]:
                with patch('file_to_md.providers.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout, '')) as run:
                    r = generate(p, 'image', {'provider': provider, 'model': 'chosen'})
                self.assertEqual(r['text'], '이미지 전사')
                self.assertIsInstance(run.call_args.args[0], list)
                self.assertNotIn('shell', run.call_args.kwargs)
                with patch('file_to_md.providers.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{"is_error":true}', '')):
                    with self.assertRaises(ConversionError):
                        generate(p, 'image', {'provider': provider, 'model': 'chosen'})

    def test_http_error_does_not_leak_response_or_retry(self):
        from file_to_md.providers import request_json, ConversionError
        from urllib.error import HTTPError
        with patch('file_to_md.providers.urllib.request.urlopen', side_effect=HTTPError('https://example.invalid', 429, 'secret-server-body', {}, None)) as call:
            with self.assertRaises(ConversionError) as error:
                request_json('https://example.invalid')
        self.assertNotIn('secret-server-body', str(error.exception))
        self.assertEqual(call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
