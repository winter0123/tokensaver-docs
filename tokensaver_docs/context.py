# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Prepare documents once and return bounded original evidence, never a generated summary."""
import json
from pathlib import Path
from .engine import convert, discover
from .shared_cache import cache_root
from .storage import digest, file_hash, load_profiles, load_state


def document_context(source, query, output, *, max_tokens=None, max_chars=6000, use_configured_providers=False):
    source, output = Path(source), Path(output)
    if not query.strip():
        raise ValueError('검색어가 비어 있습니다.')
    if max_chars < 1 or (max_tokens is not None and max_tokens < 1):
        raise ValueError('출력 예산은 1 이상이어야 합니다.')
    if source.is_symlink():
        raise ValueError('입력 심볼릭 링크는 따라가지 않습니다.')
    encoder = None
    if max_tokens is not None:
        from .cli import token_encoder
        encoder = token_encoder('cl100k_base')
    def fits(value):
        text = json.dumps(value, ensure_ascii=False)
        return len(text) <= max_chars and (encoder is None or len(encoder.encode(text, disallowed_special=())) <= max_tokens)
    result = {'status':'ready', 'sources':[], 'excerpts':[], 'pending':[], 'truncated':False, 'next':None}
    if not fits(result):
        raise ValueError('상태 정보도 담을 수 없는 예산입니다. 예산을 늘려 주세요.')
    if source.suffix.lower() == '.md' and source.is_file():
        records = [{'file':str(source), 'output':str(source), 'status':'완료'}]
    else:
        if source.exists():
            # Recheck each source in its last selected image mode, including linked HTML images.
            root = source.resolve() if source.is_dir() else source.resolve().parent
            state = load_state(output)
            profiles = load_profiles() if use_configured_providers else {}
            if use_configured_providers:
                from .model_setup import load_model_selection
                selected = load_model_selection(legacy_profiles=profiles)
                if selected:
                    profiles = {**profiles, 'image': selected}
            records = []
            for path in discover(source, output):
                path = path.resolve()
                previous = state['records'].get(str(path.relative_to(root)) + '.md', {})
                if previous.get('source') == str(path) and previous.get('current_output'):
                    current = output.resolve() / previous['current_output']
                    if current.is_symlink() or not current.resolve().is_relative_to(output.resolve()):
                        records.append({'file': str(path), 'status': '충돌', 'detail': '기존 결과 경로를 확인하세요.'})
                        continue
                    if current.is_file() and (not previous.get('output_hash') or file_hash(current) != previous['output_hash']):
                        records.append({'file': str(path), 'status': '충돌', 'detail': f'기존 MD가 편집되어 자동 검색을 중단했습니다. 편집 결과를 확인하세요: {current}'})
                        continue
                if previous.get('source') == str(path) and previous.get('image_mode') in ('analyze', 'preserve', 'placeholder'):
                    model_key = previous.get('image_model_key')
                    if use_configured_providers and previous['image_mode'] == 'analyze' and profiles.get('image'):
                        model_key = digest(json.dumps(profiles['image'], sort_keys=True).encode())
                    records.extend(convert(path, output, profiles=profiles, cache_dir=cache_root(), image_mode=previous['image_mode'], image_model_key=model_key, source_root=root))
                else:
                    mode = use_configured_providers or (previous.get('image_analysis') is True and previous.get('source') == str(path))
                    records.extend(convert(path, output, profiles=profiles, cache_dir=cache_root(), transcribe_images=mode, source_root=root))
        else:
            records = convert(source, output, profiles=load_profiles() if use_configured_providers else {}, cache_dir=cache_root(), transcribe_images=use_configured_providers)
        if source.is_dir():
            records += [{'file': str(path), 'output': str(path), 'status': '완료'}
                        for path in discover(source, output, include_markdown=True)
                        if path.suffix.lower() == '.md']
    candidates=[]
    pending_truncated=False
    words=query.casefold().split()
    for record in records:
        path=record.get('output')
        if record['status'] not in ('완료','확인필요') or record.get('untranscribed_images', 0):
            result['status']='partial'
            pending={'source':record['file'], 'status':record['status']}
            if record.get('detail'):
                pending['detail'] = record['detail']
            result['pending'].append(pending)
            if not fits(result):
                result['pending'].pop();result['truncated']=True;pending_truncated=True
        if not path or record['status'] not in ('완료', '확인필요', '부분완료'):
            continue
        lines=Path(path).read_text(encoding='utf-8').splitlines()
        # Heading sections keep nearby exceptions with the rule; very long sections need follow-up reads.
        starts=[i for i,line in enumerate(lines) if line.startswith('#') and line.lstrip('#').startswith(' ')]
        starts=sorted(set([0,*starts,len(lines)]))
        for section,(begin,end) in enumerate(zip(starts,starts[1:])):
            text='\n'.join(lines[begin:end]).strip()
            folded=text.casefold()
            score=sum(word in folded for word in words)
            if score:
                if lines[begin].startswith('## 본문'):
                    end=starts[min(section+3,len(starts)-1)]
                anchor=max(range(begin,end), key=lambda i:sum(word in lines[i].casefold() for word in words))
                candidates.append((score,str(path),begin,end,anchor,lines,record['status']))
    prefix_next=None
    for score,path,begin,end,anchor,lines,status in sorted(candidates,key=lambda item:-item[0]):
        context_end=min(anchor+3,end)
        probe={**result, 'sources':list(dict.fromkeys([*result['sources'],path])),
               'excerpts':[*result['excerpts'], {'file':path,'start_line':begin+1,'end_line':context_end,
                           'status':status,'text':'\n'.join(lines[begin:context_end])}],
               'truncated':True, 'next':{'file':path,'start_line':context_end+1}}
        if anchor > begin and not fits(probe):
            if prefix_next is None:
                prefix_next={'file':path,'start_line':begin+1}
            begin=max(begin,anchor-2)
            while begin < anchor:
                probe['excerpts'][-1].update(start_line=begin+1, text='\n'.join(lines[begin:context_end]))
                if fits(probe):
                    break
                begin+=1
        excerpt={'file':path,'start_line':begin+1,'end_line':begin,'status':status,'text':''}
        if path not in result['sources']:
            result['sources'].append(path)
        result['excerpts'].append(excerpt)
        accepted=[]
        for i in range(begin,end):
            excerpt.update(text='\n'.join([*accepted,lines[i]]),end_line=i+1)
            # Reserve continuation metadata before measuring the complete response.
            result['next']={'file':path,'start_line':i+2}
            result['truncated']=True
            if not fits(result):
                excerpt.update(text='\n'.join(accepted),end_line=i)
                result['next']={'file':path,'start_line':i+1}
                break
            accepted.append(lines[i])
        if not accepted:
            result['excerpts'].pop()
            if not any(e['file']==path for e in result['excerpts']):result['sources'].remove(path)
        if len(accepted)<end-begin:
            break
        result['next']=None
    else:
        result['truncated']=bool(result['pending']) or pending_truncated or prefix_next is not None
        result['next']=prefix_next
    if not result['excerpts'] and result['status']=='ready':
        result['status']='budget_exceeded' if candidates else 'no_match'
    if not fits(result):
        # Metadata truncation is explicit, never silently exceed the requested budget.
        result={'status':result['status'],'sources':[],'excerpts':[],'pending':[],'truncated':True,'next':None}
        if not fits(result):raise ValueError('출력 예산을 늘려 주세요.')
    return result
