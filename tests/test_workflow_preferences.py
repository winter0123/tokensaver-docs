"""Persistent conversion onboarding: no repeated prompts, network-boundary safety."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tokensaver_docs import preparation
from tokensaver_docs.providers import validate_image_profile
from tokensaver_docs.workflow import configure_preferences, current_preferences, load_preferences


class WorkflowPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'config.json'
        stub = patch('tokensaver_docs.workflow.config_path', return_value=self.config)
        stub.start()
        self.addCleanup(stub.stop)

    def test_local_mode_saved_once_and_applied_on_later_request(self):
        self.assertEqual(current_preferences()['status'], 'setup_required')
        configure_preferences('preserve')
        self.assertEqual(load_preferences()['image_mode'], 'preserve')
        with patch.object(preparation, 'convert', return_value=[
            {'status': '완료', 'file': 'source.html', 'output': 'converted/source.md'}]) as convert:
            first = preparation.prepare_documents('source.html', onboarding=True)
            second = preparation.prepare_documents('source.html', onboarding=True)
        self.assertEqual(first['status'], 'ready')
        self.assertEqual(second['status'], 'ready')
        self.assertEqual(convert.call_count, 2)
        self.assertTrue(all(call.kwargs['image_mode'] == 'preserve'
                            for call in convert.call_args_list))

    def test_korean_folder_and_html_name_with_saved_preserve(self):
        # Reproduce a macOS path containing Hangul, spaces and a numeric prefix.
        configure_preferences('preserve')
        root=Path(self.temp.name)
        folder=root/'글로벌_트루베라'
        folder.mkdir()
        source=folder/'0. 그림으로 보는 AWS 배포.html'
        source.write_text('<html><body><h1>배포 지침</h1><p>이미지 포함</p>'
                          '<img alt="도표" src="figure.png"></body></html>',
                          encoding='utf-8')
        from PIL import Image
        Image.new('RGB',(2,2)).save(folder/'figure.png')
        output=root/'converted'
        with patch.object(preparation, 'cache_root',return_value=root/'cache'):
            result=preparation.prepare_documents(source,output,onboarding=True)
        self.assertIn(result['status'], ('ready','needs_review'))
        self.assertTrue(result['files'])
        self.assertTrue(Path(result['files'][0]['output']).exists())
        self.assertEqual(result['files'][0]['ai_calls'],0)

    def test_placeholder_reused_and_change_only_on_user_request(self):
        configure_preferences('placeholder')
        self.assertEqual(load_preferences()['image_mode'], 'placeholder')
        configure_preferences('preserve')
        self.assertEqual(load_preferences()['image_mode'], 'preserve')
        self.assertEqual(json.loads(
            self.config.with_name('conversion-preferences.json').read_text())['image_mode'], 'preserve')

    def test_local_model_does_not_require_external_consent(self):
        configure_preferences('analyze', runtime='local', provider='ollama',
                              model='vision-local', network_policy='local_only')
        saved = load_preferences()
        self.assertFalse(saved['allow_external_images'])
        self.assertEqual(saved['endpoint'], 'http://127.0.0.1:11434/v1')
        profile = validate_image_profile({
            'provider':'local','model':saved['model'],'endpoint':saved['endpoint'],
            'network_policy':saved['network_policy']})
        with patch.object(preparation, '_needs_image_choice', return_value=True), \
             patch('tokensaver_docs.providers.inspect_image_model',
                   return_value={'capability':'unknown','price':'local','reason':'local_catalog'}), \
             patch.object(preparation, 'convert', return_value=[
                 {'status':'완료','file':'local.png','output':'converted/local.md'}]) as convert:
            result = preparation.prepare_documents('local.png', onboarding=True)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(convert.call_args.kwargs['profiles']['image'], profile)
        self.assertEqual(convert.call_args.kwargs['image_mode'], 'analyze')

    def test_network_boundaries_deny_remote_or_dns_and_keep_old_settings(self):
        configure_preferences('preserve')
        for endpoint in ('https://api.openai.com/v1', 'http://example.com/v1',
                         'http://192.168.1.4/v1', 'http://127.0.0.1:11434/v1/../oops',
                         'http://127.0.0.1:11434/v1?x=1'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                configure_preferences('analyze', runtime='local', provider='ollama',
                                      model='vision-local', endpoint=endpoint,
                                      network_policy='local_only')
        self.assertEqual(load_preferences()['image_mode'], 'preserve')

    def test_internal_private_endpoint_with_explicit_policy(self):
        configure_preferences('analyze', runtime='local', provider='openai_compatible',
                              model='intranet-vl', endpoint='http://10.22.0.4:8000/v1',
                              network_policy='internal_only')
        self.assertEqual(load_preferences()['endpoint'], 'http://10.22.0.4:8000/v1')

    def test_external_image_transfer_requires_persistent_consent(self):
        with self.assertRaises(ValueError):
            configure_preferences('analyze', runtime='api', provider='openrouter',
                                  model='vision-test', network_policy='external_allowed')
        with self.assertRaises(ValueError):
            configure_preferences('analyze', runtime='api', provider='openrouter',
                                  model='vision-test', allow_external_images=True,
                                  network_policy='local_only')
        configure_preferences('analyze', runtime='api', provider='openrouter',
                              model='vision-test', network_policy='external_allowed',
                              allow_external_images=True)
        self.assertTrue(load_preferences()['allow_external_images'])
        configure_preferences('preserve')
        self.assertNotIn('allow_external_images', load_preferences())

    def test_codex_catalog_sanitizes_raw_templates(self):
        from tokensaver_docs import providers
        from unittest.mock import Mock
        raw = {'models': [
            {'slug':'gpt-a', 'display_name':'Test Model',
             'base_instructions':'SECRET-INTERNAL-TEMPLATE', 'visibility':'list'},
            {'slug':'gpt-b', 'display_name':'Second', 'instructions':'SECRET-INTERNAL-TEMPLATE'}]}
        result=Mock(returncode=0,stdout=json.dumps(raw),stderr='')
        with patch.object(providers.subprocess, 'run', return_value=result) as runner:
            catalog=providers.catalog_image_models('codex',query='gpt-',limit=1)
        self.assertEqual(catalog['total'],2)
        self.assertTrue(catalog['has_more'])
        self.assertFalse(catalog['account_verified'])
        self.assertNotIn('SECRET-INTERNAL-TEMPLATE',json.dumps(catalog))
        self.assertEqual(runner.call_args.args[0], ['codex','debug','models','--bundled'])

    def test_claude_aliases_not_marked_as_account_verified(self):
        from tokensaver_docs import providers
        catalog=providers.catalog_image_models('claude')
        self.assertEqual({m['id'] for m in catalog['models']},
                         {'opus','sonnet','haiku'})
        self.assertFalse(catalog['account_verified'])
        self.assertTrue(all(m['vision']=='unknown' for m in catalog['models']))

    def test_local_catalog_never_claims_vision_from_model_name(self):
        from tokensaver_docs import providers
        response = {'data': [{'id':'vision-local'}, {'id':'text-local'}, {'not_id':'invalid'}]}
        with patch.object(providers, '_local_request', return_value=response) as request:
            result = providers.catalog_image_models('ollama')
        self.assertEqual([x['id'] for x in result['models']], ['text-local','vision-local'])
        self.assertTrue(all(x['vision']=='unknown' for x in result['models']))
        request.assert_called_once_with('http://127.0.0.1:11434/v1/models')
        with patch.object(providers, '_local_request', return_value=response):
            page = providers.catalog_image_models('ollama', query='vision', limit=1)
        self.assertEqual([m['id'] for m in page['models']], ['vision-local'])
        self.assertEqual(page['total'], 1)
        self.assertFalse(page['has_more'])

    def test_local_inference_uses_selected_endpoint_and_never_external_provider(self):
        from tokensaver_docs import providers
        with tempfile.TemporaryDirectory() as work:
            sample = Path(work) / 'image.png'
            from PIL import Image
            Image.new('RGB', (2, 2)).save(sample)
            profile = validate_image_profile({
                'provider':'local','model':'selected-local',
                'endpoint':'http://127.0.0.1:11434/v1',
                'network_policy':'local_only'})
            response={'choices':[{'finish_reason':'stop',
                      'message':{'content':'{"image_text":"sample","image_description":"diagram"}'}}]}
            with patch.object(providers, '_local_request', return_value=response) as request:
                result = providers.generate(sample, 'image', profile)
        self.assertIn('diagram', result['text'])
        self.assertEqual(request.call_args.args[0],
                         'http://127.0.0.1:11434/v1/chat/completions')
        payload=request.call_args.args[1]
        self.assertEqual(payload['model'], 'selected-local')
        self.assertTrue(payload['messages'][0]['content'][1]['image_url']['url'].startswith(
            'data:image/png;base64,'))

    def test_configured_model_does_not_trigger_repeated_selection_on_unverified_metadata(self):
        configure_preferences('analyze', runtime='api', provider='openrouter',
                              model='vision-test:free', network_policy='external_allowed',
                              allow_external_images=True)
        with patch.object(preparation, '_needs_image_choice', return_value=True), \
             patch('tokensaver_docs.providers.inspect_image_model',
                   return_value={'capability':'unknown','price':'unknown','reason':'lookup_failed'}), \
             patch.object(preparation, 'convert', return_value=[
                 {'status':'완료','file':'source.html','output':'converted/source.md'}]) as convert:
            result = preparation.prepare_documents('source.html', onboarding=True)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(convert.call_args.kwargs['image_mode'], 'analyze')

    def test_symlinked_settings_are_rejected(self):
        destination = Path(self.temp.name) / 'target.json'
        destination.write_text('{"version":1,"image_mode":"preserve"}')
        self.config.with_name('conversion-preferences.json').symlink_to(destination)
        with self.assertRaises(ValueError):
            load_preferences()


if __name__ == '__main__':
    unittest.main()
