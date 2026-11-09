import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tokensaver_docs import __version__

ROOT=Path(__file__).resolve().parent.parent


class ReleaseTests(unittest.TestCase):
    def test_source_package_versions_match(self):
        import tomllib
        with (ROOT/'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'],__version__)
        self.assertEqual(json.loads((ROOT/'plugins/opencode/package.json').read_text())['version'],__version__)

    def fixture(self, artifacts):
        for system,cpu in (('darwin','arm64'),('darwin','x64'),('win32','x64')):
            for agent in ('claude','codex','opencode'):
                folder=artifacts/f'{system}-{cpu}'
                folder.mkdir(parents=True,exist_ok=True)
                files={'platform.json':json.dumps({'os':system,'cpu':cpu,'agent':agent,'version':__version__}).encode(), 'bin/tokensaver-docs':b'fixture executable'}
                checks={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
                with zipfile.ZipFile(folder/f'tokensaver-docs-{agent}-{system}-{cpu}.zip','w') as archive:
                    for name,data in files.items():archive.writestr(name,data)
                    archive.writestr('checksums.json',json.dumps(checks))

    def run_prepare(self,root,tag=None):
        return subprocess.run([sys.executable,str(ROOT/'scripts/prepare_release.py'),'--artifacts',str(root/'artifacts'),'--output',str(root/'release'),'--tag',tag or 'v'+__version__],capture_output=True,text=True)

    def test_merges_all_platforms_without_losing_checksums(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root/'artifacts')
            result=self.run_prepare(root)
            self.assertEqual(result.returncode,0,result.stderr)
            rows=(root/'release/checksums.txt').read_text().splitlines()
            self.assertEqual(len(rows),12)
            for row in rows:
                expected,name=row.split()
                self.assertEqual(hashlib.sha256((root/'release'/name).read_bytes()).hexdigest(),expected)
            self.assertTrue((root/'release/install.ps1').is_file())
            for system,cpu in (('darwin','arm64'),('darwin','x64'),('win32','x64')):
                with zipfile.ZipFile(root/f'release/tokensaver-docs-{system}-{cpu}.zip') as unified:
                    common={n.removeprefix('common/'):unified.read(n) for n in unified.namelist() if n.startswith('common/')}
                    self.assertEqual(common['bin/tokensaver-docs'],b'fixture executable')
                    for agent in ('claude','codex','opencode'):
                        prefix=f'plugins/{agent}/'
                        restored={**common,**{n.removeprefix(prefix):unified.read(n) for n in unified.namelist() if n.startswith(prefix)}}
                        with zipfile.ZipFile(root/f'release/tokensaver-docs-{agent}-{system}-{cpu}.zip') as original:
                            self.assertEqual(restored,{n:original.read(n) for n in original.namelist()})
            self.assertNotEqual(self.run_prepare(root).returncode,0)

    @unittest.skipIf(sys.platform == 'win32', 'POSIX launcher runs on macOS')
    def test_unified_launcher_selects_agent_and_preserves_failure(self):
        import os
        from scripts.platform_downloads import MAC_INSTALL
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'common/bin').mkdir(parents=True)
            (root/'plugins/codex').mkdir(parents=True)
            (root/'plugins/codex/marker').write_text('codex payload')
            binary=root/'common/bin/tokensaver-docs'
            binary.write_text('#!/bin/sh\ntest -f "$2/marker" || exit 8\nprintf "%s\\n" "$4" > "$TEST_AGENT_LOG"\nexit "${TEST_EXIT_CODE:-0}"\n')
            launcher=root/'install.command';launcher.write_text(MAC_INSTALL)
            env=dict(os.environ,TEST_AGENT_LOG=str(root/'called'))
            result=subprocess.run(['sh',str(launcher)],input='2\n',text=True,capture_output=True,env=env)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((root/'called').read_text().strip(),'codex')
            self.assertTrue((root/'plugins/codex/marker').exists())
            failed=subprocess.run(['sh',str(launcher)],input='2\n',text=True,capture_output=True,env={**env,'TEST_EXIT_CODE':'9'})
            self.assertEqual(failed.returncode,9)
            self.assertNotIn('Installed.',failed.stdout)
            invalid=subprocess.run(['sh',str(launcher)],input='0\n',text=True,capture_output=True,env=env)
            self.assertEqual(invalid.returncode,2)

    def test_windows_launcher_parses_and_rejects_invalid_selection(self):
        import shutil
        shell=shutil.which('powershell') or shutil.which('pwsh')
        if not shell:self.skipTest('PowerShell not installed')
        from scripts.platform_downloads import WINDOWS_INSTALL
        with tempfile.TemporaryDirectory() as temp:
            script=Path(temp)/'install.ps1';script.write_text(WINDOWS_INSTALL,encoding='utf-8-sig')
            result=subprocess.run([shell,'-NoProfile','-File',str(script)],input='0\n',text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Invalid selection',result.stderr)
            self.assertFalse((Path(temp)/'common').exists())

    def test_missing_platform_and_wrong_tag_cannot_prepare_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root/'artifacts')
            invalid=self.run_prepare(root,'v9.9.9')
            self.assertNotEqual(invalid.returncode,0)
            self.assertIn('Release tag must match',invalid.stderr)
            next((root/'artifacts').rglob('*.zip')).unlink()
            missing=self.run_prepare(root)
            self.assertNotEqual(missing.returncode,0)
            self.assertIn('nine unique',missing.stderr)
            self.assertFalse((root/'release').exists())

    def test_tampered_archive_cannot_prepare_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root/'artifacts')
            with zipfile.ZipFile(next((root/'artifacts').rglob('*.zip')),'a') as archive:
                archive.writestr('unlisted-file',b'changed')
            result=self.run_prepare(root)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((root/'release').exists())
