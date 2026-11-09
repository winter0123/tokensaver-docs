"""Offline synthetic HTML comparison; run from the repo: python benchmarks/html_policy_demo.py.

Requires the optional tiktoken dependency and a locally cached cl100k_base encoding.
Results are token estimates for the shown payloads, not model usage or accuracy.
"""
import base64
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tiktoken
from file_to_md.context import document_context
from file_to_md.preparation import prepare_documents


def main():
    source = Path(__file__).with_name('html-policy-example.html').resolve()
    raw = source.read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='file-to-md-benchmark-') as tmp:
        root = Path(tmp)
        with patch.dict(os.environ, {'FILE_TO_MD_CACHE_DIR': str(root / 'cache')}), \
             patch('file_to_md.providers.generate', side_effect=AssertionError('Unexpected provider call')) as provider:
            first = prepare_documents(source, root / 'output')
            second = prepare_documents(source, root / 'output')
            context = document_context(source, 'Refund policy', root / 'output', max_tokens=500)
        assert first['total'] == second['total'] == 1
        first_file, second_file = first['files'][0], second['files'][0]
        assert first_file['ai_calls'] == second_file['ai_calls'] == provider.call_count == 0
        assert second_file.get('cached') and second_file.get('structure_cached')
        markdown = Path(first_file['output']).read_text(encoding='utf-8')
        expected = ('within 7 days of delivery', 'custom-made items cannot be refunded unless defective')
        assert all(fact in markdown for fact in expected)
        evidence = json.dumps(context, ensure_ascii=False)
        assert all(fact in evidence for fact in expected)
        assert '| Standard item | 7 days |' in markdown
        assert '| Custom-made item | Defects only |' in markdown
        image = re.search(r'!\[[^\]]*\]\(([^)]+)\)', markdown)
        assert image
        original_image = base64.b64decode(re.search(r'base64,([^"\']+)', raw).group(1))
        assert (Path(first_file['output']).parent / image.group(1)).read_bytes() == original_image
        with patch('socket.socket.connect', side_effect=RuntimeError('cl100k_base must already be cached for offline use')):
            encoding = tiktoken.get_encoding('cl100k_base')
        counts = {name: len(encoding.encode(value, disallowed_special=())) for name, value in {
            'original_html': raw, 'complete_markdown': markdown, 'bounded_context_json': evidence,
        }.items()}
        print(json.dumps({
            'fixture': source.name, 'fixture_license': 'CC0-1.0', 'query': 'Refund policy',
            'tokenizer': 'cl100k_base', 'estimated_payload_tokens': counts,
            'first_provider_calls': first_file['ai_calls'], 'repeat_provider_calls': second_file['ai_calls'],
            'repeat_output_cached': second_file['cached'], 'fact_and_exception_present': True,
            'table_and_image_preserved': True, 'actual_model_usage': None,
            'limitations': 'Synthetic single example; payload counts exclude model instructions, tool schemas, and other conversation turns. No model answer, external provider, billing, or general accuracy/savings measured.',
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
