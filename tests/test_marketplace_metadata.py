"""Offline metadata and packaging tests for the three plugin-host paths."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "marketplace-plugin"
OPENCODE = ROOT / "plugins/opencode"


class MarketplaceMetadataTests(unittest.TestCase):
    def test_codex_skills_only_manifest(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tokensaver-docs")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["interface"]["displayName"], "TokenSaver Docs")
        self.assertNotIn("mcpServers", manifest)
        self.assertFalse((PLUGIN / "mcp.json").exists())
        self.assertTrue((PLUGIN / "skills/tokensaver-docs/SKILL.md").is_file())

    def test_claude_skills_only_manifest(self):
        manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tokensaver-docs")
        self.assertFalse((PLUGIN / ".mcp.json").exists())
        skill = (PLUGIN / "skills/tokensaver-docs/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("context INPUT", skill)
        self.assertIn("prepare INPUT", skill)

    def test_platform_launchers(self):
        shell = PLUGIN / "scripts/run.sh"
        powershell = PLUGIN / "scripts/run.ps1"
        self.assertTrue(shell.is_file())
        self.assertTrue(powershell.is_file())
        self.assertEqual(shell.read_text(encoding="utf-8"),
                         (OPENCODE / "scripts/run.sh").read_text(encoding="utf-8"))
        self.assertEqual(powershell.read_text(encoding="utf-8"),
                         (OPENCODE / "scripts/run.ps1").read_text(encoding="utf-8"))
        if shutil.which("sh"):
            subprocess.run(["sh", "-n", str(shell)], check=True)

    def test_opencode_git_subdirectory_has_all_assets(self):
        pkg = json.loads((OPENCODE / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["name"], "tokensaver-docs-opencode")
        for item in ("index.js", "runtime.js", "research-routing.json", "skills/tokensaver-docs/SKILL.md", "scripts/run.sh", "scripts/run.ps1"):
            self.assertTrue((OPENCODE / item).is_file(), item)
        self.assertEqual((OPENCODE / "research-routing.json").read_bytes(),
                         (ROOT / "tokensaver_docs/data/research-routing.json").read_bytes())
        source = (OPENCODE / "index.js").read_text(encoding="utf-8")
        self.assertIn("ensureTokenSaverExecutable", source)
        self.assertIn("./research-routing.json", source)


if __name__ == "__main__":
    unittest.main()
