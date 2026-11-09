param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [Parameter(Mandatory=$true)][string]$Version,
  [Parameter(Mandatory=$true)][ValidateSet('claude','codex','opencode')][string]$Agent
)
$ErrorActionPreference = 'Stop'
if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) { throw 'This installer is for Windows' }
if ($Repo -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or $Version -notmatch '^[A-Za-z0-9_.-]+$') { throw 'Invalid repository or version' }
$Arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
if ($Arch -ne 'x64') { throw 'This release installer currently supports Windows x64 only' }
$Asset = "file-to-md-$Agent-win32-x64.zip"
$BaseUrl = "https://github.com/$Repo/releases/download/$Version"
$TaskTemp = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $TaskTemp | Out-Null
try {
  Invoke-WebRequest "$BaseUrl/checksums.txt" -OutFile (Join-Path $TaskTemp 'checksums.txt') -TimeoutSec 300
  $Archive = Join-Path $TaskTemp 'bundle.zip'
  Invoke-WebRequest "$BaseUrl/$Asset" -OutFile $Archive -TimeoutSec 300
  $Rows = @(Get-Content (Join-Path $TaskTemp 'checksums.txt') | Where-Object { ($_ -split '\s+')[1] -eq $Asset })
  if ($Rows.Count -ne 1) { throw 'Missing or duplicate checksum' }
  $Expected = ($Rows[0] -split '\s+')[0]
  if ($Expected -notmatch '^[a-fA-F0-9]{64}$' -or (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected.ToLowerInvariant()) { throw 'Checksum mismatch' }
  $Bundle = Join-Path $TaskTemp 'bundle'
  Expand-Archive -Path $Archive -DestinationPath $Bundle
  & (Join-Path $Bundle 'bin/file-to-md.exe') install-plugin $Bundle --agent $Agent --expected-version ($Version -replace '^v','')
  if ($LASTEXITCODE -ne 0) { throw 'Plugin registration failed' }
  Write-Host "Installed $Version for $Agent. Restart your agent to load the plugin."
} finally { Remove-Item -Recurse -Force $TaskTemp }
