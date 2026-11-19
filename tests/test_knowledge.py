import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tokensaver_docs.knowledge import INBOX, STORE, activate, adopt, hook, search, sync, versions


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        cache = patch.dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(self.root / 'cache'),
                           XDG_CONFIG_HOME=str(self.root / 'config'))
        cache.start()
        self.addCleanup(cache.stop)
        self.inbox = self.root / INBOX
        self.store = self.root / STORE

    def test_hook_archives_and_searches_without_model_calls(self):
        self.assertEqual(hook({'cwd':str(self.root), 'hook_event_name':'Stop'}), {})
        self.assertFalse(self.store.exists())
        activate(self.root)
        self.assertIn('/docs/research/inbox/', (self.root/'.gitignore').read_text())
        prompt = {'cwd':str(self.root), 'hook_event_name':'UserPromptSubmit', 'prompt':'환불 규정 조사해줘'}
        self.assertIn('research.json', hook(prompt)['hookSpecificOutput']['additionalContext'])
        prompt['prompt'] = '상품 반품 기한 찾아보고 프로젝트에 정리해줘'
        self.assertIn('research.json', hook(prompt)['hookSpecificOutput']['additionalContext'])
        prompt['prompt'] = '저번에 찾아둔 반품 정책의 예외가 뭐였지?'
        follow_up = hook(prompt)['hookSpecificOutput']['additionalContext']
        self.assertIn('First use search_research', follow_up)
        self.assertIn('FOCUSED KEYWORDS', follow_up)
        self.assertIn('one quoted argument', follow_up)
        original = self.inbox/'policy.txt'
        original.write_text('# Policy\nReturns within seven days.\n', encoding='utf-8')
        (self.inbox/'copy.md').write_bytes(original.read_bytes())
        draft = {'topic':'refund', 'conclusion':'Seven days', 'evidence':[
            {'source':f'{INBOX.as_posix()}/policy.txt', 'quote':'Returns within seven days.'}]}
        (self.inbox/'refund.research.json').write_text(json.dumps(draft), encoding='utf-8')
        with patch('tokensaver_docs.providers.generate', side_effect=AssertionError('unexpected call')):
            self.assertEqual(hook({'cwd':str(self.root), 'hook_event_name':'Stop'}), {})
            result = json.loads(search(self.root, 'Returns'))
            self.assertEqual(result['status'], 'ready')
            first = result['excerpts'][0]
            self.assertTrue((self.root / result['sources'][first['source_index']]).is_file())
            self.assertNotIn('file', first)
        self.assertEqual(len(list((self.store/'raw/objects').iterdir())), 1)
        self.assertEqual(len(list(versions(self.store))), 2)
        summary = self.store/'reports/refund/summary.md'
        self.assertIn('#L2', summary.read_text())
        self.assertIn('[원본]', summary.read_text())
        self.assertEqual(sync(self.root)['updated'], 0)

        original.write_text('# Policy\nReturns within ten days.\n', encoding='utf-8')
        self.assertEqual(sync(self.root)['updated'], 1)
        self.assertIn('새 원본 버전 확인 필요', (self.store/'index.md').read_text())
        self.assertIn('seven days', summary.read_text())
        summary.write_text('Human revision', encoding='utf-8')
        draft['conclusion'] = 'Ten days'
        draft['evidence'][0]['quote'] = 'Returns within ten days.'
        (self.inbox/'refund.research.json').write_text(json.dumps(draft), encoding='utf-8')
        self.assertEqual(sync(self.root)['status'], 'ready')
        self.assertEqual(summary.read_text(), 'Human revision')
        self.assertEqual(len(list(summary.parent.glob('summary.pending-*.md'))), 1)

    def test_linked_image_changes_version_and_corruption_blocks_evidence(self):
        activate(self.root)
        page = self.inbox/'page.html'
        page.write_text('<p>Refund policy</p><img src="photo.png">', encoding='utf-8')
        image = self.inbox/'photo.png'
        Image.new('RGB', (8, 8), 'red').save(image)
        self.assertEqual(sync(self.root)['status'], 'ready')
        page_records = [r for r in versions(self.store) if r['source'].endswith('/page.html')]
        self.assertEqual(len(page_records[0]['files']), 2)
        Image.new('RGB', (8, 8), 'blue').save(image)
        self.assertEqual(sync(self.root)['status'], 'ready')
        page_records = [r for r in versions(self.store) if r['source'].endswith('/page.html')]
        newest = max(page_records, key=lambda r: r['captured_ns'])
        self.assertIsNotNone(newest['previous'])
        image.unlink()
        self.assertEqual(sync(self.root)['status'], 'ready')
        page_records = [r for r in versions(self.store) if r['source'].endswith('/page.html')]
        missing = max(page_records, key=lambda r: r['captured_ns'])
        self.assertEqual(missing['previous'], newest['id'])
        self.assertEqual(missing['missing_assets'], 1)
        sha = newest['files'][newest['source']]
        next((self.store/'raw/objects'/sha).iterdir()).write_bytes(b'corrupt')
        result = json.loads(search(self.root, 'Refund', version=newest['id']))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['excerpts'], [])
        self.assertEqual(result['pending'][0]['status'], 'integrity_error')

    def test_existing_transcription_can_be_attached_without_inference(self):
        from tokensaver_docs.storage import file_hash, save_state

        activate(self.root)
        source = self.inbox/'audio.wav'
        source.write_bytes(b'audio fixture')
        self.assertEqual(sync(self.root)['status'], 'ready')
        self.assertEqual(next(versions(self.store))['status'], 'needs_transcription')
        prior = self.root/'converted'
        prior.mkdir()
        md = prior/'audio.wav.md'
        md.write_text('## Audio 0–2 seconds\nRefunds are covered.', encoding='utf-8')
        save_state(prior, {'version':1, 'records':{'audio.wav.md':{
            'source':str(source), 'source_hash':file_hash(source), 'current_output':md.name,
            'output_hash':file_hash(md), 'status':'완료'}}})
        with patch('tokensaver_docs.providers.generate', side_effect=AssertionError('unexpected call')):
            first = adopt(self.root, source.relative_to(self.root), 'converted')
            self.assertEqual(first['status'], 'ready')
        self.assertIn('Refunds are covered.', search(self.root, 'Refunds'))
        md.write_text('Refunds are excluded.', encoding='utf-8')
        state_path = prior / '.tokensaver-docs/state.json'
        state = json.loads(state_path.read_text())
        state['records']['audio.wav.md']['output_hash'] = file_hash(md)
        save_state(prior, state)
        second = adopt(self.root, source.relative_to(self.root), 'converted')
        self.assertEqual(first['version_id'], second['version_id'])
        self.assertNotEqual(first['conversion_id'], second['conversion_id'])
        self.assertIn('Refunds are excluded.', search(self.root, 'Refunds'))
        self.assertIn('Refunds are covered.', search(self.root, 'Refunds',
            version=first['version_id'], conversion=first['conversion_id']))

    def test_pending_audio_and_long_line_leave_room_for_evidence(self):
        from tokensaver_docs.cli import token_encoder

        activate(self.root)
        for index in range(30):
            (self.inbox / f'audio-{index}.wav').write_bytes(b'fixture')
        (self.inbox / 'policy.md').write_text('Filler word. ' * 500 + 'Refund deadline: seven days.', encoding='utf-8')
        self.assertEqual(sync(self.root)['status'], 'ready')
        response = search(self.root, 'refund deadline')
        self.assertLessEqual(len(token_encoder('cl100k_base').encode(response)), 500)
        parsed = json.loads(response)
        self.assertIn('seven days', parsed['excerpts'][0]['text'])
        self.assertTrue(parsed['excerpts'][0]['clipped'])
        self.assertEqual(parsed['excerpts'][0]['start_line'], 1)

    def test_late_evidence_updates_report_and_keeps_pinned_citation(self):
        activate(self.root)
        draft = self.inbox / 'shipping.research.json'
        first = self.inbox / 'delivery.md'
        second = self.inbox / 'exception.md'
        first.write_text('Delivery takes seven days.\n')
        draft.write_text(json.dumps({'topic':'shipping','conclusion':'Draft','evidence':[
            {'source':first.relative_to(self.root).as_posix(),'quote':'Delivery takes seven days.'},
            {'source':second.relative_to(self.root).as_posix(),'quote':'International orders are excluded.'}]}))
        self.assertEqual(sync(self.root)['status'], 'ready')
        summary = self.store / 'reports/shipping/summary.md'
        initial = summary.read_text()
        self.assertIn('근거 확인 필요', initial)
        original_citation = next(line for line in initial.splitlines() if '#L1' in line)
        summary.write_bytes(summary.read_bytes().replace(b'\n', b'\r\n'))
        first.write_text('Delivery takes ten days.\n')
        second.write_text('International orders are excluded.\n')
        self.assertEqual(sync(self.root)['status'], 'ready')
        updated = summary.read_text()
        self.assertEqual(updated.count('#L1'), 2)
        self.assertIn(original_citation, updated)
        self.assertFalse(list(summary.parent.glob('summary.pending-*.md')))
        self.assertNotIn(b'\r\n', summary.read_bytes())

    def test_source_name_prioritizes_relevant_topic_under_budget(self):
        activate(self.root)
        (self.inbox / 'policy.md').write_text('# Shipping\n배송 규정 기간 예외와 테스트\n' + 'Unrelated policy.\n' * 80)
        (self.inbox / 'shipping-insurance.md').write_text('가입 후 11일 동안 유효\n해외 운송 제외\n')
        sync(self.root)
        response = json.loads(search(self.root, 'shipping insurance 배송 기간 예외 해외 운송'))
        self.assertIn('11일 동안 유효', response['excerpts'][0]['text'])
        self.assertIn('해외 운송 제외', response['excerpts'][0]['text'])

    def test_codex_fallback_keeps_existing_hooks_and_disable_keeps_archive(self):
        from tokensaver_docs.knowledge import deactivate

        settings = self.root / '.codex/hooks.json'
        settings.parent.mkdir()
        existing = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'existing'}]}]}}
        settings.write_text(json.dumps(existing), encoding='utf-8')
        activate(self.root, codex_project_hooks=True)
        activate(self.root, codex_project_hooks=True, claude_project_hooks=True)
        claude = self.root / '.claude/settings.local.json'
        self.assertIn('Stop', json.loads(claude.read_text())['hooks'])
        hooks = json.loads(settings.read_text())['hooks']
        self.assertEqual(hooks['Stop'][0], existing['hooks']['Stop'][0])
        self.assertEqual(len(hooks['Stop']), 2)
        (self.inbox/'one.md').write_text('Evidence', encoding='utf-8')
        self.assertEqual(sync(self.root)['updated'], 1)
        deactivate(self.root)
        self.assertEqual(sync(self.root)['status'], 'disabled')
        self.assertEqual(len(list(versions(self.store))), 1)
        self.assertEqual(json.loads(settings.read_text()), existing)
        self.assertEqual(json.loads(claude.read_text()), {'hooks': {}})

    def test_web_snapshots_require_local_exact_domain_opt_in(self):
        from tokensaver_docs.research_web import public_address
        activate(self.root)
        url = 'https://docs.example.org/returns'
        draft = self.inbox / 'web.research.json'
        draft.write_text(json.dumps({'topic':'web','conclusion':'Draft','references':[
            url, 'https://elsewhere.example.org/private', 'https://docs.example.org/token?key=private']}))
        with patch('tokensaver_docs.research_web.fetch_html', return_value=b'<p>Return window is nine days.</p>') as get:
            sync(self.root)
            get.assert_not_called()
            report = self.store / 'reports/web/summary.md'
            self.assertIn('REFERENCE_ONLY', report.read_text())
            activate(self.root, snapshot_domains=['docs.example.org'])
            sync(self.root)
            sync(self.root)
            get.assert_called_once_with('docs.example.org', '/returns')
        self.assertIn('원문 스냅샷', report.read_text())
        self.assertIn('nine days', search(self.root, 'return window'))
        with patch('socket.getaddrinfo', return_value=[(0, 0, 0, '', ('127.0.0.1', 443))]):
            with self.assertRaisesRegex(ValueError, 'non-public'):
                public_address('docs.example.org')

    def test_snapshot_fetch_rejects_redirects_without_following_them(self):
        from tokensaver_docs.research_web import fetch_html
        with patch('tokensaver_docs.research_web.public_address', return_value='93.184.216.34'), \
             patch('http.client.HTTPSConnection') as connect:
            connection = connect.return_value
            connection.getresponse.return_value.status = 302
            with self.assertRaisesRegex(ValueError, 'direct HTML'):
                fetch_html('docs.example.org', '/redirect')
            connection.request.assert_called_once()
            connection.close.assert_called_once()

    def test_snapshot_fetch_rejects_an_incomplete_declared_body(self):
        import http.client
        import io
        from tokensaver_docs.research_web import fetch_html

        class ResponseSocket:
            def makefile(self, mode):
                return io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n'
                                  b'Content-Length: 200\r\n\r\n<p>Only the first clause.')

        response = http.client.HTTPResponse(ResponseSocket())
        response.begin()
        with patch('tokensaver_docs.research_web.public_address', return_value='93.184.216.34'), \
             patch('http.client.HTTPSConnection') as connect:
            connect.return_value.getresponse.return_value = response
            with self.assertRaisesRegex(ValueError, 'declared Content-Length'):
                fetch_html('docs.example.org', '/policy')

    def test_approval_does_not_follow_a_new_project_at_the_same_path(self):
        project = self.root / 'project'
        project.mkdir()
        approved = activate(project, snapshot_domains=['docs.example.org'])
        self.assertEqual(activate(project)['automation'], approved['automation'])
        shutil.rmtree(project)
        project.mkdir()
        self.assertEqual(activate(project)['automation'], {})
        (project / INBOX / 'web.research.json').write_text(json.dumps({
            'topic':'web','conclusion':'Draft','references':['https://docs.example.org/policy']}))
        with patch('tokensaver_docs.research_web.fetch_html') as fetch:
            self.assertEqual(sync(project)['status'], 'ready')
            fetch.assert_not_called()

    def test_waiting_sync_checks_approval_after_locking(self):
        from contextlib import contextmanager
        from tokensaver_docs import knowledge

        activate(self.root, snapshot_domains=['docs.example.org'])
        (self.inbox / 'web.research.json').write_text(json.dumps({
            'topic':'web','conclusion':'Draft','references':['https://docs.example.org/policy']}))
        real_lock = knowledge.output_lock
        @contextmanager
        def revoke_before_sync(path):
            with patch.object(knowledge, 'output_lock', real_lock):
                self.assertEqual(knowledge.deactivate(self.root)['status'], 'disabled')
            with real_lock(path):
                yield

        with patch.object(knowledge, 'output_lock', revoke_before_sync), \
             patch('tokensaver_docs.research_web.fetch_html') as fetch:
            self.assertEqual(sync(self.root)['status'], 'disabled')
            fetch.assert_not_called()

    def test_web_references_deferred_by_budget_mark_sync_pending(self):
        activate(self.root, snapshot_domains=['docs.example.org'])
        (self.inbox / 'web.research.json').write_text(json.dumps({
            'topic':'web','conclusion':'Draft','references':['https://docs.example.org/policy']}))
        with patch('tokensaver_docs.knowledge.time.monotonic', side_effect=[0, 21]), \
             patch('tokensaver_docs.research_web.fetch_html') as fetch:
            self.assertEqual(sync(self.root)['status'], 'pending')
            fetch.assert_not_called()
        with patch('tokensaver_docs.research_web.fetch_html', return_value=b'<p>Approved policy text</p>') as fetch:
            self.assertEqual(sync(self.root)['status'], 'ready')
            fetch.assert_called_once()

    def test_interrupted_local_audio_retries_once_and_stays_visible(self):
        model = self.root / 'whisper.bin'
        profile = {'provider':'whisper.cpp','model':str(model)}
        with patch('tokensaver_docs.storage.load_profiles', return_value={'audio':profile}), \
             patch('tokensaver_docs.providers.whisper_paths', return_value=(model, 'whisper-cli')):
            activate(self.root, auto_audio=True)
        (self.inbox / 'audio.wav').write_bytes(b'fixture')
        with patch('tokensaver_docs.knowledge.convert', side_effect=KeyboardInterrupt) as convert:
            for _ in range(2):
                with self.assertRaises(KeyboardInterrupt):
                    sync(self.root)
            self.assertEqual(convert.call_count, 2)
        with patch('tokensaver_docs.knowledge.convert') as convert:
            self.assertEqual(sync(self.root)['status'], 'partial')
            convert.assert_not_called()
        self.assertIn('analysis_interrupted', (self.store / 'index.md').read_text())

    def test_interrupted_external_image_is_not_sent_again(self):
        with patch('tokensaver_docs.model_setup.load_model_selection',
                   return_value={'provider':'openrouter','model':'test/image'}):
            activate(self.root, auto_images=True)
        Image.new('RGB', (8, 8), 'red').save(self.inbox / 'photo.png')
        with patch('tokensaver_docs.knowledge.convert', side_effect=KeyboardInterrupt) as convert:
            with self.assertRaises(KeyboardInterrupt):
                sync(self.root)
            self.assertEqual(len(convert.call_args_list), 1)
        self.assertEqual(sync(self.root)['status'], 'partial')
        self.assertIn('analysis_interrupted', (self.store / 'index.md').read_text())

    def test_media_opt_ins_pin_profiles_and_analyze_new_bytes_once(self):
        from tokensaver_docs.knowledge import automation_receipt

        activate(self.root)
        image = self.inbox / 'receipt.png'
        Image.new('RGB', (8, 8), 'red').save(image)
        audio = self.inbox / 'recording.wav'
        audio.write_bytes(b'synthetic audio')
        model = self.root / 'whisper-model.bin'
        image_profile = {'provider':'openrouter','model':'test/image'}
        audio_profile = {'provider':'whisper.cpp','model':str(model)}
        with patch('tokensaver_docs.model_setup.load_model_selection', return_value=image_profile), \
             patch('tokensaver_docs.storage.load_profiles', return_value={'audio':audio_profile}), \
             patch('tokensaver_docs.providers.whisper_paths', return_value=(model, 'whisper-cli')):
            activate(self.root, auto_audio=True, auto_images=True)
        receipt = automation_receipt(self.root)
        self.assertEqual(json.loads(receipt.read_text())['image'], image_profile)

        calls = []
        def convert(source, output, *, profiles, **kwargs):
            calls.append(profiles)
            output.mkdir(parents=True, exist_ok=True)
            markdown = output / 'fixture.md'
            markdown.write_text('Synthetic converted receipt.', encoding='utf-8')
            return [{'status':'완료','output':str(markdown)}]

        with patch('tokensaver_docs.knowledge.convert', side_effect=convert):
            self.assertEqual(sync(self.root)['status'], 'pending')
            self.assertEqual(sync(self.root)['status'], 'ready')
            sync(self.root)
            self.assertCountEqual([profile for profile in calls if profile],
                             [{'audio':audio_profile}, {'image':image_profile}])
            Image.new('RGB', (8, 8), 'blue').save(image)
            sync(self.root)
            self.assertEqual(calls[-1], {'image':image_profile})
            activate(self.root, clear_automation=True)
            Image.new('RGB', (8, 8), 'black').save(image)
            sync(self.root)
            self.assertIsNone(calls[-1])
