"""Data models for PromptForge prompt compilation and linting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TargetAI(str, Enum):
    CLAUDE = "claude"
    GPT = "gpt"
    GEMINI = "gemini"
    LOCAL_SMALL = "local_small"
    CODING_AGENT = "coding_agent"


class Domain(str, Enum):
    AUTO = "auto"
    CODING = "coding"
    CYBERSEC = "cybersec"
    DEVOPS = "devops"
    DATA_ANALYTICS = "data_analytics"
    WRITING = "writing"
    GENERAL = "general"


class Tone(str, Enum):
    DIRECT = "direct"
    STRICT = "strict"
    MENTOR = "mentor"
    BALANCED = "balanced"


@dataclass
class BehaviorFlags:
    direct_mode: bool = True
    full_code: bool = True
    engineering_security_context: bool = False
    step_by_step: bool = False
    compact: bool = False


@dataclass
class PromptSpec:
    user_request: str
    target: TargetAI = TargetAI.GPT
    domain: Domain = Domain.AUTO
    tone: Tone = Tone.DIRECT
    flags: BehaviorFlags = field(default_factory=BehaviorFlags)
    language: str = "ru"
    extra_constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LintIssue:
    level: str  # "info" | "warning" | "error"
    code: str
    message: str
    suggestion: str


@dataclass
class GeneratedPrompt:
    text: str
    estimated_tokens: int
    detected_domain: Domain
    detected_role: str
    lint_issues: list[LintIssue]
    install_guide: str
    export_filename: str
