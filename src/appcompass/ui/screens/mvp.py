"""화면 E: MVP.

주목적 하나 — 무엇을 만들고 무엇을 만들지 않을지 확정하는 것.
CLAUDE.md §2.5: MVP는 P0 + 최소한의 P1. §2.6: 측정 없는 기능은 넣지 않는다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import IMPLEMENTATION_STATUS_LABELS, ImplementationStatus
from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..widgets import BulletList, EmptyState, h1, h2, hint, scrollable
from .base import ScreenBase


class MvpScreen(ScreenBase):
    title = "E. MVP"
    purpose = "검증할 가설과 만들 기능, 그리고 이번에는 만들지 않을 기능을 확정합니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._features: list = []
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

        # 구현 상태 — 개선 명세를 만들려면 무엇을 이미 만들었는지 알아야 한다.
        status_box = QGroupBox("기능별 구현 상태")
        s_layout = QVBoxLayout(status_box)
        s_layout.addWidget(
            hint(
                "이미 만든 기능을 표시하면 'G. 피벗 보고서'에서 개선 명세를 내보낼 수 있습니다. "
                "만들지 않은 기능은 개선 대상이 아닙니다."
            )
        )
        self.status_table = QTableWidget(0, 4)
        self.status_table.setHorizontalHeaderLabels(
            ["우선순위", "기능", "구현 상태", "관찰된 문제 (선택)"]
        )
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.setAlternatingRowColors(True)
        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.status_table.setMinimumHeight(240)
        s_layout.addWidget(self.status_table)

        status_row = QHBoxLayout()
        self.status_hint = QLabel("")
        self.status_hint.setObjectName("Hint")
        status_row.addWidget(self.status_hint, 1)
        self.save_status_button = QPushButton("구현 상태 저장")
        self.save_status_button.setObjectName("Primary")
        self.save_status_button.clicked.connect(self._save_status)
        status_row.addWidget(self.save_status_button)
        s_layout.addLayout(status_row)
        layout.addWidget(status_box)

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
        self._ctx = ctx
        result = ctx.result
        self.empty.setVisible(result is None)
        self.scroll.setVisible(result is not None)
        if result is None:
            return

        self._load_status(ctx)

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

    # -- 구현 상태 ---------------------------------------------------------
    def _load_status(self, ctx: ScreenContext) -> None:
        if ctx.project is None:
            return
        self._features = ctx.service.list_feature_status(ctx.project.id)
        self.status_table.setRowCount(len(self._features))
        for row, f in enumerate(self._features):
            self.status_table.setItem(row, 0, QTableWidgetItem(f.priority))
            text_item = QTableWidgetItem(f.text)
            text_item.setFlags(text_item.flags() & ~Qt.ItemIsEditable)
            self.status_table.setItem(row, 1, text_item)

            combo = QComboBox()
            for status, label in IMPLEMENTATION_STATUS_LABELS.items():
                combo.addItem(label, status)
            index = combo.findData(f.status)
            if index >= 0:
                combo.setCurrentIndex(index)
            self.status_table.setCellWidget(row, 2, combo)

            note = QLineEdit(f.note)
            note.setPlaceholderText("이 기능에서 실제로 관찰된 문제 (개선 명세에 들어갑니다)")
            self.status_table.setCellWidget(row, 3, note)

        self.status_table.resizeRowsToContents()
        built = sum(
            1 for f in self._features if f.status == ImplementationStatus.DONE
        )
        self.status_hint.setText(
            f"기능 {len(self._features)}개 중 구현됨 {built}개."
            + (
                "  구현된 기능이 없으면 개선 명세에 개선 대상이 나오지 않습니다."
                if built == 0
                else "  'G. 피벗 보고서'에서 개선 명세를 내보낼 수 있습니다."
            )
        )
        self.save_status_button.setEnabled(bool(self._features))

    def _save_status(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None:
            return
        try:
            for row, f in enumerate(self._features):
                combo = self.status_table.cellWidget(row, 2)
                note_edit = self.status_table.cellWidget(row, 3)
                ctx.service.set_feature_status(
                    ctx.project.id,
                    f,
                    combo.currentData(),
                    note_edit.text().strip(),
                )
        except ServiceError as exc:
            self.status_hint.setText(f"저장 실패: {exc}")
            return
        self.status_message.emit("구현 상태를 저장했습니다.")
        self.data_changed.emit()
