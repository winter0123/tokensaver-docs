#!/bin/sh
# Install only from a release repository you trust. No sudo or Python required.
set -eu
repo='' version='' agent=''
usage() { echo 'Usage: install.sh --repo owner/repo --version tag --agent claude|codex|opencode' >&2; exit 2; }
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || usage
  case "$1" in
    --repo) repo=$2; shift 2;;
    --version) version=$2; shift 2;;
    --agent) agent=$2; shift 2;;
    *) usage;;
  esac
done
case "$repo" in *[!a-zA-Z0-9_./-]*|''|/*|*/|*/*/*) echo 'Invalid repository' >&2; exit 2;; esac
case "$repo" in */*) ;; *) echo 'Use owner/repo' >&2; exit 2;; esac
case "$version" in *[!a-zA-Z0-9._-]*|'') echo 'Invalid version' >&2; exit 2;; esac
case "$agent" in claude|codex|opencode) ;; *) echo 'Choose an agent' >&2; exit 2;; esac
[ "$(uname -s)" = Darwin ] || { echo 'This installer is for macOS' >&2; exit 2; }
case "$(uname -m)" in arm64) arch=arm64;; x86_64) arch=x64;; *) echo 'Unsupported CPU' >&2; exit 2;; esac
asset="file-to-md-${agent}-darwin-${arch}.zip"
base="https://github.com/$repo/releases/download/$version"
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT HUP INT TERM
curl -fL --proto '=https' --connect-timeout 15 --max-time 300 "$base/checksums.txt" -o "$task_tmp/checksums.txt"
curl -fL --proto '=https' --connect-timeout 15 --max-time 300 "$base/$asset" -o "$task_tmp/bundle.zip"
expected=$(awk -v name="$asset" '$2 == name { print $1 }' "$task_tmp/checksums.txt")
[ "${#expected}" -eq 64 ] || { echo 'Missing checksum' >&2; exit 2; }
actual=$(shasum -a 256 "$task_tmp/bundle.zip" | awk '{print $1}')
[ "$actual" = "$expected" ] || { echo 'Checksum mismatch' >&2; exit 2; }
mkdir "$task_tmp/bundle"
unzip -q "$task_tmp/bundle.zip" -d "$task_tmp/bundle"
chmod +x "$task_tmp/bundle/bin/file-to-md"
"$task_tmp/bundle/bin/file-to-md" install-plugin "$task_tmp/bundle" --agent "$agent" --expected-version "${version#v}"
echo "Installed $version for $agent. Restart your agent to load the plugin."
