"""Synthetic, offline cache/context demonstration. No paid APIs or accuracy claims."""
import json,os,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from docx import Document
from PIL import Image
import tiktoken
from file_to_md.engine import convert
from file_to_md.context import document_context

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);source=root/'policy.docx';doc=Document()
    doc.add_paragraph('Refunds are allowed within 7 days. Exception: custom items excluded.')
    for i in range(200):doc.add_paragraph(f'Unrelated inventory record {i}. '+('Internal description. '*10))
    doc.save(source)
    start=time.perf_counter()
    with patch.dict(os.environ,{'FILE_TO_MD_CACHE_DIR':str(root/'cache')}):
        convert(source,root/'out',cache_dir=root/'cache')
        first_seconds=time.perf_counter()-start;start=time.perf_counter()
        result=document_context(source,'Refunds',root/'out',max_tokens=500)
        repeated_seconds=time.perf_counter()-start
    image=root/'image.png';Image.new('RGB',(31,47),'orange').save(image)
    with patch('file_to_md.providers.generate',return_value={'text':'Synthetic image transcript'}) as model:
        convert(image,root/'first',cache_dir=root/'image-cache',profiles={'image':{'provider':'codex','model':'mock'}})
        first_calls=model.call_count
        convert(image,root/'second',cache_dir=root/'image-cache')
        repeat_calls=model.call_count-first_calls
    enc=tiktoken.get_encoding('cl100k_base')
    full=len(enc.encode((root/'out/policy.docx.md').read_text()))
    context=len(enc.encode(json.dumps(result,ensure_ascii=False)))
    assert first_calls==1 and repeat_calls==0
    assert 'custom items' in str(result['excerpts']) and context<full
    print(json.dumps({'fixture':'synthetic','tokenizer':'cl100k_base','full_markdown_tokens':full,'context_json_tokens':context,'mock_transcription_first_calls':first_calls,'mock_transcription_repeat_calls':repeat_calls,'first_processing_seconds':first_seconds,'repeated_context_seconds':repeated_seconds,'note':'Mock image provider and synthetic text only. Not billed usage, production accuracy, or a general savings claim.'},indent=2))
