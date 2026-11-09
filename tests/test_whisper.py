import contextlib,io,json,subprocess,tempfile,unittest
import sys,wave
from pathlib import Path
from unittest.mock import patch
from file_to_md.providers import generate,ConversionError
from file_to_md.cli import main
from file_to_md.storage import load_profiles

class WhisperTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.model=self.root/'ggml-small.bin';self.model.write_bytes(b'model')
  self.audio=self.root/'sample.wav';self.audio.write_bytes(b'RIFF')
  self.profile={'provider':'whisper.cpp','model':str(self.model.resolve())}
 def tearDown(self):self.temp.cleanup()
 def test_local_output_uses_no_network(self):
  def transcribe(args,**kw):
   self.assertEqual(args[args.index('-l')+1],'auto')
   self.assertEqual(args[args.index('-f')+1],str(self.audio.resolve()))
   Path(args[args.index('-of')+1]+'.txt').write_text('실제 전사')
   return subprocess.CompletedProcess(args,0,'','')
  with patch('file_to_md.providers.shutil.which',return_value='/bin/whisper-cli'),patch('file_to_md.providers.subprocess.run',side_effect=transcribe),patch('file_to_md.providers.request_json',side_effect=AssertionError('외부 요청 금지')):
   self.assertEqual(generate(self.audio,'audio',self.profile)['text'],'실제 전사')
 def test_missing_model_and_wrong_input_are_rejected(self):
  with self.assertRaises(ConversionError):generate(self.audio,'image',self.profile)
  self.model.unlink()
  with self.assertRaises(ConversionError):generate(self.audio,'audio',self.profile)
 def test_configure_and_load_local_profile(self):
  config=self.root/'config.json'
  with patch('file_to_md.providers.shutil.which',return_value='/bin/whisper-cli'),contextlib.redirect_stdout(io.StringIO()):
   code=main(['configure','--kind','audio','--provider','whisper.cpp','--model',str(self.model),'--config',str(config)])
  self.assertEqual(code,0)
  self.assertEqual(load_profiles(config)['audio'],self.profile)
 def test_timeout_is_reported(self):
  with patch('file_to_md.providers.shutil.which',return_value='/bin/whisper-cli'),patch('file_to_md.providers.subprocess.run',side_effect=subprocess.TimeoutExpired('whisper-cli',300)):
   with self.assertRaisesRegex(ConversionError,'시간'):generate(self.audio,'audio',self.profile)

 def test_model_change_invalidates_local_cache(self):
  from file_to_md.engine import convert
  with wave.open(str(self.audio),'wb') as audio:
   audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*160)
  profiles={'audio':self.profile}
  with patch('file_to_md.providers.shutil.which',return_value=sys.executable),patch('file_to_md.providers.generate',return_value={'text':'로컬 전사'}) as call:
   convert(self.audio,self.root/'out',profiles=profiles)
   again=convert(self.audio,self.root/'out',profiles=profiles)
   self.assertTrue(again[0]['cached'])
   self.assertEqual(call.call_count,1)
   self.model.write_bytes(b'different model')
   convert(self.audio,self.root/'out',profiles=profiles)
   self.assertEqual(call.call_count,2)

 def test_missing_executable_and_failed_transcription(self):
  with patch('file_to_md.providers.shutil.which',return_value=None):
   with self.assertRaisesRegex(ConversionError,'whisper-cli'):generate(self.audio,'audio',self.profile)
  with patch('file_to_md.providers.shutil.which',return_value='/bin/whisper-cli'),patch('file_to_md.providers.subprocess.run',return_value=subprocess.CompletedProcess([],1,b'',b'private stderr')):
   with self.assertRaisesRegex(ConversionError,'로컬 음성 인식 실패'):generate(self.audio,'audio',self.profile)
