# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Build one offline download per platform, sharing identical runtime files."""
import zipfile
from pathlib import Path

AGENTS = ('claude', 'codex', 'opencode')

MAC_INSTALL = '''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
echo 'TokenSaver Docs by winter0123'
choice=${1:-4}
case "$choice" in
    1) agents=claude;; 2) agents=codex;; 3) agents=opencode;;
    ''|4)
        agents=
        for agent in opencode codex claude; do
            if command -v "$agent" >/dev/null; then agents="${agents:+$agents }$agent"; fi
        done
        [ -n "$agents" ] || { echo 'Install at least one supported agent CLI first.' >&2; exit 2; }
        ;;
    *) echo 'Invalid selection'; exit 2;;
esac
set -- $agents
activation=agent
case " $agents " in *' codex claude '*) activation=codex-claude;; esac
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT HUP INT TERM
while [ "$#" -gt 0 ]; do
    agent=$1
    shift
    agent_bundle="$task_tmp/$agent"
    mkdir "$agent_bundle"
    cp -R "$root/common/." "$agent_bundle/"
    cp -R "$root/plugins/$agent/." "$agent_bundle/"
    chmod +x "$agent_bundle/bin/tokensaver-docs"
    mode=none
    if [ "$#" -eq 0 ]; then mode=$activation; fi
    "$agent_bundle/bin/tokensaver-docs" install-plugin "$agent_bundle" --agent "$agent" --activation "$mode"
done
echo 'Installed. Restart the selected agents to load TokenSaver Docs.'
'''
WINDOWS_INSTALL = '''param([string]$Choice = '4')
$ErrorActionPreference = 'Stop'
Write-Host 'TokenSaver Docs by winter0123'
if (-not $Choice -or $Choice -eq '4') {
    $Agents = @('opencode', 'codex', 'claude' | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue })
    if ($Agents.Count -eq 0) { throw 'Install at least one supported agent CLI first.' }
} else {
    $Agents = @(switch ($Choice) { '1' { 'claude' } '2' { 'codex' } '3' { 'opencode' } default { throw 'Invalid selection' } })
}
$Activation = if ($Agents -contains 'codex' -and $Agents -contains 'claude') { 'codex-claude' } else { 'agent' }
$TaskTemp = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $TaskTemp | Out-Null
try {
    for ($Index = 0; $Index -lt $Agents.Count; $Index++) {
        $Agent = $Agents[$Index]
        $Mode = if ($Index -eq $Agents.Count - 1) { $Activation } else { 'none' }
        $Bundle = Join-Path $TaskTemp $Agent
        New-Item -ItemType Directory -Path $Bundle | Out-Null
        Copy-Item -Path (Join-Path $PSScriptRoot 'common/*') -Destination $Bundle -Recurse -Force
        Copy-Item -Path (Join-Path $PSScriptRoot "plugins/$Agent/*") -Destination $Bundle -Recurse -Force
        & (Join-Path $Bundle 'bin/tokensaver-docs.exe') install-plugin $Bundle --agent $Agent --activation $Mode
        if ($LASTEXITCODE -ne 0) { throw "Plugin registration failed for $Agent" }
    }
    Write-Host 'Installed. Restart the selected agents to load TokenSaver Docs.'
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
            archive.writestr('README.txt', 'TokenSaver Docs by winter0123\nhttps://github.com/winter0123/tokensaver-docs\nExtract the entire ZIP first.\n'
                + ('Double-click install.command, or run: sh install.command\n' if system == 'darwin' else 'Open PowerShell in this folder and run: .\\install.ps1\n')
                + 'The installer connects every supported agent CLI it finds.\n'
                + 'Restart your agent after installation. Do not run the internal common runtime directly.\n')
        created.append(path)
    return created
