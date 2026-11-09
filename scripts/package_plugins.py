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
from file_to_md import __version__


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
    if name not in ('file-to-md', 'file-to-md.exe'):
        parser.error('binary must be named file-to-md or file-to-md.exe')
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
            target = root / 'skills' / 'file-to-md'
            target.mkdir(parents=True)
            shutil.copy2(ROOT / 'plugins/skill/SKILL.md', target / 'SKILL.md')
        if platform == 'claude':
            write_json(root / '.claude-plugin/plugin.json', {'name': 'file-to-md', 'version': __version__, 'description': 'TokenSaver Docs: prepare documents once and retrieve bounded evidence.', 'author': {'name': 'file-to-md contributors'}})
            write_json(root / '.claude-plugin/marketplace.json', {'name': 'file-to-md-marketplace', 'description': 'TokenSaver Docs document context plugins for coding agents.', 'owner': {'name': 'file-to-md contributors'}, 'plugins': [{'name': 'file-to-md', 'source': './'}]})
            write_json(root / '.mcp.json', {'mcpServers': {'file-to-md': {'command': '${CLAUDE_PLUGIN_ROOT}/bin/' + name, 'args': ['mcp']}}})
        elif platform == 'codex':
            write_json(root / 'plugin.json', {'$schema': 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json', 'name': 'file-to-md', 'version': __version__, 'description': 'TokenSaver Docs: prepare documents once and retrieve bounded evidence.', 'author': {'name': 'file-to-md contributors'}})
            write_json(root / 'mcp.json', {'$schema': 'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json', 'mcpServers': {'file-to-md': {'type': 'stdio', 'command': '${PLUGIN_ROOT}/bin/' + name, 'args': ['mcp']}}})
            write_json(root / '.agents/plugins/marketplace.json', {'name': 'file-to-md-marketplace', 'plugins': [{'name': 'file-to-md', 'source': {'source': 'local', 'path': './'}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]})
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
        shutil.copy2(ROOT/'LICENSE',root/'LICENSE')
        checks={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        write_json(root/'checksums.json',checks)
    print(args.output)


if __name__ == '__main__':
    main()
