"""합성 예제로 전문 읽기와 검색 응답의 토큰 수를 비교한다."""
import contextlib
import io
import json
import statistics
import tempfile
import time
from pathlib import Path

import tiktoken
from file_to_md.cli import main

encoding = tiktoken.get_encoding('cl100k_base')
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    doc = root / 'policy.md'
    text = '# 정책\n' + ''.join(f'\n## 일반 조항 {i}\n문의는 고객센터에서 처리합니다.\n' for i in range(200)) + '\n## 환불\n환불 신청 기한은 수령 후 7일입니다.\n'
    doc.write_text(text, encoding='utf-8')
    times = []
    for _ in range(5):
        out = io.StringIO()
        started = time.perf_counter()
        with contextlib.redirect_stdout(out):
            code = main(['search', '환불 신청 기한', '--output', str(root), '--context', '1'])
        times.append((time.perf_counter() - started) * 1000)
    result = out.getvalue()
    assert code == 0 and '수령 후 7일' in result
    baseline = len(encoding.encode(text))
    selected = len(encoding.encode(result))
    print(json.dumps({'fixture': 'synthetic', 'encoding': 'cl100k_base',
                      'full_document_tokens': baseline, 'search_output_tokens': selected,
                      'reduction_percent': round(100 * (baseline - selected) / baseline, 1),
                      'gold_fact_found': True, 'search_ms_median': round(statistics.median(times), 2)},
                     ensure_ascii=False, indent=2))
