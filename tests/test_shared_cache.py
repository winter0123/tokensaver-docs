import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from file_to_md.engine import convert


class SharedCacheTests(unittest.TestCase):
    def test_standalone_gif_is_discovered_and_preserved(self):
        import re
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            image = source / 'picture.gif'
            Image.new('RGB', (10, 12), 'red').save(image)
            with patch('file_to_md.providers.generate', side_effect=AssertionError('provider must not run')):
                records = convert(source, root/'out', cache_dir=root/'cache', transcribe_images=False)
            self.assertEqual(len(records), 1)
            markdown = Path(records[0]['output'])
            link = re.search(r'!\[[^\]]*\]\(([^)]+)\)', markdown.read_text()).group(1)
            self.assertEqual((markdown.parent / link).read_bytes(), image.read_bytes())
            self.assertEqual(records[0]['untranscribed_images'], 1)

    def test_refresh_reuses_image_once_across_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            Image.new('RGB', (10, 12), 'red').save(source/'a.png')
            shutil.copy2(source/'a.png', source/'b.png')
            (source/'c.html').write_text('<img src="a.png"><img src="b.png">')
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            response = {'text': json.dumps({'image_text': 'no text', 'image_description': 'red square'})}
            with patch('file_to_md.providers.generate', return_value=response) as calls:
                records = convert(source, root/'out', profiles=profile, cache_dir=root/'cache', transcribe_images=True, refresh=True)
                self.assertEqual(calls.call_count, 1)
                self.assertTrue(all(r['status'] == '완료' for r in records), records)
                convert(source, root/'out', profiles=profile, cache_dir=root/'cache', transcribe_images=True, refresh=True)
                self.assertEqual(calls.call_count, 2)

    def test_refresh_reuses_image_across_html_without_shared_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            image = root / 'image.png'
            Image.new('RGB', (10, 12), 'red').save(image)
            import base64
            uri = 'data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode()
            (source/'a.html').write_text(f'<img src="{uri}">')
            (source/'b.html').write_text(f'<img src="{uri}">')
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            response = {'text': json.dumps({'image_text': 'no text', 'image_description': 'red square'})}
            with patch('file_to_md.providers.generate', return_value=response) as calls:
                records = convert(source, root/'out', profiles=profile, transcribe_images=True, refresh=True)
                self.assertTrue(all(r['status'] == '완료' for r in records), records)
                self.assertEqual(calls.call_count, 1)

    def test_refresh_reuses_image_across_html_and_image_without_shared_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            Image.new('RGB', (10, 12), 'red').save(source/'a.png')
            (source/'b.html').write_text('<img src="a.png">')
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            response = {'text': json.dumps({'image_text': 'no text', 'image_description': 'red square'})}
            with patch('file_to_md.providers.generate', return_value=response) as calls:
                records = convert(source, root/'out', profiles=profile, transcribe_images=True, refresh=True)
                self.assertTrue(all(r['status'] == '완료' for r in records), records)
                self.assertEqual(calls.call_count, 1)

    @unittest.skipIf(os.name == 'nt', 'Windows does not permit backslashes or newlines in filenames')
    def test_image_filename_is_safe_in_markdown_alt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / 'a[b]\\c\n.png'
            Image.new('RGB', (10, 12), 'red').save(image)
            record = convert(image, root/'out', cache_dir=root/'cache', transcribe_images=False)[0]
            text = Path(record['output']).read_text()
            self.assertIn(r'![a\[b\]\\c .png](', text)

    def test_embedded_word_and_excel_images_are_preserved_across_outputs(self):
        import re
        from docx import Document
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as SheetImage
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root/'source'
            source.mkdir()
            image = root/'image.png'
            Image.new('RGB', (12, 14), 'blue').save(image)
            doc = Document()
            doc.add_paragraph('before')
            doc.add_picture(str(image))
            doc.add_paragraph('after')
            doc.save(source/'doc.docx')
            book = Workbook()
            book.active.add_image(SheetImage(str(image)))
            book.save(source/'book.xlsx')
            with patch('file_to_md.providers.generate', side_effect=AssertionError('must not call provider')):
                first = convert(source, root/'one', cache_dir=root/'cache', transcribe_images=False)
                second = convert(source, root/'two', cache_dir=root/'cache', transcribe_images=False)
            for record in first + second:
                md = Path(record['output'])
                text = md.read_text()
                links = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text)
                self.assertTrue(links, text)
                self.assertTrue(any((md.parent/link).read_bytes() == image.read_bytes() for link in links))
                if md.name.startswith('doc.'):
                    self.assertLess(text.index('before'), text.index('!['))
                    self.assertLess(text.index('!['), text.index('after'))

    def test_duplicate_image_failure_is_retried_only_on_next_conversion(self):
        from file_to_md.providers import ConversionError
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            Image.new('RGB', (10, 12), 'red').save(source/'a.png')
            shutil.copy2(source/'a.png', source/'b.png')
            (source/'c.html').write_text('<img src="a.png">')
            (source/'d.html').write_text('<img src="b.png">')
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            with patch('file_to_md.providers.generate', side_effect=ConversionError('provider failed')) as calls:
                first = convert(source, root/'out', profiles=profile, cache_dir=root/'cache', transcribe_images=True)
                self.assertEqual(calls.call_count, 1)
                self.assertEqual(len(first), 4)
                self.assertTrue(all(x['status'] in ('실패', '부분완료') for x in first))
                convert(source, root/'out', profiles=profile, cache_dir=root/'cache', transcribe_images=True)
                self.assertEqual(calls.call_count, 2)

    def test_cached_image_restores_missing_asset_and_preserves_edited_asset(self):
        import re
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'picture.png'
            Image.new('RGB', (10, 12), 'red').save(source)
            output, cache = root/'out', root/'cache'
            first = convert(source, output, cache_dir=cache, transcribe_images=False)[0]
            first_md = Path(first['output'])
            image = first_md.parent / re.search(r'!\[[^\]]*\]\(([^)]+)\)', first_md.read_text()).group(1)
            image.unlink()
            restored = convert(source, output, cache_dir=cache, transcribe_images=False)[0]
            self.assertEqual(Path(restored['output']).resolve(), first_md.resolve())
            self.assertEqual(image.read_bytes(), source.read_bytes())
            image.write_bytes(b'user edit')
            revised = convert(source, output, cache_dir=cache, transcribe_images=False)[0]
            self.assertEqual(image.read_bytes(), b'user edit')
            self.assertNotEqual(Path(revised['output']).resolve(), first_md.resolve())
            new_md = Path(revised['output'])
            new_image = new_md.parent / re.search(r'!\[[^\]]*\]\(([^)]+)\)', new_md.read_text()).group(1)
            self.assertEqual(new_image.read_bytes(), source.read_bytes())

    def test_missing_image_model_reports_unprocessed_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'picture.png'
            Image.new('RGB', (10, 12), 'red').save(source)
            record = convert(source, root/'out', cache_dir=root/'cache', transcribe_images=True)[0]
            self.assertEqual(record['status'], '차단')
            self.assertEqual(record['images'], 1)
            self.assertEqual(record['untranscribed_images'], 1)
            self.assertEqual(record['ai_calls'], 0)

    def test_cached_result_preserves_image_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'picture.png'
            Image.new('RGB', (10, 12), 'red').save(source)
            first = convert(source, root/'out', cache_dir=root/'cache', transcribe_images=False)[0]
            repeated = convert(source, root/'out', cache_dir=root/'cache', transcribe_images=False)[0]
            moved = convert(source, root/'other', cache_dir=root/'cache', transcribe_images=False)[0]
            for record in (first, repeated, moved):
                self.assertEqual(record['images'], 1)
                self.assertEqual(record['untranscribed_images'], 1)

    def test_standalone_skip_preserves_image_and_ignores_analysis_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'picture.png'
            Image.new('RGB', (10, 12), 'red').save(source)
            profile = {'image': {'provider': 'codex', 'model': 'chosen'}}
            with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': 'analysis', 'image_description': 'fixture image'})}) as calls:
                convert(source, root/'analyzed', profiles=profile, cache_dir=root/'cache', transcribe_images=True)
                skipped = convert(source, root/'skipped', profiles=profile, cache_dir=root/'cache', transcribe_images=False)[0]
            text = Path(skipped['output']).read_text()
            self.assertIn('](assets/', text)
            self.assertNotIn('analysis', text)
            self.assertEqual(calls.call_count, 1)
            self.assertTrue(any(p.read_bytes() == source.read_bytes() for p in (root/'skipped/assets').iterdir()))

    def test_stale_shared_result_is_rebuilt_without_losing_edits_or_media(self):
        import json
        from file_to_md.storage import digest, load_state, save_state
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'doc.pdf'
            source.write_bytes(b'source')
            image = root / 'asset.png'
            Image.new('RGB', (13, 17), 'blue').save(image)
            def units(*args):
                yield {'id': 'text', 'title': 'Text', 'text': 'complete text'}
                yield {'id': 'image', 'title': 'Image', 'kind': 'image', 'path': image}
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            with patch('file_to_md.engine.units', side_effect=units), patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': 'transcribed', 'image_description': 'fixture image'})}) as calls:
                first = convert(source, root / 'out', profiles=profile, cache_dir=root / 'cache')
                entry_path = next((root / 'cache').glob('*/entry.json'))
                entry = json.loads(entry_path.read_text())
                entry['identity'].pop('version', None)
                entry['body'] = entry['body'].replace('complete text', 'obsolete document')
                entry['body_hash'] = digest(entry['body'].encode())
                old_key = digest(json.dumps(entry['identity'], sort_keys=True).encode())
                old_folder = root / 'cache' / old_key
                if old_folder != entry_path.parent:
                    entry_path.parent.rename(old_folder)
                (old_folder / 'entry.json').write_text(json.dumps(entry))
                state = load_state(root / 'out')
                state['records']['doc.pdf.md']['signature'] = 'old extractor version'
                state['records']['doc.pdf.md']['shared_key'] = old_key
                save_state(root / 'out', state)
                original = Path(first[0]['output'])
                original.write_text('user edit')
                result = convert(source, root / 'out', cache_dir=root / 'cache')
                self.assertEqual(original.read_text(), 'user edit')
                self.assertIn('complete text', Path(result[0]['output']).read_text())
                self.assertIn('transcribed', Path(result[0]['output']).read_text())
                self.assertEqual(calls.call_count, 1)

    def test_oversize_file_does_not_prevent_other_files_in_folder(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            with (source / 'a.pdf').open('wb') as large:
                large.truncate(100 * 1024 * 1024 + 1)
            document = Document()
            document.add_paragraph('small document')
            document.save(source / 'b.docx')
            result = convert(source, root / 'out', cache_dir=root / 'cache')
            by_name = {Path(item['file']).name: item for item in result}
            self.assertEqual(by_name['a.pdf']['status'], '실패')
            self.assertEqual(by_name['b.docx']['status'], '완료')
            self.assertIn('small document', Path(by_name['b.docx']['output']).read_text())

    def test_old_pdf_cache_must_prove_requested_visual_pages_were_transcribed(self):
        import json
        from file_to_md.storage import digest
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'document.pdf'
            source.write_bytes(b'unchanged pdf')
            def text_units(*args):
                yield {'id': 'page-1', 'title': '페이지 1', 'text': 'text only'}
            with patch('file_to_md.engine.units', side_effect=text_units):
                convert(source, root / 'one', cache_dir=root / 'cache')
            entry = json.loads(next((root / 'cache').glob('*/entry.json')).read_text())
            entry['identity']['pages'] = [1]
            key = digest(json.dumps(entry['identity'], sort_keys=True).encode())
            target = root / 'cache' / key
            target.mkdir()
            (target / 'entry.json').write_text(json.dumps(entry), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '재변환'):
                convert(source, root / 'two', vision_pages={1}, cache_dir=root / 'cache')

    def test_edit_after_conversion_is_not_saved_as_shared_transcription(self):
        from file_to_md.engine import _convert_local
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'image.png'
            Image.new('RGB', (13, 17), 'blue').save(source)
            def edit_after_local(*args, **kwargs):
                result = _convert_local(*args, **kwargs)
                Path(result[0]['output']).write_text('# Edited\n\n## Text\n\nUSER EDIT', encoding='utf-8')
                return result
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            with patch('file_to_md.engine._convert_local', side_effect=edit_after_local), patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': 'original transcription', 'image_description': 'fixture image'})}) as calls:
                first = convert(source, root / 'one', profiles=profile, cache_dir=root / 'cache')
            with patch('file_to_md.providers.generate', side_effect=AssertionError('unit should be reused')):
                second = convert(source, root / 'two', cache_dir=root / 'cache')
            self.assertEqual(calls.call_count, 1)
            self.assertIn('USER EDIT', Path(first[0]['output']).read_text())
            self.assertIn('original transcription', Path(second[0]['output']).read_text())
            self.assertNotIn('USER EDIT', Path(second[0]['output']).read_text())

    def test_requested_pdf_vision_pages_are_not_replaced_by_prior_text_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'document.pdf'
            source.write_bytes(b'unchanged pdf')
            image = root / 'page.png'
            Image.new('RGB', (13, 17), 'blue').save(image)
            def pdf_units(path, folder, pages, chunk):
                if 1 in pages:
                    yield {'id': 'page-1', 'title': '페이지 1', 'kind': 'image', 'path': image}
                else:
                    yield {'id': 'page-1', 'title': '페이지 1', 'text': 'extracted text'}
            profile = {'image': {'provider': 'codex', 'model': 'selected'}}
            with patch('file_to_md.engine.units', side_effect=pdf_units), patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': 'image transcription', 'image_description': 'fixture image'})}) as calls:
                convert(source, root / 'out', cache_dir=root / 'cache')
                selected = convert(source, root / 'out', profiles=profile, vision_pages={1}, cache_dir=root / 'cache')
                reused = convert(source, root / 'other', vision_pages={1}, cache_dir=root / 'cache')
            self.assertEqual(calls.call_count, 1)
            self.assertIn('image transcription', Path(selected[0]['output']).read_text())
            self.assertIn('image transcription', Path(reused[0]['output']).read_text())

    def test_reuses_renamed_source_and_different_output_without_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'first.png'
            Image.new('RGB', (13, 17), 'blue').save(source)
            cache = root / 'cache'
            with patch('file_to_md.providers.generate', return_value={'text': json.dumps({'image_text': '원문 123', 'image_description': 'fixture image'})}) as call:
                first = convert(source, root / 'out1', profiles={'image': {'provider': 'codex', 'model': 'selected'}}, cache_dir=cache)
                renamed = root / 'renamed.png'
                shutil.copy2(source, renamed)
                second = convert(renamed, root / 'out2', cache_dir=cache)
            self.assertEqual(first[0]['status'], '완료')
            self.assertEqual(call.call_count, 1)
            self.assertTrue(second[0]['cached'])
            text = Path(second[0]['output']).read_text()
            self.assertIn(str(renamed.resolve()), text)
            self.assertNotIn(str(source.resolve()), text)

    def test_nested_paths_refresh_and_edited_output_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); source=root/'src'; (source/'nested').mkdir(parents=True)
            Image.new('RGB',(17,19),'green').save(source/'nested/a.png')
            cache=root/'cache'; output=root/'out'
            profile={'image':{'provider':'codex','model':'selected'}}
            with patch('file_to_md.providers.generate', return_value={'text':json.dumps({'image_text': '처음 전사', 'image_description': 'fixture image'})}) as call:
                convert(source,output,profiles=profile,cache_dir=cache)
                current=output/'nested/a.png.md';current.write_text('사용자 편집')
                result=convert(source,output,cache_dir=cache)
                self.assertEqual(call.call_count,1)
                self.assertEqual(current.read_text(),'사용자 편집')
                self.assertIn('처음 전사',Path(result[0]['output']).read_text())
                result=convert(source,output,profiles=profile,cache_dir=cache,refresh=True)
                self.assertEqual(call.call_count,2)
                self.assertEqual(current.read_text(),'사용자 편집')

    def test_changed_source_and_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'a.png';cache=root/'cache'
            profile={'image':{'provider':'codex','model':'selected'}}
            Image.new('RGB',(17,19),'blue').save(source)
            with patch('file_to_md.providers.generate',return_value={'text':json.dumps({'image_text': '전사', 'image_description': 'fixture image'})}) as call:
                convert(source,root/'one',profiles=profile,cache_dir=cache)
                Image.new('RGB',(17,19),'red').save(source)
                convert(source,root/'two',profiles=profile,cache_dir=cache)
                self.assertEqual(call.call_count,2)
                for entry in cache.rglob('entry.json'):entry.write_text('{}')
                with self.assertRaises(ValueError):convert(source,root/'three',cache_dir=cache)
                self.assertEqual(call.call_count,2)

    def test_partial_resume_in_another_output_and_changed_document_units(self):
        from file_to_md.providers import ConversionError
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); source=root/'pages.pdf';source.write_bytes(b'first source')
            image1=root/'first.png';image2=root/'second.png'
            Image.new('RGB',(9,10),'yellow').save(image1)
            Image.new('RGB',(9,10),'purple').save(image2)
            def units(*args):
                yield {'id':'one','title':'First','kind':'image','path':image1}
                yield {'id':'two','title':'Second','kind':'image','path':image2}
            profile={'image':{'provider':'codex','model':'selected'}}
            with patch('file_to_md.engine.units',side_effect=units), patch('file_to_md.providers.generate',side_effect=[{'text':json.dumps({'image_text': 'first', 'image_description': 'fixture image'})},ConversionError('temporary')]) as calls:
                result=convert(source,root/'one',profiles=profile,cache_dir=root/'cache')
                self.assertEqual(result[0]['status'],'부분완료')
                self.assertEqual(calls.call_count,2)
            with patch('file_to_md.engine.units',side_effect=units), patch('file_to_md.providers.generate',return_value={'text':json.dumps({'image_text': 'second', 'image_description': 'fixture image'})}) as calls:
                result=convert(source,root/'two',profiles=profile,cache_dir=root/'cache')
                self.assertEqual(result[0]['status'],'완료')
                self.assertEqual(calls.call_count,1)
            source.write_bytes(b'changed source')
            with patch('file_to_md.engine.units',side_effect=units), patch('file_to_md.providers.generate',side_effect=AssertionError('must reuse units')):
                result=convert(source,root/'three',cache_dir=root/'cache')
                self.assertEqual(result[0]['status'],'완료')

    def test_legacy_exact_result_is_imported_without_transcription(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'a.png';Image.new('RGB',(17,23),'cyan').save(source)
            profile={'image':{'provider':'codex','model':'selected'}}
            with patch('file_to_md.providers.generate',return_value={'text':json.dumps({'image_text': 'legacy', 'image_description': 'fixture image'})}) as call:
                convert(source,root/'old',profiles=profile)
                convert(source,root/'old',profiles=profile,cache_dir=root/'cache')
                result=convert(source,root/'new',cache_dir=root/'cache')
                self.assertEqual(call.call_count,1)
                self.assertTrue(result[0]['cached'])

    def test_shared_unit_cache_serializes_processes(self):
        import os, subprocess, sys
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);asset=root/'asset.png';Image.new('RGB',(17,23),'cyan').save(asset)
            code = '''import sys,time,json
from pathlib import Path
from file_to_md.shared_cache import UnitStore
root=Path(sys.argv[1])
def produce():
 with (root/'calls').open('a') as f:f.write('call\\n')
 time.sleep(0.5)
 return {'text':'shared'}
result,cached=UnitStore(root).obtain(root/'asset.png','image',produce)
assert result['text']=='shared'
'''
            processes=[subprocess.Popen([sys.executable,'-c',code,str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
            completed=[p.communicate(timeout=20) for p in processes]
            for p,(out,err) in zip(processes,completed):
                self.assertEqual(p.returncode,0,err.decode())
            self.assertEqual((root/'calls').read_text().splitlines(),['call'])

    def test_same_source_is_transcribed_once_across_processes(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);Image.new('RGB',(23,29),'magenta').save(root/'asset.png')
            code='''import sys,time,json
from pathlib import Path
from unittest.mock import patch
from file_to_md.engine import convert
root=Path(sys.argv[1])
def generate(*args):
 with (root/'calls').open('a') as f:f.write('call\\n')
 time.sleep(0.3)
 return {'text':json.dumps({'image_text': 'shared source', 'image_description': 'fixture image'})}
with patch('file_to_md.providers.generate',side_effect=generate):
 r=convert(root/'asset.png',root/sys.argv[2],cache_dir=root/'cache',profiles={'image':{'provider':'codex','model':'mock'}})
 assert r[0]['status']=='완료',r
'''
            processes=[subprocess.Popen([sys.executable,'-c',code,str(root),name],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for name in ('one','two')]
            completed=[p.communicate(timeout=20) for p in processes]
            for p,(_,err) in zip(processes,completed):self.assertEqual(p.returncode,0,err.decode())
            self.assertEqual((root/'calls').read_text().splitlines(),['call'])
