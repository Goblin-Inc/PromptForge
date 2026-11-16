"""CLI entry point for testing PromptForge core generation and linting."""

from __future__ import annotations

import argparse
import sys

from .compiler import compile_prompt
from .models import BehaviorFlags, Domain, PromptSpec, TargetAI, Tone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptforge",
        description="Генератор и адаптер системных промптов для разных ИИ.",
    )
    parser.add_argument("request", help="Короткий запрос (роль/задача)")
    parser.add_argument(
        "--target",
        choices=[t.value for t in TargetAI],
        default=TargetAI.GPT.value,
        help="Целевая нейросеть или агент",
    )
    parser.add_argument(
        "--domain",
        choices=[d.value for d in Domain],
        default=Domain.AUTO.value,
        help="Предметная область",
    )
    parser.add_argument(
        "--tone",
        choices=[t.value for t in Tone],
        default=Tone.DIRECT.value,
        help="Стиль общения",
    )
    parser.add_argument("--lang", default="ru", choices=["ru", "en"], help="Язык промпта")
    parser.add_argument("--no-direct", action="store_true", help="Отключить режим без воды/извинений")
    parser.add_argument("--no-full-code", action="store_true", help="Не требовать полный код без заглушек")
    parser.add_argument("--sec-context", action="store_true", help="Включить инженерный/учебный контекст безопасности")
    parser.add_argument("--step-by-step", action="store_true", help="Добавить проверку крайних случаев")
    parser.add_argument("--compact", action="store_true", help="Сжать промпт (рекомендуется для 7B–14B)")
    parser.add_argument("--constraint", action="append", default=[], help="Дополнительное правило (можно несколько раз)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec = PromptSpec(
        user_request=args.request,
        target=TargetAI(args.target),
        domain=Domain(args.domain),
        tone=Tone(args.tone),
        flags=BehaviorFlags(
            direct_mode=not args.no_direct,
            full_code=not args.no_full_code,
            engineering_security_context=args.sec_context,
            step_by_step=args.step_by_step,
            compact=args.compact,
        ),
        language=args.lang,
        extra_constraints=args.constraint,
    )
    result = compile_prompt(spec)

    print(f"=== PromptForge ({result.detected_domain.value} | ~{result.estimated_tokens} tokens | {result.export_filename}) ===\n")
    print(result.text)
    print("\n--- Инструкция ---")
    print(result.install_guide)

    if result.lint_issues:
        print("\n--- Линтер ---")
        for issue in result.lint_issues:
            print(f"[{issue.level.upper()}] {issue.message} -> {issue.suggestion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
