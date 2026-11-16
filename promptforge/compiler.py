"""Prompt compiler and target-specific formatter for PromptForge."""

from __future__ import annotations

import re

from .linter import estimate_tokens, lint_prompt
from .models import Domain, GeneratedPrompt, PromptSpec, TargetAI
from .presets import DOMAIN_TEMPLATES, INSTALL_GUIDES, TONE_RULES, detect_domain


def _extract_role(user_request: str, fallback: str) -> str:
    cleaned = re.sub(r"\s+", " ", user_request).strip(" .,:;-")
    if not cleaned:
        return fallback
    # Trim polite lead-ins so the role statement stays crisp
    cleaned = re.sub(r"^(ты|вы|будь|стань|представь,? что ты)\s+", "", cleaned, flags=re.IGNORECASE)
    if not cleaned:
        return fallback
    return cleaned[0].upper() + cleaned[1:]


def _collect_rules(spec: PromptSpec, domain: Domain) -> tuple[list[str], list[str], list[str]]:
    tpl = DOMAIN_TEMPLATES[domain]
    is_ru = spec.language.lower().startswith("ru")

    principles = list(tpl.principles_ru if is_ru else tpl.principles_en)
    constraints = list(tpl.constraints_ru if is_ru else tpl.constraints_en)
    output_format = list(tpl.output_format_ru if is_ru else tpl.output_format_en)

    tone_rule = TONE_RULES[spec.tone][0 if is_ru else 1]
    principles.insert(0, tone_rule)

    flags = spec.flags
    if flags.direct_mode:
        if is_ru:
            constraints.extend(
                [
                    "Начинай сразу с решения/кода. Никаких 'Конечно!', 'Вот пример:', извинений, нравоучений и фраз 'Как ИИ-модель...'.",
                    "Если задача решается за 3 строки — не растягивай ответ на 30 строк.",
                ]
            )
        else:
            constraints.extend(
                [
                    "Start directly with the solution or code. Never say 'Sure', 'Here is', apologies, lecturing, or 'As an AI model...' disclaimers.",
                    "Keep answers concise unless depth is genuinely required.",
                ]
            )

    if flags.full_code and domain in (Domain.CODING, Domain.CYBERSEC, Domain.DEVOPS, Domain.DATA_ANALYTICS):
        if is_ru:
            output_format.append(
                "Пиши полный рабочий код без пропусков, TODO-заглушек и '...остальное допишите сами'."
            )
        else:
            output_format.append(
                "Provide complete, runnable code without placeholders or '...rest of code here'."
            )

    if flags.engineering_security_context:
        if is_ru:
            constraints.append(
                "Применяй лучшие практики защитного программирования: таймауты, пулы потоков, строгую валидацию и безопасную работу с ресурсами."
            )
        else:
            constraints.append(
                "Apply defensive engineering best practices: explicit timeouts, bounded worker pools, strict validation, and safe resource cleanup."
            )

    if flags.step_by_step:
        if is_ru:
            principles.append("Перед итоговым ответом кратко сверься с крайними случаями и скрытыми зависимостями.")
        else:
            principles.append("Verify edge cases and hidden dependencies before finalizing the output.")

    for extra in spec.extra_constraints:
        stripped = extra.strip()
        if stripped:
            constraints.append(stripped)

    if flags.compact:
        principles = principles[:2]
        constraints = constraints[:3]
        output_format = output_format[:1]

    return principles, constraints, output_format


def _format_claude_xml(role: str, principles: list[str], constraints: list[str], output_format: list[str]) -> str:
    p_lines = "\n".join(f"  - {item}" for item in principles)
    c_lines = "\n".join(f"  - {item}" for item in constraints)
    o_lines = "\n".join(f"  - {item}" for item in output_format)
    return (
        f"<role>\n{role}\n</role>\n\n"
        f"<principles>\n{p_lines}\n</principles>\n\n"
        f"<constraints>\n{c_lines}\n</constraints>\n\n"
        f"<output_format>\n{o_lines}\n</output_format>"
    )


def _format_markdown(
    role: str,
    principles: list[str],
    constraints: list[str],
    output_format: list[str],
    agent_header: bool = False,
) -> str:
    p_lines = "\n".join(f"- {item}" for item in principles)
    c_lines = "\n".join(f"- {item}" for item in constraints)
    o_lines = "\n".join(f"- {item}" for item in output_format)
    title = "# Agent Instructions" if agent_header else "# Role"
    return (
        f"{title}\n{role}\n\n"
        f"## Core Principles\n{p_lines}\n\n"
        f"## Rules & Constraints\n{c_lines}\n\n"
        f"## Output Format\n{o_lines}"
    )


def _format_local_small(role: str, principles: list[str], constraints: list[str], output_format: list[str]) -> str:
    rules = principles[:2] + constraints[:3] + output_format[:1]
    numbered = "\n".join(f"{idx}. {item}" for idx, item in enumerate(rules, start=1))
    return f"ROLE: {role}\n\nSTRICT RULES:\n{numbered}"


def compile_prompt(spec: PromptSpec) -> GeneratedPrompt:
    """Compiles a short user request into a structured, target-adapted system prompt."""
    domain = detect_domain(spec.user_request, spec.domain)
    tpl = DOMAIN_TEMPLATES[domain]
    is_ru = spec.language.lower().startswith("ru")
    fallback_role = tpl.default_role_ru if is_ru else tpl.default_role_en
    role = _extract_role(spec.user_request, fallback_role)

    principles, constraints, output_format = _collect_rules(spec, domain)

    if spec.target == TargetAI.CLAUDE:
        text = _format_claude_xml(role, principles, constraints, output_format)
    elif spec.target == TargetAI.LOCAL_SMALL:
        text = _format_local_small(role, principles, constraints, output_format)
    elif spec.target == TargetAI.CODING_AGENT:
        text = _format_markdown(role, principles, constraints, output_format, agent_header=True)
    else:
        text = _format_markdown(role, principles, constraints, output_format, agent_header=False)

    tokens = estimate_tokens(text)
    issues = lint_prompt(spec, text, domain, estimated_tokens=tokens)
    export_filename, install_guide = INSTALL_GUIDES[spec.target]

    return GeneratedPrompt(
        text=text,
        estimated_tokens=tokens,
        detected_domain=domain,
        detected_role=role,
        lint_issues=issues,
        install_guide=install_guide,
        export_filename=export_filename,
    )
