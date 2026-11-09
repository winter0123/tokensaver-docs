"""Build one offline download per platform, sharing identical runtime files."""
import zipfile
from pathlib import Path

AGENTS = ('claude', 'codex', 'opencode')

MAC_INSTALL = '''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
printf 'TokenSaver Docs — choose your agent\\n1) Claude Code\\n2) Codex\\n3) OpenCode\\nEnter 1, 2 or 3: '
read -r choice
case "$choice" in 1) agent=claude;; 2) agent=codex;; 3) agent=opencode;; *) echo 'Invalid selection'; exit 2;; esac
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT HUP INT TERM
cp -R "$root/common/." "$task_tmp/"
cp -R "$root/plugins/$agent/." "$task_tmp/"
chmod +x "$task_tmp/bin/tokensaver-docs"
"$task_tmp/bin/tokensaver-docs" install-plugin "$task_tmp" --agent "$agent"
echo 'Installed. Restart your agent to load TokenSaver Docs.'
'''
WINDOWS_INSTALL = '''$ErrorActionPreference = 'Stop'
Write-Host 'TokenSaver Docs — choose your agent'
Write-Host '1) Claude Code'
Write-Host '2) Codex'
Write-Host '3) OpenCode'
$Choice = Read-Host 'Enter 1, 2 or 3'
$Agent = switch ($Choice) { '1' { 'claude' } '2' { 'codex' } '3' { 'opencode' } default { throw 'Invalid selection' } }
$TaskTemp = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $TaskTemp | Out-Null
try {
    Copy-Item -Path (Join-Path $PSScriptRoot 'common/*') -Destination $TaskTemp -Recurse -Force
    Copy-Item -Path (Join-Path $PSScriptRoot "plugins/$Agent/*") -Destination $TaskTemp -Recurse -Force
    & (Join-Path $TaskTemp 'bin/tokensaver-docs.exe') install-plugin $TaskTemp --agent $Agent
    if ($LASTEXITCODE -ne 0) { throw 'Plugin registration failed' }
    Write-Host 'Installed. Restart your agent to load TokenSaver Docs.'
} finally { Remove-Item -Recurse -Force $TaskTemp }
'''


def create_platform_downloads(folder):
    folder = Path(folder)
    created = []
    for system, cpu in (('darwin', 'arm64'), ('darwin', 'x64'), ('win32', 'x64')):
        contents = {}
        for agent in AGENTS:
            with zipfile.ZipFile(folder/f'tokensaver-docs-{agent}-{system}-{cpu}.zip') as archive:
                contents[agent] = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
        common = set.intersection(*(set(files) for files in contents.values()))
        common = {name for name in common if len({files[name] for files in contents.values()}) == 1}
        path = folder/f'tokensaver-docs-{system}-{cpu}.zip'
        with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(common):
                archive.writestr('common/'+name, contents['claude'][name])
            for agent, files in contents.items():
                for name in sorted(set(files)-common):
                    archive.writestr(f'plugins/{agent}/{name}', files[name])
            script = 'install.command' if system == 'darwin' else 'install.ps1'
            info = zipfile.ZipInfo(script)
            info.create_system = 3
            info.external_attr = 0o100755 << 16
            archive.writestr(info, MAC_INSTALL if system == 'darwin' else WINDOWS_INSTALL.encode('utf-8-sig'))
            archive.writestr('README.txt', 'TokenSaver Docs: extract the entire ZIP first.\n'
                + ('Double-click install.command, or run: sh install.command\n' if system == 'darwin' else 'Open PowerShell in this folder and run: .\\install.ps1\n')
                + 'Choose 1 (Claude Code), 2 (Codex), or 3 (OpenCode). The selected agent CLI must already be installed.\n'
                + 'Restart your agent after installation. Do not run the internal common runtime directly.\n')
        created.append(path)
    return created
