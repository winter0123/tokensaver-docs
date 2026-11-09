"""합성 문서에서 전문, tokensaver-docs, QMD 키워드 검색을 비교한다."""
import contextlib
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

import tiktoken
from tokensaver_docs.cli import main

QMD = ['bunx', '--bun', '@tobilu/qmd@2.8.3']
FIXTURES = [
    ('환불 신청 기한', '수령 후 7일', '환불 신청 기한은 수령 후 7일입니다.'),
    ('배송 주소 변경', '출고 전', '배송 주소 변경은 출고 전 가능합니다.'),
    ('API timeout limit', '30 seconds', 'API timeout limit is 30 seconds.'),
]
enc = tiktoken.get_encoding('cl100k_base')
with tempfile.TemporaryDirectory(prefix='tokensaver-docs-bench-') as temporary:
    root = Path(temporary)
    docs = root / 'docs'
    docs.mkdir()
    for index, (_, _, fact) in enumerate(FIXTURES):
        text = '# Document\n' + ''.join(f'\n## Section {i}\n일반적인 안내 문장입니다. General information.\n' for i in range(150)) + '\n## Relevant\n' + fact + '\n'
        (docs / f'doc-{index}.md').write_text(text, encoding='utf-8')
    env = os.environ.copy()
    env['XDG_CONFIG_HOME'] = str(root / 'config')
    env['XDG_CACHE_HOME'] = str(root / 'cache')
    env['QMD_CONFIG_DIR'] = str(root / 'config' / 'qmd')
    env['NO_COLOR'] = '1'
    add = subprocess.run([*QMD, 'collection', 'add', str(docs), '--name', 'bench'], cwd=root, env=env, capture_output=True, text=True, timeout=180)
    if add.returncode:
        raise SystemExit('QMD 색인 실패: ' + (add.stderr or add.stdout)[-1200:])
    full = '\n'.join(p.read_text(encoding='utf-8') for p in sorted(docs.glob('*.md')))
    total = len(enc.encode(full, disallowed_special=()))
    results = []
    for query, expected, _ in FIXTURES:
        ours = io.StringIO()
        with contextlib.redirect_stdout(ours):
            code = main(['search', query, '--output', str(docs), '--context', '1'])
        qmd = subprocess.run([*QMD, 'search', query, '-c', 'bench', '--json', '-n', '5'], cwd=root, env=env, capture_output=True, text=True, timeout=120)
        qmd_output = qmd.stdout.strip()
        try:
            parsed = json.loads(qmd_output)
            qmd_text = json.dumps(parsed, ensure_ascii=False)
        except (ValueError, TypeError):
            qmd_text = qmd_output
        ours_text = ours.getvalue()
        results.append({'query': query, 'expected': expected, 'full_tokens': total,
                        'tokensaver_docs': {'exit': code, 'tokens': len(enc.encode(ours_text, disallowed_special=())), 'fact_found': expected.casefold() in ours_text.casefold()},
                        'qmd_bm25': {'exit': qmd.returncode, 'tokens': len(enc.encode(qmd_text, disallowed_special=())), 'fact_found': expected.casefold() in qmd_text.casefold(),
                                     'error': qmd.stderr[-500:] if qmd.returncode else ''}})
    print(json.dumps({'fixture': 'synthetic', 'encoding': 'cl100k_base', 'qmd_version': '2.8.3', 'results': results,
                      'note': '전문·검색 출력의 텍스트 토큰과 정답 포함 여부만 비교하며 모델 최종 답변 정확도·실전 성능을 뜻하지 않음'}, ensure_ascii=False, indent=2))
