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
            # The installed skill must advertise the user's actual conversion goal.
            for agent in ('claude', 'codex'):
                text = (output / agent / 'skills/tokensaver-docs/SKILL.md').read_text(encoding='utf-8')
                frontmatter = text.split('---', 2)[1]
                self.assertIn('description:', frontmatter)
                self.assertIn('Markdown', frontmatter)
                self.assertIn('HTML', frontmatter)
                self.assertIn('photo/image/screenshot', text)
                self.assertIn('output` is a directory', text)
                self.assertIn('ordinary image viewing or image questions', text)
                self.assertEqual(text, (ROOT/'plugins/skill/SKILL.md').read_text(encoding='utf-8'))
            opencode_skill=output/'opencode/skills/tokensaver-docs/SKILL.md'
            self.assertEqual(opencode_skill.read_text(encoding='utf-8'),(ROOT/'plugins/skill/SKILL.md').read_text(encoding='utf-8'))
            self.assertIn('skills',json.loads((output/'opencode/package.json').read_text())['files'])
            local_skill=(ROOT/'skills/tokensaver-docs/SKILL.md').read_text(encoding='utf-8').split('---',2)[1]
            self.assertIn('Markdown',local_skill)
            self.assertIn('HTML',local_skill)
            local_text=(ROOT/'skills/tokensaver-docs/SKILL.md').read_text(encoding='utf-8')
            self.assertIn('사진/이미지/스크린샷',local_text)
            self.assertIn('디렉터리다',local_text)
            claude = json.loads((output / 'claude/.mcp.json').read_text())
            codex = json.loads((output / 'codex/mcp.json').read_text())
            npm = json.loads((output / 'opencode/package.json').read_text())
            self.assertEqual(claude['mcpServers']['tokensaver-docs']['command'], '${CLAUDE_PLUGIN_ROOT}/bin/tokensaver-docs')
            self.assertEqual(claude['mcpServers']['tokensaver-docs']['args'], ['mcp'])
            self.assertEqual(codex['mcpServers']['tokensaver-docs']['type'], 'stdio')
            self.assertEqual(codex['mcpServers']['tokensaver-docs']['command'], './bin/' + binary.name)
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

    def test_codex_portable_command_keeps_windows_executable_name(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            binary = base / 'tokensaver-docs.exe'
            binary.write_bytes(b'fixture')
            (base/'third-party').mkdir()
            output = base / 'plugins'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/package_plugins.py'), '--binary', str(binary), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            codex = json.loads((output / 'codex/mcp.json').read_text())
            claude = json.loads((output / 'claude/.mcp.json').read_text())
            self.assertEqual(codex['mcpServers']['tokensaver-docs']['command'], './bin/tokensaver-docs.exe')
            self.assertEqual(claude['mcpServers']['tokensaver-docs']['command'], '${CLAUDE_PLUGIN_ROOT}/bin/tokensaver-docs.exe')
