import asyncio,contextlib,io,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tokensaver_docs.cli import main

class PortabilityTests(unittest.TestCase):
 def test_convert_can_ignore_configured_providers(self):
  with tempfile.TemporaryDirectory() as temp:
   source=Path(temp)/'source';source.mkdir()
   with patch('tokensaver_docs.cli.load_profiles',side_effect=AssertionError('profiles must not be loaded')), patch('tokensaver_docs.cli.convert',return_value=[{'status':'완료','file':'x'}]) as convert, contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(main(['convert',str(source),'--output',str(Path(temp)/'out'),'--no-configured-providers']),0)
    self.assertEqual(convert.call_args.kwargs['profiles'],{})

 def test_convert_keeps_existing_configured_provider_behavior(self):
  with tempfile.TemporaryDirectory() as temp:
   profiles={'image':{'provider':'openrouter','model':'example:free'}}
   with patch('tokensaver_docs.cli.load_profiles',return_value=profiles), patch('tokensaver_docs.cli.convert',return_value=[{'status':'완료','file':'x'}]) as convert, contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(main(['convert',temp]),0)
    self.assertEqual(convert.call_args.kwargs['profiles'],profiles)

 def test_skill_install_preserves_existing_file(self):
  with tempfile.TemporaryDirectory() as temp:
   output=io.StringIO()
   with contextlib.redirect_stdout(output):self.assertEqual(main(['install-skill','--agent','codex','--destination',temp]),0)
   target=Path(temp)/'tokensaver-docs'/'SKILL.md';self.assertTrue(target.is_file())
   target.write_text('사용자 내용')
   with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(['install-skill','--agent','codex','--destination',temp]),2)
   self.assertEqual(target.read_text(),'사용자 내용')

 def test_search_token_budget(self):
  try:import tiktoken
  except ImportError:self.skipTest('선택 토큰 패키지 없음')
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'a.md').write_text('환불 가능합니다\n환불 규정 7일\n')
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','환불','--output',temp,'--max-tokens','1']),0)
   self.assertIn('토큰 제한',out.getvalue());self.assertNotIn('환불 가능합니다',out.getvalue())

 def test_mcp_stdio_search(self):
  try:
   from mcp import ClientSession,StdioServerParameters
   from mcp.client.stdio import stdio_client
  except ImportError:self.skipTest('선택 MCP 패키지 없음')
  import sys
  async def verify(root):
   params=StdioServerParameters(command=sys.executable,args=['-m','tokensaver_docs.mcp_server'])
   async with stdio_client(params) as (reader,writer):
    async with ClientSession(reader,writer) as session:
     await session.initialize()
     tools=await session.list_tools()
     self.assertIn('search_documents',[t.name for t in tools.tools])
     result=await session.call_tool('search_documents',{'query':'환불','output':str(root),'context':0})
     self.assertFalse(result.isError, str(result.content))
     self.assertIn('환불은 7일',str(result.content))
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'doc.md').write_text('# 안내\n환불은 7일\n')
   asyncio.run(verify(root))

 def test_mcp_conversion_does_not_use_configured_provider_implicitly(self):
  try:from tokensaver_docs.mcp_server import convert_documents
  except ImportError:self.skipTest('선택 MCP 패키지 없음')
  from PIL import Image
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);image=root/'image.png';Image.new('RGB',(8,8)).save(image)
   with patch.dict(os.environ, {'TOKENSAVER_DOCS_CACHE_DIR': str(root/'cache')}), patch('tokensaver_docs.mcp_server.load_profiles',side_effect=AssertionError('설정된 제공자를 자동 실행하면 안 됨')), patch('tokensaver_docs.providers.generate',side_effect=AssertionError('이미지 저장만 선택하면 모델을 호출하면 안 됨')):
    result=convert_documents(str(image),str(root/'out'))
   record=result['files'][0]
   self.assertEqual(record['status'],'확인필요',record)
   text=Path(record['output']).read_text()
   self.assertIn('이미지 내용 정리 안 함',text)
   import re
   match=re.search(r'!\[[^\]]*\]\(([^)]+)\)',text)
   self.assertIsNotNone(match)
   self.assertEqual((Path(record['output']).parent/match.group(1)).read_bytes(),image.read_bytes())

 def test_mcp_provider_configuration_requires_explicit_confirmation(self):
  try:from tokensaver_docs.mcp_server import configure_provider
  except ImportError:self.skipTest('선택 MCP 패키지 없음')
  with patch('tokensaver_docs.mcp_server._run') as run:
   self.assertIn('confirmation',configure_provider('image','openrouter','example:free',False).lower())
   run.assert_not_called()
   configure_provider('image','openrouter','example:free',True)
   run.assert_called_once_with(['configure','--kind','image','--provider','openrouter','--model','example:free'])

 def test_read_token_budget_keeps_whole_lines_and_continuation(self):
  try:import tiktoken
  except ImportError:self.skipTest('선택 토큰 패키지 없음')
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'doc.md';path.write_text('첫 문장\n둘째 문장\n셋째 문장\n')
   enc=tiktoken.get_encoding('cl100k_base')
   budget=len(enc.encode('1: 첫 문장'))
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['read',str(path),'--max-tokens',str(budget)]),0)
   self.assertIn('1: 첫 문장',out.getvalue());self.assertNotIn('2: 둘째 문장',out.getvalue())
   self.assertIn('--start-line 2',out.getvalue())

 def test_read_budget_too_small_explains_how_to_proceed(self):
  try:import tiktoken
  except ImportError:self.skipTest('선택 토큰 패키지 없음')
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'doc.md';path.write_text('가나다라마바사 여러 단어\n')
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['read',str(path),'--max-tokens','1']),0)
   self.assertIn('예산을 늘려',out.getvalue())
