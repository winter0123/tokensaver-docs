"""Offline comparison of full Markdown, existing context and archived evidence."""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tiktoken
from tokensaver_docs.context import document_context, serialize_context
from tokensaver_docs.engine import convert
from tokensaver_docs.knowledge import INBOX, activate, search, sync


with TemporaryDirectory(prefix='tokensaver-research-') as temporary:
    root = Path(temporary)
    activate(root)
    source = root / INBOX / 'policy.html'
    facts = ('seven days after delivery', 'custom orders excluded')
    unrelated = ''.join(
        f'<h2>Inventory {i}</h2><p>' + 'Unrelated merchandise. ' * 20 + '</p>'
        for i in range(200)
    )
    source.write_text(f'<h1>Policy</h1><p>Refund deadline: {facts[0]}.</p><p>Exception: {facts[1]}.</p>'
                      + unrelated, encoding='utf-8')
    query = 'refund deadline exception'
    with patch.dict(os.environ, {'TOKENSAVER_DOCS_CACHE_DIR': str(root / 'cache')}), \
         patch('tokensaver_docs.providers.generate', side_effect=AssertionError('Unexpected provider call')):
        result, = convert(source, root / 'baseline', cache_dir=root / 'cache', image_mode='preserve')
        full = Path(result['output']).read_text(encoding='utf-8')
        existing = serialize_context(document_context(source, query, root / 'baseline', max_tokens=300))
        assert sync(root)['status'] == 'ready'
        archived = search(root, query, max_tokens=300)
        assert sync(root)['updated'] == 0
        assert search(root, query, max_tokens=300) == archived
    assert all(fact in archived and fact in existing for fact in facts)
    encoding = tiktoken.get_encoding('cl100k_base')
    sizes = {label: len(encoding.encode(body, disallowed_special=())) for label, body in {
        'whole_markdown': full, 'existing_search': existing, 'archived_search': archived,
    }.items()}
    assert sizes['archived_search'] <= 300
    print(json.dumps(sizes, indent=2))
