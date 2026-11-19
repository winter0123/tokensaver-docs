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
agent_name() {
    case "$1" in 1) echo claude;; 2) echo codex;; 3) echo opencode;; esac
}
available=
for number in 1 2 3; do
    agent=$(agent_name "$number")
    if command -v "$agent" >/dev/null; then
        available="$available $number"
    fi
done
if [ "$#" -eq 0 ]; then
    [ -n "$available" ] || { echo 'Install at least one supported agent CLI first.' >&2; exit 2; }
    if [ -t 0 ] && [ -t 1 ] && [ "${TERM:-dumb}" != dumb ]; then
        set -- $available
        rows=$#
        cursor=1
        checked=
        redraw=0
        terminal=$(stty -g)
        trap 'stty "$terminal"' EXIT
        trap 'exit 130' INT
        trap 'exit 143' HUP TERM
        stty -icanon -echo min 1 time 0
        printf 'Tab or arrows to move, Space to check, Enter to install.\\n'
        key_byte() { dd bs=1 count=1 2>/dev/null | od -An -tu1 | tr -d ' '; }
        while :; do
            if [ "$redraw" -eq 1 ]; then printf '\\033[%sA' "$rows"; fi
            index=0
            for number do
                index=$((index + 1))
                pointer=' '
                [ "$index" -ne "$cursor" ] || pointer='>'
                mark=' '
                case "$checked " in *" $number "*) mark=x;; esac
                case "$number" in 1) label='Claude Code';; 2) label=Codex;; 3) label=OpenCode;; esac
                printf '\\r\\033[2K%s [%s] %s\\n' "$pointer" "$mark" "$label"
            done
            redraw=1
            key=$(key_byte)
            if [ "$key" = 27 ]; then
                stty -icanon -echo min 0 time 2
                prefix=$(key_byte)
                suffix=$(key_byte)
                stty -icanon -echo min 1 time 0
                case "$prefix:$suffix" in 91:65|79:65|91:90) key=up;; 91:66|79:66) key=down;; esac
            fi
            case "$key" in
                9|down) cursor=$((cursor % rows + 1));;
                up) cursor=$(((cursor + rows - 2) % rows + 1));;
                32)
                    index=0
                    for number do
                        index=$((index + 1))
                        if [ "$index" -eq "$cursor" ]; then
                            case "$checked " in
                                *" $number "*) checked=$(printf '%s' "$checked" | tr -d "$number");;
                                *) checked="$checked $number";;
                            esac
                            break
                        fi
                    done
                    ;;
                10|13) case "$checked" in *[123]*) break;; *) printf '\\007';; esac;;
                ''|4) exit 2;;
            esac
        done
        stty "$terminal"
        trap - EXIT INT HUP TERM
        choice=$checked
    else
        echo 'Installed agents:'
        for number in $available; do
            case "$number" in 1) label='Claude Code';; 2) label=Codex;; 3) label=OpenCode;; esac
            printf '%s) %s\\n' "$number" "$label"
        done
        printf 'Choose one or more numbers separated by commas or spaces (Enter for all): '
        IFS= read -r choice || exit 2
    fi
else
    choice=$1
fi
set -f
selection=$(printf '%s' "$choice" | tr ',' ' ')
set -- $selection
if [ "$#" -eq 0 ]; then
    case "$choice" in *,*) echo 'Invalid selection' >&2; exit 2;; esac
    set -- $available
fi
[ "$#" -gt 0 ] || { echo 'Install at least one supported agent CLI first.' >&2; exit 2; }
selected=
for number do
    case "$number" in 1|2|3) ;; *) echo 'Invalid selection' >&2; exit 2;; esac
    case "$available " in *" $number "*) ;; *) echo 'Selected agent CLI is not installed.' >&2; exit 2;; esac
    selected="$selected $number"
done
agents=
for number in 3 2 1; do
    case "$selected " in *" $number "*) agents="$agents $(agent_name "$number")";; esac
done
set -- $agents
activation=agent
case "$agents " in *' codex claude '*) activation=codex-claude;; esac
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT HUP INT TERM
while [ "$#" -gt 0 ]; do
    agent=$1
    shift
    case "$agent" in claude) label='Claude Code';; codex) label=Codex;; opencode) label=OpenCode;; esac
    printf 'Installing %s plugin...\\n' "$label"
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
WINDOWS_INSTALL = '''param([string]$Choice)
$ErrorActionPreference = 'Stop'
Write-Host 'TokenSaver Docs by winter0123'
$Names = @{ '1' = 'claude'; '2' = 'codex'; '3' = 'opencode' }
$Labels = @{ '1' = 'Claude Code'; '2' = 'Codex'; '3' = 'OpenCode' }
$Available = @('1', '2', '3' | Where-Object { Get-Command -Name $Names[$_] -ErrorAction SilentlyContinue })
if (-not $PSBoundParameters.ContainsKey('Choice')) {
    if ($Available.Count -eq 0) { throw 'Install at least one supported agent CLI first.' }
    if (-not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected) {
        Write-Host 'Tab or arrows to move, Space to check, Enter to install.'
        $Checked = @{}
        $Cursor = 0
        $Top = [Console]::CursorTop
        while ($true) {
            [Console]::SetCursorPosition(0, $Top)
            for ($Row = 0; $Row -lt $Available.Count; $Row++) {
                $Number = $Available[$Row]
                $Pointer = if ($Row -eq $Cursor) { '>' } else { ' ' }
                $Mark = if ($Checked.ContainsKey($Number)) { 'x' } else { ' ' }
                [Console]::WriteLine("$Pointer [$Mark] $($Labels[$Number])")
            }
            $Top = [Console]::CursorTop - $Available.Count
            $Key = [Console]::ReadKey($true)
            if ($Key.Key -eq 'Enter' -and $Checked.Count -gt 0) { break }
            switch ($Key.Key) {
                Tab {
                    $Step = if ($Key.Modifiers -band [ConsoleModifiers]::Shift) { -1 } else { 1 }
                    $Cursor = ($Cursor + $Available.Count + $Step) % $Available.Count
                }
                DownArrow { $Cursor = ($Cursor + 1) % $Available.Count }
                UpArrow { $Cursor = ($Cursor + $Available.Count - 1) % $Available.Count }
                Spacebar {
                    $Number = $Available[$Cursor]
                    if ($Checked.ContainsKey($Number)) { $Checked.Remove($Number) }
                    else { $Checked[$Number] = $true }
                }
            }
        }
        $Choice = $Checked.Keys -join ','
    } else {
        Write-Host 'Installed agents:'
        foreach ($Number in $Available) { Write-Host "$Number) $($Labels[$Number])" }
        $Choice = Read-Host 'Choose one or more numbers separated by commas or spaces (Enter for all)'
    }
}
if ([string]::IsNullOrWhiteSpace($Choice)) {
    $Selected = $Available
} else {
    $Selected = @($Choice.Trim() -split '[,\\s]+' | Where-Object { $_ })
    if ($Selected.Count -eq 0) { throw 'Invalid selection' }
    foreach ($Number in $Selected) {
        if (-not $Names.ContainsKey($Number)) { throw 'Invalid selection' }
        if ($Available -notcontains $Number) { throw 'Selected agent CLI is not installed.' }
    }
}
if ($Selected.Count -eq 0) { throw 'Install at least one supported agent CLI first.' }
$Agents = @('3', '2', '1' | Where-Object { $Selected -contains $_ } | ForEach-Object { $Names[$_] })
$Activation = if ($Agents -contains 'codex' -and $Agents -contains 'claude') { 'codex-claude' } else { 'agent' }
$TaskTemp = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $TaskTemp | Out-Null
try {
    for ($Index = 0; $Index -lt $Agents.Count; $Index++) {
        $Agent = $Agents[$Index]
        $Label = switch ($Agent) { 'claude' { 'Claude Code' } 'codex' { 'Codex' } 'opencode' { 'OpenCode' } }
        Write-Host "Installing $Label plugin..."
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
                + 'Use Tab or the arrow keys to move, Space to check agents, and Enter to install.\n'
                + 'Restart your agent after installation. Do not run the internal common runtime directly.\n')
        created.append(path)
    return created
