import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from file_to_md import __version__

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
                files={'platform.json':json.dumps({'os':system,'cpu':cpu,'agent':agent,'version':__version__}).encode(), 'bin/file-to-md':b'fixture executable'}
                checks={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
                with zipfile.ZipFile(folder/f'file-to-md-{agent}-{system}-{cpu}.zip','w') as archive:
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
            self.assertEqual(len(rows),9)
            for row in rows:
                expected,name=row.split()
                self.assertEqual(hashlib.sha256((root/'release'/name).read_bytes()).hexdigest(),expected)
            self.assertTrue((root/'release/install.ps1').is_file())
            self.assertNotEqual(self.run_prepare(root).returncode,0)

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
