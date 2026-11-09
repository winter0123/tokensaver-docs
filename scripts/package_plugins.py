# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Assemble local platform-specific plugin bundles without overwriting prior output."""
import argparse
import json
import platform as host_platform
import shutil
import subprocess
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tokensaver_docs import __version__


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle-opencode', action='store_true', help='Bundle the JS SDK so installation needs no npm or Bun')
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    if args.output.exists():
        parser.error('output already exists; choose a new directory')
    name = binary.name
    if name not in ('tokensaver-docs', 'tokensaver-docs.exe'):
        parser.error('binary must be named tokensaver-docs or tokensaver-docs.exe')
    notices=binary.parent/'third-party'
    if not notices.is_dir():
        parser.error('binary must have its third-party notices directory from build_standalone.py')
    os_name = {'darwin': 'darwin', 'linux': 'linux', 'win32': 'win32'}.get(sys.platform)
    cpu = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'amd64': 'x64'}.get(host_platform.machine().lower())
    if not os_name or not cpu:
        parser.error('unsupported build OS or CPU')
    args.output.mkdir(parents=True)
    for platform in ('claude', 'codex', 'opencode'):
        root = args.output / platform
        (root / 'bin').mkdir(parents=True)
        shutil.copy2(binary, root / 'bin' / name)
        shutil.copytree(notices,root/'third-party')
        if platform != 'opencode':
            target = root / 'skills' / 'tokensaver-docs'
            target.mkdir(parents=True)
            shutil.copy2(ROOT / 'plugins/skill/SKILL.md', target / 'SKILL.md')
        if platform == 'claude':
            write_json(root / '.claude-plugin/plugin.json', {'name': 'tokensaver-docs', 'version': __version__, 'description': 'TokenSaver Docs: prepare documents once and retrieve bounded evidence.', 'author': {'name': 'winter0123', 'url': 'https://github.com/winter0123'}})
            write_json(root / '.claude-plugin/marketplace.json', {'name': 'tokensaver-docs-marketplace', 'description': 'TokenSaver Docs document context plugins for coding agents.', 'owner': {'name': 'winter0123', 'url': 'https://github.com/winter0123'}, 'plugins': [{'name': 'tokensaver-docs', 'source': './'}]})
            write_json(root / '.mcp.json', {'mcpServers': {'tokensaver-docs': {'command': '${CLAUDE_PLUGIN_ROOT}/bin/' + name, 'args': ['mcp']}}})
        elif platform == 'codex':
            write_json(root / 'plugin.json', {'$schema': 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json', 'name': 'tokensaver-docs', 'version': __version__, 'description': 'TokenSaver Docs: prepare documents once and retrieve bounded evidence.', 'author': {'name': 'winter0123', 'url': 'https://github.com/winter0123'}})
            write_json(root / 'mcp.json', {'$schema': 'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json', 'mcpServers': {'tokensaver-docs': {'type': 'stdio', 'command': '${PLUGIN_ROOT}/bin/' + name, 'args': ['mcp']}}})
            write_json(root / '.agents/plugins/marketplace.json', {'name': 'tokensaver-docs-marketplace', 'plugins': [{'name': 'tokensaver-docs', 'source': {'source': 'local', 'path': './'}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]})
        else:
            for item in ('index.js', 'package.json', 'README.md'):
                shutil.copy2(ROOT / 'plugins/opencode' / item, root / item)
            package_path = root / 'package.json'
            package = json.loads(package_path.read_text(encoding='utf-8'))
            package.update(os=[os_name], cpu=[cpu])
            if args.bundle_opencode:
                subprocess.run(['bun','build',str(ROOT/'plugins/opencode/index.js'),'--target=node','--format=esm','--outfile',str(root/'index.js')],check=True)
                package.pop('dependencies',None)
            write_json(package_path, package)
        write_json(root/'platform.json',{'os':os_name,'cpu':cpu,'agent':platform,'version':__version__})
        for notice in ('LICENSE', 'NOTICE', 'AUTHORS.md'):
            shutil.copy2(ROOT/notice,root/notice)
        checks={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        write_json(root/'checksums.json',checks)
    print(args.output)


if __name__ == '__main__':
    main()
