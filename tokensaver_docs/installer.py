# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Install a verified local plugin bundle without requiring Python on the target machine."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import platform
import re
import sys
from pathlib import Path
from . import __version__
from .shared_cache import cache_root
from .storage import atomic_write, file_hash


def verify_bundle(bundle):
    bundle=Path(bundle).resolve()
    manifest=bundle/'checksums.json'
    if manifest.is_symlink():raise ValueError('체크섬 경로가 올바르지 않습니다.')
    checks=json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(checks,dict) or not checks:raise ValueError('비어 있는 패키지입니다.')
    if any(p.is_symlink() for p in bundle.rglob('*')):raise ValueError('패키지에 심볼릭 링크가 있습니다.')
    for name,expected in checks.items():
        path=bundle/name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle) or not path.is_file() or file_hash(path)!=expected:
            raise ValueError('패키지 무결성 확인 실패: '+name)
    actual={str(p.relative_to(bundle)).replace(os.sep,'/') for p in bundle.rglob('*') if p.is_file() and p!=manifest}
    if actual!=set(checks):raise ValueError('체크섬에 없는 파일이 포함돼 있습니다.')
    return checks


def install_bundle(bundle, agent, *, destination=None, config_dir=None, register=True, expected_version=None):
    bundle=Path(bundle).resolve();checks=verify_bundle(bundle)
    metadata=json.loads((bundle/'platform.json').read_text())
    if metadata.get('version') != __version__ or (expected_version is not None and metadata.get('version') != expected_version):
        raise ValueError('요청한 버전·패키지 버전·실행 파일 버전이 일치하지 않습니다.')
    cpu={'amd64':'x64','x86_64':'x64','aarch64':'arm64','arm64':'arm64'}.get(platform.machine().lower())
    if metadata.get('agent')!=agent or metadata.get('os')!=sys.platform or metadata.get('cpu')!=cpu:
        raise ValueError('현재 에이전트·운영체제·CPU와 맞지 않는 패키지입니다.')
    executable='tokensaver-docs.exe' if os.name=='nt' else 'tokensaver-docs'
    if 'bin/'+executable not in checks:raise ValueError('현재 운영체제용 실행 파일이 없습니다.')
    if agent not in ('claude','codex','opencode'):raise ValueError('지원하지 않는 에이전트입니다.')
    if agent=='opencode':
        package=json.loads((bundle/'package.json').read_text())
        if package.get('dependencies'):raise ValueError('OpenCode용 번들 빌드가 필요합니다. --bundle-opencode로 패키징하세요.')
        if 'skills/tokensaver-docs/SKILL.md' not in checks:raise ValueError('OpenCode 패키지에 TokenSaver Docs 스킬이 없습니다.')
    identity=hashlib.sha256(json.dumps(checks,sort_keys=True).encode()).hexdigest()[:16]
    parent=Path(destination) if destination is not None else cache_root().parent/'plugins'/agent
    if parent.is_symlink():raise ValueError('설치 경로 심볼릭 링크는 허용하지 않습니다.')
    parent.mkdir(parents=True,exist_ok=True)
    marketplace=parent/'marketplace'
    container=marketplace/'plugins' if agent in ('claude','codex') else parent
    if marketplace.is_symlink() or container.is_symlink():raise ValueError('설치 경로가 올바르지 않습니다.')
    container.mkdir(parents=True,exist_ok=True)
    target=container/identity
    if target.exists():
        if target.is_symlink():raise ValueError('기존 설치 경로가 올바르지 않습니다.')
        verify_bundle(target)
    else:
        with tempfile.TemporaryDirectory(dir=container,prefix='install-') as temp:
            staging=Path(temp)/'bundle'
            shutil.copytree(bundle,staging,symlinks=False)
            verify_bundle(staging)
            staging.rename(target)
    if register:
        if agent in ('claude','codex'):
            relative='.claude-plugin/marketplace.json' if agent=='claude' else '.agents/plugins/marketplace.json'
            catalog=marketplace/relative
            if marketplace.is_symlink() or catalog.parent.is_symlink() or catalog.is_symlink():raise ValueError('마켓 경로가 올바르지 않습니다.')
            previous=catalog.read_text() if catalog.exists() else None
            data=json.loads((target/relative).read_text())
            data['plugins'][0]['source']='./plugins/'+identity if agent=='claude' else {'source':'local','path':'./plugins/'+identity}
            atomic_write(catalog,json.dumps(data))
            try:
                subprocess.run([agent,'plugin','marketplace','add',str(marketplace)],check=True)
                if agent=='claude':
                    subprocess.run(['claude','plugin','install','tokensaver-docs@tokensaver-docs-marketplace'],check=True)
                    subprocess.run(['claude','plugin','update','tokensaver-docs@tokensaver-docs-marketplace'],check=True)
                else:
                    subprocess.run(['codex','plugin','add','tokensaver-docs@tokensaver-docs-marketplace'],check=True)
            except (OSError,subprocess.CalledProcessError):
                if previous is not None:atomic_write(catalog,previous)
                else:catalog.unlink(missing_ok=True)
                raise
        else:
            base=Path(config_dir) if config_dir else Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'opencode'
            plugins=base/'plugins'
            if base.is_symlink() or plugins.is_symlink():raise ValueError('플러그인 경로가 올바르지 않습니다.')
            plugins.mkdir(parents=True,exist_ok=True)
            shim=plugins/'tokensaver-docs.js'
            marker='// tokensaver-docs managed plugin\n'
            state_file=parent/'registration.json'
            if state_file.is_symlink():raise ValueError('설치 기록 경로가 올바르지 않습니다.')
            state=json.loads(state_file.read_text()) if state_file.exists() else {}
            if shim.is_symlink() or (shim.exists() and state.get(str(shim))!=file_hash(shim)):
                raise ValueError('기존 사용자 플러그인을 보존했습니다: '+str(shim))
            opencode = shutil.which('opencode')
            version = subprocess.run([opencode, '--version'], capture_output=True, text=True, timeout=10) if opencode else None
            match = re.search(r'\bv?(\d+)\.', version.stdout) if version and version.returncode == 0 else None
            is_v2 = bool(match and match.group(1) == '2')
            exports = 'default' if is_v2 else 'TokenSaverDocsPlugin'
            atomic_write(shim,marker+'export { '+exports+' } from '+json.dumps((target/'index.js').as_uri())+';\n')
            state[str(shim)]=file_hash(shim)
            atomic_write(state_file,json.dumps(state))
    return target
