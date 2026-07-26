"""화면 E: MVP.

주목적 하나 — 무엇을 만들고 무엇을 만들지 않을지 확정하는 것.
CLAUDE.md §2.5: MVP는 P0 + 최소한의 P1. §2.6: 측정 없는 기능은 넣지 않는다.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..context import ScreenContext
from ..widgets import BulletList, EmptyState, h1, h2, hint, scrollable
from .base import ScreenBase


class MvpScreen(ScreenBase):
    title = "E. MVP"
    purpose = "검증할 가설과 만들 기능, 그리고 이번에는 만들지 않을 기능을 확정합니다."

    def __init__(self) -> None:
        super().__init__()
        self.empty = EmptyState(
            "분석 결과가 없습니다", "분석을 실행하면 MVP 초안이 생성됩니다."
        )

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        hypo_box = QGroupBox("검증할 가설")
        h_layout = QVBoxLayout(hypo_box)
        self.hypotheses = QLabel("-")
        self.hypotheses.setWordWrap(True)
        h_layout.addWidget(self.hypotheses)
        layout.addWidget(hypo_box)

        first_box = QGroupBox("첫 성공 경험")
        f_layout = QVBoxLayout(first_box)
        f_layout.addWidget(
            hint("활성화 지점입니다. 여기가 흔들리면 나머지 지표는 의미가 없습니다.")
        )
        self.first_success = QLabel("-")
        self.first_success.setWordWrap(True)
        f_layout.addWidget(self.first_success)
        layout.addWidget(first_box)

        feature_row = QHBoxLayout()
        for title, attr, empty in (
            ("P0 · 핵심 문제 해결", "p0", "P0 기능 없음"),
            ("P1 · 핵심 행동 완료율", "p1", "P1 기능 없음"),
            ("이번 MVP에서 제외", "excluded", "제외 기능 없음"),
        ):
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            widget = BulletList([], empty)
            setattr(self, attr, widget)
            box_layout.addWidget(widget)
            box_layout.addStretch(1)
            feature_row.addWidget(box, 1)
        layout.addLayout(feature_row)

        flow_row = QHBoxLayout()
        flow_box = QGroupBox("핵심 사용자 흐름")
        fl = QVBoxLayout(flow_box)
        self.flow = BulletList([], "흐름 미정의")
        fl.addWidget(self.flow)
        fl.addStretch(1)

        metric_box = QGroupBox("측정 이벤트")
        ml = QVBoxLayout(metric_box)
        ml.addWidget(hint("이벤트가 연결되지 않은 기능은 MVP에 넣지 않습니다."))
        self.metrics = BulletList([], "측정 이벤트 없음")
        ml.addWidget(self.metrics)
        ml.addStretch(1)

        flow_row.addWidget(flow_box, 1)
        flow_row.addWidget(metric_box, 1)
        layout.addLayout(flow_row)

        risk_box = QGroupBox("위험")
        r_layout = QVBoxLayout(risk_box)
        self.risks = BulletList([], "확인된 위험 없음")
        r_layout.addWidget(self.risks)
        layout.addWidget(risk_box)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scrollable(inner)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll)

    def refresh(self, ctx: ScreenContext) -> None:
        result = ctx.result
        self.empty.setVisible(result is None)
        self.scroll.setVisible(result is not None)
        if result is None:
            return

        m = result["mvp"]
        self.hypotheses.setText(
            "<br>".join(
                [
                    f"<b>핵심</b>　{m['core_hypothesis']}",
                    f"<b>문제</b>　{m['problem_hypothesis']}",
                    f"<b>행동</b>　{m['behavior_hypothesis']}",
                    f"<b>가치</b>　{m['value_hypothesis']}",
                    f"<b>재방문</b>　{m['retention_hypothesis']}",
                    f"<b>수익</b>　{m['revenue_hypothesis'] or '-'}",
                ]
            )
        )
        self.first_success.setText(m["first_success_experience"])
        self.p0.set_items(m["p0_features"])
        self.p1.set_items(m["p1_features"])
        self.excluded.set_items(m["excluded_features"])
        self.flow.set_items(m["core_user_flow"])
        self.metrics.set_items(m["metrics"])
        self.risks.set_items(m["risks"])
