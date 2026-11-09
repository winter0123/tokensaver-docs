import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PluginPackagingTests(unittest.TestCase):
    def test_platform_bundles_include_binary_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            binary = base / 'tokensaver-docs'
            binary.write_bytes(b'fixture')
            (base/'third-party').mkdir()
            (base/'third-party/pdfium-license.txt').write_text('upstream PDFium notices')
            output = base / 'plugins'
            command = [sys.executable, str(ROOT / 'scripts/package_plugins.py'), '--binary', str(binary), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for platform in ('claude', 'codex', 'opencode'):
                self.assertEqual((output / platform / 'bin/tokensaver-docs').read_bytes(), b'fixture')
                self.assertIn('PDFium', (output/platform/'third-party/pdfium-license.txt').read_text())
            claude = json.loads((output / 'claude/.mcp.json').read_text())
            codex = json.loads((output / 'codex/mcp.json').read_text())
            npm = json.loads((output / 'opencode/package.json').read_text())
            self.assertEqual(claude['mcpServers']['tokensaver-docs']['args'], ['mcp'])
            self.assertEqual(codex['mcpServers']['tokensaver-docs']['type'], 'stdio')
            self.assertEqual(npm['name'], 'tokensaver-docs-opencode')
            for agent, catalog_path in [('claude', '.claude-plugin/marketplace.json'), ('codex', '.agents/plugins/marketplace.json')]:
                catalog = json.loads((output/agent/catalog_path).read_text())
                self.assertEqual(catalog['name'], 'tokensaver-docs-marketplace')
                self.assertEqual(catalog['plugins'][0]['name'], 'tokensaver-docs')
                self.assertTrue((output/agent/'skills/tokensaver-docs/SKILL.md').is_file())
            self.assertEqual(len(npm['os']), 1)
            self.assertEqual(len(npm['cpu']), 1)
            sentinel = output / 'sentinel'
            sentinel.write_text('keep')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(sentinel.read_text(), 'keep')
