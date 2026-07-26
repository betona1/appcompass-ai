"""도메인 진단 화면 (Phase 4).

기획 진단은 "이 기획이 검증 가능한가"를 본다.
이 화면은 "이 콘텐츠 자체가 제대로 됐는가"를 본다.

    examath   : 아이 오답 하나 → 어떤 개념이 빠졌는지
    VibeQuest : 문항 하나 → 정의 암기형인지 실제 상황형인지

양식은 도메인이 정한다. 이 화면은 그 양식을 그리고 결과를 보여줄 뿐이다.
그래서 새 도메인을 추가해도 이 파일은 바뀌지 않는다.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.domains.registry import get_domain
from ...core.enums import Severity
from ..context import ScreenContext
from ..theme import SEVERITY_COLOR, SEVERITY_MARK
from ..widgets import (
    Banner,
    BulletList,
    EmptyState,
    clear_layout,
    h1,
    h2,
    hint,
    labeled_text_area,
    scrollable,
)
from .base import ScreenBase


class ContentScreen(ScreenBase):
    title = "도메인 진단"
    purpose = "기획이 아니라 콘텐츠 자체를 진단합니다. 도메인에 따라 내용이 다릅니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._spec = None
        self._editors: dict[str, QWidget] = {}

        self.empty = EmptyState(
            "이 도메인에는 콘텐츠 진단이 없습니다",
            "프로젝트 도메인을 VibeQuest 또는 examath로 바꾸면 사용할 수 있습니다.",
        )

        self.body = QWidget()
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(18, 16, 18, 16)

        self.head = h1(self.title)
        layout.addWidget(self.head)
        self.desc = hint(self.purpose)
        layout.addWidget(self.desc)

        self.input_box = QGroupBox("입력")
        self.form = QFormLayout(self.input_box)
        layout.addWidget(self.input_box)

        row = QHBoxLayout()
        self.example_button = QPushButton("예시 채우기")
        self.example_button.clicked.connect(self._fill_example)
        self.clear_button = QPushButton("비우기")
        self.clear_button.clicked.connect(self._clear)
        row.addWidget(self.example_button)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        self.run_button = QPushButton("진단하기")
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self._run)
        row.addWidget(self.run_button)
        layout.addLayout(row)

        self.banner = Banner("", "info")
        self.banner.setVisible(False)
        layout.addWidget(self.banner)

        self.result_box = QGroupBox("진단 결과")
        r_layout = QVBoxLayout(self.result_box)
        self.classification = QLabel("-")
        self.classification.setWordWrap(True)
        self.classification.setStyleSheet("font-size: 18px; font-weight: 700;")
        r_layout.addWidget(self.classification)
        self.summary = QLabel("-")
        self.summary.setWordWrap(True)
        r_layout.addWidget(self.summary)

        r_layout.addWidget(h2("발견된 것"))
        self.findings_host = QWidget()
        self.findings_layout = QVBoxLayout(self.findings_host)
        self.findings_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.addWidget(self.findings_host)

        r_layout.addWidget(h2("다음에 할 것"))
        self.suggestions = BulletList([], "제안 없음")
        r_layout.addWidget(self.suggestions)

        self.limits = QLabel("")
        self.limits.setWordWrap(True)
        self.limits.setObjectName("Hint")
        r_layout.addWidget(self.limits)

        self.result_box.setVisible(False)
        layout.addWidget(self.result_box)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.empty)
        self.scroll = scrollable(self.body)
        outer.addWidget(self.scroll)

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        if ctx.project is None:
            self.empty.setVisible(True)
            self.scroll.setVisible(False)
            return

        spec = get_domain(ctx.project.domain_code).content_spec()
        self._spec = spec
        self.empty.setVisible(spec is None)
        self.scroll.setVisible(spec is not None)
        if spec is None:
            return

        self.head.setText(f"{spec.title}  ({ctx.project.domain_code})")
        self.desc.setText(spec.description)
        self.example_button.setText(spec.example_label)
        self.example_button.setVisible(bool(spec.example))
        self._build_form(spec)

    def _build_form(self, spec) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self._editors.clear()

        for field in spec.fields:
            if field.multiline:
                editor = labeled_text_area(field.hint, 80)
            else:
                editor = QLineEdit()
                editor.setPlaceholderText(field.hint)
            self._editors[field.key] = editor
            mark = " <span style='color:#b3261e'>*</span>" if field.required else ""
            label = QLabel(field.label + mark)
            label.setWordWrap(True)
            self.form.addRow(label, editor)

        self.result_box.setVisible(False)
        self.banner.setVisible(False)

    def _values(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, editor in self._editors.items():
            if isinstance(editor, QLineEdit):
                out[key] = editor.text().strip()
            else:
                out[key] = editor.toPlainText().strip()
        return out

    # -- 동작 -------------------------------------------------------------
    def _fill_example(self) -> None:
        if self._spec is None:
            return
        for key, value in self._spec.example.items():
            editor = self._editors.get(key)
            if editor is None:
                continue
            if isinstance(editor, QLineEdit):
                editor.setText(value)
            else:
                editor.setPlainText(value)
        self.banner.setVisible(True)
        self.banner.set_text(
            "예시를 채웠습니다. '진단하기'를 눌러 어떻게 판정되는지 보고, "
            "실제 내용으로 바꿔 다시 진단하세요.",
            "info",
        )

    def _clear(self) -> None:
        for editor in self._editors.values():
            if isinstance(editor, QLineEdit):
                editor.clear()
            else:
                editor.setPlainText("")
        self.result_box.setVisible(False)
        self.banner.setVisible(False)

    def _run(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None or self._spec is None:
            return
        try:
            diagnosis = get_domain(ctx.project.domain_code).diagnose_content(self._values())
        except ValueError as exc:
            self.banner.setVisible(True)
            self.banner.set_text(str(exc), "critical")
            self.result_box.setVisible(False)
            return

        self.banner.setVisible(False)
        self.result_box.setVisible(True)
        self.classification.setText(diagnosis.classification_label)
        self.classification.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: "
            + ("#b3261e" if diagnosis.critical_count else "#1b5e20")
        )
        self.summary.setText(diagnosis.summary)

        clear_layout(self.findings_layout)
        if not diagnosis.findings:
            self.findings_layout.addWidget(hint("— 발견된 문제 없음"))
        else:
            order = {Severity.CRITICAL: 0, Severity.WARN: 1, Severity.INFO: 2}
            for f in sorted(diagnosis.findings, key=lambda x: order[x.severity]):
                label = QLabel(
                    f"<b style='color:{SEVERITY_COLOR[f.severity]}'>"
                    f"{SEVERITY_MARK[f.severity]}</b>　{f.message}"
                    + (
                        f"<br><span style='color:#5a6068'>→ {f.recommended_action}</span>"
                        if f.recommended_action
                        else ""
                    )
                )
                label.setWordWrap(True)
                self.findings_layout.addWidget(label)

        self.suggestions.set_items(diagnosis.suggestions)
        self.limits.setText(diagnosis.limits)
        self.status_message.emit(f"진단 완료: {diagnosis.classification_label}")
