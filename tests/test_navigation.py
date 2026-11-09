import contextlib,io,tempfile,unittest
from pathlib import Path
from tokensaver_docs.cli import main

class NavigationTests(unittest.TestCase):
 def test_outline_and_context(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'doc.md';p.write_text('# 제목\n앞 문장\n환불 규정\n뒤 문장\n## 예외\n')
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['outline',str(p)]),0)
   self.assertIn(':1: # 제목',out.getvalue());self.assertIn(':5: ## 예외',out.getvalue())
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','환불','--output',tmp,'--context','1']),0)
   self.assertIn('앞 문장',out.getvalue());self.assertIn('뒤 문장',out.getvalue())

 def test_search_latest_tracked_and_explicit_history(self):
  from tokensaver_docs.storage import save_state
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'a.pdf.md').write_text('구버전 환불')
   (root/'a.pdf.2.md').write_text('최신 환불')
   (root/'manual.md').write_text('직접작성 환불')
   save_state(root,{'version':1,'records':{'a.pdf.md':{'current_output':'a.pdf.2.md'}}})
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','환불','--output',tmp]),0)
   self.assertIn('최신 환불',out.getvalue());self.assertIn('직접작성 환불',out.getvalue());self.assertNotIn('구버전 환불',out.getvalue())
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','환불','--output',tmp,'--all-versions']),0)
   self.assertIn('구버전 환불',out.getvalue())

 def test_phrase_ranked_above_all_terms(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'a.md').write_text('환불 신청 기한은 7일\n');(root/'b.md').write_text('환불 기한은 7일\n')
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','환불 기한','--output',tmp]),0)
   self.assertIn('환불 신청 기한',out.getvalue())
   self.assertLess(out.getvalue().index('환불 기한은'),out.getvalue().index('환불 신청 기한'))

 def test_search_shows_source_section_and_warning_status(self):
  from tokensaver_docs.storage import save_state
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'doc.pdf.md').write_text('# 원본\n## 페이지 3\n배송은 7일\n')
   save_state(root,{'version':1,'records':{'doc.pdf.md':{'status':'확인필요'}}})
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','배송','--output',tmp]),0)
   self.assertIn('페이지 3',out.getvalue());self.assertIn('확인필요',out.getvalue())

 def test_real_conversion_tracks_multiple_versions(self):
  from docx import Document
  from tokensaver_docs.engine import convert
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'document.docx';output=root/'out'
   for value in ['오래된 계약','이전 계약','최신 계약']:
    doc=Document();doc.add_paragraph(value);doc.save(source)
    self.assertEqual(convert(source,output)[0]['status'],'완료')
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(main(['search','계약','--output',str(output)]),0)
   self.assertIn('최신 계약',out.getvalue());self.assertNotIn('이전 계약',out.getvalue());self.assertNotIn('오래된 계약',out.getvalue())

 def test_failed_conversion_keeps_latest_version_record(self):
  from docx import Document
  from unittest.mock import patch
  from tokensaver_docs.engine import convert
  from tokensaver_docs.storage import load_state
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'document.docx';output=root/'out'
   for value in ['처음','두번째']:
    doc=Document();doc.add_paragraph(value);doc.save(source)
    result=convert(source,output)
   latest=Path(result[0]['output'])
   doc=Document();doc.add_paragraph('변경됨');doc.save(source)
   with patch('tokensaver_docs.engine.units',side_effect=ValueError('임시 실패')):
    self.assertEqual(convert(source,output)[0]['status'],'실패')
   state=load_state(output)['records']['document.docx.md']
   self.assertEqual(state['current_output'],latest.name)
   self.assertTrue(latest.is_file())
