"""PySide6 desktop GUI for PromptForge (Stage 2)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .compiler import compile_prompt
from .deployer import (
    AgentTarget,
    DeployResult,
    create_ollama_assistant,
    deploy_to_agent_file,
    detect_environment,
    install_ollama_linux,
    is_ollama_running,
    pull_ollama_model,
    resolve_agent_path,
    start_ollama_daemon,
)
from .models import BehaviorFlags, Domain, PromptSpec, TargetAI, Tone
from .sandbox import ChatResult, LLMProvider, SandboxConfig, fetch_models, run_ab_test, run_chat

QUICK_PRESETS: dict[str, tuple[str, TargetAI, bool]] = {
    "Senior C++ / Rust": ("Очень опытный системный программист C++ и Rust", TargetAI.CODING_AGENT, False),
    "Кибербез / Аудит": ("Специалист по кибербезопасности, аудиту кода и защите серверов", TargetAI.CLAUDE, True),
    "Linux / DevOps": ("Старший Linux и DevOps инженер по Arch, Docker и автоматизации", TargetAI.GPT, False),
    "Локалка 7B (Кодер)": ("Опытный программист Python и bash без лишних объяснений", TargetAI.LOCAL_SMALL, False),
}

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #14161b;
    color: #e6e8ee;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}
QLabel, QCheckBox {
    background-color: transparent;
}
QScrollArea, QScrollArea QWidget#LintContainer, QWidget#TransparentBox {
    background-color: transparent;
}
QFrame#Panel {
    background-color: #1b1e25;
    border: 1px solid #2b303b;
    border-radius: 10px;
}
QLabel#HeaderTitle {
    font-size: 18px;
    font-weight: 700;
    color: #f3f4f6;
}
QLabel#SectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #9aa4b2;
    text-transform: uppercase;
}
QLabel#Badge {
    background-color: #252a34;
    border: 1px solid #353c4a;
    border-radius: 6px;
    padding: 4px 10px;
    color: #d6dce6;
    font-weight: 600;
}
QPlainTextEdit, QComboBox, QLineEdit {
    background-color: #111318;
    border: 1px solid #2f3542;
    border-radius: 8px;
    padding: 8px;
    color: #f0f2f7;
    selection-background-color: #d97706;
}
QPlainTextEdit:focus, QComboBox:focus, QLineEdit:focus {
    border: 1px solid #f59e0b;
}
QPushButton {
    background-color: #272c37;
    border: 1px solid #3a4252;
    border-radius: 8px;
    padding: 7px 14px;
    color: #eef1f6;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #323947;
    border-color: #f59e0b;
}
QPushButton#PrimaryBtn {
    background-color: #d97706;
    border: 1px solid #f59e0b;
    color: #111318;
}
QPushButton#PrimaryBtn:hover {
    background-color: #f59e0b;
}
QCheckBox {
    spacing: 8px;
    padding: 2px 0;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #495366;
    background-color: #111318;
}
QCheckBox::indicator:checked {
    background-color: #f59e0b;
    border-color: #f59e0b;
}
QTabWidget::pane {
    border: 1px solid #2b303b;
    border-radius: 8px;
    background-color: #161920;
    padding: 6px;
}
QTabBar::tab {
    background-color: #1e222b;
    border: 1px solid #2b303b;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 10px;
    margin-right: 4px;
    color: #9aa4b2;
}
QTabBar::tab:selected {
    background-color: #161920;
    color: #f59e0b;
    font-weight: 700;
}
"""


def _ensure_local_ollama(config: SandboxConfig) -> None:
    if config.provider != LLMProvider.OLLAMA:
        return
    url = config.base_url.lower()
    if "localhost" not in url and "127.0.0.1" not in url:
        return
    if not is_ollama_running(config.base_url):
        start_ollama_daemon(lambda _msg: None)


class _ModelsWorker(QThread):
    finished_models = Signal(list, str)

    def __init__(self, config: SandboxConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            _ensure_local_ollama(self.config)
            models = fetch_models(self.config)
            self.finished_models.emit(models, "")
        except Exception as exc:
            self.finished_models.emit([], str(exc))


class _SandboxWorker(QThread):
    chunk_base = Signal(str)
    chunk_prompted = Signal(str)
    finished_run = Signal(object, object)

    def __init__(self, config: SandboxConfig, system_prompt: str, user_msg: str, ab_mode: bool) -> None:
        super().__init__()
        self.config = config
        self.system_prompt = system_prompt
        self.user_msg = user_msg
        self.ab_mode = ab_mode

    def run(self) -> None:
        _ensure_local_ollama(self.config)
        if self.ab_mode:
            base_res, prompted_res = run_ab_test(
                self.config,
                self.system_prompt,
                self.user_msg,
                on_base_chunk=self.chunk_base.emit,
                on_prompted_chunk=self.chunk_prompted.emit,
            )
            self.finished_run.emit(base_res, prompted_res)
        else:
            prompted_res = run_chat(
                self.config,
                self.system_prompt,
                self.user_msg,
                on_chunk=self.chunk_prompted.emit,
            )
            self.finished_run.emit(None, prompted_res)


class _DeployTaskWorker(QThread):
    log_line = Signal(str)
    finished_task = Signal(bool, str)

    def __init__(self, fn) -> None:
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            ok, msg = self.fn(self.log_line.emit)
            self.finished_task.emit(ok, msg)
        except Exception as exc:
            self.finished_task.emit(False, str(exc))


class PromptForgeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PromptForge — System Prompt Studio")
        self.resize(1180, 760)
        self._last_export_name = "gpt_instructions.md"
        self._build_ui()
        self.refresh_prompt()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("PromptForge")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Генератор, адаптер и линтер системных промптов")
        subtitle.setStyleSheet("color: #9aa4b2; margin-left: 8px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch()
        main_layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # Left builder panel
        left_panel = QFrame()
        left_panel.setObjectName("Panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        presets_label = QLabel("Быстрые пресеты")
        presets_label.setObjectName("SectionTitle")
        left_layout.addWidget(presets_label)

        presets_grid = QGridLayout()
        presets_grid.setSpacing(6)
        for idx, label in enumerate(QUICK_PRESETS):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, name=label: self._apply_preset(name))
            presets_grid.addWidget(btn, idx // 2, idx % 2)
        left_layout.addLayout(presets_grid)

        req_label = QLabel("Идея / Роль (1–3 предложения)")
        req_label.setObjectName("SectionTitle")
        left_layout.addWidget(req_label)

        self.request_input = QPlainTextEdit()
        self.request_input.setPlaceholderText(
            "Например: Очень опытный программист C++ и Linux, который пишет чистый код без воды..."
        )
        self.request_input.setPlainText("Очень опытный программист Python и Linux с фокусом на чистую архитектуру")
        self.request_input.setFixedHeight(92)
        self.request_input.textChanged.connect(self.refresh_prompt)
        left_layout.addWidget(self.request_input)

        # Target, Domain, Tone, Language
        grid_row1 = QHBoxLayout()
        self.target_combo = self._make_combo(
            [
                ("GPT / OpenAI", TargetAI.GPT),
                ("Claude (XML)", TargetAI.CLAUDE),
                ("Gemini / Antigravity", TargetAI.GEMINI),
                ("Local LLM (7B–14B)", TargetAI.LOCAL_SMALL),
                ("Coding Agent (.cursorrules/CLAUDE.md)", TargetAI.CODING_AGENT),
            ]
        )
        self.domain_combo = self._make_combo(
            [
                ("Автоопределение", Domain.AUTO),
                ("Программирование", Domain.CODING),
                ("Кибербезопасность", Domain.CYBERSEC),
                ("DevOps / Linux", Domain.DEVOPS),
                ("Аналитика данных", Domain.DATA_ANALYTICS),
                ("Тексты / Редактура", Domain.WRITING),
                ("Общая область", Domain.GENERAL),
            ]
        )
        grid_row1.addWidget(self._labeled_widget("Целевой ИИ", self.target_combo))
        grid_row1.addWidget(self._labeled_widget("Область", self.domain_combo))
        left_layout.addLayout(grid_row1)

        grid_row2 = QHBoxLayout()
        self.tone_combo = self._make_combo(
            [
                ("Прямой (Direct)", Tone.DIRECT),
                ("Жёсткий (Strict)", Tone.STRICT),
                ("Наставник (Mentor)", Tone.MENTOR),
                ("Сбалансированный", Tone.BALANCED),
            ]
        )
        self.lang_combo = self._make_combo([("Русский (RU)", "ru"), ("English (EN)", "en")])
        grid_row2.addWidget(self._labeled_widget("Тон общения", self.tone_combo))
        grid_row2.addWidget(self._labeled_widget("Язык промпта", self.lang_combo))
        left_layout.addLayout(grid_row2)

        flags_label = QLabel("Модули поведения")
        flags_label.setObjectName("SectionTitle")
        left_layout.addWidget(flags_label)

        self.chk_direct = QCheckBox("Direct Mode — без воды, извинений и морализаторства")
        self.chk_direct.setChecked(True)
        self.chk_full_code = QCheckBox("Full Code — полный рабочий код без заглушек")
        self.chk_full_code.setChecked(True)
        self.chk_sec = QCheckBox("Инженерный / учебный контекст (для аудита и защиты)")
        self.chk_step = QCheckBox("Step-by-step проверка крайних случаев")
        self.chk_compact = QCheckBox("Compact — сжать под локальные 7B–14B модели")

        for chk in (self.chk_direct, self.chk_full_code, self.chk_sec, self.chk_step, self.chk_compact):
            chk.stateChanged.connect(self.refresh_prompt)
            left_layout.addWidget(chk)

        extra_label = QLabel("Свои правила (по одному на строку)")
        extra_label.setObjectName("SectionTitle")
        left_layout.addWidget(extra_label)

        self.extra_input = QPlainTextEdit()
        self.extra_input.setPlaceholderText("Например:\nВсегда пиши юнит-тесты.\nНе используй устаревшие библиотеки.")
        self.extra_input.setFixedHeight(78)
        self.extra_input.textChanged.connect(self.refresh_prompt)
        left_layout.addWidget(self.extra_input)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # Right output panel
        right_panel = QFrame()
        right_panel.setObjectName("Panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        # Status badges + action buttons (2 compact rows so narrow tiling never clips text)
        badges_bar = QHBoxLayout()
        badges_bar.setSpacing(6)
        self.badge_domain = QLabel("Домен: —")
        self.badge_domain.setObjectName("Badge")
        self.badge_tokens = QLabel("~0 tokens")
        self.badge_tokens.setObjectName("Badge")
        self.badge_file = QLabel("file")
        self.badge_file.setObjectName("Badge")

        badges_bar.addWidget(self.badge_domain)
        badges_bar.addWidget(self.badge_tokens)
        badges_bar.addWidget(self.badge_file)
        badges_bar.addStretch()
        right_layout.addLayout(badges_bar)

        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(8)
        self.btn_copy = QPushButton("Копировать промпт")
        self.btn_copy.setObjectName("PrimaryBtn")
        self.btn_copy.clicked.connect(self._copy_prompt)

        self.btn_save = QPushButton("Сохранить файл...")
        self.btn_save.clicked.connect(self._save_prompt)

        actions_bar.addWidget(self.btn_copy)
        actions_bar.addWidget(self.btn_save)
        actions_bar.addStretch()
        right_layout.addLayout(actions_bar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(False)
        self.output_edit = QPlainTextEdit()
        mono = QFont("JetBrains Mono", 11)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.output_edit.setFont(mono)

        self.guide_view = QPlainTextEdit()
        self.guide_view.setReadOnly(True)

        self.sandbox_tab = self._build_sandbox_tab()
        self.deploy_tab = self._build_deploy_tab()

        self.tabs.addTab(self.output_edit, "Промпт")
        self.tabs.addTab(self.guide_view, "Куда вставить")
        self.tabs.addTab(self.sandbox_tab, "Песочница A/B")
        self.tabs.addTab(self.deploy_tab, "Auto-Deploy")
        right_layout.addWidget(self.tabs, stretch=1)

        # Linter area
        lint_title = QLabel("Линтер совместимости")
        lint_title.setObjectName("SectionTitle")
        right_layout.addWidget(lint_title)

        self.lint_scroll = QScrollArea()
        self.lint_scroll.setWidgetResizable(True)
        self.lint_scroll.setFixedHeight(130)
        self.lint_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.lint_container = QWidget()
        self.lint_container.setObjectName("LintContainer")
        self.lint_layout = QVBoxLayout(self.lint_container)
        self.lint_layout.setContentsMargins(0, 0, 0, 0)
        self.lint_layout.setSpacing(6)
        self.lint_scroll.setWidget(self.lint_container)
        right_layout.addWidget(self.lint_scroll)

        splitter.addWidget(right_panel)
        splitter.setSizes([440, 720])

    def _make_combo(self, items: list[tuple[str, object]]) -> QComboBox:
        combo = QComboBox()
        for label, value in items:
            combo.addItem(label, value)
        combo.currentIndexChanged.connect(self.refresh_prompt)
        return combo

    @staticmethod
    def _labeled_widget(label_text: str, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl)
        layout.addWidget(widget)
        return wrapper

    def _apply_preset(self, name: str) -> None:
        text, target, sec = QUICK_PRESETS[name]
        self.request_input.setPlainText(text)
        idx = self.target_combo.findData(target.value)
        if idx < 0:
            idx = self.target_combo.findData(target)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        self.chk_sec.setChecked(sec)
        self.chk_compact.setChecked(target == TargetAI.LOCAL_SMALL)

    def refresh_prompt(self) -> None:
        extra = [line.strip() for line in self.extra_input.toPlainText().splitlines() if line.strip()]
        spec = PromptSpec(
            user_request=self.request_input.toPlainText(),
            target=TargetAI(self.target_combo.currentData()),
            domain=Domain(self.domain_combo.currentData()),
            tone=Tone(self.tone_combo.currentData()),
            flags=BehaviorFlags(
                direct_mode=self.chk_direct.isChecked(),
                full_code=self.chk_full_code.isChecked(),
                engineering_security_context=self.chk_sec.isChecked(),
                step_by_step=self.chk_step.isChecked(),
                compact=self.chk_compact.isChecked(),
            ),
            language=self.lang_combo.currentData(),
            extra_constraints=extra,
        )
        result = compile_prompt(spec)
        self._last_export_name = result.export_filename

        self.output_edit.setPlainText(result.text)
        self.guide_view.setPlainText(result.install_guide)
        self.badge_domain.setText(f"Домен: {result.detected_domain.value}")
        self.badge_tokens.setText(f"~{result.estimated_tokens} tokens")
        self.badge_file.setText(result.export_filename)

        self._render_lint_issues(result.lint_issues)

    def _render_lint_issues(self, issues: list) -> None:
        while self.lint_layout.count():
            item = self.lint_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not issues:
            ok_lbl = QLabel("✔ Промпт чист и хорошо подходит для выбранной цели.")
            ok_lbl.setStyleSheet(
                "background-color: #16291e; border: 1px solid #245c3a; "
                "border-radius: 6px; padding: 8px; color: #7ee787;"
            )
            self.lint_layout.addWidget(ok_lbl)
        else:
            for issue in issues:
                is_warn = issue.level == "warning"
                bg = "#2b2113" if is_warn else "#162233"
                border = "#7c5216" if is_warn else "#284c7a"
                fg = "#fbbf24" if is_warn else "#79c0ff"
                prefix = "⚠" if is_warn else "ℹ"
                card = QLabel(f"{prefix} {issue.message}\n   Совет: {issue.suggestion}")
                card.setWordWrap(True)
                card.setStyleSheet(
                    f"background-color: {bg}; border: 1px solid {border}; "
                    f"border-radius: 6px; padding: 8px; color: {fg};"
                )
                self.lint_layout.addWidget(card)

        self.lint_layout.addStretch()

    def _copy_prompt(self) -> None:
        QApplication.clipboard().setText(self.output_edit.toPlainText())
        self.btn_copy.setText("Скопировано ✔")
        QApplication.processEvents()

    def _save_prompt(self) -> None:
        default_path = str(Path.home() / self._last_export_name)
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить системный промпт", default_path)
        if not file_path:
            return
        content = self.output_edit.toPlainText()
        if Path(file_path).name == "Modelfile":
            escaped = content.replace('"""', '\\"\\"\\"')
            content = f'FROM qwen2.5-coder:7b\n\nSYSTEM """\n{escaped}\n"""\n'
        Path(file_path).write_text(content, encoding="utf-8")
        QMessageBox.information(self, "PromptForge", f"Сохранено: {file_path}")

    def _build_sandbox_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("TransparentBox")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        cfg_grid = QGridLayout()
        cfg_grid.setSpacing(6)

        self.sb_provider = QComboBox()
        self.sb_provider.addItem("Ollama (localhost:11434)", LLMProvider.OLLAMA.value)
        self.sb_provider.addItem("OpenAI-compatible (LM Studio / API)", LLMProvider.OPENAI_COMPAT.value)
        self.sb_provider.currentIndexChanged.connect(self._on_provider_changed)

        self.sb_url = QLineEdit("http://localhost:11434")
        self.sb_url.setPlaceholderText("http://localhost:11434")

        self.sb_model = QComboBox()
        self.sb_model.setEditable(True)
        self.sb_model.addItems(["qwen2.5-coder:7b", "llama3.1:8b", "mistral:7b"])

        self.sb_key = QLineEdit()
        self.sb_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.sb_key.setPlaceholderText("API Key (не нужен для локалки)")

        self.btn_models = QPushButton("Обновить модели")
        self.btn_models.clicked.connect(self._refresh_models)

        cfg_grid.addWidget(self._labeled_widget("Провайдер", self.sb_provider), 0, 0)
        cfg_grid.addWidget(self._labeled_widget("URL сервера", self.sb_url), 0, 1)
        cfg_grid.addWidget(self._labeled_widget("Модель", self.sb_model), 1, 0)
        cfg_grid.addWidget(self._labeled_widget("API Key", self.sb_key), 1, 1)
        layout.addLayout(cfg_grid)

        btn_row = QHBoxLayout()
        self.sb_status = QLabel("Готов к тесту (выбери модель или нажми «Обновить модели»)")
        self.sb_status.setStyleSheet("color: #9aa4b2;")
        btn_row.addWidget(self.btn_models)
        btn_row.addWidget(self.sb_status, stretch=1)
        layout.addLayout(btn_row)

        self.sb_prompt_input = QPlainTextEdit()
        self.sb_prompt_input.setFixedHeight(64)
        self.sb_prompt_input.setPlainText(
            "Напиши функцию на Python для безопасной проверки пароля и коротко укажи, что улучшить."
        )
        layout.addWidget(self.sb_prompt_input)

        run_row = QHBoxLayout()
        self.btn_run_ab = QPushButton("Запустить A/B тест (До / После)")
        self.btn_run_ab.setObjectName("PrimaryBtn")
        self.btn_run_ab.clicked.connect(lambda: self._run_sandbox(ab_mode=True))

        self.btn_run_single = QPushButton("Только с промптом")
        self.btn_run_single.clicked.connect(lambda: self._run_sandbox(ab_mode=False))

        run_row.addWidget(self.btn_run_ab)
        run_row.addWidget(self.btn_run_single)
        run_row.addStretch()
        layout.addLayout(run_row)

        ab_split = QSplitter(Qt.Orientation.Horizontal)
        self.sb_out_base = QPlainTextEdit()
        self.sb_out_base.setReadOnly(True)
        self.sb_out_base.setPlaceholderText("Ответ A: Базовая модель (без системного промпта)")

        self.sb_out_prompted = QPlainTextEdit()
        self.sb_out_prompted.setReadOnly(True)
        self.sb_out_prompted.setPlaceholderText("Ответ B: С твоим системным промптом PromptForge")

        self.lbl_base = QLabel("A: Без систем-промпта")
        self.lbl_base.setObjectName("SectionTitle")
        self.lbl_prompted = QLabel("B: С твоим промптом")
        self.lbl_prompted.setObjectName("SectionTitle")

        left_box = QWidget()
        left_box.setObjectName("TransparentBox")
        lb_l = QVBoxLayout(left_box)
        lb_l.setContentsMargins(0, 0, 0, 0)
        lb_l.addWidget(self.lbl_base)
        lb_l.addWidget(self.sb_out_base)

        right_box = QWidget()
        right_box.setObjectName("TransparentBox")
        rb_l = QVBoxLayout(right_box)
        rb_l.setContentsMargins(0, 0, 0, 0)
        rb_l.addWidget(self.lbl_prompted)
        rb_l.addWidget(self.sb_out_prompted)

        ab_split.addWidget(left_box)
        ab_split.addWidget(right_box)
        layout.addWidget(ab_split, stretch=1)
        return tab

    def _current_sandbox_config(self) -> SandboxConfig:
        return SandboxConfig(
            provider=LLMProvider(self.sb_provider.currentData()),
            base_url=self.sb_url.text().strip() or "http://localhost:11434",
            model=self.sb_model.currentText().strip(),
            api_key=self.sb_key.text().strip(),
        )

    def _on_provider_changed(self) -> None:
        prov = LLMProvider(self.sb_provider.currentData())
        cur = self.sb_url.text().strip()
        if prov == LLMProvider.OLLAMA and cur in ("", "http://localhost:1234/v1"):
            self.sb_url.setText("http://localhost:11434")
        elif prov == LLMProvider.OPENAI_COMPAT and cur in ("", "http://localhost:11434"):
            self.sb_url.setText("http://localhost:1234/v1")

    def _refresh_models(self) -> None:
        self.btn_models.setEnabled(False)
        self.sb_status.setText("Запрашиваю список моделей...")
        self._models_worker = _ModelsWorker(self._current_sandbox_config())
        self._models_worker.finished_models.connect(self._on_models_loaded)
        self._models_worker.start()

    def _on_models_loaded(self, models: list[str], error: str) -> None:
        self.btn_models.setEnabled(True)
        if error:
            self.sb_status.setText(f"Не удалось подключиться: {error}")
            return
        if not models:
            self.sb_status.setText("Сервер ответил, но моделей не найдено.")
            return
        current = self.sb_model.currentText()
        self.sb_model.clear()
        self.sb_model.addItems(models)
        if current in models:
            self.sb_model.setCurrentText(current)
        self.sb_status.setText(f"Загружено моделей: {len(models)}")

    def _run_sandbox(self, ab_mode: bool) -> None:
        user_msg = self.sb_prompt_input.toPlainText().strip()
        if not user_msg:
            self.sb_status.setText("Введи тестовый запрос.")
            return
        cfg = self._current_sandbox_config()
        if not cfg.model:
            self.sb_status.setText("Укажи модель.")
            return

        self.btn_run_ab.setEnabled(False)
        self.btn_run_single.setEnabled(False)
        self.sb_status.setText("Генерация ответа (стриминг)...")
        self._base_started = False
        self._prompted_started = False
        if ab_mode:
            self.sb_out_base.setPlainText("Ожидание ответа...")
        else:
            self.sb_out_base.setPlainText("(пропущено — режим только с промптом)")
        self.sb_out_prompted.setPlainText("Ожидание ответа...")

        self._sb_worker = _SandboxWorker(cfg, self.output_edit.toPlainText(), user_msg, ab_mode)
        self._sb_worker.chunk_base.connect(self._on_base_chunk)
        self._sb_worker.chunk_prompted.connect(self._on_prompted_chunk)
        self._sb_worker.finished_run.connect(self._on_sandbox_done)
        self._sb_worker.start()

    def _on_base_chunk(self, delta: str) -> None:
        if not self._base_started:
            self.sb_out_base.clear()
            self._base_started = True
        cursor = self.sb_out_base.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(delta)

    def _on_prompted_chunk(self, delta: str) -> None:
        if not self._prompted_started:
            self.sb_out_prompted.clear()
            self._prompted_started = True
        cursor = self.sb_out_prompted.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(delta)

    def _on_sandbox_done(self, base_res: ChatResult | None, prompted_res: ChatResult) -> None:
        self.btn_run_ab.setEnabled(True)
        self.btn_run_single.setEnabled(True)

        if base_res is not None:
            self.lbl_base.setText(f"A: Без систем-промпта ({base_res.elapsed_sec:.1f}s)")
            self.sb_out_base.setPlainText(base_res.content if base_res.ok else base_res.error)
        else:
            self.lbl_base.setText("A: Без систем-промпта")

        self.lbl_prompted.setText(f"B: С твоим промптом ({prompted_res.elapsed_sec:.1f}s)")
        self.sb_out_prompted.setPlainText(prompted_res.content if prompted_res.ok else prompted_res.error)
        self.sb_status.setText("Готово" if prompted_res.ok else "Ошибка подключения к модели")

    def _build_deploy_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("TransparentBox")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Environment status header
        env_row = QHBoxLayout()
        self.dep_env_label = QLabel("Среда: нажмите «Проверить среду»")
        self.dep_env_label.setWordWrap(True)
        self.btn_env_check = QPushButton("Проверить среду")
        self.btn_env_check.clicked.connect(self._refresh_env_status)
        env_row.addWidget(self.dep_env_label, stretch=1)
        env_row.addWidget(self.btn_env_check)
        layout.addLayout(env_row)

        # Ollama section
        ollama_title = QLabel("Локальная нейросеть (Ollama)")
        ollama_title.setObjectName("SectionTitle")
        layout.addWidget(ollama_title)

        ollama_grid = QGridLayout()
        ollama_grid.setSpacing(6)
        self.dep_base_model = QComboBox()
        self.dep_base_model.setEditable(True)
        self.dep_base_model.addItems(["qwen2.5-coder:3b", "qwen2.5-coder:7b", "llama3.1:8b", "mistral:7b"])

        self.dep_assistant_name = QLineEdit("promptforge-expert")
        self.dep_assistant_name.setPlaceholderText("Имя создаваемого ассистента")

        ollama_grid.addWidget(self._labeled_widget("Базовая модель", self.dep_base_model), 0, 0)
        ollama_grid.addWidget(self._labeled_widget("Имя ассистента в Ollama", self.dep_assistant_name), 0, 1)
        layout.addLayout(ollama_grid)

        ollama_btns = QGridLayout()
        ollama_btns.setSpacing(6)
        self.btn_install_ollama = QPushButton("1. Установить / Запустить Ollama")
        self.btn_install_ollama.clicked.connect(self._install_ollama)
        self.btn_pull_model = QPushButton("2. Скачать модель (pull)")
        self.btn_pull_model.clicked.connect(self._pull_model)
        self.btn_create_ollama = QPushButton("3. Создать ассистента в Ollama")
        self.btn_create_ollama.setObjectName("PrimaryBtn")
        self.btn_create_ollama.clicked.connect(self._create_ollama_assistant)
        ollama_btns.addWidget(self.btn_install_ollama, 0, 0)
        ollama_btns.addWidget(self.btn_pull_model, 0, 1)
        ollama_btns.addWidget(self.btn_create_ollama, 1, 0, 1, 2)
        layout.addLayout(ollama_btns)

        # CLI / IDE Agents section
        agent_title = QLabel("CLI и IDE-агенты (с авто-бэкапом .bak)")
        agent_title.setObjectName("SectionTitle")
        layout.addWidget(agent_title)

        agent_grid = QGridLayout()
        agent_grid.setSpacing(6)
        self.dep_agent_target = QComboBox()
        for label, tgt in (
            ("Antigravity Global (~/.gemini/GEMINI.md)", AgentTarget.ANTIGRAVITY_GLOBAL),
            ("Codex CLI Global (~/.codex/AGENTS.md)", AgentTarget.CODEX_GLOBAL),
            ("Claude Code Global (~/.claude/CLAUDE.md)", AgentTarget.CLAUDE_GLOBAL),
            ("Проект: CLAUDE.md", AgentTarget.CLAUDE_PROJECT),
            ("Проект: GEMINI.md", AgentTarget.ANTIGRAVITY_PROJECT),
            ("Проект: AGENTS.md", AgentTarget.CODEX_PROJECT),
            ("Проект: .cursorrules", AgentTarget.CURSOR_PROJECT),
        ):
            self.dep_agent_target.addItem(label, tgt.value)

        self.dep_project_dir = QLineEdit(str(Path.home() / "Work"))
        btn_browse = QPushButton("Папка...")
        btn_browse.clicked.connect(self._browse_project_dir)

        proj_row = QHBoxLayout()
        proj_row.setSpacing(6)
        proj_row.addWidget(self.dep_project_dir, stretch=1)
        proj_row.addWidget(btn_browse)
        proj_wrap = QWidget()
        proj_wrap.setObjectName("TransparentBox")
        proj_wrap.setLayout(proj_row)

        agent_grid.addWidget(self._labeled_widget("Целевой агент", self.dep_agent_target), 0, 0)
        agent_grid.addWidget(self._labeled_widget("Папка проекта", proj_wrap), 0, 1)
        layout.addLayout(agent_grid)

        agent_action_row = QHBoxLayout()
        self.chk_merge_section = QCheckBox("Обновлять только блок PromptForge")
        self.chk_merge_section.setChecked(True)
        self.btn_deploy_agent = QPushButton("Применить к агенту")
        self.btn_deploy_agent.setObjectName("PrimaryBtn")
        self.btn_deploy_agent.clicked.connect(self._deploy_agent)
        agent_action_row.addWidget(self.chk_merge_section, stretch=1)
        agent_action_row.addWidget(self.btn_deploy_agent)
        layout.addLayout(agent_action_row)

        # Log output
        log_title = QLabel("Лог операций")
        log_title.setObjectName("SectionTitle")
        layout.addWidget(log_title)

        self.dep_log = QPlainTextEdit()
        self.dep_log.setReadOnly(True)
        self.dep_log.setPlaceholderText("Здесь появится вывод команд установки, скачивания модели и пути к бэкапам...")
        layout.addWidget(self.dep_log, stretch=1)

        self._refresh_env_status()
        return tab

    def _append_deploy_log(self, line: str) -> None:
        self.dep_log.appendPlainText(line)

    def _refresh_env_status(self) -> None:
        env = detect_environment()
        ollama_state = (
            "запущена" if env.ollama_running else ("установлена (не запущена)" if env.ollama_bin else "не установлена")
        )
        found_clis = [name for name, path in env.installed_clis.items() if path]
        cli_text = ", ".join(found_clis) if found_clis else "не найдены"
        self.dep_env_label.setText(
            f"RAM: {env.ram_gb} GB | Ollama: {ollama_state} | Рек. модель: {env.recommended_model}\n"
            f"Найденные CLI: {cli_text}"
        )
        self.dep_base_model.setCurrentText(env.recommended_model)

    def _browse_project_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Выбери папку проекта", self.dep_project_dir.text())
        if chosen:
            self.dep_project_dir.setText(chosen)

    def _deploy_agent(self) -> None:
        target = AgentTarget(self.dep_agent_target.currentData())
        proj = Path(self.dep_project_dir.text().strip() or str(Path.cwd()))
        dest_preview = resolve_agent_path(target, proj)
        reply = QMessageBox.question(
            self,
            "Подтверждение Auto-Deploy",
            f"Записать текущий системный промпт в:\n{dest_preview}\n\n"
            "(Если файл уже существует, будет создана резервная копия .bak)",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        res: DeployResult = deploy_to_agent_file(
            target=target,
            prompt_text=self.output_edit.toPlainText(),
            project_dir=proj,
            merge_section=self.chk_merge_section.isChecked(),
        )
        self._append_deploy_log(f"✔ {res.message}")
        if res.backup_path:
            self._append_deploy_log(f"  Бэкап: {res.backup_path}")

    def _set_deploy_buttons_enabled(self, enabled: bool) -> None:
        for btn in (self.btn_install_ollama, self.btn_pull_model, self.btn_create_ollama):
            btn.setEnabled(enabled)

    def _run_deploy_worker(self, fn) -> None:
        self._set_deploy_buttons_enabled(False)
        self._deploy_worker = _DeployTaskWorker(fn)
        self._deploy_worker.log_line.connect(self._append_deploy_log)
        self._deploy_worker.finished_task.connect(self._on_deploy_task_done)
        self._deploy_worker.start()

    def _on_deploy_task_done(self, ok: bool, msg: str) -> None:
        self._set_deploy_buttons_enabled(True)
        self._append_deploy_log(("✔ " if ok else "✖ ") + msg)
        self._refresh_env_status()
        if ok:
            self._refresh_models()

    def _install_ollama(self) -> None:
        reply = QMessageBox.question(
            self,
            "Установка / запуск Ollama",
            "Установить (через pacman/инсталлятор, может спросить пароль) и запустить локальный сервер Ollama?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._append_deploy_log("--- Установка / запуск Ollama ---")
        self._run_deploy_worker(lambda log: (install_ollama_linux(log), "Готово"))

    def _pull_model(self) -> None:
        model = self.dep_base_model.currentText().strip()
        if not model:
            return
        self._append_deploy_log(f"--- Скачивание модели {model} ---")
        self._run_deploy_worker(lambda log: (pull_ollama_model(model, log), f"Загрузка {model} завершена"))

    def _create_ollama_assistant(self) -> None:
        base_model = self.dep_base_model.currentText().strip()
        name = self.dep_assistant_name.text().strip()
        prompt_text = self.output_edit.toPlainText()
        self._append_deploy_log(f"--- Создание ассистента {name} на базе {base_model} ---")

        def task(log):
            res = create_ollama_assistant(name, base_model, prompt_text, log)
            return res.ok, res.message

        self._run_deploy_worker(task)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = PromptForgeWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
