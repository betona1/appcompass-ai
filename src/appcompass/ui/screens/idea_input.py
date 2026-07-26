"""화면 A: 아이디어 원문 입력.

주목적 하나 — 사용자가 쓴 원문을 그대로 받아 보존하는 것.
여기서는 어떤 판정도 하지 않는다. 원문은 이후에도 덮어쓰지 않는다 (TECHSPEC F-020).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.models import IdeaStructure, RawIdeaInput
from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..widgets import Banner, EmptyState, h1, hint, labeled_text_area, scrollable
from .base import ScreenBase


class IdeaInputScreen(ScreenBase):
    title = "A. 아이디어 입력"
    purpose = "머릿속에 있는 아이디어를 그대로 적습니다. 정리는 다음 화면에서 합니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None

        self.empty = EmptyState(
            "선택된 프로젝트가 없습니다",
            "왼쪽 목록에서 프로젝트를 선택하거나 새로 만드세요.",
        )

        self.form_widget = QWidget()
        outer = QVBoxLayout(self.form_widget)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.addWidget(h1(self.title))
        outer.addWidget(hint(self.purpose))

        self.banner = Banner(
            "원문은 저장 후에도 수정되지 않습니다. AI나 규칙 엔진이 이 텍스트를 덮어쓰지 않습니다.",
            "info",
        )
        outer.addWidget(self.banner)

        box = QGroupBox("원문")
        form = QFormLayout(box)
        form.setLabelAlignment(form.labelAlignment())
        self.app_name = QLineEdit()
        self.app_name.setPlaceholderText("예: VibeQuest")
        self.raw_idea = labeled_text_area(
            "한 문단으로 아이디어를 적으세요. 문장이 다듬어지지 않아도 됩니다.", 110
        )
        self.target_raw = labeled_text_area(
            "지금 떠오르는 사용자. '모든 사람'이라고 써도 됩니다. 다음 화면에서 좁힙니다.", 70
        )
        self.problem_raw = labeled_text_area("사용자가 겪는 문제", 90)
        self.solution_raw = labeled_text_area("어떻게 해결할 생각인지", 90)
        self.revenue_raw = labeled_text_area("수익 모델 (모르면 비워 두세요)", 60)
        self.channel_raw = labeled_text_area("유입 경로 (모르면 비워 두세요)", 60)

        form.addRow("앱 이름", self.app_name)
        form.addRow("아이디어", self.raw_idea)
        form.addRow("예상 사용자", self.target_raw)
        form.addRow("문제 상황", self.problem_raw)
        form.addRow("해결 방법", self.solution_raw)
        form.addRow("수익 모델", self.revenue_raw)
        form.addRow("유입 경로", self.channel_raw)
        outer.addWidget(box)

        self.reason = QLineEdit()
        self.reason.setPlaceholderText(
            "이번 버전을 만든 이유 (예: 타깃을 상황 기반으로 좁힘)"
        )
        reason_box = QGroupBox("변경 사유")
        reason_layout = QVBoxLayout(reason_box)
        reason_layout.addWidget(
            hint("버전 비교 화면에서 '왜 바뀌었는지'를 추적하는 데 쓰입니다.")
        )
        reason_layout.addWidget(self.reason)
        outer.addWidget(reason_box)

        row = QHBoxLayout()
        row.addStretch(1)
        self.save_button = QPushButton("새 버전으로 저장하고 구조화로 이동")
        self.save_button.setObjectName("Primary")
        self.save_button.clicked.connect(self._save)
        row.addWidget(self.save_button)
        outer.addLayout(row)
        outer.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = scrollable(self.form_widget)
        layout.addWidget(self.empty)
        layout.addWidget(self.scroll)

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        self.empty.setVisible(not ctx.has_project)
        self.scroll.setVisible(ctx.has_project)
        if not ctx.has_project:
            return

        raw = (ctx.version.raw_input if ctx.version else {}) or {}
        self.app_name.setText(raw.get("app_name") or (ctx.project.app_name or ""))
        self.raw_idea.setPlainText(raw.get("raw_idea", ""))
        self.target_raw.setPlainText(raw.get("target_user_raw", ""))
        self.problem_raw.setPlainText(raw.get("problem_raw", ""))
        self.solution_raw.setPlainText(raw.get("solution_raw", ""))
        self.revenue_raw.setPlainText(raw.get("revenue_model_raw", ""))
        self.channel_raw.setPlainText(raw.get("distribution_channel_raw", ""))
        self.reason.setText("")

        if ctx.version:
            self.banner.set_text(
                f"현재 v{ctx.version.version_no}의 원문을 불러왔습니다. "
                "저장하면 항상 새 버전이 만들어지고 이전 버전은 그대로 남습니다.",
                "info",
            )

    # -- 동작 -------------------------------------------------------------
    def _save(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None:
            return
        raw = RawIdeaInput(
            app_name=self.app_name.text().strip(),
            raw_idea=self.raw_idea.toPlainText().strip(),
            target_user_raw=self.target_raw.toPlainText().strip(),
            problem_raw=self.problem_raw.toPlainText().strip(),
            solution_raw=self.solution_raw.toPlainText().strip(),
            revenue_model_raw=self.revenue_raw.toPlainText().strip(),
            distribution_channel_raw=self.channel_raw.toPlainText().strip(),
            current_stage=ctx.project.stage,
        )
        if not raw.raw_idea and not raw.problem_raw:
            self.banner.set_text(
                "아이디어나 문제 상황 중 하나는 적어야 저장할 수 있습니다.", "critical"
            )
            return

        # 이전 버전의 구조화 결과를 이어받아 편집 부담을 줄인다.
        previous = IdeaStructure.from_dict(ctx.version.structured_idea) if ctx.version else None
        seed = _seed_structure(raw, previous)

        try:
            version = ctx.service.create_version(
                ctx.project.id, raw, seed, change_reason=self.reason.text()
            )
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return

        self.status_message.emit(f"v{version.version_no} 저장됨")
        self.data_changed.emit()
        self.request_screen.emit("structure")


def _seed_structure(raw: RawIdeaInput, previous: IdeaStructure | None) -> IdeaStructure:
    """구조화 화면의 시작값.

    자동 해석은 하지 않는다. 원문을 해당 칸에 옮겨 놓고 나머지는 사용자가 채운다.
    """
    if previous is not None:
        from dataclasses import replace

        return replace(previous, app_name=raw.app_name or previous.app_name)
    return IdeaStructure(
        app_name=raw.app_name,
        target_user=raw.target_user_raw,
        problem_situation=raw.problem_raw,
        core_action=raw.solution_raw,
        revenue_model=raw.revenue_model_raw or None,
        distribution_channel=raw.distribution_channel_raw or None,
    )
