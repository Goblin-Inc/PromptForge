"""Unit tests for PromptForge Stage 4 Auto-Deploy engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from promptforge.deployer import (
    MARKER_END,
    MARKER_START,
    AgentTarget,
    build_modelfile,
    deploy_to_agent_file,
    recommend_ollama_model,
    sanitize_model_name,
)


class TestDeployer(unittest.TestCase):
    def test_deploy_to_agent_file_merges_and_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            target_file = proj / "CLAUDE.md"
            target_file.write_text("# My Existing Project Rules\nKeep tests fast.\n", encoding="utf-8")

            res1 = deploy_to_agent_file(
                AgentTarget.CLAUDE_PROJECT,
                "# Role\nSenior Security Auditor",
                project_dir=proj,
                merge_section=True,
            )
            self.assertTrue(res1.ok)
            self.assertIsNotNone(res1.backup_path)
            self.assertTrue(res1.backup_path.exists())

            text1 = target_file.read_text(encoding="utf-8")
            self.assertIn("# My Existing Project Rules", text1)
            self.assertIn(MARKER_START, text1)
            self.assertIn("Senior Security Auditor", text1)
            self.assertIn(MARKER_END, text1)

            # Second deploy should replace only the PromptForge section, not duplicate it
            res2 = deploy_to_agent_file(
                AgentTarget.CLAUDE_PROJECT,
                "# Role\nSenior Rust Engineer",
                project_dir=proj,
                merge_section=True,
            )
            self.assertTrue(res2.ok)
            text2 = target_file.read_text(encoding="utf-8")
            self.assertEqual(text2.count(MARKER_START), 1)
            self.assertIn("# My Existing Project Rules", text2)
            self.assertIn("Senior Rust Engineer", text2)
            self.assertNotIn("Senior Security Auditor", text2)

    def test_modelfile_and_sanitization(self) -> None:
        self.assertEqual(sanitize_model_name("My Coder 2.0!"), "my-coder-2.0")
        self.assertEqual(recommend_ollama_model(8.0), "qwen2.5-coder:3b")
        self.assertEqual(recommend_ollama_model(16.0), "qwen2.5-coder:7b")
        self.assertEqual(recommend_ollama_model(32.0), "qwen2.5-coder:14b")

        mf = build_modelfile("qwen2.5-coder:7b", 'ROLE: "Test"')
        self.assertIn("FROM qwen2.5-coder:7b", mf)
        self.assertIn('SYSTEM """', mf)
        self.assertIn('ROLE: "Test"', mf)


if __name__ == "__main__":
    unittest.main()
