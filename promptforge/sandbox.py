"""Local LLM sandbox and A/B test runner (Ollama & OpenAI-compatible APIs)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI_COMPAT = "openai_compat"


@dataclass(frozen=True)
class SandboxConfig:
    provider: LLMProvider = LLMProvider.OLLAMA
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    api_key: str = ""
    timeout_sec: int = 300


@dataclass(frozen=True)
class ChatResult:
    ok: bool
    content: str
    elapsed_sec: float
    error: str = ""


def _http_json(
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data = None
    method = "GET"
    if payload is not None:
        method = "POST"
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def fetch_models(config: SandboxConfig) -> list[str]:
    """Queries available model names from Ollama or an OpenAI-compatible endpoint."""
    base = config.base_url.rstrip("/")
    headers: dict[str, str] = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    if config.provider == LLMProvider.OLLAMA:
        data = _http_json(f"{base}/api/tags", headers=headers, timeout=10)
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return sorted(models)

    data = _http_json(f"{base}/models", headers=headers, timeout=10)
    models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    return sorted(models)


def _stream_ollama_chat(
    url: str,
    payload: dict,
    headers: dict[str, str],
    timeout: int,
    on_chunk: Callable[[str], None] | None,
) -> str:
    req_headers = {"Accept": "application/json", "Content-Type": "application/json", **headers}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    parts: list[str] = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            chunk_data = json.loads(line)
            delta = chunk_data.get("message", {}).get("content", "")
            if delta:
                parts.append(delta)
                if on_chunk is not None:
                    on_chunk(delta)
            if chunk_data.get("done"):
                break
    return "".join(parts)


def run_chat(
    config: SandboxConfig,
    system_prompt: str,
    user_message: str,
    on_chunk: Callable[[str], None] | None = None,
) -> ChatResult:
    """Runs a chat completion against the configured endpoint (streaming for Ollama when requested)."""
    base = config.base_url.rstrip("/")
    headers: dict[str, str] = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    messages: list[dict[str, str]] = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    started = time.monotonic()
    try:
        if config.provider == LLMProvider.OLLAMA:
            use_stream = on_chunk is not None
            payload = {
                "model": config.model,
                "messages": messages,
                "stream": use_stream,
            }
            if use_stream:
                content = _stream_ollama_chat(
                    f"{base}/api/chat",
                    payload=payload,
                    headers=headers,
                    timeout=config.timeout_sec,
                    on_chunk=on_chunk,
                )
            else:
                data = _http_json(f"{base}/api/chat", payload=payload, headers=headers, timeout=config.timeout_sec)
                content = data.get("message", {}).get("content", "")
        else:
            payload = {
                "model": config.model,
                "messages": messages,
                "stream": False,
            }
            data = _http_json(f"{base}/chat/completions", payload=payload, headers=headers, timeout=config.timeout_sec)
            choices = data.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            if on_chunk is not None and content:
                on_chunk(content)

        return ChatResult(ok=True, content=content.strip(), elapsed_sec=time.monotonic() - started)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except OSError:
            pass
        return ChatResult(
            ok=False,
            content="",
            elapsed_sec=time.monotonic() - started,
            error=f"HTTP {exc.code}: {body or exc.reason}",
        )
    except Exception as exc:
        return ChatResult(
            ok=False,
            content="",
            elapsed_sec=time.monotonic() - started,
            error=f"Ошибка подключения: {exc}",
        )


def run_ab_test(
    config: SandboxConfig,
    system_prompt: str,
    user_message: str,
    on_base_chunk: Callable[[str], None] | None = None,
    on_prompted_chunk: Callable[[str], None] | None = None,
) -> tuple[ChatResult, ChatResult]:
    """Runs baseline and prompted inference (sequentially for local Ollama, concurrently for remote APIs)."""
    if config.provider == LLMProvider.OLLAMA:
        base_res = run_chat(config, "", user_message, on_chunk=on_base_chunk)
        prompted_res = run_chat(config, system_prompt, user_message, on_chunk=on_prompted_chunk)
        return base_res, prompted_res

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_base = pool.submit(run_chat, config, "", user_message, on_base_chunk)
        fut_prompted = pool.submit(run_chat, config, system_prompt, user_message, on_prompted_chunk)
        return fut_base.result(), fut_prompted.result()
