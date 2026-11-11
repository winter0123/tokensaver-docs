import hashlib
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipIf(os.name == 'nt', 'POSIX installer; Windows uses PowerShell')
class MacReleaseInstallerTests(unittest.TestCase):
    def test_verified_release_and_checksum_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            commands = root/'commands'
            commands.mkdir()
            log = root/'calls'
            archive = root/'tokensaver-docs-opencode-darwin-arm64.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('bin/tokensaver-docs', '#!/bin/sh\nprintf "%s\\n" "$@" > "$INSTALL_TEST_LOG"\n')
            checks = root/'checksums.txt'
            checks.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
            (commands/'uname').write_text('#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo arm64;; esac\n')
            (commands/'curl').write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\ncase "$1" in https://*) url=$1;; -o) shift; target=$1;; esac\nshift\ndone\ncp "$INSTALL_TEST_FILES/${url##*/}" "$target"\n')
            for command in commands.iterdir():command.chmod(0o755)
            env=dict(os.environ, PATH=str(commands)+os.pathsep+os.environ['PATH'], INSTALL_TEST_FILES=str(root), INSTALL_TEST_LOG=str(log))
            command=['sh', str(ROOT/'scripts/install.sh'), '--repo', 'owner/repo', '--version', 'v0.3.0', '--agent', 'opencode']
            result=subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('--expected-version\n0.3.0',log.read_text())
            log.unlink()
            checks.write_text('0'*64+'  '+archive.name+'\n')
            result=subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(log.exists())

    def test_missing_argument_has_usage(self):
        result=subprocess.run(['sh',str(ROOT/'scripts/install.sh'),'--repo'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('Usage:',result.stderr)


@unittest.skipUnless(os.name == 'nt' and os.environ.get('TOKENSAVER_DOCS_STANDALONE'), 'requires Windows built executable')
class WindowsReleaseInstallerTests(unittest.TestCase):
    def test_install_and_update_with_local_release_download(self):
        import json
        from tokensaver_docs import __version__
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            files={'bin/tokensaver-docs.exe':Path(os.environ['TOKENSAVER_DOCS_STANDALONE']).read_bytes(),
                   'platform.json':json.dumps({'agent':'opencode','os':'win32','cpu':'x64','version':__version__}).encode(),
                   'index.js':b'export const TokenSaverDocsPlugin=()=>({});', 'package.json':b'{}',
                   'skills/tokensaver-docs/SKILL.md':(ROOT/'plugins/skill/SKILL.md').read_bytes()}
            checks={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
            archive=root/'tokensaver-docs-opencode-win32-x64.zip'
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
                for name,data in files.items():bundle.writestr(name,data)
                bundle.writestr('checksums.json',json.dumps(checks))
            (root/'checksums.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
            wrapper=root/'test.ps1'
            wrapper.write_text('function Invoke-WebRequest { param($Uri,$OutFile,$TimeoutSec) Copy-Item (Join-Path $env:INSTALL_TEST_FILES (($Uri -split "/")[-1])) $OutFile }\n& $env:INSTALL_TEST_SCRIPT -Repo owner/repo -Version $env:INSTALL_TEST_VERSION -Agent opencode\n',encoding='utf-8')
            cache=root/'cache';cache.mkdir()
            (cache/'sentinel').write_text('keep my cached documents')
            env=dict(os.environ, TOKENSAVER_DOCS_CACHE_DIR=str(cache), XDG_CONFIG_HOME=str(root/'config'), INSTALL_TEST_FILES=str(root), INSTALL_TEST_SCRIPT=str(ROOT/'scripts/install.ps1'), INSTALL_TEST_VERSION='v'+__version__)
            for _ in range(2):
                result=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(wrapper)],env=env,capture_output=True,text=True,timeout=180)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertTrue((root/'config/opencode/plugins/tokensaver-docs.js').is_file())
                self.assertEqual((cache/'sentinel').read_text(),'keep my cached documents')
