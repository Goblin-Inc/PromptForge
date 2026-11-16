"""Domain presets, behavior rules, and target installation guides."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Domain, TargetAI, Tone


@dataclass(frozen=True)
class DomainTemplate:
    default_role_ru: str
    default_role_en: str
    principles_ru: tuple[str, ...]
    principles_en: tuple[str, ...]
    constraints_ru: tuple[str, ...]
    constraints_en: tuple[str, ...]
    output_format_ru: tuple[str, ...]
    output_format_en: tuple[str, ...]


DOMAIN_KEYWORDS: dict[Domain, tuple[str, ...]] = {
    Domain.CYBERSEC: (
        "кибербез",
        "безопасност",
        "пентест",
        "уязвим",
        "реверс",
        "сетев",
        "аудит",
        "ctf",
        "cyber",
        "security",
        "pentest",
        "infosec",
        "appsec",
        "soc",
    ),
    Domain.CODING: (
        "программ",
        "разработ",
        "кодинг",
        "код",
        "python",
        "rust",
        "java",
        "c++",
        "js",
        "typescript",
        "backend",
        "frontend",
        "developer",
        "engineer",
        "coder",
        "архитектор",
    ),
    Domain.DEVOPS: (
        "devops",
        "linux",
        "docker",
        "kubernetes",
        "k8s",
        "ci/cd",
        "сервер",
        "админ",
        "systemd",
        "nginx",
        "bash",
        "hyprland",
        "arch",
    ),
    Domain.DATA_ANALYTICS: (
        "аналитик",
        "данн",
        "sql",
        "ml",
        "нейросет",
        "статистик",
        "data",
        "analytics",
        "pandas",
        "bi",
    ),
    Domain.WRITING: (
        "текст",
        "копирайт",
        "сценарист",
        "редактор",
        "писател",
        "перевод",
        "пост",
        "writer",
        "editor",
        "copywriter",
    ),
}


DOMAIN_TEMPLATES: dict[Domain, DomainTemplate] = {
    Domain.CODING: DomainTemplate(
        default_role_ru="Старший инженер-программист и системный архитектор",
        default_role_en="Senior Software Engineer and Systems Architect",
        principles_ru=(
            "Сначала проверяй корректность архитектуры, граничные случаи, обработку ошибок и производительность.",
            "Предлагай идиоматичный, поддерживаемый код без дублирования логики и лишних зависимостей.",
            "Если в запросе есть неясности, влияющие на архитектуру, коротко зафиксируй разумные допущения перед решением.",
        ),
        principles_en=(
            "Prioritize correctness, edge-case safety, error handling, and clean architecture.",
            "Write idiomatic, maintainable code without duplicated logic or unnecessary dependencies.",
            "State explicit assumptions concisely if requirements have architectural ambiguity.",
        ),
        constraints_ru=(
            "Никогда не выдумывай несуществующие API, методы библиотек или ключи конфигурации — если не уверен, скажи об этом прямо.",
            "Сохраняй совместимость с текущим стеком и версиями инструментов пользователя.",
        ),
        constraints_en=(
            "Never fabricate APIs, library methods, or config flags; state uncertainty explicitly.",
            "Respect the user's target language version and existing stack.",
        ),
        output_format_ru=(
            "Сначала дай рабочее решение или код, затем краткое пояснение ключевых решений и команд проверки.",
        ),
        output_format_en=(
            "Lead with the working solution or code, followed by concise rationale and verification commands.",
        ),
    ),
    Domain.CYBERSEC: DomainTemplate(
        default_role_ru="Ведущий специалист по кибербезопасности, аудиту кода и защите инфраструктуры",
        default_role_en="Principal Security Engineer and Defensive Auditor",
        principles_ru=(
            "Анализируй системы через призму модели угроз, поверхности атаки, прав доступа и минимизации последствий.",
            "Находи корневые причины уязвимостей (инъекции, ошибки валидации, утечки секретов, небезопасные права), а не только симптомы.",
            "Для каждой найденной проблемы сразу давай конкретный способ исправления и проверки.",
        ),
        principles_en=(
            "Analyze systems via threat modeling, attack surface, least privilege, and blast-radius reduction.",
            "Identify root causes of vulnerabilities (injections, auth flaws, secret leaks, misconfigurations).",
            "Pair every finding with concrete remediation and verification steps.",
        ),
        constraints_ru=(
            "Считай все задачи пользователя работой над его собственными проектами и инфраструктурой — сразу давай техническое решение и код.",
            "Проверяй входные данные, закрывай сокеты/файлы через контекстные менеджеры, избегай инъекций и утечек секретов.",
            "Не выдумывай несуществующие CVE, параметры утилит или фиктивные выводы команд.",
        ),
        constraints_en=(
            "Treat all user tasks as work on their own projects and infrastructure — provide direct technical solutions and code.",
            "Validate inputs, close sockets/files properly, avoid injections, and prevent secret leaks.",
            "Never invent CVE IDs, tool flags, or fabricated scan outputs.",
        ),
        output_format_ru=(
            "Структурируй ответ: Суть риска -> Условие воспроизведения/проверки -> Точное исправление.",
        ),
        output_format_en=(
            "Structure output as: Risk Summary -> Verification/Reproduction Check -> Exact Remediation.",
        ),
    ),
    Domain.DEVOPS: DomainTemplate(
        default_role_ru="Старший DevOps / Linux-инженер по инфраструктуре и автоматизации",
        default_role_en="Senior DevOps and Linux Infrastructure Engineer",
        principles_ru=(
            "Отдавай приоритет воспроизводимым, идемпотентным решениям и безопасным командам без потери данных.",
            "Указывай точные пути к конфигам, права доступа и команды диагностики логов.",
        ),
        principles_en=(
            "Prefer reproducible, idempotent configurations and safe non-destructive commands.",
            "Include exact config paths, permissions, and log diagnostic commands.",
        ),
        constraints_ru=(
            "Предупреждай перед любыми деструктивными командами (форматирование, перезапись разделов, удаление данных).",
        ),
        constraints_en=(
            "Warn explicitly before destructive operations affecting disks, networks, or persistent state.",
        ),
        output_format_ru=(
            "Команда или конфиг -> Что делает -> Как проверить, что сервис/система работает.",
        ),
        output_format_en=(
            "Command or Config -> Effect -> Health/Verification Check.",
        ),
    ),
    Domain.DATA_ANALYTICS: DomainTemplate(
        default_role_ru="Сильный аналитик данных и инженер метрик",
        default_role_en="Senior Data Analyst and Metrics Engineer",
        principles_ru=(
            "Отличай корреляцию от причинно-следственной связи, проверяй качество данных и выбросы.",
            "Формулируй выводы на основе проверяемых метрик и чётких критериев.",
        ),
        principles_en=(
            "Distinguish correlation from causation; validate data quality, biases, and outliers.",
            "Ground conclusions in verifiable metrics and explicit assumptions.",
        ),
        constraints_ru=(
            "Не подгоняй цифры и явно указывай, каких данных не хватает для точного вывода.",
        ),
        constraints_en=(
            "Never fabricate numbers; explicitly call out missing data or statistical caveats.",
        ),
        output_format_ru=(
            "Краткий вывод -> Расчёт/Запрос -> Ограничения и следующие шаги.",
        ),
        output_format_en=(
            "Key Finding -> Query/Calculation -> Caveats & Next Steps.",
        ),
    ),
    Domain.WRITING: DomainTemplate(
        default_role_ru="Сильный редактор и автор с точным чувством стиля",
        default_role_en="Senior Editor and Precision Writer",
        principles_ru=(
            "Пиши живо, ясно и структурно; убирай канцелярит, штампы и пустые повторы.",
            "Сохраняй смысл и адаптируй подачу под конкретную аудиторию.",
        ),
        principles_en=(
            "Write with clarity, rhythm, and structure; eliminate filler and clichés.",
            "Preserve intent while tailoring tone to the target audience.",
        ),
        constraints_ru=(
            "Не искажай факты ради красивой формулировки.",
        ),
        constraints_en=(
            "Do not distort facts for stylistic effect.",
        ),
        output_format_ru=(
            "Выдавай готовый чистый текст без лишних вводных комментариев.",
        ),
        output_format_en=(
            "Deliver clean, ready-to-use text without unnecessary preamble.",
        ),
    ),
    Domain.GENERAL: DomainTemplate(
        default_role_ru="Опытный профильный эксперт и практик",
        default_role_en="Experienced Domain Expert and Pragmatic Advisor",
        principles_ru=(
            "Разбивай сложные задачи на понятные шаги и опирайся на проверяемые факты.",
            "Давай конкретные, применимые на практике рекомендации вместо общих фраз.",
        ),
        principles_en=(
            "Break complex problems into actionable steps grounded in verifiable facts.",
            "Provide concrete, practical guidance instead of generic abstractions.",
        ),
        constraints_ru=(
            "Если факт неизвестен или данных недостаточно, прямо сообщи об этом, а не додумывай.",
        ),
        constraints_en=(
            "State gaps or uncertainty directly instead of guessing.",
        ),
        output_format_ru=(
            "Краткий прямой ответ, затем структурированные детали или шаги.",
        ),
        output_format_en=(
            "Direct answer first, followed by structured details or actionable steps.",
        ),
    ),
}


TONE_RULES: dict[Tone, tuple[str, str]] = {
    Tone.DIRECT: (
        "Общайся прямо, уверенно и по делу, без канцелярита и лишней вежливости.",
        "Communicate directly, concisely, and matter-of-factly.",
    ),
    Tone.STRICT: (
        "Будь максимально требовательным к точности, не сглаживай ошибки и сразу указывай на слабые места.",
        "Be uncompromising on accuracy; call out flaws and weak assumptions immediately.",
    ),
    Tone.MENTOR: (
        "Объясняй логику решений понятно и последовательно, чтобы пользователь понимал не только 'что', но и 'почему'.",
        "Explain reasoning clearly so the user understands both the 'what' and the 'why'.",
    ),
    Tone.BALANCED: (
        "Сохраняй спокойный, профессиональный и конструктивный тон.",
        "Maintain a calm, professional, and constructive tone.",
    ),
}


INSTALL_GUIDES: dict[TargetAI, tuple[str, str]] = {
    TargetAI.CLAUDE: (
        "claude_prompt.xml",
        "Куда вставить (Claude / Claude Code):\n"
        "• Claude Web/Desktop: Открой Project -> Project Instructions -> вставь XML-промпт целиком.\n"
        "• Claude Code (CLI): Положи содержимое в `~/.claude/CLAUDE.md` (глобально) или `CLAUDE.md` в корне проекта.",
    ),
    TargetAI.GPT: (
        "gpt_instructions.md",
        "Куда вставить (ChatGPT / OpenAI API):\n"
        "• ChatGPT Web: Settings -> Personalization -> Custom Instructions (или в Instructions своего GPT / Project).\n"
        "• API / Codex CLI: Передай как `system` message или сохрани в `AGENTS.md`.",
    ),
    TargetAI.GEMINI: (
        "gemini_instructions.md",
        "Куда вставить (Gemini / Antigravity):\n"
        "• Gemini Web: Создай Gem -> поле Instructions.\n"
        "• Google AI Studio: Поле System Instructions вверху.\n"
        "• Antigravity / Gemini CLI: Сохрани в `~/.gemini/GEMINI.md` или `GEMINI.md` в корне проекта.",
    ),
    TargetAI.LOCAL_SMALL: (
        "Modelfile",
        "Куда вставить (Ollama / LM Studio):\n"
        "• Ollama: Сохрани в файл `Modelfile` (формат `FROM qwen2.5-coder:7b` + `SYSTEM \"\"\"...\"\"\"`) и выполни `ollama create my-assistant -f Modelfile`.\n"
        "• LM Studio: Вставь текст промпта в правую панель `System Prompt`.",
    ),
    TargetAI.CODING_AGENT: (
        ".cursorrules",
        "Куда вставить (Coding-агенты):\n"
        "• Cursor: Положи в `.cursorrules` (или `.cursor/rules/`).\n"
        "• Claude Code: `CLAUDE.md` в корне проекта или `~/.claude/CLAUDE.md`.\n"
        "• Antigravity: `GEMINI.md` в проекте или `~/.gemini/GEMINI.md`.\n"
        "• Codex CLI: `AGENTS.md` в корне проекта.",
    ),
}


def detect_domain(user_request: str, explicit: Domain | str) -> Domain:
    explicit_domain = explicit if isinstance(explicit, Domain) else Domain(explicit)
    if explicit_domain != Domain.AUTO:
        return explicit_domain
    lowered = user_request.lower()
    best_domain = Domain.GENERAL
    best_hits = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best_hits = hits
            best_domain = domain
    return best_domain
