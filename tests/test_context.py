import json
import tempfile
import unittest
from pathlib import Path
from tokensaver_docs.context import document_context

class ContextTests(unittest.TestCase):
    def test_edited_output_is_not_silently_replaced_for_search(self):
        from unittest.mock import patch
        from tokensaver_docs.preparation import prepare_documents
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'page.html'; source.write_text('<p>Refund in 7 days.</p>')
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR':str(root/'cache')}):
                prepared = prepare_documents(source, root/'out', transcribe_images=False)
                result_file = Path(prepared['files'][0]['output'])
                result_file.write_text('User edited refund policy: refund in 30 days.')
                with patch('tokensaver_docs.context.load_profiles', return_value={'image': {'provider':'codex', 'model':'x'}}), patch('tokensaver_docs.providers.generate', side_effect=AssertionError('edited document must not be regenerated')):
                    for configured in (False, True):
                        result = document_context(source, 'refund', root/'out', use_configured_providers=configured)
                        self.assertEqual(result['status'], 'partial')
                        self.assertEqual(result['excerpts'], [])
                        self.assertIn('편집', str(result['pending']))
                self.assertEqual(result_file.read_text(), 'User edited refund policy: refund in 30 days.')

    def test_edited_output_is_not_treated_as_current_after_source_change(self):
        from unittest.mock import patch
        from tokensaver_docs.preparation import prepare_documents
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'page.html'; source.write_text('<p>Refund in 7 days.</p>')
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR':str(root/'cache')}):
                prepared = prepare_documents(source, root/'out', transcribe_images=False)
                result_file = Path(prepared['files'][0]['output'])
                result_file.write_text('User edited refund policy: 30 days.')
                source.write_text('<p>New refund policy: 90 days.</p>')
                result = document_context(source, 'refund', root/'out')
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(result['excerpts'], [])
                self.assertIn('편집', str(result['pending']))

    def test_unprocessed_image_is_reported_as_pending(self):
        from PIL import Image
        from unittest.mock import patch
        from tokensaver_docs.preparation import prepare_documents
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (8, 8), 'red').save(root/'image.png')
            source = root/'page.html'; source.write_text('<p>Intro</p><img src="image.png">')
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR': str(root/'cache')}):
                prepare_documents(source, root/'out', transcribe_images=False)
                result = document_context(source, 'triangle', root/'out')
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(Path(result['pending'][0]['source']).resolve(), source.resolve())

    def test_directory_uses_each_documents_image_choice_offline(self):
        from PIL import Image
        from unittest.mock import patch
        from tokensaver_docs.engine import convert
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); docs = root / 'docs'; docs.mkdir()
            Image.new('RGB', (8, 8), 'red').save(docs / 'image.png')
            first = docs / 'one.html'; first.write_text('<p>First</p><img src="image.png">')
            second = docs / 'two.html'; second.write_text('<p>Second</p><img src="image.png">')
            response = json.dumps({'image_text': 'notice', 'image_description': 'red triangle'})
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR': str(root / 'cache')}), patch('tokensaver_docs.providers.generate', return_value={'text': response}) as generate:
                convert(first, root/'out', profiles={'image': {'provider':'codex', 'model':'x'}}, cache_dir=root/'cache', transcribe_images=True)
                convert(second, root/'out', cache_dir=root/'cache', transcribe_images=False)
                result = document_context(docs, 'triangle', root/'out')
            self.assertEqual(generate.call_count, 1)
            self.assertIn('red triangle', str(result['excerpts']))
            self.assertNotIn('two.html', str(result['excerpts']))

    def test_search_reuses_selected_image_description_without_new_requests(self):
        from PIL import Image
        from unittest.mock import patch
        from tokensaver_docs.preparation import prepare_documents
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); docs = root / 'docs'; docs.mkdir()
            Image.new('RGB', (8, 8), 'red').save(docs/'image.png')
            source = docs/'page.html'; source.write_text('<p>Intro</p><img src="image.png">')
            response = json.dumps({'image_text':'notice', 'image_description':'red triangle'}, ensure_ascii=False)
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR':str(root/'cache')}), patch('tokensaver_docs.preparation.load_profiles', return_value={'image':{'provider':'codex','model':'x'}}), patch('tokensaver_docs.providers.generate', return_value={'text':response}) as generate:
                prepared = prepare_documents(source, root/'out', transcribe_images=True)
                result = document_context(source, 'triangle', root/'out')
                self.assertEqual(generate.call_count, 1)
                self.assertIn('red triangle', str(result['excerpts']))
                self.assertEqual(result['excerpts'][0]['file'], prepared['files'][0]['output'])

    def test_changed_linked_image_cannot_reuse_old_description_as_current(self):
        from PIL import Image
        from unittest.mock import patch
        from tokensaver_docs.preparation import prepare_documents
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); image = root/'image.png'; Image.new('RGB',(8,8),'red').save(image)
            source = root/'page.html'; source.write_text('<p>Intro</p><img src="image.png">')
            response = json.dumps({'image_text':'notice', 'image_description':'red triangle'})
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR':str(root/'cache')}), patch('tokensaver_docs.preparation.load_profiles', return_value={'image':{'provider':'codex','model':'x'}}), patch('tokensaver_docs.providers.generate', return_value={'text':response}) as generate:
                prepare_documents(source, root/'out', transcribe_images=True)
                Image.new('RGB',(8,8),'blue').save(image)
                result = document_context(source, 'triangle', root/'out')
                self.assertEqual(generate.call_count, 1)
                self.assertEqual(result['status'], 'partial')
                self.assertNotIn('red triangle', str(result['excerpts']))

    def test_late_match_and_exception_fit_in_bounded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'policy.md'
            source.write_text('# Policy\n' + 'Unrelated information.\n' * 500 +
                              'Refund deadline is seven days.\nException: custom items excluded.\n', encoding='utf-8')
            result = document_context(source, 'Refund', Path(tmp) / 'out', max_chars=600)
            self.assertIn('Refund deadline is seven days.', str(result['excerpts']))
            self.assertIn('Exception: custom items excluded.', str(result['excerpts']))
            self.assertTrue(result['truncated'])
            self.assertEqual(result['next'], {'file': str(source), 'start_line': 1})
            self.assertGreater(result['excerpts'][0]['start_line'], 1)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), 600)

    def test_late_match_keeps_nearby_preceding_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'policy.md'
            source.write_text('# Policy\n' + 'Unrelated information.\n' * 500 +
                              'Exception: custom items excluded.\nRefund deadline is seven days.\n', encoding='utf-8')
            result = document_context(source, 'Refund', Path(tmp) / 'out', max_chars=600)
            self.assertIn('Refund deadline is seven days.', str(result['excerpts']))
            self.assertIn('Exception: custom items excluded.', str(result['excerpts']))

    def test_prefers_match_and_exception_over_filler_at_budget_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'policy.md'
            source.write_text('# Policy\n' + 'Unrelated information.\n' * 8 +
                              'Refund deadline is seven days.\nException: custom items excluded.\n', encoding='utf-8')
            result = document_context(source, 'Refund', Path(tmp) / 'out', max_chars=500)
            self.assertIn('Refund deadline is seven days.', str(result['excerpts']))
            self.assertIn('Exception: custom items excluded.', str(result['excerpts']))

    def test_directory_context_includes_existing_markdown(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'documents'
            source.mkdir()
            (source / 'policy.md').write_text('# Refund\nRefunds are allowed within 7 days.', encoding='utf-8')
            output = source / 'output'
            output.mkdir()
            (output / 'old.md').write_text('# Refund\nRefunds never allowed.', encoding='utf-8')
            with patch.dict('os.environ', {'TOKENSAVER_DOCS_CACHE_DIR': str(root / 'cache')}):
                result = document_context(source, 'Refunds', output)
            self.assertEqual(result['status'], 'ready')
            self.assertIn('within 7 days', str(result['excerpts']))
            self.assertNotIn('never allowed', str(result['excerpts']))

    def test_conflicting_output_is_not_used_as_evidence(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_output = root / 'old.md'
            old_output.write_text('# Policy\nRefunds allowed for a different customer.', encoding='utf-8')
            conflict = {'file': str(root / 'new.pdf'), 'output': str(old_output), 'status': '충돌'}
            with patch('tokensaver_docs.context.convert', return_value=[conflict]):
                result = document_context(root / 'new.pdf', 'Refunds', root / 'out')
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['excerpts'], [])
            self.assertEqual(result['pending'][0]['status'], '충돌')

    def test_multiline_evidence_preserves_exception_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'policy.md'
            source.write_text('# Refund\nRefund requests\nwithin 7 days.\nException: custom items excluded.\n\n# Other\nSomething else.\n',encoding='utf-8')
            result=document_context(source,'Refund days',Path(tmp)/'out',max_tokens=300)
            self.assertIn('custom items',str(result['excerpts']))
            self.assertIn('7 days',str(result['excerpts']))
            import tiktoken
            self.assertLessEqual(len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(result,ensure_ascii=False))),300)

    def test_tiny_budget_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'a.md';source.write_text('text')
            with self.assertRaises(ValueError):document_context(source,'text',Path(tmp)/'out',max_tokens=1)

    def test_word_rule_and_next_paragraph_exception(self):
        from docx import Document
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'policy.docx'
            doc=Document();doc.add_paragraph('Refunds are allowed within 7 days.');doc.add_paragraph('Exception: custom items excluded.');doc.save(source)
            with patch.dict('os.environ',{'TOKENSAVER_DOCS_CACHE_DIR':str(root/'cache')}):
                result=document_context(source,'Refunds',root/'out',max_tokens=500)
            self.assertIn('custom items',str(result['excerpts']))

    def test_omitted_pending_metadata_remains_marked_truncated(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with patch('tokensaver_docs.context.convert',return_value=[{'file':'x'*5000,'status':'차단'}]):
                result=document_context(Path(tmp)/'input.pdf','refund',Path(tmp)/'out',max_tokens=100)
            self.assertEqual(result['status'],'partial')
            self.assertTrue(result['truncated'])
