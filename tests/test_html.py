import base64
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tokensaver_docs.engine import convert


class HtmlTests(unittest.TestCase):
    def test_css_backgrounds_are_reported_as_unconverted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for number, style in enumerate((
                '<style>.notice { background-image: url(policy.png) }</style><p>본문</p>',
                '<p style="BACKGROUND: url(policy.png) center">본문</p>',
                '<link rel="stylesheet" href="external.css"><p>본문</p>',
            )):
                with self.subTest(style=style):
                    source = root / f'{number}.html'
                    source.write_text(style, encoding='utf-8')
                    result = convert(source, root/'out', cache_dir=root/'cache')[0]
                    self.assertEqual(result['status'], '확인필요')
                    self.assertIn('배경 이미지', Path(result['output']).read_text())
                    again = convert(source, root/'out', cache_dir=root/'cache')[0]
                    self.assertEqual(again['status'], '확인필요')
                    self.assertIn('배경 이미지', Path(again['output']).read_text())

    def test_old_html_cache_is_reparsed_for_background_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'policy.html'
            source.write_text('<style>p { background: url(policy.png) }</style><p>본문</p>')
            old_document = {'text': '본문', 'resources': [], 'base': '', 'warnings': []}
            with patch('tokensaver_docs.html_document.HTML_VERSION', 2), patch('tokensaver_docs.html_document.parse_html', return_value=old_document):
                old = convert(source, root/'out', cache_dir=root/'cache')[0]
            updated = convert(source, root/'out', cache_dir=root/'cache')[0]
            self.assertEqual(updated['status'], '확인필요')
            self.assertIn('배경 이미지', Path(updated['output']).read_text())
            self.assertTrue(Path(old['output']).exists())

    def test_corrupt_embedded_png_does_not_prevent_text_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root/'image.png'
            Image.new('RGB', (2, 2), 'blue').save(image)
            data = bytearray(image.read_bytes())
            chunk = data.index(b'IDAT')
            size = int.from_bytes(data[chunk-4:chunk], 'big')
            data[chunk+4+size] ^= 1
            source = root/'policy.html'
            source.write_text('<p>환불 조건</p><img src="data:image/png;base64,' + base64.b64encode(data).decode() + '">')
            result = convert(source, root/'out', cache_dir=root/'cache')[0]
            self.assertEqual(result['status'], '확인필요')
            text = Path(result['output']).read_text()
            self.assertIn('환불 조건', text)
            self.assertIn('이미지 확인 필요', text)

    def test_large_local_image_does_not_interrupt_folder_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'docs'
            source.mkdir()
            Image.new('RGB', (10, 10), 'blue').save(source/'large.png')
            (source/'first.html').write_text('<p>본문</p><img src="large.png">')
            (source/'second.html').write_text('<p>다른 문서</p>')
            with patch('PIL.Image.MAX_IMAGE_PIXELS', 10):
                results = convert(source, root/'out', cache_dir=root/'cache')
            by_name = {Path(result['file']).name: result for result in results}
            first = by_name['first.html']
            self.assertEqual(first['status'], '확인필요')
            self.assertIn('이미지 확인 필요', Path(first['output']).read_text())
            self.assertEqual(by_name['second.html']['status'], '완료')

    def test_one_call_preparation_never_returns_document_text_or_base64(self):
        from tokensaver_docs.preparation import prepare_documents
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            with patch.dict('os.environ',{'TOKENSAVER_DOCS_CACHE_DIR':str(root/'cache')}), patch('tokensaver_docs.providers.generate',side_effect=AssertionError('no external call')):
                result=prepare_documents(html,root/'out')
            self.assertEqual(result['total'],1)
            payload=json.dumps(result,ensure_ascii=False)
            self.assertNotIn('사진 앞',payload)
            self.assertNotIn('data:image',payload.lower())
            self.assertLessEqual(len(payload),6000)

    def test_html_encoding_and_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            html.write_bytes('<meta charset="cp949"><p>환불은 7일 이내</p>'.encode('cp949'))
            result=convert(html,root/'out',cache_dir=root/'cache')[0]
            self.assertIn('환불은 7일 이내',Path(result['output']).read_text())
            for p in (root/'cache').rglob('parsed.json'):p.write_text('{}')
            result=convert(html,root/'out',cache_dir=root/'cache')[0]
            self.assertEqual(result['status'],'실패')

    def fixture(self, root):
        source=root/'docs';source.mkdir()
        image=source/'a.png';Image.new('RGB',(12,13),'blue').save(image)
        encoded=base64.b64encode(image.read_bytes()).decode()
        html=source/'guide.html'
        html.write_text('<h1>안내</h1><p>사진 앞</p><img alt="규정 사진" src="data:image/png;base64,'+encoded+'"><p>사진 뒤</p><table><colgroup><col><col></colgroup><tr><th>환불</th><th>7일</th></tr></table>',encoding='utf-8')
        return html,image

    def test_html_tool_preserves_image_table_order_and_reuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,image=self.fixture(root)
            with patch('tokensaver_docs.providers.generate',side_effect=AssertionError('no AI')):
                first=convert(html,root/'out',cache_dir=root/'cache')[0]
                self.assertEqual(first['status'],'확인필요',first)
                text=Path(first['output']).read_text()
                self.assertNotIn('base64',text)
                self.assertIn('| ---',text)
                self.assertLess(text.index('사진 앞'),text.index('![규정 사진]'))
                self.assertLess(text.index('![규정 사진]'),text.index('사진 뒤'))
                link=re.search(r'!\[.*?\]\((.*?)\)',text).group(1)
                self.assertTrue(Path(link).name.startswith('guide-image-01-'))
                self.assertTrue(Path(link).name.isascii())
                self.assertEqual((Path(first['output']).parent/link).read_bytes(),image.read_bytes())
                again=convert(html,root/'out',cache_dir=root/'cache')[0]
                self.assertTrue(again['cached'])
                moved=html.with_suffix('.htm');moved.write_bytes(html.read_bytes())
                other=convert(moved,root/'other',cache_dir=root/'cache')[0]
                self.assertTrue(other['structure_cached'])

    def test_changed_local_image_and_edited_assets_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,image=self.fixture(root)
            html.write_text('<p>이미지</p><img src="a.png">',encoding='utf-8')
            first=convert(html,root/'out',cache_dir=root/'cache')[0]
            md=Path(first['output']);link=re.search(r'!\[.*?\]\((.*?)\)',md.read_text()).group(1)
            asset=md.parent/link;asset.write_bytes(b'user edit')
            again=convert(html,root/'out',cache_dir=root/'cache')[0]
            self.assertEqual(asset.read_bytes(),b'user edit')
            self.assertNotEqual(again['output'],first['output'])
            Image.new('RGB',(12,13),'red').save(image)
            changed=convert(html,root/'out',cache_dir=root/'cache')[0]
            self.assertNotEqual(changed['output'],again['output'])

    def test_html_does_not_read_external_or_parent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,image=self.fixture(root)
            html.write_text('<p>본문</p><img src="https://invalid.example/a.png"><img src="../secret.png">')
            result=convert(html,root/'out',cache_dir=root/'cache')[0]
            self.assertEqual(result['status'],'확인필요',result)
            self.assertFalse(list((root/'out').glob('assets/*')))
            analyzed=convert(html,root/'analyzed',cache_dir=root/'cache',transcribe_images=True)[0]
            self.assertEqual(analyzed['status'],'부분완료')
            self.assertFalse(analyzed['image_configuration_required'])
            self.assertEqual(analyzed['image_errors'],2)

    def test_transcription_can_upgrade_saved_html_and_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            profiles={'image':{'provider':'openrouter','model':'selected:free'}}
            with patch('tokensaver_docs.providers.generate',return_value={'text':json.dumps({'image_text':'사진에 적힌 내용','image_description':'파란색 사각형'})}) as calls:
                convert(html,root/'out',profiles=profiles,cache_dir=root/'cache')
                calls.assert_not_called()
                upgraded=convert(html,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertEqual(upgraded['status'],'완료',upgraded)
                self.assertIn('사진에 적힌 내용',Path(upgraded['output']).read_text())
                reused=convert(html,root/'other',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertIn('사진에 적힌 내용',Path(reused['output']).read_text())
                self.assertIn('파란색 사각형',Path(reused['output']).read_text())
                cached_without_profile=convert(html,root/'cached',cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertEqual(cached_without_profile['status'],'완료')
                self.assertIn('파란색 사각형',Path(cached_without_profile['output']).read_text())
                with patch('tokensaver_docs.html_document.UnitStore', side_effect=AssertionError('skip must not read image analysis cache')):
                    skipped=convert(html,root/'skipped',cache_dir=root/'cache')[0]
                self.assertNotIn('사진에 적힌 내용',Path(skipped['output']).read_text())
                self.assertNotIn('파란색 사각형',Path(skipped['output']).read_text())
                self.assertEqual(calls.call_count,1)

    def test_identical_images_only_analyzed_once_and_resume_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,image=self.fixture(root)
            Image.new('RGB',(12,13),'red').save(image.with_name('other.png'))
            html.write_text('<p>앞</p><img src="a.png"><img src="other.png"><img src="a.png"><p>뒤</p>')
            from tokensaver_docs.providers import ConversionError
            good={'text':json.dumps({'image_text':'확인되는 글자 없음','image_description':'색이 있는 사각형'})}
            profiles={'image':{'provider':'openrouter','model':'selected:free'}}
            with patch('tokensaver_docs.providers.generate',side_effect=[good,ConversionError('일시 오류'),good]) as calls:
                first=convert(html,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertEqual(first['status'],'부분완료')
                self.assertEqual(first['ai_calls'],2)
                text=Path(first['output']).read_text()
                self.assertEqual(text.count('색이 있는 사각형'),2)
                self.assertIn('일시 오류',text)
                self.assertEqual(calls.call_count,2)
                second=convert(html,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertEqual(second['status'],'완료')
                self.assertEqual(second['ai_calls'],1)
                self.assertEqual(Path(second['output']).read_text().count('색이 있는 사각형'),3)
                self.assertEqual(calls.call_count,3)
                self.assertTrue(Path(first['output']).exists())

    def test_image_model_needed_preserves_document_and_marks_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            result=convert(html,root/'out',cache_dir=root/'cache',transcribe_images=True)[0]
            self.assertEqual(result['status'],'부분완료')
            self.assertEqual(result['ai_calls'],0)
            self.assertTrue(result['image_configuration_required'])
            self.assertEqual(result['image_errors'],0)
            self.assertIn('이미지 모델을 선택', Path(result['output']).read_text())
            self.assertIn('사진 뒤', Path(result['output']).read_text())

    def test_mixed_missing_provider_and_image_error_reports_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            html.write_text('<img src="a.png"><img src="https://invalid.example/a.png">')
            for _ in range(2):
                result=convert(html,root/'out',cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertTrue(result['image_configuration_required'])
                self.assertEqual(result['image_errors'],1)

    def test_cached_old_state_records_analysis_choice(self):
        from tokensaver_docs.storage import load_state, save_state
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            convert(html,root/'out',cache_dir=root/'cache',transcribe_images=False)
            state=load_state(root/'out')
            state['records'][html.name+'.md'].pop('image_analysis')
            save_state(root/'out',state)
            result=convert(html,root/'out',cache_dir=root/'cache',transcribe_images=False)[0]
            self.assertTrue(result['cached'])
            self.assertIs(load_state(root/'out')['records'][html.name+'.md']['image_analysis'],False)

    def test_duplicate_failure_does_not_retry_without_a_new_run(self):
        from tokensaver_docs.providers import ConversionError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);html,_=self.fixture(root)
            html.write_text('<img src="a.png"><img src="a.png">')
            profiles={'image':{'provider':'openrouter','model':'selected:free'}}
            with patch('tokensaver_docs.providers.generate',side_effect=ConversionError('일시 오류')) as calls:
                result=convert(html,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertEqual(result['status'],'부분완료')
                self.assertEqual(calls.call_count,1)
                self.assertEqual(result['ai_calls'],1)
                self.assertEqual(Path(result['output']).read_text().count('일시 오류'),2)

    def test_duplicate_failure_across_documents_retries_only_on_next_run(self):
        from tokensaver_docs.providers import ConversionError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'docs'; source.mkdir()
            Image.new('RGB',(12,13),'blue').save(source/'a.png')
            for name in ('one.html','two.html'):
                (source/name).write_text('<img src="a.png">')
            profiles={'image':{'provider':'openrouter','model':'selected:free'}}
            good={'text':json.dumps({'image_text':'확인되는 글자 없음','image_description':'파란 사각형'})}
            with patch('tokensaver_docs.providers.generate',side_effect=[ConversionError('일시 오류'),good]) as calls:
                first=convert(source,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)
                documents=[r for r in first if r['file'].endswith('.html')]
                self.assertEqual(len(documents),2)
                self.assertTrue(all(r['status']=='부분완료' for r in documents))
                self.assertEqual(calls.call_count,1)
                second=convert(source,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)
                self.assertEqual(calls.call_count,2)
                self.assertTrue(all(r['status']=='완료' for r in second if r['file'].endswith('.html')))

    def test_multiframe_image_preserves_success_when_a_frame_fails(self):
        from tokensaver_docs.providers import ConversionError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'multi.tiff'
            Image.new('RGB',(10,10),'red').save(source,save_all=True,append_images=[Image.new('RGB',(10,10),'blue')])
            html=root/'guide.html';html.write_text('<p>전</p><img src="multi.tiff"><p>후</p>')
            profiles={'image':{'provider':'openrouter','model':'selected:free'}}
            good={'text':json.dumps({'image_text':'확인되는 글자 없음','image_description':'색이 있는 사각형'})}
            with patch('tokensaver_docs.providers.generate',side_effect=[good,ConversionError('일시 오류'),good]) as calls:
                first=convert(html,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                text=Path(first['output']).read_text()
                self.assertEqual(first['status'],'부분완료')
                self.assertIn('프레임 1/2',text)
                self.assertIn('색이 있는 사각형',text)
                self.assertIn('프레임 2/2: 일시 오류',text)
                second=convert(html,root/'out',profiles=profiles,cache_dir=root/'cache',transcribe_images=True)[0]
                self.assertEqual(second['status'],'완료')
                self.assertEqual(calls.call_count,3)
