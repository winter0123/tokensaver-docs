# TokenSaver Docs native Windows launcher. Does not change any agent configuration.
$ErrorActionPreference = 'Stop'
$version = 'v0.5.6'
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
$homeDir = if ($env:TOKENSAVER_DOCS_RUNTIME_HOME) { $env:TOKENSAVER_DOCS_RUNTIME_HOME } else { Join-Path $env:LOCALAPPDATA 'tokensaver-docs\marketplace-runtime' }
$parent = Join-Path $homeDir $version
$target = Join-Path $parent 'win32-x64'
$binary = Join-Path $target 'bin\tokensaver-docs.exe'
if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
    if ($env:TOKENSAVER_DOCS_NO_BOOTSTRAP -eq '1') { throw 'Automatic runtime download disabled.' }
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $lock = Join-Path $parent '.win32-x64.lock'
    $handle = $null
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $handle = [System.IO.File]::Open($lock, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        } catch {
            if (Test-Path -LiteralPath $binary -PathType Leaf) { break }
            Start-Sleep -Seconds 1
        }
    }
    if (-not $handle -and -not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw 'Runtime install lock timeout.' }
    $temp = Join-Path $parent ('.download.' + [guid]::NewGuid().ToString('N'))
    try {
        if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
            New-Item -ItemType Directory -Path $temp | Out-Null
            $asset = 'tokensaver-docs-codex-win32-x64.zip'
            $url = "https://github.com/winter0123/tokensaver-docs/releases/download/$version"
            Write-Host "TokenSaver Docs: downloading $version runtime from GitHub Release."
            $sums = Join-Path $temp 'checksums.txt'
            $archive = Join-Path $temp 'bundle.zip'
            Invoke-WebRequest -Uri "$url/checksums.txt" -OutFile $sums -MaximumRedirection 5
            Invoke-WebRequest -Uri "$url/$asset" -OutFile $archive -MaximumRedirection 5
            $pattern = '^[A-Fa-f0-9]{64}\s+' + [regex]::Escape($asset) + '$'
            $line = Get-Content -LiteralPath $sums | Where-Object { $_ -match $pattern } | Select-Object -First 1
            if (-not $line) { throw 'Missing checksum entry.' }
            $expected = ($line -split '\s+')[0].ToLowerInvariant()
            $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($expected -ne $actual) { throw 'SHA-256 mismatch.' }
            Add-Type -AssemblyName System.IO.Compression
            $zip = [IO.Compression.ZipFile]::OpenRead($archive)
            try {
                foreach ($entry in $zip.Entries) {
                    $name = $entry.FullName
                    if ($name.StartsWith('/') -or $name.Contains('\') -or $name -match '(^|/)\.\.(/|$)' -or [IO.Path]::IsPathRooted($name)) { throw 'Unsafe archive entry.' }
                }
            } finally { $zip.Dispose() }
            $payload = Join-Path $temp 'payload'
            Expand-Archive -LiteralPath $archive -DestinationPath $payload
            if (-not (Test-Path -LiteralPath (Join-Path $payload 'bin\tokensaver-docs.exe') -PathType Leaf)) { throw 'Binary missing.' }
            if (-not (Test-Path -LiteralPath $target)) { Move-Item -LiteralPath $payload -Destination $target }
        }
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
        if ($handle) { $handle.Dispose(); Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue }
    }
}
if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw 'Native runtime missing.' }
& $binary @args
exit $LASTEXITCODE
