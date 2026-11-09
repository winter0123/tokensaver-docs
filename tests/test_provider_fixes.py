import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from file_to_md.providers import generate

class ProviderFixTests(unittest.TestCase):
 def test_image_rejection_explains_capability_and_price_separately(self):
  from file_to_md.providers import ConversionError
  cases=[
   ({'input_modalities':['text']}, {'prompt':'0','completion':'0'}, '이미지 입력을 지원하지'),
   ({'input_modalities':['image']}, {'prompt':'0.1','completion':'0'}, '무료가 아니'),
   ({'input_modalities':['image']}, {}, '무료 가격을 확인'),
   ({}, {'prompt':'0','completion':'0'}, '입력 지원 여부를 확인'),
  ]
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'sample.png';path.write_bytes(b'image')
   for architecture,pricing,message in cases:
    model={'id':'chosen','architecture':architecture,'pricing':pricing}
    with self.subTest(message=message),patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch('file_to_md.providers.list_models',return_value=[model]),patch('file_to_md.providers.request_json') as request:
     with self.assertRaisesRegex(ConversionError,message):
      generate(path,'image',{'provider':'openrouter','model':'chosen'})
     request.assert_not_called()

 def test_payment_rejection_is_not_reported_as_format_failure(self):
  from urllib.error import HTTPError
  from file_to_md.providers import request_json,ConversionError
  with patch('file_to_md.providers.urllib.request.urlopen',side_effect=HTTPError('https://example.invalid',402,'private',{},None)):
   with self.assertRaisesRegex(ConversionError,'잔액·결제'):
    request_json('https://example.invalid')

 def test_audio_uses_chat_audio_input(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'sample.wav';path.write_bytes(b'RIFF')
   model={'id':'audio:free','pricing':{'prompt':'0','completion':'0'},'architecture':{'input_modalities':['audio']}}
   response={'choices':[{'finish_reason':'stop','message':{'content':'테스트 음성'}}]}
   with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch('file_to_md.providers.list_models',return_value=[model]),patch('file_to_md.providers.request_json',return_value=response) as request:
    self.assertEqual(generate(path,'audio',{'provider':'openrouter','model':'audio:free'})['text'],'테스트 음성')
   url,payload,_=request.call_args.args
   self.assertTrue(url.endswith('/chat/completions'))
   self.assertEqual(payload['messages'][0]['content'][1]['type'],'input_audio')
   from file_to_md.providers import PROMPT
   self.assertEqual(payload['messages'][0]['content'][0]['text'], PROMPT)

 def test_large_image_supplies_readable_detail_views(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'sample.png';Image.new('RGB',(2172,2896),'white').save(path)
   model={'id':'vision:free','pricing':{'prompt':'0','completion':'0'},'architecture':{'input_modalities':['image']}}
   response={'choices':[{'finish_reason':'stop','message':{'content':'전사'}}]}
   with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test'}),patch('file_to_md.providers.list_models',return_value=[model]),patch('file_to_md.providers.request_json',return_value=response) as request:
    generate(path,'image',{'provider':'openrouter','model':'vision:free'})
   images=[p for p in request.call_args.args[1]['messages'][0]['content'] if p['type']=='image_url']
   self.assertGreater(len(images),1)
   self.assertTrue(all(p['image_url']['detail']=='high' for p in images))
   prompt=request.call_args.args[1]['messages'][0]['content'][0]['text']
   self.assertIn('image_text',prompt)
   self.assertIn('image_description',prompt)

 def test_cli_providers_receive_image_description_prompt(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'image.png';path.write_bytes(b'image')
   codex='\n'.join(json.dumps(x) for x in [{'type':'item.completed','item':{'type':'agent_message','text':'{}'}},{'type':'turn.completed'}])
   claude=json.dumps({'subtype':'success','is_error':False,'result':'{}'})
   for provider,output in [('codex',codex),('claude',claude)]:
    with patch('file_to_md.providers.subprocess.run',return_value=subprocess.CompletedProcess([],0,output,'')) as run:
     generate(path,'image',{'provider':provider,'model':'selected'})
    prompt=run.call_args.kwargs['input']
    self.assertIn('image_text',prompt)
    self.assertIn('image_description',prompt)
