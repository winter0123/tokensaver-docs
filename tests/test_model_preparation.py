import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tokensaver_docs.preparation import prepare_documents


class ModelPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'), TOKENSAVER_DOCS_CACHE_DIR=str(self.root/'cache'))
        self.env.start()
        self.addCleanup(self.env.stop)
        Image.new('RGB', (10, 10), 'blue').save(self.root/'a.png')
        self.source = self.root/'a.html'
        self.source.write_text('<p>Before</p><img src="a.png"><p>After</p>')
        self.output = self.root/'out'

    def test_first_use_returns_setup_without_output_or_inference(self):
        with patch('tokensaver_docs.providers.generate') as generate:
            result = prepare_documents(self.source, self.output, onboarding=True)
        self.assertEqual(result['status'], 'setup_required')
        self.assertIn('나중에 선택하기', result['choices'])
        self.assertFalse(self.output.exists())
        generate.assert_not_called()

    def test_nonvision_selection_asks_switch_or_placeholder_before_conversion(self):
        with patch('tokensaver_docs.providers.inspect_image_model', return_value={'capability':'unsupported','price':'free','reason':None}), patch('tokensaver_docs.providers.generate') as generate:
            result = prepare_documents(self.source, self.output, image_mode='analyze', model_provider='openrouter', model='text:free')
        self.assertEqual(result['status'], 'model_incompatible')
        self.assertIn('[이미지]', json.dumps(result, ensure_ascii=False))
        self.assertFalse(self.output.exists())
        generate.assert_not_called()

    def test_placeholder_needs_no_model_or_inspection(self):
        with patch('tokensaver_docs.providers.inspect_image_model') as inspect, patch('tokensaver_docs.providers.generate') as generate:
            result = prepare_documents(self.source, self.output, image_mode='placeholder')
        md = Path(result['files'][0]['output']).read_text()
        self.assertIn('[이미지]', md)
        self.assertNotIn('![', md)
        self.assertLess(md.index('Before'), md.index('[이미지]'))
        self.assertLess(md.index('[이미지]'), md.index('After'))
        inspect.assert_not_called()
        generate.assert_not_called()

    def test_unknown_and_price_are_not_called_unsupported(self):
        for report, status in [({'capability':'unknown','price':'free','reason':'lookup_failed'}, 'model_lookup_failed'), ({'capability':'unknown','price':'unknown','reason':'unavailable'}, 'model_support_unknown'), ({'capability':'supported','price':'not_free','reason':None}, 'model_price_unverified')]:
            with patch('tokensaver_docs.providers.inspect_image_model', return_value=report), patch('tokensaver_docs.preparation.convert') as convert:
                result = prepare_documents(self.source, self.output, image_mode='analyze', model_provider='openrouter', model='chosen')
            self.assertEqual(result['status'], status)
            convert.assert_not_called()

    def test_one_time_model_is_used_without_saving_or_audio(self):
        from tokensaver_docs.storage import config_path
        response = {'text':json.dumps({'image_text':'확인되는 글자 없음','image_description':'파란 사각형'})}
        with patch('tokensaver_docs.providers.inspect_image_model', return_value={'capability':'supported','price':'free','reason':None}), patch('tokensaver_docs.providers.generate', return_value=response) as generate:
            result = prepare_documents(self.source, self.output, image_mode='analyze', model_provider='openrouter', model='vision:free')
        self.assertEqual(generate.call_args.args[2], {'provider':'openrouter','model':'vision:free'})
        self.assertFalse(config_path().exists())
        self.assertFalse(config_path().with_name('model-choice.json').exists())
        self.assertIn('파란 사각형', Path(result['files'][0]['output']).read_text())

    def test_invalid_or_conflicting_arguments_do_not_convert(self):
        with patch('tokensaver_docs.preparation.convert') as convert:
            for kwargs in ({'image_mode':'invalid'}, {'image_mode':'placeholder','transcribe_images':True}, {'model_provider':'openrouter'}, {'allow_unverified_model':'yes'}):
                with self.assertRaises(ValueError):
                    prepare_documents(self.source, self.output, **kwargs)
        convert.assert_not_called()

    def test_cli_setup_defer_and_placeholder(self):
        import contextlib, io
        from tokensaver_docs.cli import main
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['setup-model','--defer']), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'deferred')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['prepare',str(self.source),'--output',str(self.output),'--image-mode','placeholder']), 0)
        self.assertEqual(json.loads(output.getvalue())['ai_calls'], 0)

    def test_saved_default_is_used_by_legacy_cli_and_mcp(self):
        import contextlib, io
        from tokensaver_docs.cli import main
        from tokensaver_docs.mcp_server import convert_documents
        from tokensaver_docs.model_setup import select_model
        from tokensaver_docs.storage import atomic_write, config_path
        atomic_write(config_path(), json.dumps({'image':{'provider':'codex','model':'old'}}))
        select_model('codex', 'new', save_as_default=True, confirmed=True)
        with patch('tokensaver_docs.cli.convert', return_value=[{'status':'완료','file':'x'}]) as convert, contextlib.redirect_stdout(io.StringIO()):
            main(['convert', 'docs', '--transcribe-images'])
        self.assertEqual(convert.call_args.kwargs['profiles']['image']['model'], 'new')
        with patch('tokensaver_docs.mcp_server.convert', return_value=[]) as convert:
            convert_documents('docs', 'out', use_configured_providers=True)
        self.assertEqual(convert.call_args.kwargs['profiles']['image']['model'], 'new')
