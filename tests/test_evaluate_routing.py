import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evaluate_routing.py'


def opencode(tool, status='completed', output=None, call_id='one', **state):
    return {'type': 'tool_use', 'part': {'callID': call_id, 'tool': tool,
            'state': {'status': status, 'output': output, **state}}}


class RoutingEvaluationTests(unittest.TestCase):
    def evaluate(self, events, *, process_exit_code=0, **kwargs):
        spec = importlib.util.spec_from_file_location('evaluate_routing', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'events.jsonl'
            path.write_text('\n'.join(json.dumps(e) if not isinstance(e, str) else e for e in events))
            return module.evaluate(path, process_exit_code=process_exit_code, **kwargs)

    def test_ready_tool_result_is_separate_from_verified_output(self):
        events = [opencode('tokensaver_docs_prepare', output='{"status":"ready"}')]
        result = self.evaluate(events)
        self.assertTrue(result['tokensaver_first'])
        self.assertTrue(result['tokensaver_tool_success'])
        self.assertFalse(result['final_success'])
        self.assertTrue(self.evaluate(events, verified_tokensaver_call_id='one')['final_success'])

    def test_fallback_and_denials_do_not_become_tokensaver_success(self):
        result = self.evaluate([
            opencode('tokensaver_docs_prepare', 'denied', call_id='denied'),
            opencode('read', output='secret', call_id='read'),
            opencode('bash', input={'command': 'pandoc input.pdf -o output.md'}, call_id='shell'),
            opencode('tokensaver_docs_prepare', output='{"status":"partial"}', call_id='ts'),
        ], unnecessary_call_ids={'read'})
        self.assertEqual(result['first_valid_conversion'], 'other')
        self.assertFalse(result['tokensaver_first'])
        self.assertFalse(result['tokensaver_tool_success'])
        self.assertEqual(result['denied_calls'], 1)
        self.assertEqual(result['unnecessary_calls'], 1)
        self.assertEqual(result['read_calls'], 1)
        self.assertEqual(result['script_calls'], 1)
        self.assertNotIn('secret', json.dumps(result))

    def test_failed_other_conversion_is_still_the_first_selection(self):
        result = self.evaluate([
            opencode('bash', 'failed', input={'command': 'pandoc input.pdf -o output.md'}, call_id='other'),
            opencode('tokensaver_docs_prepare', output='{"status":"ready"}'),
        ], verified_tokensaver_call_id='one')
        self.assertTrue(result['evaluable'])
        self.assertEqual(result['first_valid_conversion'], 'other')
        self.assertFalse(result['tokensaver_first'])
        self.assertTrue(result['tokensaver_tool_success'])
        self.assertTrue(result['final_success'])

    def test_malformed_event_and_result_json_are_distinct(self):
        result = self.evaluate(['{"broken":', [], opencode('tokensaver_docs_prepare', output='not json')])
        self.assertEqual(result['malformed_event_lines'], [1, 2])
        self.assertEqual(result['malformed_tool_results'], 1)
        self.assertFalse(result['evaluable'])
        self.assertFalse(result['final_success'])

    def test_lifecycle_updates_count_once_in_start_order(self):
        result = self.evaluate([
            opencode('tokensaver_docs_prepare', 'running', call_id='first'),
            opencode('bash', input={'command': 'pandoc x -o y.md'}, call_id='second'),
            opencode('tokensaver_docs_prepare', output='{"status":"ready"}', call_id='first'),
        ])
        self.assertEqual(result['total_calls'], 2)
        self.assertTrue(result['tokensaver_first'])

    def test_claude_tool_result_and_codex_mcp_result(self):
        claude = [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'a', 'name': 'mcp__tokensaver_docs__prepare_documents', 'input': {}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': [{'type': 'text', 'text': '{"status":"ready"}'}]}]}},
        ]
        codex = [{'type': 'item.completed', 'item': {'id': 'b', 'type': 'mcp_tool_call', 'server': 'tokensaver-docs', 'tool': 'prepare_documents', 'status': 'completed', 'result': {'content': [{'type': 'text', 'text': '{"status":"ready"}'}]}}}]
        for events in (claude, codex):
            with self.subTest(events=events):
                self.assertTrue(self.evaluate(events)['tokensaver_tool_success'])

    def test_control_and_host_error_are_not_selection_failures(self):
        events = [opencode('tokensaver_docs_prepare', output='{"status":"ready"}')]
        control = self.evaluate(events, supported_request=False)
        self.assertFalse(control['evaluable'])
        self.assertTrue(control['unexpected_intervention'])
        self.assertIsNone(control['tokensaver_first'])
        failed = self.evaluate([{'type': 'error', 'error': {'message': 'secret key'}}])
        self.assertEqual(failed['host_errors'], 1)
        self.assertFalse(failed['evaluable'])
        self.assertNotIn('secret', json.dumps(failed))

    def test_unrelated_prepare_tool_does_not_count(self):
        self.assertFalse(self.evaluate([opencode('other_prepare_documents', output='{"status":"ready"}')])['tokensaver_tool_success'])

    def test_empty_log_is_not_evaluable(self):
        self.assertFalse(self.evaluate([])['evaluable'])

    def test_mcp_error_envelope_cannot_report_success(self):
        event = opencode('tokensaver_docs_prepare', output={'isError': True, 'content': [{'type': 'text', 'text': '{"status":"ready"}'}]})
        result = self.evaluate([event])
        self.assertFalse(result['tokensaver_tool_success'])
        self.assertEqual(result['error_calls'], 1)

    def test_mentioning_a_converter_in_shell_is_not_using_it(self):
        result = self.evaluate([opencode('bash', input={'command': 'echo pandoc'})])
        self.assertIsNone(result['first_valid_conversion'])

    def test_namespaced_read_and_shell_tools_are_classified_by_exact_leaf(self):
        result = self.evaluate([
            opencode('mcp__filesystem__read_file', call_id='read1'),
            opencode('filesystem__read_file', call_id='read2'),
            opencode('mcp__terminal__bash', input={'command': 'pandoc x -o y.md'}, call_id='bash'),
            opencode('filesystem__read_file_extra', call_id='unrelated'),
        ])
        self.assertEqual(result['read_calls'], 2)
        self.assertEqual(result['script_calls'], 1)
        self.assertEqual(result['first_valid_conversion'], 'other')

    def test_needs_review_is_recorded_separately_from_ready_and_output_verification(self):
        result = self.evaluate([
            opencode('tokensaver_docs_prepare', output='{"status":"needs_review"}'),
        ], verified_tokensaver_call_id='one')
        self.assertTrue(result['tokensaver_first'])
        self.assertEqual(result['tokensaver_result_counts']['needs_review'], 1)
        self.assertEqual(result['tokensaver_result_counts']['ready'], 0)
        self.assertFalse(result['tokensaver_tool_success'])
        self.assertFalse(result['final_success'])

    def test_unknown_result_status_is_not_copied_into_report(self):
        result = self.evaluate([
            opencode('tokensaver_docs_prepare', output='{"status":"secret-value"}'),
        ])
        self.assertEqual(result['tokensaver_result_counts']['other'], 1)
        self.assertNotIn('secret-value', json.dumps(result))

    def test_other_converter_after_tokensaver_blocks_final_success(self):
        result = self.evaluate([
            opencode('tokensaver_docs_prepare', output='{"status":"ready"}'),
            opencode('bash', input={'command': 'pandoc x -o y.md'}, call_id='other'),
        ], verified_tokensaver_call_id='one')
        self.assertTrue(result['tokensaver_tool_success'])
        self.assertTrue(result['other_conversion_after_tokensaver'])
        self.assertFalse(result['final_success'])

    def test_other_converter_before_tokensaver_does_not_replace_its_verified_output(self):
        result = self.evaluate([
            opencode('bash', input={'command': 'pandoc x -o y.md'}, call_id='other'),
            opencode('tokensaver_docs_prepare', output='{"status":"ready"}'),
        ], verified_tokensaver_call_id='one')
        self.assertTrue(result['final_success'])
        self.assertFalse(result['other_conversion_after_tokensaver'])

    def test_verification_must_match_the_ready_tokensaver_call(self):
        events = [
            opencode('tokensaver_docs_prepare', output='{"status":"ready"}', call_id='ready'),
            opencode('tokensaver_docs_prepare', output='{"status":"needs_review"}', call_id='review'),
            opencode('read', output='private-path', call_id='read'),
        ]
        for call_id in ('review', 'read', 'unknown-private-id'):
            with self.subTest(call_id=call_id):
                result = self.evaluate(events, verified_tokensaver_call_id=call_id)
                self.assertTrue(result['tokensaver_tool_success'])
                self.assertFalse(result['final_success'])
                self.assertNotIn('private', json.dumps(result))
        self.assertTrue(self.evaluate(events, verified_tokensaver_call_id='ready')['final_success'])

    def test_verification_cannot_accept_failed_denied_or_incomplete_calls(self):
        for status in ('failed', 'denied', 'running'):
            with self.subTest(status=status):
                result = self.evaluate([
                    opencode('tokensaver_docs_prepare', output='{"status":"ready"}', call_id='ready'),
                    opencode('tokensaver_docs_prepare', status, output='{"status":"ready"}', call_id='invalid'),
                ], verified_tokensaver_call_id='invalid')
                self.assertFalse(result['final_success'])

    def test_cli_binds_human_attestation_to_call_id_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'events'
            path.write_text(json.dumps(opencode('tokensaver_docs_prepare', output='{"status":"ready"}')))
            for call_id, expected in (('one', True), ('private-unknown-id', False)):
                with self.subTest(call_id=call_id):
                    result = subprocess.run([
                        sys.executable, str(SCRIPT), str(path),
                        '--verified-tokensaver-call-id', call_id, '--process-exit-code', '0',
                    ], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)['final_success'], expected)
                    self.assertNotIn('private', result.stdout + result.stderr)

    def test_only_explicit_successful_process_exit_is_evaluable(self):
        events = [opencode('tokensaver_docs_prepare', output='{"status":"ready"}')]
        for exit_code in (None, 1, -15, 130, False, '0'):
            with self.subTest(exit_code=exit_code):
                result = self.evaluate(events, process_exit_code=exit_code,
                                       verified_tokensaver_call_id='one')
                self.assertTrue(result['tokensaver_tool_success'])
                self.assertFalse(result['evaluable'])
                self.assertIsNone(result['tokensaver_first'])
                self.assertFalse(result['final_success'])
        self.assertTrue(self.evaluate(events, process_exit_code=0)['evaluable'])

    def test_cli_does_not_infer_process_completion_from_ready_events(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'events'
            path.write_text(json.dumps(opencode('tokensaver_docs_prepare', output='{"status":"ready"}')))
            for options in ([], ['--process-exit-code', '130']):
                with self.subTest(options=options):
                    result = subprocess.run([
                        sys.executable, str(SCRIPT), str(path),
                        '--verified-tokensaver-call-id', 'one', *options,
                    ], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertFalse(report['evaluable'])
                    self.assertFalse(report['final_success'])

    def test_cli_prints_only_sanitized_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'events'
            path.write_text(json.dumps(opencode('read', output='private-token')))
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['total_calls'], 1)
            self.assertNotIn('private-token', result.stdout + result.stderr)
