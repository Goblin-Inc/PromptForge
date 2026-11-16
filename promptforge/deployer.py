"""Auto-deployment engine for Ollama and CLI/IDE AI agents (Stage 4)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class AgentTarget(str, Enum):
    ANTIGRAVITY_GLOBAL = "antigravity_global"
    ANTIGRAVITY_PROJECT = "antigravity_project"
    CLAUDE_GLOBAL = "claude_global"
    CLAUDE_PROJECT = "claude_project"
    CODEX_GLOBAL = "codex_global"
    CODEX_PROJECT = "codex_project"
    CURSOR_PROJECT = "cursor_project"


MARKER_START = "<!-- PROMPTFORGE_START -->"
MARKER_END = "<!-- PROMPTFORGE_END -->"


@dataclass(frozen=True)
class EnvStatus:
    ollama_bin: str | None
    ollama_running: bool
    ram_gb: float
    recommended_model: str
    installed_clis: dict[str, str | None]


@dataclass(frozen=True)
class DeployResult:
    ok: bool
    message: str
    target_path: Path | None = None
    backup_path: Path | None = None


def get_system_ram_gb() -> float:
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return 8.0
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MemTotal:"):
            kb = int(re.findall(r"\d+", line)[0])
            return round(kb / (1024 * 1024), 1)
    return 8.0


def recommend_ollama_model(ram_gb: float) -> str:
    if ram_gb >= 20:
        return "qwen2.5-coder:14b"
    if ram_gb >= 10:
        return "qwen2.5-coder:7b"
    return "qwen2.5-coder:3b"


def is_ollama_running(base_url: str = "http://localhost:11434") -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def detect_environment() -> EnvStatus:
    ram_gb = get_system_ram_gb()
    ollama_bin = shutil.which("ollama")
    running = is_ollama_running() if ollama_bin else False
    clis = {
        "ollama": ollama_bin,
        "claude": shutil.which("claude"),
        "codex": shutil.which("codex"),
        "antigravity": shutil.which("antigravity-cli") or shutil.which("agy") or shutil.which("gemini"),
        "cursor": shutil.which("cursor"),
    }
    return EnvStatus(
        ollama_bin=ollama_bin,
        ollama_running=running,
        ram_gb=ram_gb,
        recommended_model=recommend_ollama_model(ram_gb),
        installed_clis=clis,
    )


def resolve_agent_path(target: AgentTarget, project_dir: Path | None = None) -> Path:
    home = Path.home()
    proj = project_dir or Path.cwd()
    mapping = {
        AgentTarget.ANTIGRAVITY_GLOBAL: home / ".gemini" / "GEMINI.md",
        AgentTarget.ANTIGRAVITY_PROJECT: proj / "GEMINI.md",
        AgentTarget.CLAUDE_GLOBAL: home / ".claude" / "CLAUDE.md",
        AgentTarget.CLAUDE_PROJECT: proj / "CLAUDE.md",
        AgentTarget.CODEX_GLOBAL: home / ".codex" / "AGENTS.md",
        AgentTarget.CODEX_PROJECT: proj / "AGENTS.md",
        AgentTarget.CURSOR_PROJECT: proj / ".cursorrules",
    }
    return mapping[target]


def deploy_to_agent_file(
    target: AgentTarget,
    prompt_text: str,
    project_dir: Path | None = None,
    merge_section: bool = True,
) -> DeployResult:
    """Writes or safely merges the system prompt into an AI agent instruction file with backup."""
    dest = resolve_agent_path(target, project_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)

    backup_path: Path | None = None
    existing = ""
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = dest.with_name(f"{dest.name}.bak.{stamp}")
        shutil.copy2(dest, backup_path)

    block = f"{MARKER_START}\n{prompt_text.strip()}\n{MARKER_END}\n"
    if merge_section and existing.strip():
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n?",
            flags=re.DOTALL,
        )
        if pattern.search(existing):
            new_content = pattern.sub(block, existing, count=1)
        else:
            sep = "\n\n" if not existing.endswith("\n\n") else ""
            new_content = existing.rstrip() + sep + "\n" + block
    else:
        new_content = block if merge_section else (prompt_text.strip() + "\n")

    dest.write_text(new_content, encoding="utf-8")
    return DeployResult(
        ok=True,
        message=f"Промпт применён: {dest}",
        target_path=dest,
        backup_path=backup_path,
    )


def sanitize_model_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._:-]+", "-", name.strip().lower()).strip("-")
    return cleaned or "promptforge-assistant"


def build_modelfile(base_model: str, prompt_text: str) -> str:
    escaped = prompt_text.strip().replace('"""', '\\"\\"\\"')
    return f'FROM {base_model}\n\nSYSTEM """\n{escaped}\n"""\n'


def _run_streaming(cmd: list[str], log: Callable[[str], None]) -> int:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        stripped = line.rstrip()
        if stripped:
            log(stripped)
    return proc.wait()


def start_ollama_daemon(log: Callable[[str], None]) -> bool:
    if is_ollama_running():
        log("Ollama уже запущена.")
        return True
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        log("Ошибка: бинарник ollama не найден в PATH.")
        return False

    log("Запускаю `ollama serve` в фоне...")
    subprocess.Popen(
        [ollama_bin, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(15):
        if is_ollama_running():
            log("Ollama успешно запущена на http://localhost:11434.")
            return True
        time.sleep(0.4)
    log("Не удалось дождаться старта Ollama на порту 11434.")
    return False


def install_ollama_linux(log: Callable[[str], None]) -> bool:
    """Installs Ollama on Linux using pkexec+pacman on Arch or official install script."""
    if shutil.which("ollama"):
        log("Ollama уже установлена.")
        return start_ollama_daemon(log)

    if shutil.which("pacman") and shutil.which("pkexec"):
        log("Обнаружен Arch Linux: устанавливаю пакет `ollama` через pkexec pacman...")
        rc = _run_streaming(["pkexec", "pacman", "-S", "--noconfirm", "ollama"], log)
        if rc == 0:
            log("Ollama установлена через pacman.")
            return start_ollama_daemon(log)
        log(f"pacman завершился с кодом {rc}.")
        return False

    if shutil.which("curl"):
        log("Устанавливаю Ollama через официальный скрипт ollama.com/install.sh...")
        rc = _run_streaming(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], log)
        if rc == 0:
            return start_ollama_daemon(log)
        return False

    log("Авто-установка недоступна: установи Ollama вручную (`sudo pacman -S ollama`).")
    return False


def pull_ollama_model(model: str, log: Callable[[str], None]) -> bool:
    if not start_ollama_daemon(log):
        return False
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False
    log(f"Скачиваю модель {model}...")
    rc = _run_streaming([ollama_bin, "pull", model], log)
    if rc == 0:
        log(f"Модель {model} готова.")
        return True
    log(f"Ошибка скачивания {model} (код {rc}).")
    return False


def create_ollama_assistant(
    assistant_name: str,
    base_model: str,
    prompt_text: str,
    log: Callable[[str], None],
) -> DeployResult:
    if not start_ollama_daemon(log):
        return DeployResult(ok=False, message="Ollama не запущена.")
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return DeployResult(ok=False, message="Ollama не установлена.")

    safe_name = sanitize_model_name(assistant_name)
    modelfile_dir = Path.home() / ".local" / "share" / "promptforge" / "modelfiles"
    modelfile_dir.mkdir(parents=True, exist_ok=True)
    modelfile_path = modelfile_dir / f"Modelfile.{safe_name}"
    modelfile_path.write_text(build_modelfile(base_model, prompt_text), encoding="utf-8")
    log(f"Сохранён Modelfile: {modelfile_path}")

    rc = _run_streaming([ollama_bin, "create", safe_name, "-f", str(modelfile_path)], log)
    if rc == 0:
        return DeployResult(
            ok=True,
            message=f"Ассистент '{safe_name}' создан! Запуск: ollama run {safe_name}",
            target_path=modelfile_path,
        )
    return DeployResult(ok=False, message=f"ollama create завершился с кодом {rc}", target_path=modelfile_path)
