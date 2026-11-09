import hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from file_to_md.audio_setup import setup_audio

class AudioSetupTests(unittest.TestCase):
    def test_no_download_without_confirmation(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('no network')):
            self.assertEqual(setup_audio('tiny')['status'],'confirmation_required')

    def test_verified_download_preserves_settings_and_reuses_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json'
            config.write_text('{"image":{"provider":"codex","model":"chosen"}}')
            model={'small':{'url':'https://example.invalid/model','sha256':hashlib.sha256(b'abc').hexdigest(),'size':3}}
            response=io.BytesIO(b'abc');response.status=200;response.headers={}
            with patch('file_to_md.audio_setup.model_catalog',return_value=model),patch('file_to_md.audio_setup.config_path',return_value=config),patch('file_to_md.audio_setup.load_profiles',return_value=json.loads(config.read_text())),patch('file_to_md.providers.whisper_paths',return_value=(root/'models/ggml-small.bin','bundled')),patch('urllib.request.urlopen',return_value=response) as network:
                result=setup_audio('small',confirmed=True,root=root/'models')
                self.assertEqual(result['status'],'ready')
                setup_audio('small',confirmed=True,root=root/'models')
                self.assertEqual(network.call_count,1)
                self.assertIn('image',json.loads(config.read_text()))
