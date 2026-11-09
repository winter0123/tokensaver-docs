import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tokensaver_docs import providers


class ModelCapabilityTests(unittest.TestCase):
    def inspect(self, model):
        with patch('tokensaver_docs.providers.list_models', return_value=[model]):
            return providers.inspect_image_model({'provider': 'openrouter', 'model': 'chosen'})

    def test_price_and_image_support_are_independent(self):
        for modes, price, capability, cost in [
            (['text', 'image'], '0', 'supported', 'free'),
            (['text'], '0', 'unsupported', 'free'),
            (['image'], '0.001', 'supported', 'not_free'),
            (None, '0', 'unknown', 'free'),
            (['image'], None, 'supported', 'unknown'),
        ]:
            model = {'id': 'chosen', 'architecture': {'input_modalities': modes}}
            if price is not None:
                model['pricing'] = {'prompt': price, 'completion': '0'}
            with self.subTest(model=model):
                result = self.inspect(model)
                self.assertEqual(result['capability'], capability)
                self.assertEqual(result['price'], cost)

    def test_lookup_failure_and_missing_model_are_distinct(self):
        profile = {'provider': 'openrouter', 'model': 'chosen'}
        with patch('tokensaver_docs.providers.list_models', side_effect=providers.ConversionError('offline')):
            self.assertEqual(providers.inspect_image_model(profile)['reason'], 'lookup_failed')
        with patch('tokensaver_docs.providers.list_models', return_value=[]):
            self.assertEqual(providers.inspect_image_model(profile)['reason'], 'model_not_found')

    def test_cli_provider_support_is_unknown_without_calling_it(self):
        for provider in ('codex', 'claude'):
            with patch('tokensaver_docs.providers.cli_generate') as generate:
                result = providers.inspect_image_model({'provider': provider, 'model': 'chosen'})
                self.assertEqual(result['capability'], 'unknown')
                generate.assert_not_called()

    def test_profile_rejects_secrets_and_unsupported_providers(self):
        for profile in ({'provider': 'openrouter', 'model': 'chosen', 'key': 'secret'},
                        {'provider': 'whisper.cpp', 'model': 'chosen'},
                        {'provider': 'codex', 'model': ''}):
            with self.assertRaises(ValueError):
                providers.inspect_image_model(profile)


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root))
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_first_use_defer_and_legacy_setting(self):
        from tokensaver_docs.model_setup import setup_status, select_model, load_model_selection
        self.assertEqual(setup_status()['status'], 'setup_required')
        self.assertEqual(select_model(defer=True)['status'], 'deferred')
        self.assertEqual(setup_status()['status'], 'deferred')
        self.assertIsNone(load_model_selection())
        legacy = self.root/'tokensaver-docs/config.json'
        legacy.write_text(json.dumps({'image': {'provider': 'codex', 'model': 'legacy'}}))
        self.assertEqual(load_model_selection()['model'], 'legacy')
        self.assertEqual(setup_status()['status'], 'configured')

    def test_supplied_legacy_profiles_are_used_without_loading_global_profiles(self):
        from tokensaver_docs.model_setup import load_model_selection, select_model
        profile = {'provider': 'codex', 'model': 'custom-config'}
        with patch('tokensaver_docs.model_setup.load_profiles') as load:
            self.assertEqual(load_model_selection(legacy_profiles={'image': profile}), profile)
            self.assertIsNone(load_model_selection(legacy_profiles={}))
            load.assert_not_called()
        select_model('claude', 'selected', save_as_default=True, confirmed=True)
        self.assertEqual(load_model_selection(legacy_profiles={'image': profile})['model'], 'selected')

    def test_one_time_selection_does_not_save_and_default_needs_confirmation(self):
        from tokensaver_docs.model_setup import setup_status, select_model, load_model_selection
        result = select_model('codex', 'temporary')
        self.assertEqual(result['status'], 'selection_ready')
        self.assertEqual(result['profile'], {'provider': 'codex', 'model': 'temporary'})
        self.assertEqual(result['inspection']['capability'], 'unknown')
        self.assertEqual(setup_status()['status'], 'setup_required')
        self.assertEqual(select_model('codex', 'default', save_as_default=True)['status'], 'confirmation_required')
        self.assertIsNone(load_model_selection())
        self.assertEqual(select_model('codex', 'default', save_as_default=True, confirmed=True)['status'], 'configured')
        self.assertEqual(load_model_selection()['model'], 'default')
        select_model('claude', 'other')
        self.assertEqual(load_model_selection()['model'], 'default')

    def test_saved_selection_preserves_legacy_and_defer_does_not_erase_it(self):
        from tokensaver_docs.model_setup import select_model, load_model_selection
        legacy = self.root/'tokensaver-docs/config.json'
        legacy.parent.mkdir()
        content = json.dumps({'image': {'provider': 'codex', 'model': 'legacy'}, 'audio': {'provider': 'whisper.cpp', 'model': 'local'}})
        legacy.write_text(content)
        select_model('claude', 'new', save_as_default=True, confirmed=True)
        self.assertEqual(legacy.read_text(), content)
        select_model(defer=True)
        self.assertEqual(load_model_selection()['model'], 'new')

    def test_invalid_or_symlink_selection_is_rejected(self):
        from tokensaver_docs.model_setup import setup_status, select_model
        with self.assertRaises(ValueError):
            select_model('codex', 'chosen', defer=True)
        path = self.root/'tokensaver-docs/model-choice.json'
        path.parent.mkdir()
        path.write_text('{"version":99}')
        with self.assertRaises(ValueError):
            setup_status()
        path.unlink()
        target = self.root/'private'
        target.write_text('{}')
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            select_model(defer=True)
