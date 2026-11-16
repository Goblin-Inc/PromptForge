"""Compatibility linter and token estimator for compiled system prompts."""

from __future__ import annotations

import re

from .models import Domain, LintIssue, PromptSpec, TargetAI

RISKY_JAILBREAK_PATTERNS = (
    "игнорируй все",
    "ignore all previous",
    "ignore all rules",
    "bypass all",
    "обойди все ограничения",
    "отключи безопасность",
    "забудь свои правила",
)


def estimate_tokens(text: str) -> int:
    """Approximates token count for mixed Cyrillic/Latin prompts."""
    if not text.strip():
        return 0
    cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", text))
    other = max(0, len(text) - cyrillic)
    # Cyrillic averages ~2 chars/token; Latin/punctuation ~3.8 chars/token
    return max(1, round(cyrillic / 2.0 + other / 3.8))


def lint_prompt(
    spec: PromptSpec,
    compiled_text: str,
    detected_domain: Domain,
    estimated_tokens: int | None = None,
) -> list[LintIssue]:
    tokens = estimated_tokens if estimated_tokens is not None else estimate_tokens(compiled_text)
    issues: list[LintIssue] = []
    lowered_req = spec.user_request.lower()
    lowered_full = compiled_text.lower()

    if len(spec.user_request.strip()) < 8:
        issues.append(
            LintIssue(
                level="warning",
                code="SHORT_INPUT",
                message="Слишком короткий исходный запрос — роль может получиться слишком общей.",
                suggestion="Уточни стек, уровень задач или целевую аудиторию (например: 'Python/Linux, без воды').",
            )
        )

    if spec.target == TargetAI.LOCAL_SMALL and tokens > 350 and not spec.flags.compact:
        issues.append(
            LintIssue(
                level="warning",
                code="LOCAL_TOO_LONG",
                message=f"Для локальных моделей 7B–14B промпт тяжеловат (~{tokens} токенов) — часть правил может теряться.",
                suggestion="Включи режим Compact (--compact), чтобы сжать инструкции до коротких директив.",
            )
        )
    elif tokens > 1200:
        issues.append(
            LintIssue(
                level="warning",
                code="VERY_LONG_PROMPT",
                message=f"Промпт занимает ~{tokens} токенов — в длинных диалогах часть деталей может размываться.",
                suggestion="Убери второстепенные ограничения или включи Compact-режим.",
            )
        )

    if detected_domain == Domain.CYBERSEC and not spec.flags.engineering_security_context:
        issues.append(
            LintIssue(
                level="info",
                code="CYBERSEC_CONTEXT_RECOMMENDED",
                message="Для задач кибербезопасности облачные ИИ иногда дают ложные отказы на термины вроде уязвимостей.",
                suggestion="Включи 'Инженерный/учебный контекст' (engineering_security_context), чтобы модель понимала рамку аудита и защиты.",
            )
        )

    if any(pat in lowered_req or pat in lowered_full for pat in RISKY_JAILBREAK_PATTERNS):
        issues.append(
            LintIssue(
                level="warning",
                code="FALSE_REFUSAL_RISK",
                message="Обнаружены жёсткие формулировки ('игнорируй все правила' / 'отключи безопасность'), которые вызывают отказы у GPT/Claude/Gemini.",
                suggestion="Используй Direct Mode + инженерный/учебный контекст вместо прямых команд на обход правил.",
            )
        )

    if spec.target == TargetAI.CLAUDE and "<role>" not in compiled_text:
        issues.append(
            LintIssue(
                level="info",
                code="CLAUDE_XML_TIP",
                message="Claude стабильнее соблюдает системные инструкции при разметке XML-тегами (<role>, <rules>).",
                suggestion="Используй целевой формат Claude.",
            )
        )

    return issues
