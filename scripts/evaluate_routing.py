# SPDX-License-Identifier: MIT
"""Offline JSONL routing evidence evaluator; never invokes a host or changes permissions.

Accepts OpenCode tool_use, Claude stream-json message content, and Codex
item.started/item.completed events. first_valid_conversion identifies the first
non-denied completed or failed conversion attempt in call-start order, not its
success; tokensaver_first reports whether that attempt selected TokenSaver.
Tool success means a completed ready result. A session is evaluable only when
--process-exit-code explicitly records the actual host process exit code as 0;
events alone do not establish that the session finished.
Final success requires --verified-tokensaver-call-id ID: the reviewer attests
they directly checked the Markdown returned by that completed ready TokenSaver
preparation call. The evaluator does not inspect the Markdown itself.
Later non-denied conversion calls conservatively block final success.
Completed needs_review/partial/no_files results are counted separately, not as ready.
Use --other-conversion-call-id for converters not recognized by name/command,
and --unnecessary-call-id for calls judged unnecessary by a human reviewer.
Neither reads nor arbitrary scripts are assumed unnecessary automatically.
Reports contain counts/classifications only, never raw inputs, outputs or errors.
"""
import argparse
import json
import shlex
from pathlib import Path


SHELL_TOOLS = {'shell', 'execute', 'bash', 'command_execution'}
READ_TOOLS = {'read', 'read_file', 'glob', 'grep', 'webfetch'}
CONVERTERS = {'pandoc', 'markitdown', 'docling', 'pdftotext', 'tokensaver-docs'}


def _conversion_command(command):
    # shortcut: only direct converter commands; reviewer IDs cover wrappers and scripts.
    if not isinstance(command, str):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return bool(words and Path(words[0]).name.lower() in CONVERTERS)


def _tokensaver(name):
    name = name.lower().replace('-', '_')
    return name == 'tokensaver_docs_prepare' or (
        'tokensaver_docs' in name and name.endswith(('__prepare_documents', '_prepare_documents')))


def _payload(value):
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict) and 'structuredContent' in value:
        return _payload(value['structuredContent'])
    if isinstance(value, dict) and 'content' in value:
        return _payload(value['content'])
    if isinstance(value, list):
        return _payload(''.join(p.get('text', '') for p in value if isinstance(p, dict) and p.get('type') == 'text'))
    if isinstance(value, dict):
        return value
    raise ValueError('No JSON result')


def _calls(event, line):
    """Yield host call updates; IDs join lifecycle events without logging their data."""
    kind = event.get('type')
    if kind == 'tool_use':
        part = event['part']
        state = part['state']
        yield {'id': part.get('callID', part.get('id', f'line:{line}')),
               'name': part['tool'], 'status': state['status'],
               'input': state.get('input', {}), 'output': state.get('output')}
    elif kind in ('assistant', 'user'):
        content = event.get('message', {}).get('content', [])
        if not isinstance(content, list):
            return
        for part in content:
            if part.get('type') == 'tool_use':
                yield {'id': part['id'], 'name': part['name'], 'status': 'running', 'input': part.get('input', {})}
            elif part.get('type') == 'tool_result':
                yield {'id': part['tool_use_id'], 'status': 'error' if part.get('is_error') else 'completed', 'output': part.get('content')}
    elif kind in ('item.started', 'item.completed', 'item.updated'):
        item = event['item']
        if item.get('type') not in ('mcp_tool_call', 'command_execution'):
            return
        name = item.get('tool', 'command_execution')
        if item.get('server'):
            name = item['server'] + '__' + name
        yield {'id': item['id'], 'name': name,
               'status': item.get('status', 'completed' if kind == 'item.completed' else 'running'),
               'input': item.get('arguments', {'command': item.get('command', '')}),
               'output': item.get('result'), 'error': item.get('error')}


def evaluate(path, *, process_exit_code=None, supported_request=True, verified_tokensaver_call_id=None,
             unnecessary_call_ids=(), other_conversion_call_ids=()):
    calls = {}
    verified_ready_call = False
    malformed = []
    host_errors = 0
    event_count = 0
    for line_number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('Expected event object')
            event_count += 1
            if event.get('type') in ('error', 'turn.failed'):
                host_errors += 1
            for update in _calls(event, line_number):
                call_id = update['id']
                if not isinstance(call_id, str):
                    raise ValueError('Expected call ID')
                calls.setdefault(call_id, {}).update(update)
        except (ValueError, KeyError, TypeError, AttributeError):
            malformed.append(line_number)

    report = {'evaluable': False, 'first_valid_conversion': None,
              'tokensaver_first': None, 'tokensaver_tool_success': False,
              'final_success': False, 'unexpected_intervention': False,
              'other_conversion_after_tokensaver': False,
              'event_count': event_count, 'total_calls': len(calls), 'tokensaver_calls': 0,
              'read_calls': 0, 'script_calls': 0, 'unnecessary_calls': 0,
              'denied_calls': 0, 'error_calls': 0, 'incomplete_calls': 0,
              'malformed_event_lines': malformed, 'malformed_tool_results': 0,
              'host_errors': host_errors,
              'tokensaver_result_counts': dict.fromkeys(('ready', 'needs_review', 'partial', 'no_files', 'other'), 0)}
    for call_id, call in calls.items():
        name = call.get('name', '')
        if not isinstance(name, str) or not name:
            report['malformed_tool_results'] += 1
            continue
        tool = name.lower().rsplit('__', 1)[-1]
        status = call.get('status')
        denied = status in ('denied', 'rejected', 'permission_denied')
        failed = (status in ('error', 'failed') or bool(call.get('error'))
                  or isinstance(call.get('output'), dict) and call['output'].get('isError') is True)
        completed = status in ('completed', 'success') and not failed
        report['denied_calls'] += denied
        report['error_calls'] += failed and not denied
        report['incomplete_calls'] += not (denied or failed or completed)
        report['read_calls'] += tool in READ_TOOLS
        report['script_calls'] += tool in SHELL_TOOLS
        report['unnecessary_calls'] += call_id in unnecessary_call_ids
        tokensaver = _tokensaver(name)
        report['tokensaver_calls'] += tokensaver
        command = call.get('input', {})
        if isinstance(command, dict):
            command = command.get('command', '')
        other = call_id in other_conversion_call_ids or (
            tool in SHELL_TOOLS and _conversion_command(command))
        if other and not denied and report['tokensaver_tool_success']:
            report['other_conversion_after_tokensaver'] = True
        if (tokensaver or other) and not denied and (completed or failed):
            if report['first_valid_conversion'] is None:
                report['first_valid_conversion'] = 'tokensaver' if tokensaver else 'other'
        if tokensaver and completed:
            try:
                result = _payload(call.get('output'))
                if not isinstance(result, dict) or not isinstance(result.get('status'), str):
                    raise ValueError('Expected preparation status')
                result_status = result['status']
                bucket = result_status if result_status in report['tokensaver_result_counts'] else 'other'
                report['tokensaver_result_counts'][bucket] += 1
                report['tokensaver_tool_success'] |= result_status == 'ready'
                verified_ready_call |= result_status == 'ready' and call_id == verified_tokensaver_call_id
            except (ValueError, TypeError):
                report['malformed_tool_results'] += 1
    report['evaluable'] = bool(type(process_exit_code) is int and process_exit_code == 0
                               and supported_request and event_count and not malformed and not host_errors
                               and not report['malformed_tool_results'] and not report['incomplete_calls'])
    if report['evaluable']:
        report['tokensaver_first'] = report['first_valid_conversion'] == 'tokensaver'
    report['final_success'] = bool(report['evaluable'] and verified_ready_call
                                   and not report['other_conversion_after_tokensaver'])
    report['unexpected_intervention'] = bool(not supported_request and report['tokensaver_calls'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('events', type=Path)
    parser.add_argument('--process-exit-code', type=int, help='Actual host process exit code, recorded after the process finishes; only explicit 0 permits evaluation')
    parser.add_argument('--control', action='store_true', help='Exclude a negative/control request from selection denominators')
    parser.add_argument('--verified-tokensaver-call-id', metavar='ID', help='Human attestation: reviewer directly checked the Markdown returned by this completed ready TokenSaver preparation call; the evaluator does not inspect the Markdown')
    parser.add_argument('--unnecessary-call-id', action='append', default=[])
    parser.add_argument('--other-conversion-call-id', action='append', default=[])
    args = parser.parse_args()
    try:
        report = evaluate(args.events, process_exit_code=args.process_exit_code,
                          supported_request=not args.control,
                          verified_tokensaver_call_id=args.verified_tokensaver_call_id,
                          unnecessary_call_ids=args.unnecessary_call_id,
                          other_conversion_call_ids=args.other_conversion_call_id)
    except (OSError, UnicodeError):
        parser.exit(2, 'Cannot read UTF-8 event log.\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
