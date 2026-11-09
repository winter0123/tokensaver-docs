"""Explicit, checksum-verified download of a user-selected multilingual Whisper model."""
import json
import os
import urllib.request
from pathlib import Path
from .shared_cache import cache_root, shared_lock
from .storage import atomic_write, config_path, file_hash, load_profiles


def model_catalog():
    return json.loads((Path(__file__).parent/'data/audio_models.json').read_text(encoding='utf-8'))


def setup_audio(model, *, confirmed=False, root=None):
    models=model_catalog()
    if model not in models:raise ValueError('tiny, base, small 중 모델을 선택하세요.')
    info=models[model]
    if not confirmed:return {'status':'confirmation_required','model':model,'bytes':info['size'],'local_processing':True}
    root=Path(root) if root is not None else cache_root().parent/'models'
    if root.is_symlink():raise ValueError('모델 폴더 심볼릭 링크는 허용하지 않습니다.')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=root/f'ggml-{model}.bin';partial=root/f'ggml-{model}.part'
    if target.is_symlink() or partial.is_symlink():raise ValueError('모델 파일 경로가 올바르지 않습니다.')
    with shared_lock(root):
        # Reuse a verified previous local installation, without downloading it again.
        legacy=Path.home()/'.local/share/file-to-md/models'/target.name
        candidate=target if target.exists() else legacy
        if candidate.is_file() and candidate.stat().st_size==info['size'] and file_hash(candidate)==info['sha256']:
            target=candidate
        else:
            if target.exists():raise ValueError('기존 모델 무결성이 다릅니다. 파일을 보존했습니다.')
            offset=partial.stat().st_size if partial.exists() else 0
            if offset>info['size']:raise ValueError('부분 다운로드 크기가 올바르지 않습니다.')
            if offset<info['size']:
                headers={'Range':f'bytes={offset}-'} if offset else {}
                request=urllib.request.Request(info['url'],headers=headers)
                with urllib.request.urlopen(request,timeout=30) as response:
                    append=offset>0 and response.status==206 and response.headers.get('Content-Range','').startswith(f'bytes {offset}-')
                    if response.status==206 and not append:
                        raise ValueError('모델 이어받기 응답 범위가 올바르지 않습니다.')
                    with partial.open('ab' if append else 'wb') as stream:
                        total=offset if append else 0
                        while chunk:=response.read(1024*1024):
                            total+=len(chunk)
                            if total>info['size']:raise ValueError('모델 다운로드가 예상 크기를 초과했습니다.')
                            stream.write(chunk)
                        stream.flush();os.fsync(stream.fileno())
            if partial.stat().st_size!=info['size'] or file_hash(partial)!=info['sha256']:
                raise ValueError('모델 검증 실패. 부분 파일을 보존했습니다.')
            partial.rename(target)
        from .providers import whisper_paths
        whisper_paths(str(target))
        profiles=load_profiles()
        profiles['audio']={'provider':'whisper.cpp','model':str(target)}
        atomic_write(config_path(),json.dumps(profiles,ensure_ascii=False,indent=2))
    return {'status':'ready','model':model,'path':str(target),'local_processing':True}
