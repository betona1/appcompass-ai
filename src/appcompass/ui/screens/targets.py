"""화면 D: 타깃 후보.

주목적 하나 — 후보를 비교해 다음에 검증할 타깃 하나를 고르는 것.
근거가 부족하면 추천하지 않고 비교만 제공한다 (TECHSPEC F-060).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..context import ScreenContext
from ..widgets import (
    Banner,
    BulletList,
    EmptyState,
    clear_layout,
    h1,
    h2,
    hint,
    scrollable,
)
from .base import ScreenBase


class TargetsScreen(ScreenBase):
    title = "D. 타깃 후보"
    purpose = "후보를 비교하고, 이번 주에 실제로 만날 수 있는 타깃 하나를 고릅니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None

        self.empty = EmptyState(
            "분석 결과가 없습니다",
            "분석을 실행하면 타깃 후보가 생성됩니다.",
        )

        self.inner = QWidget()
        self.layout_ = QVBoxLayout(self.inner)
        self.layout_.setContentsMargins(18, 16, 18, 16)
        self.layout_.addWidget(h1(self.title))
        self.layout_.addWidget(hint(self.purpose))
        self.banner = Banner("", "info")
        self.layout_.addWidget(self.banner)
        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.cards_host)
        self.layout_.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scrollable(self.inner)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll)

    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        result = ctx.result
        self.empty.setVisible(result is None)
        self.scroll.setVisible(result is not None)
        if result is None:
            return

        targets = result["targets"]
        recommended = targets["recommended_candidate_index"]
        self.banner.set_text(
            targets["recommendation_reason"],
            "ok" if recommended is not None else "info",
        )

        clear_layout(self.cards_layout)

        if not targets["candidates"]:
            self.cards_layout.addWidget(
                hint("후보가 없습니다. 구조화 화면에서 타깃을 먼저 다시 정의하세요.")
            )
            return

        for i, c in enumerate(targets["candidates"]):
            self.cards_layout.addWidget(
                _CandidateCard(i + 1, c, is_recommended=(recommended == i))
            )


class _CandidateCard(QGroupBox):
    def __init__(self, number: int, data: dict, is_recommended: bool) -> None:
        mark = "  ★ 추천" if is_recommended else ""
        super().__init__(f"{number}. {data['name']}{mark}")
        layout = QVBoxLayout(self)

        roles = QLabel(
            f"<b>사용자</b> {data['user']}<br>"
            f"<b>구매자</b> {data.get('payer') or '-'}　　"
            f"<b>영향자</b> {data.get('influencer') or '-'}"
        )
        roles.setWordWrap(True)
        layout.addWidget(roles)

        situation = QLabel(
            f"<b>발생 상황</b> {data.get('trigger_situation') or '-'}<br>"
            f"<b>문제</b> {data.get('problem') or '-'}<br>"
            f"<b>현재 대안</b> {data.get('current_alternative') or '-'}"
        )
        situation.setWordWrap(True)
        layout.addWidget(situation)

        columns = QHBoxLayout()
        for title, key, empty in (
            ("유망한 이유", "why_promising", "근거 없음"),
            ("위험", "risks", "확인된 위험 없음"),
            ("검증 질문", "validation_questions", "질문 없음"),
        ):
            col = QWidget()
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.addWidget(h2(title))
            col_layout.addWidget(BulletList(data.get(key) or [], empty))
            col_layout.addStretch(1)
            columns.addWidget(col, 1)
        layout.addLayout(columns)

        exp = QLabel(f"<b>추천 실험</b>　{data.get('recommended_experiment') or '-'}")
        exp.setWordWrap(True)
        layout.addWidget(exp)
