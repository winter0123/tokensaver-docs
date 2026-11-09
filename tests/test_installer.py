import hashlib,json,tempfile,unittest
from pathlib import Path
from file_to_md.installer import install_bundle,verify_bundle

class InstallerTests(unittest.TestCase):
    def make_claude_bundle(self, root):
        import os, platform, sys
        from file_to_md import __version__
        bundle=root/'bundle'
        (bundle/'bin').mkdir(parents=True)
        exe='file-to-md.exe' if os.name=='nt' else 'file-to-md'
        (bundle/'bin'/exe).write_bytes(b'executable')
        (bundle/'.claude-plugin').mkdir()
        (bundle/'.claude-plugin/marketplace.json').write_text(json.dumps({'plugins':[{'name':'file-to-md','source':'./'}]}))
        cpu={'amd64':'x64','x86_64':'x64','aarch64':'arm64','arm64':'arm64'}[platform.machine().lower()]
        (bundle/'platform.json').write_text(json.dumps({'os':sys.platform,'cpu':cpu,'agent':'claude','version':__version__}))
        checks={p.relative_to(bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
        (bundle/'checksums.json').write_text(json.dumps(checks))
        return bundle

    def test_requested_version_mismatch_does_not_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=self.make_claude_bundle(root)
            with self.assertRaisesRegex(ValueError,'버전'):
                install_bundle(bundle,'claude',destination=root/'installed',expected_version='9.9.9')
            self.assertFalse((root/'installed').exists())

    def test_registration_failure_restores_previous_catalog(self):
        from unittest.mock import patch
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=self.make_claude_bundle(root)
            catalog=root/'installed/marketplace/.claude-plugin/marketplace.json'
            for old in (None, '{"previous":"user catalog"}'):
                if old is not None:
                    catalog.parent.mkdir(parents=True,exist_ok=True)
                    catalog.write_text(old)
                with patch('file_to_md.installer.subprocess.run',side_effect=subprocess.CalledProcessError(1,'claude')):
                    with self.assertRaises(subprocess.CalledProcessError):
                        install_bundle(bundle,'claude',destination=root/'installed')
                if old is None:self.assertFalse(catalog.exists())
                else:self.assertEqual(catalog.read_text(),old)

    def test_integrity_idempotency_and_user_plugin_preservation(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'bundle';(bundle/'bin').mkdir(parents=True)
            exe='file-to-md.exe' if os.name=='nt' else 'file-to-md'
            (bundle/'bin'/exe).write_bytes(b'executable')
            (bundle/'index.js').write_text('export const FileToMdPlugin=()=>({});')
            (bundle/'package.json').write_text('{}')
            import platform,sys
            cpu={'amd64':'x64','x86_64':'x64','aarch64':'arm64','arm64':'arm64'}[platform.machine().lower()]
            from file_to_md import __version__
            (bundle/'platform.json').write_text(json.dumps({'os':sys.platform,'cpu':cpu,'agent':'opencode','version':__version__}))
            checks={p.relative_to(bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
            (bundle/'checksums.json').write_text(json.dumps(checks))
            args=dict(destination=root/'installed',config_dir=root/'config')
            from unittest.mock import patch
            import subprocess
            for major, expected in [('1', 'FileToMdPlugin'), ('2', 'default')]:
                with patch('file_to_md.installer.shutil.which', return_value='/usr/bin/opencode'), patch('file_to_md.installer.subprocess.run', return_value=subprocess.CompletedProcess([], 0, f'opencode v{major}.1.3', '')):
                    first=install_bundle(bundle,'opencode',**args)
                    self.assertEqual(install_bundle(bundle,'opencode',**args),first)
                    self.assertIn('export { '+expected+' }', (root/'config/plugins/file-to-md.js').read_text())
            shim=root/'config/plugins/file-to-md.js';shim.write_text('// user plugin')
            with self.assertRaises(ValueError):install_bundle(bundle,'opencode',**args)
            self.assertEqual(shim.read_text(),'// user plugin')
            (bundle/'index.js').write_text('tampered')
            with self.assertRaises(ValueError):verify_bundle(bundle)
