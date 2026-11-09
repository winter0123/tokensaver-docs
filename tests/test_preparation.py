import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tokensaver_docs.preparation import prepare_documents


class PreparationChoiceTests(unittest.TestCase):
    def test_cli_image_consent_does_not_enable_audio(self):
        import contextlib, io
        from tokensaver_docs.cli import main
        profiles = {'image': {'provider': 'openrouter', 'model': 'vision'}, 'audio': {'provider': 'openrouter', 'model': 'audio'}}
        with patch('tokensaver_docs.cli.load_profiles', return_value=profiles), patch('tokensaver_docs.cli.convert', return_value=[{'status': '완료', 'file': 'sample'}]) as convert, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['convert', 'docs', '--transcribe-images']), 0)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image'})
            self.assertEqual(main(['convert', 'docs', '--vision-pages', '1']), 0)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image'})
            self.assertEqual(main(['convert', 'docs', '--transcribe-images', '--use-configured-audio-provider']), 0)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image', 'audio'})
            self.assertEqual(main(['convert', 'docs']), 0)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image', 'audio'})

    def test_mcp_image_consent_does_not_enable_audio(self):
        from tokensaver_docs.mcp_server import convert_documents
        profiles = {'image': {'provider': 'openrouter', 'model': 'vision'}, 'audio': {'provider': 'openrouter', 'model': 'audio'}}
        with patch('tokensaver_docs.mcp_server.load_profiles', return_value=profiles), patch('tokensaver_docs.mcp_server.convert', return_value=[]) as convert:
            convert_documents('docs', 'out', use_configured_providers=True)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image'})
            self.assertTrue(convert.call_args.kwargs['transcribe_images'])
            convert_documents('docs', 'out', use_configured_audio_provider=True)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'audio'})
            self.assertFalse(convert.call_args.kwargs['transcribe_images'])
            convert_documents('docs', 'out', use_configured_providers=True, use_configured_audio_provider=True)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image', 'audio'})

    def test_non_boolean_choice_cannot_enable_image_analysis(self):
        with patch('tokensaver_docs.preparation.load_profiles') as load, patch('tokensaver_docs.preparation.convert') as convert:
            with self.assertRaises(ValueError):
                prepare_documents('unused', transcribe_images='false')
            load.assert_not_called()
            convert.assert_not_called()

    @unittest.skipIf(os.name == 'nt', 'POSIX fake CLI fixture; Windows executable is tested separately')
    def test_opencode_v1_preserves_choice_required_json(self):
        import json
        import shutil
        import subprocess
        import sys
        if not shutil.which('node'):
            self.skipTest('Node.js is not installed')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root/'index.mjs'
            plugin.write_text((Path(__file__).resolve().parents[1]/'plugins/opencode/index.js').read_text())
            package = root/'node_modules/@opencode-ai/plugin'
            package.mkdir(parents=True)
            (package/'package.json').write_text('{"type":"module","exports":"./index.js"}')
            (package/'index.js').write_text('export const tool = x => x; const schema = () => ({optional: schema, int: schema, min: schema, max: schema}); tool.schema = {string: schema, boolean: schema, number: schema, enum: schema};')
            binary = root/'bin/tokensaver-docs'
            binary.parent.mkdir()
            binary.write_text('#!' + sys.executable + '\nprint(\'{"status":"choice_required"}\')\nraise SystemExit(2)\n')
            binary.chmod(0o755)
            script = 'import {pathToFileURL} from "node:url"; const p=await import(pathToFileURL(process.argv[1])); const api=await p.TokenSaverDocsPlugin(); console.log(await api.tool.tokensaver_docs_prepare.execute({source:"image.png"}));'
            result = subprocess.run(['node', '--input-type=module', '-e', script, str(plugin)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'choice_required')

    def test_inaccessible_image_does_not_claim_model_configuration_needed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'a.html'
            source.write_text('<p>text</p><img src="https://example.invalid/a.png">', encoding='utf-8')
            with patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache')), patch('tokensaver_docs.preparation.load_profiles', return_value={}):
                result = prepare_documents(source, root/'out', transcribe_images=True)
            self.assertEqual(result['status'], 'partial', result)
            self.assertNotIn('choose an image provider', result['next'])

    def test_missing_model_and_inaccessible_image_both_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'a.html'
            Image.new('RGB', (10, 10)).save(root/'a.png')
            source.write_text('<p>text</p><img src="a.png"><img src="https://example.invalid/a.png">', encoding='utf-8')
            with patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache')), patch('tokensaver_docs.preparation.load_profiles', return_value={}):
                result = prepare_documents(source, root/'out', transcribe_images=True)
            self.assertEqual(result['status'], 'partial', result)
            self.assertIn('choose an image provider', result['next'])
            self.assertIn('failed for other reasons', result['next'])

    def test_cli_requires_image_choice_without_changing_output(self):
        import contextlib, io, json
        from tokensaver_docs.cli import main
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (10, 10)).save(root/'image.png')
            result = io.StringIO()
            with patch.dict(os.environ, XDG_CONFIG_HOME=str(root/'config')), contextlib.redirect_stdout(result):
                self.assertEqual(main(['prepare', str(root/'image.png'), '--output', str(root/'out')]), 2)
            self.assertEqual(json.loads(result.getvalue())['status'], 'setup_required')
            self.assertFalse((root/'out').exists())

    def test_text_only_document_formats_do_not_need_an_image_choice(self):
        from docx import Document
        from openpyxl import Workbook
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            doc = Document(); doc.add_paragraph('Just text'); doc.save(root/'a.docx')
            book = Workbook(); book.active['A1'] = 'Just text'; book.save(root/'b.xlsx')
            writer = PdfWriter(); writer.add_blank_page(width=72, height=72); writer.write(root/'c.pdf')
            with patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache')), patch('tokensaver_docs.providers.generate') as generate:
                for source in (root/'a.docx', root/'b.xlsx', root/'c.pdf'):
                    result = prepare_documents(source, root/'out', transcribe_images=None)
                    self.assertNotEqual(result['status'], 'choice_required', result)
                generate.assert_not_called()

    def test_missing_choice_requires_an_answer_for_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (10, 10)).save(root/'image.png')
            with patch('tokensaver_docs.preparation.convert') as convert:
                result = prepare_documents(root/'image.png', root/'out', transcribe_images=None)
                self.assertEqual(result['status'], 'choice_required')
                convert.assert_not_called()

    def test_text_only_html_does_not_need_choice_or_image_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'a.html'
            source.write_text('<p>Just text</p>', encoding='utf-8')
            with patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache')), patch('tokensaver_docs.preparation.load_profiles', return_value={}), patch('tokensaver_docs.providers.generate') as generate:
                for choice in (None, True):
                    result = prepare_documents(source, root/'out', transcribe_images=choice)
                    self.assertEqual(result['status'], 'ready', result)
                generate.assert_not_called()

    def test_missing_image_model_allows_text_and_keeps_image(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (10, 10)).save(root/'a.png')
            source = root/'a.html'
            source.write_text('<p>Text is retained</p><img src="a.png">', encoding='utf-8')
            with patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache')), patch('tokensaver_docs.preparation.load_profiles', return_value={}), patch('tokensaver_docs.providers.generate') as generate:
                result = prepare_documents(source, root/'out', transcribe_images=True)
                self.assertEqual(result['status'], 'configuration_required', result)
                self.assertIn('Text is retained', Path(result['files'][0]['output']).read_text())
                generate.assert_not_called()

    def test_image_choice_never_uses_audio_profile(self):
        with patch('tokensaver_docs.preparation.load_profiles', return_value={'image': {'provider': 'openrouter', 'model': 'vision:free'}, 'audio': {'provider': 'openrouter', 'model': 'audio:free'}}), patch('tokensaver_docs.preparation.convert', return_value=[]) as convert:
            prepare_documents('unused', transcribe_images=True)
            self.assertEqual(set(convert.call_args.kwargs['profiles']), {'image'})

    def test_user_choice_keeps_image_and_adds_text_only_when_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (10, 10), 'red').save(root/'a.png')
            source = root/'a.html'
            source.write_text('<p>Before</p><img src="a.png"><p>After</p>')
            with patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache')), patch('tokensaver_docs.preparation.load_profiles', return_value={'image': {'provider': 'openrouter', 'model': 'chosen:free'}}), patch('tokensaver_docs.providers.generate', return_value={'text': '{"image_text":"Image words","image_description":"Red rectangle"}'}) as generate:
                first = prepare_documents(source, root/'out', transcribe_images=False)
                generate.assert_not_called()
                selected = prepare_documents(source, root/'out', transcribe_images=True)
                old = Path(first['files'][0]['output']).read_text()
                text = Path(selected['files'][0]['output']).read_text()
                self.assertIn('이미지 내용 정리 안 함', old)
                self.assertIn('](assets/', text)
                self.assertIn('Red rectangle', text)
                self.assertLess(text.index('Before'), text.index('Image words'))
                self.assertLess(text.index('Image words'), text.index('After'))
                prepare_documents(source, root/'out', transcribe_images=True)
                self.assertEqual(generate.call_count, 1)
