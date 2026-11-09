# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Validate CI archives and assemble a complete release directory; never publish."""
import argparse
import hashlib
import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tokensaver_docs import __version__
from scripts.platform_downloads import create_platform_downloads


def prepare(artifacts, output, tag):
    if tag != 'v'+__version__:
        raise ValueError('Release tag must match v'+__version__)
    expected={f'tokensaver-docs-{agent}-{system}-{cpu}.zip':(agent,system,cpu)
              for agent in ('claude','codex','opencode')
              for system,cpu in (('darwin','arm64'),('darwin','x64'),('win32','x64'))}
    archives=list(artifacts.rglob('*.zip'))
    if len(archives)!=len(expected) or {p.name for p in archives}!=set(expected):
        raise ValueError('Expected exactly nine unique Windows/macOS plugin archives')
    for path in archives:
        with zipfile.ZipFile(path) as archive:
            info=archive.infolist()
            names=[i.filename for i in info if not i.is_dir()]
            if len(info)>1000 or sum(i.file_size for i in info)>1024**3 or len(names)!=len(set(names)):
                raise ValueError('Invalid archive size or duplicate entries: '+path.name)
            for item in info:
                name=PurePosixPath(item.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in item.filename or ':' in item.filename or stat.S_ISLNK(item.external_attr>>16):
                    raise ValueError('Unsafe archive path: '+path.name)
            metadata=json.loads(archive.read('platform.json'))
            agent,system,cpu=expected[path.name]
            if any(metadata.get(k)!=v for k,v in {'agent':agent,'os':system,'cpu':cpu,'version':__version__}.items()):
                raise ValueError('Incorrect archive metadata: '+path.name)
            checks=json.loads(archive.read('checksums.json'))
            if not isinstance(checks,dict) or set(checks)!=set(names)-{'checksums.json'}:
                raise ValueError('Unlisted archive contents: '+path.name)
            for name,checksum in checks.items():
                if hashlib.sha256(archive.read(name)).hexdigest()!=checksum:
                    raise ValueError('Archive checksum mismatch: '+path.name)
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for path in sorted(archives):
        shutil.copy2(path,output/path.name)
        rows.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name)
    for path in create_platform_downloads(output):
        rows.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name)
    (output/'checksums.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    for notice in ('LICENSE', 'NOTICE', 'AUTHORS.md'):
        shutil.copy2(ROOT/notice,output/notice)
    for script in ('install.sh','install.ps1'):
        shutil.copy2(ROOT/'scripts'/script,output/script)
    (output/'release-notes.md').write_text(
        f'# tokensaver-docs {tag} preview\n\n'
        'Local document context tools for Claude Code, Codex and OpenCode.\n\n'
        'Choose the unified archive for your OS and CPU, extract it, and run its installer to select your agent. Agent-specific archives remain available. '
        'No separate Python, Poppler, npm or Bun installation is required by the bundles. '
        'Local audio requires a separately selected and downloaded model.\n\n'
        'This is a prerelease. Check the CI results and perform real Windows/macOS agent installation tests before publishing. '
        'Unsigned binaries may trigger OS trust prompts. Official directory listings are separate from this release.\n',encoding='utf-8')
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    try:
        print(prepare(args.artifacts,args.output,args.tag))
    except (ValueError,OSError,KeyError,zipfile.BadZipFile) as error:
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':
    main()
