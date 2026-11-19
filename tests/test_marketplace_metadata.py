"""The repository root is a valid Git-sourced marketplace plugin package."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class MarketplaceMetadataTests(unittest.TestCase):
    def test_codex_root_manifest(self):
        manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tokensaver-docs")
        self.assertEqual(manifest["extensions"]["com.openai"]["interface"]["displayName"], "TokenSaver Docs")
        self.assertEqual(mcp["mcpServers"]["tokensaver-docs"]["command"], "tokensaver-docs")
        self.assertEqual(mcp["mcpServers"]["tokensaver-docs"]["args"], ["mcp"])
        self.assertTrue((ROOT / "skills/tokensaver-docs/SKILL.md").is_file())

    def test_claude_root_manifest(self):
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tokensaver-docs")
        self.assertEqual(mcp["mcpServers"]["tokensaver-docs"]["command"], "tokensaver-docs")
        self.assertEqual(mcp["mcpServers"]["tokensaver-docs"]["args"], ["mcp"])

if __name__ == "__main__":
    unittest.main()
