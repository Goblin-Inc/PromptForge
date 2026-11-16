"""Unit tests for PromptForge local sandbox and A/B test runner."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from promptforge.sandbox import LLMProvider, SandboxConfig, fetch_models, run_ab_test, run_chat


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TestSandbox(unittest.TestCase):
    def test_fetch_models_ollama_and_openai(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _FakeResponse(
                {"models": [{"name": "qwen2.5-coder:7b"}, {"name": "llama3.1:8b"}]}
            )
            models = fetch_models(SandboxConfig(provider=LLMProvider.OLLAMA))
            self.assertEqual(models, ["llama3.1:8b", "qwen2.5-coder:7b"])

            mock_open.return_value = _FakeResponse(
                {"data": [{"id": "gpt-4o-mini"}, {"id": "deepseek-coder"}]}
            )
            models_oai = fetch_models(
                SandboxConfig(provider=LLMProvider.OPENAI_COMPAT, base_url="http://localhost:1234/v1")
            )
            self.assertEqual(models_oai, ["deepseek-coder", "gpt-4o-mini"])

    def test_run_chat_and_ab_test_ollama(self) -> None:
        def fake_urlopen(req, timeout=30):  # noqa: ANN001, ARG001
            body = json.loads(req.data.decode("utf-8"))
            has_sys = any(m["role"] == "system" for m in body["messages"])
            reply = "STRICT CODE REPLY" if has_sys else "GENERIC REPLY"
            return _FakeResponse({"message": {"content": reply}})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cfg = SandboxConfig(provider=LLMProvider.OLLAMA, model="qwen2.5-coder:7b")
            base, prompted = run_ab_test(cfg, "ROLE: Senior", "Write hello world")
            self.assertTrue(base.ok)
            self.assertTrue(prompted.ok)
            self.assertEqual(base.content, "GENERIC REPLY")
            self.assertEqual(prompted.content, "STRICT CODE REPLY")

            single = run_chat(cfg, "ROLE: Senior", "Hi")
            self.assertTrue(single.ok)
            self.assertEqual(single.content, "STRICT CODE REPLY")


if __name__ == "__main__":
    unittest.main()
