"""화면 0: 다음 할 일.

이 도구는 화면이 아홉 개다. 처음 쓰는 사람은 "그래서 지금 뭘 해야 하지"에서 막힌다.
이 화면의 주목적 하나 — **다음에 할 일 하나를 알려주고 거기로 데려다주는 것**이다.

그래서 여기에는 정보를 많이 넣지 않는다. 할 일 하나, 왜, 어떻게, 그리고 이동 버튼.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.nextstep import JOURNEY
from ..context import ScreenContext
from ..widgets import BulletList, h1, hint, scrollable
from .base import ScreenBase


class GuideScreen(ScreenBase):
    title = "① 다음 할 일"
    purpose = "지금 해야 할 일 하나만 알려드립니다. 그것만 하시면 됩니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._target_screen = ""

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        # --- 진행 단계 ---
        self.journey_label = QLabel("")
        self.journey_label.setWordWrap(True)
        self.journey_label.setObjectName("Hint")
        layout.addWidget(self.journey_label)

        # --- 할 일 카드 ---
        self.card = QFrame()
        self.card.setObjectName("Card")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        self.step_title = QLabel("-")
        self.step_title.setWordWrap(True)
        self.step_title.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #16181d;"
        )
        card_layout.addWidget(self.step_title)

        self.step_why = QLabel("-")
        self.step_why.setWordWrap(True)
        self.step_why.setStyleSheet("font-size: 14px; color: #41474d;")
        card_layout.addWidget(self.step_why)

        how_box = QGroupBox("이렇게 하세요")
        how_layout = QVBoxLayout(how_box)
        self.step_how = BulletList([], "설명 없음")
        how_layout.addWidget(self.step_how)
        card_layout.addWidget(how_box)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.go_button = QPushButton("이동")
        self.go_button.setObjectName("Primary")
        self.go_button.setMinimumHeight(38)
        self.go_button.clicked.connect(self._go)
        button_row.addWidget(self.go_button)
        card_layout.addLayout(button_row)

        layout.addWidget(self.card)

        # --- 이 도구가 무엇을 하는지 (항상 보이는 짧은 설명) ---
        about = QGroupBox("이 도구가 하는 일")
        a_layout = QVBoxLayout(about)
        a_layout.addWidget(
            QLabel(
                "아이디어를 구조화하고, <b>가장 약한 부분과 그 이유</b>를 찾고, "
                "<b>무엇을 검증해야 하는지</b> 알려줍니다.<br>"
                "그리고 유지할지·고칠지·방향을 틀지 판단합니다."
            )
        )
        a_layout.addWidget(
            hint(
                "점수가 낮다고 아이디어가 나쁜 게 아닙니다. "
                "지금 기획서에 적힌 내용이 얼마나 '검증 가능한 형태'인지를 나타냅니다.\n"
                "판단은 AI가 아니라 규칙 엔진이 합니다. 같은 입력이면 항상 같은 결과가 나옵니다.\n"
                "최종 결정은 사람이 합니다."
            )
        )
        for w in about.findChildren(QLabel):
            w.setWordWrap(True)
        layout.addWidget(about)

        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(inner))

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        project_id = ctx.project.id if ctx.project else None
        step = ctx.service.next_step(project_id)

        self.journey_label.setText(self._journey_text(step))
        self.step_title.setText(step.title)
        self.step_why.setText(step.why)
        self.step_how.set_items(step.how)

        self._target_screen = step.screen
        self.go_button.setVisible(bool(step.screen and step.button_text))
        self.go_button.setText(step.button_text or "이동")

        if step.is_done:
            self.card.setObjectName("BannerOk")
            self.step_title.setStyleSheet(
                "font-size: 22px; font-weight: 700; color: #1b5e20;"
            )
        elif step.is_blocking:
            self.card.setObjectName("Card")
            self.step_title.setStyleSheet(
                "font-size: 22px; font-weight: 700; color: #16181d;"
            )
        else:
            self.card.setObjectName("Banner")
            self.step_title.setStyleSheet(
                "font-size: 22px; font-weight: 700; color: #8a4b00;"
            )
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)

    @staticmethod
    def _journey_text(step) -> str:
        """전체 여정에서 지금 어디쯤인지. 끝이 보여야 막막하지 않다."""
        parts = []
        for i, (code, label) in enumerate(JOURNEY):
            if i < step.stage_index:
                parts.append(f"✔ {label}")
            elif i == step.stage_index:
                parts.append(f"<b>▶ {label}</b>")
            else:
                parts.append(f"· {label}")
        return (
            f"{step.stage_index + 1} / {len(JOURNEY)} 단계<br>"
            + "　　".join(parts)
        )

    def _go(self) -> None:
        if self._target_screen:
            self.request_screen.emit(self._target_screen)
