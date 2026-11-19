#!/bin/sh
# Native TokenSaver Docs launcher; never installs agent settings.
set -eu
version=v0.5.6
[ "$(uname -s)" = Darwin ] || { echo 'Only macOS binaries available; Linux needs source installation.' >&2; exit 2; }
case "$(uname -m)" in arm64) cpu=arm64;; x86_64) cpu=x64;; *) echo 'Unsupported CPU' >&2; exit 2;; esac
for tool in curl shasum unzip awk mktemp; do command -v "$tool" >/dev/null || exit 2; done
base="$HOME/Library/Application Support/tokensaver-docs/marketplace-runtime"
if [ -n "${TOKENSAVER_DOCS_RUNTIME_HOME:-}" ]; then base="$TOKENSAVER_DOCS_RUNTIME_HOME"; fi
parent="$base/$version"
target="$parent/darwin-$cpu"
binary="$target/bin/tokensaver-docs"
if [ ! -x "$binary" ]; then
  [ "${TOKENSAVER_DOCS_NO_BOOTSTRAP:-0}" != 1 ] || { echo 'Automatic download disabled' >&2; exit 2; }
  mkdir -p "$parent"
  lock="$parent/.darwin-$cpu.lock"
  n=0
  while ! mkdir "$lock" 2>/dev/null; do
    [ -x "$binary" ] && break
    n=$((n + 1))
    [ "$n" -lt 60 ] || { echo 'Runtime lock timeout' >&2; exit 2; }
    sleep 1
  done
  if [ ! -x "$binary" ]; then
    tmp=$(mktemp -d "$parent/.download.XXXXXXXX")
    cleanup() { rm -rf "$tmp"; rmdir "$lock" 2>/dev/null || :; }
    trap cleanup EXIT HUP INT TERM
    asset="tokensaver-docs-codex-darwin-$cpu.zip"
    url="https://github.com/winter0123/tokensaver-docs/releases/download/$version"
    echo "TokenSaver Docs: downloading $version from GitHub Release for $cpu" >&2
    curl -fsSL --proto '=https' --connect-timeout 15 --max-time 300 "$url/checksums.txt" -o "$tmp/checksums.txt"
    curl -fsSL --proto '=https' --connect-timeout 15 --max-time 600 "$url/$asset" -o "$tmp/bundle.zip"
    expected=$(awk -v asset="$asset" '$2 == asset {print $1}' "$tmp/checksums.txt")
    case "$expected" in *[!0-9a-fA-F]*|'') echo 'Invalid checksum' >&2; exit 2;; esac
    [ "${#expected}" -eq 64 ] || { echo 'Missing checksum' >&2; exit 2; }
    actual=$(shasum -a 256 "$tmp/bundle.zip" | awk '{print $1}')
    [ "$actual" = "$expected" ] || { echo 'SHA-256 mismatch' >&2; exit 2; }
    unzip -Z -1 "$tmp/bundle.zip" | awk '{if ($0 ~ /^\// || $0 ~ /(^|\/)\.\.(\/|$)/ || $0 ~ /\\/) exit 1}' || { echo 'Unsafe archive' >&2; exit 2; }
    mkdir "$tmp/payload"
    unzip -q "$tmp/bundle.zip" -d "$tmp/payload"
    [ -f "$tmp/payload/bin/tokensaver-docs" ] || { echo 'Missing binary' >&2; exit 2; }
    chmod +x "$tmp/payload/bin/tokensaver-docs"
    [ -e "$target" ] || mv "$tmp/payload" "$target"
    cleanup
    trap - EXIT HUP INT TERM
  fi
fi
[ -x "$binary" ] || { echo 'Runtime not installed; inspect cache' >&2; exit 2; }
exec "$binary" "$@"
