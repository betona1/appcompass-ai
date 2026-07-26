"""화면 C: 자동 진단.

주목적 하나 — 왜 이런 판단이 나왔고 다음에 무엇을 해야 하는지 보여주는 것.
CLAUDE.md §9: "분석 결과 화면은 점수보다 이유와 다음 행동을 우선 표시".
따라서 판단 → 다음 행동 → 위험 → 점수 순서로 배치한다.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..context import ScreenContext
from ..theme import decision_color, decision_label, score_bar
from ..widgets import Banner, BulletList, EmptyState, WarningTable, h1, h2, hint, scrollable
from .base import ScreenBase


class DiagnosisScreen(ScreenBase):
    title = "C. 자동 진단"
    purpose = "규칙 엔진이 계산한 판단과 그 이유입니다. 점수는 근거일 뿐 결론이 아닙니다."

    def __init__(self) -> None:
        super().__init__()
        self.empty = EmptyState(
            "분석 결과가 없습니다",
            "'B. 구조화 검토'에서 승인한 뒤 분석을 실행하세요.",
        )

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        # 1. 판단
        decision_box = QGroupBox("판단")
        d_layout = QVBoxLayout(decision_box)
        self.decision_label = QLabel("-")
        self.decision_label.setObjectName("Big")
        self.decision_reason = QLabel("-")
        self.decision_reason.setWordWrap(True)
        self.decision_meta = QLabel("-")
        self.decision_meta.setObjectName("Hint")
        self.decision_meta.setWordWrap(True)
        d_layout.addWidget(self.decision_label)
        d_layout.addWidget(self.decision_reason)
        d_layout.addWidget(self.decision_meta)
        layout.addWidget(decision_box)

        # 2. 다음 행동
        next_box = QGroupBox("지금 할 일")
        n_layout = QVBoxLayout(next_box)
        self.next_actions = BulletList([], "다음 행동 없음")
        n_layout.addWidget(self.next_actions)
        layout.addWidget(next_box)

        # 3. 위험 / 언노운
        risk_row = QHBoxLayout()
        risk_box = QGroupBox("핵심 위험")
        r_layout = QVBoxLayout(risk_box)
        self.risks = BulletList([], "치명 위험 없음")
        r_layout.addWidget(self.risks)
        unknown_box = QGroupBox("핵심 언노운 (아직 모르는 것)")
        u_layout = QVBoxLayout(unknown_box)
        self.unknowns = BulletList([], "언노운 없음")
        u_layout.addWidget(self.unknowns)
        risk_row.addWidget(risk_box, 1)
        risk_row.addWidget(unknown_box, 1)
        layout.addLayout(risk_row)

        # 4. 경고
        warn_box = QGroupBox("경고")
        w_layout = QVBoxLayout(warn_box)
        self.warning_table = WarningTable()
        self.warning_table.setMinimumHeight(160)
        w_layout.addWidget(self.warning_table)
        layout.addWidget(warn_box)

        # 5. 점수 (마지막)
        score_box = QGroupBox("평가 점수")
        s_layout = QVBoxLayout(score_box)
        self.score_summary = QLabel("-")
        self.score_summary.setObjectName("H2")
        self.confidence_note = Banner("", "info")
        s_layout.addWidget(self.score_summary)
        s_layout.addWidget(self.confidence_note)
        self.score_table = QTableWidget(0, 6)
        self.score_table.setHorizontalHeaderLabels(
            ["항목", "점수", "가중치", "환산", "신뢰도", "이유"]
        )
        self.score_table.verticalHeader().setVisible(False)
        self.score_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.score_table.setAlternatingRowColors(True)
        self.score_table.setWordWrap(True)
        self.score_table.horizontalHeader().setStretchLastSection(True)
        self.score_table.setMinimumHeight(320)
        s_layout.addWidget(self.score_table)
        layout.addWidget(score_box)

        # 6. 부족한 근거
        missing_box = QGroupBox("부족한 근거")
        m_layout = QVBoxLayout(missing_box)
        m_layout.addWidget(
            hint("AI는 근거를 만들지 않습니다. '근거' 화면에서 직접 등록해야 신뢰도가 올라갑니다.")
        )
        self.missing = BulletList([], "모든 항목에 근거가 연결되어 있습니다.")
        m_layout.addWidget(self.missing)
        layout.addWidget(missing_box)

        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scrollable(inner)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll)

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        result = ctx.result
        failed = ctx.run is not None and ctx.run.status.startswith("FAILED")

        if failed:
            self.empty.setVisible(True)
            self.scroll.setVisible(False)
            return
        self.empty.setVisible(result is None)
        self.scroll.setVisible(result is not None)
        if result is None:
            return

        diag = result["diagnosis"]
        pivot = result["pivot"]
        meta = result["meta"]

        self.decision_label.setText(decision_label(pivot["decision"]))
        self.decision_label.setStyleSheet(
            f"color: {decision_color(pivot['decision'])};"
        )
        self.decision_reason.setText(pivot["rationale"])

        would_be = pivot.get("would_be_decision")
        meta_bits = [
            f"근거 신뢰도 {pivot['confidence']:.2f}",
            f"사유 코드 {', '.join(pivot['reason_codes']) or '-'}",
            f"판정 엔진 {meta['engine']} {meta['engine_version']}",
            f"정책 {meta['policy_version']}",
            f"모델 {meta['model_name'] or '사용 안 함 (규칙 엔진 전용)'}",
        ]
        if would_be:
            meta_bits.insert(1, f"근거가 충분했다면 → {decision_label(would_be)}")
        self.decision_meta.setText("  ·  ".join(meta_bits))

        self.next_actions.set_items(result["next_actions"])
        self.risks.set_items(diag["critical_risks"])
        self.unknowns.set_items(diag["unknowns"])
        self.warning_table.set_warnings(diag["warnings"])

        self.score_summary.setText(
            f"총점 {diag['total_score']:.1f} / 100    ·    "
            f"전체 근거 신뢰도 {diag['overall_confidence']:.2f}"
        )
        if diag["overall_confidence"] < 0.35:
            self.confidence_note.set_text(
                "근거 신뢰도가 낮아 이 점수는 '현재 서술의 완성도'만 나타냅니다. "
                "사업성 판단으로 읽으면 안 됩니다. 근거를 등록해야 판단이 확정됩니다.",
                "critical",
            )
        else:
            self.confidence_note.set_text(
                "등록된 근거가 판단에 반영되었습니다. 최종 결정은 사람이 승인해야 합니다.",
                "ok",
            )

        dims = diag["dimensions"]
        self.score_table.setRowCount(len(dims))
        for i, d in enumerate(dims):
            self.score_table.setItem(
                i, 0, QTableWidgetItem(f"{d['code']} {d['label']}")
            )
            score_item = QTableWidgetItem(f"{score_bar(d['raw_score'])} {d['raw_score']}/5")
            if d["raw_score"] <= 2:
                score_item.setForeground(QColor("#b3261e"))
            self.score_table.setItem(i, 1, score_item)
            self.score_table.setItem(i, 2, QTableWidgetItem(str(d["weight"])))
            self.score_table.setItem(
                i, 3, QTableWidgetItem(f"{d['normalized_score']:.1f}")
            )
            self.score_table.setItem(i, 4, QTableWidgetItem(f"{d['confidence']:.2f}"))
            self.score_table.setItem(i, 5, QTableWidgetItem(d["reason"]))
        self.score_table.resizeColumnsToContents()
        self.score_table.resizeRowsToContents()
        if self.score_table.columnWidth(5) > 520:
            self.score_table.setColumnWidth(5, 520)

        missing: list[str] = []
        for d in dims:
            if d.get("missing_evidence"):
                missing.append(f"{d['label']}: {', '.join(d['missing_evidence'])}")
        self.missing.set_items(missing)
