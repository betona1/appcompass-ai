"""화면 F: 실험.

주목적 하나 — 검증되지 않은 가설에 대해 **실험 하나를 시작하고 결과를 남기는 것**.

이 화면이 순환을 닫는다.
    가설 → 실험 → 결과 → 근거 등록 → 재분석 → 판단 갱신

그래서 "근거로 등록" 버튼이 이 화면의 핵심이다.
결과를 적어 놓기만 하면 판단에 아무 영향이 없다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import HYPOTHESIS_STATUS_LABELS, HypothesisStatus
from ...core.experiment import (
    CONCLUSION_LABELS,
    EXPERIMENT_STATUS_LABELS,
    EXPERIMENT_TYPE_LABELS,
    ExperimentConclusion,
    ExperimentStatus,
)
from ...services.app_service import ServiceError
from ..context import ScreenContext
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

_STATUS_MARK = {
    HypothesisStatus.SUPPORTED: ("●", "#1b5e20"),
    HypothesisStatus.REFUTED: ("■", "#b3261e"),
    HypothesisStatus.CONFLICTED: ("▲", "#8a6100"),
    HypothesisStatus.INSUFFICIENT: ("○", "#5a6068"),
}


class ExperimentsScreen(ScreenBase):
    title = "F. 실험"
    purpose = "검증되지 않은 가설에 실험을 붙이고, 결과를 근거로 등록해 판단을 갱신합니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._suggestions: list = []
        self._experiments: list = []
        self._selected = None

        self.empty = EmptyState(
            "분석 결과가 없습니다",
            "분석을 실행하면 가설별 검증 현황과 추천 실험이 나옵니다.",
        )

        # --- 좌: 가설 현황 + 추천 실험 ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 14, 10, 14)
        left_layout.addWidget(h1(self.title))
        left_layout.addWidget(hint(self.purpose))

        self.banner = Banner("", "info")
        left_layout.addWidget(self.banner)

        verdict_box = QGroupBox("가설 검증 현황")
        v_layout = QVBoxLayout(verdict_box)
        self.verdict_host = QWidget()
        self.verdict_layout = QVBoxLayout(self.verdict_host)
        self.verdict_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.addWidget(self.verdict_host)
        left_layout.addWidget(verdict_box)

        suggest_box = QGroupBox("추천 실험")
        s_layout = QVBoxLayout(suggest_box)
        s_layout.addWidget(
            hint("싼 것부터, 검증 순서대로 제안합니다. 문제 가설이 안 풀렸는데 가격 테스트는 순서가 틀립니다.")
        )
        self.suggest_host = QWidget()
        self.suggest_layout = QVBoxLayout(self.suggest_host)
        self.suggest_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.addWidget(self.suggest_host)
        left_layout.addWidget(suggest_box)
        left_layout.addStretch(1)

        # --- 우: 실험 목록 + 결과 입력 ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 14, 16, 14)
        right_layout.addWidget(h2("내 실험"))

        self.experiment_combo = QComboBox()
        self.experiment_combo.currentIndexChanged.connect(self._on_select)
        right_layout.addWidget(self.experiment_combo)

        self.detail_box = QGroupBox("실험 내용")
        d_layout = QVBoxLayout(self.detail_box)
        self.detail_meta = QLabel("-")
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setObjectName("Hint")
        d_layout.addWidget(self.detail_meta)
        d_layout.addWidget(h2("절차"))
        self.detail_procedure = BulletList([], "절차 없음")
        d_layout.addWidget(self.detail_procedure)
        right_layout.addWidget(self.detail_box)

        result_box = QGroupBox("결과 입력")
        form = QFormLayout(result_box)
        self.status_combo = QComboBox()
        for status, label in EXPERIMENT_STATUS_LABELS.items():
            self.status_combo.addItem(label, status)
        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(0, 1_000_000)
        self.sample_spin.setSpecialValueText("미기재")
        self.quant_edit = QLineEdit()
        self.quant_edit.setPlaceholderText("예: 5명 중 4명이 월 2회 이상 겪었다고 답함 (80%)")
        self.qual_edit = labeled_text_area(
            "관찰된 사실을 적습니다. 해석이 아니라 무엇을 보고 들었는지.", 80
        )
        self.conclusion_combo = QComboBox()
        self.conclusion_combo.addItem("— 아직 결론 없음 —", None)
        for conclusion, label in CONCLUSION_LABELS.items():
            self.conclusion_combo.addItem(label, conclusion)
        self.next_edit = QLineEdit()
        self.next_edit.setPlaceholderText("이 결과를 보고 다음에 할 실험 (선택)")

        form.addRow("진행 상태", self.status_combo)
        form.addRow("실제 표본 수", self.sample_spin)
        form.addRow("정량 결과", self.quant_edit)
        form.addRow("정성 요약", self.qual_edit)
        form.addRow("결론", self.conclusion_combo)
        form.addRow("다음 실험", self.next_edit)
        right_layout.addWidget(result_box)

        button_row = QHBoxLayout()
        self.delete_button = QPushButton("실험 삭제")
        self.delete_button.setObjectName("Danger")
        self.delete_button.clicked.connect(self._delete)
        self.save_button = QPushButton("결과 저장")
        self.save_button.clicked.connect(self._save)
        self.to_evidence_button = QPushButton("근거로 등록하고 재분석")
        self.to_evidence_button.setObjectName("Primary")
        self.to_evidence_button.clicked.connect(self._to_evidence)
        button_row.addWidget(self.delete_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.to_evidence_button)
        right_layout.addLayout(button_row)

        self.evidence_note = QLabel("")
        self.evidence_note.setWordWrap(True)
        self.evidence_note.setObjectName("Hint")
        right_layout.addWidget(self.evidence_note)
        right_layout.addStretch(1)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(scrollable(left))
        self.splitter.addWidget(scrollable(right))
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.empty)
        outer.addWidget(self.splitter)

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        available = ctx.result is not None and ctx.project is not None
        self.empty.setVisible(not available)
        self.splitter.setVisible(available)
        if not available:
            return

        verdicts = ctx.service.hypothesis_verdicts(ctx.project.id)
        self._render_verdicts(verdicts)

        self._suggestions = ctx.service.suggest_experiments(ctx.project.id)
        self._render_suggestions()

        self._experiments = ctx.service.list_experiments(ctx.project.id)
        self._render_experiment_list()

        unverified = [v for v in verdicts if v.status != HypothesisStatus.SUPPORTED]
        if not unverified:
            self.banner.set_text(
                "모든 가설이 근거로 뒷받침되고 있습니다. 추가 실험 없이 진행해도 됩니다.", "ok"
            )
        else:
            self.banner.set_text(
                f"검증되지 않은 가설 {len(unverified)}개. "
                "아래 추천 실험 중 하나를 시작하세요. 한 번에 하나면 충분합니다.",
                "info",
            )

    def _render_verdicts(self, verdicts) -> None:
        clear_layout(self.verdict_layout)
        if not verdicts:
            self.verdict_layout.addWidget(hint("— 분석 결과가 없습니다"))
            return
        for v in verdicts:
            mark, color = _STATUS_MARK[v.status]
            label = QLabel(
                f"<b style='color:{color}'>{mark} {HYPOTHESIS_STATUS_LABELS[v.status]}</b>"
                f"　[{v.id}] {v.label}<br>"
                f"<span style='color:#5a6068'>{v.reason}</span>"
            )
            label.setWordWrap(True)
            self.verdict_layout.addWidget(label)

    def _render_suggestions(self) -> None:
        clear_layout(self.suggest_layout)
        if not self._suggestions:
            self.suggest_layout.addWidget(
                hint("추천할 실험이 없습니다. 모든 가설이 검증되었거나 분석이 필요합니다.")
            )
            return
        for i, sug in enumerate(self._suggestions):
            box = QGroupBox(f"{sug.title}  ({EXPERIMENT_TYPE_LABELS[sug.experiment_type]})")
            b_layout = QVBoxLayout(box)
            why = QLabel(sug.why_now)
            why.setWordWrap(True)
            b_layout.addWidget(why)
            b_layout.addWidget(BulletList(sug.procedure, "절차 없음"))
            meta = QLabel(
                f"<b>성공 기준</b> {sug.success_metric}<br>"
                f"<b>목표</b> {sug.target_value}　<b>표본</b> {sug.sample_goal}명"
                + (f"<br><b>비용</b> {sug.cost_hint}" if sug.cost_hint else "")
            )
            meta.setWordWrap(True)
            b_layout.addWidget(meta)

            row = QHBoxLayout()
            row.addStretch(1)
            start = QPushButton("이 실험 시작하기")
            start.setObjectName("Primary")
            start.clicked.connect(lambda _=False, s=sug: self._start(s))
            row.addWidget(start)
            b_layout.addLayout(row)
            self.suggest_layout.addWidget(box)

    def _render_experiment_list(self) -> None:
        current_id = self._selected.id if self._selected else None
        self.experiment_combo.blockSignals(True)
        self.experiment_combo.clear()
        for e in self._experiments:
            mark = "✔ " if e.evidence_id else ""
            self.experiment_combo.addItem(
                f"{mark}[{e.hypothesis_id}] {e.title} — "
                f"{EXPERIMENT_STATUS_LABELS[e.status]}",
                e.id,
            )
        self.experiment_combo.blockSignals(False)

        has_any = bool(self._experiments)
        for w in (
            self.detail_box, self.status_combo, self.sample_spin, self.quant_edit,
            self.qual_edit, self.conclusion_combo, self.next_edit,
            self.save_button, self.delete_button, self.to_evidence_button,
        ):
            w.setEnabled(has_any)

        if not has_any:
            self._selected = None
            self.detail_meta.setText("아직 시작한 실험이 없습니다. 왼쪽에서 추천 실험을 시작하세요.")
            self.detail_procedure.set_items([])
            self.evidence_note.setText("")
            return

        index = 0
        if current_id:
            found = self.experiment_combo.findData(current_id)
            if found >= 0:
                index = found
        self.experiment_combo.setCurrentIndex(index)
        self._on_select()

    def _on_select(self) -> None:
        exp_id = self.experiment_combo.currentData()
        self._selected = next((e for e in self._experiments if e.id == exp_id), None)
        e = self._selected
        if e is None:
            return

        self.detail_meta.setText(
            f"가설 {e.hypothesis_id}　·　유형 {EXPERIMENT_TYPE_LABELS[e.experiment_type]}<br>"
            f"성공 기준: {e.success_metric}<br>"
            f"목표: {e.target_value}　·　목표 표본: {e.sample_goal or '-'}명"
        )
        self.detail_procedure.set_items(e.procedure)

        self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(e.status)))
        self.sample_spin.setValue(e.actual_sample or 0)
        self.quant_edit.setText(e.quantitative_result)
        self.qual_edit.setPlainText(e.qualitative_summary)
        self.conclusion_combo.setCurrentIndex(
            max(0, self.conclusion_combo.findData(e.conclusion))
        )
        self.next_edit.setText(e.next_experiment)

        locked = e.evidence_id is not None
        self.to_evidence_button.setEnabled(not locked)
        for w in (
            self.status_combo, self.sample_spin, self.quant_edit,
            self.qual_edit, self.conclusion_combo, self.next_edit, self.save_button,
        ):
            w.setEnabled(not locked)

        if locked:
            self.evidence_note.setText(
                "이 실험은 이미 근거로 등록되어 잠겼습니다. "
                "결과를 바꾸려면 '근거' 화면에서 해당 근거를 삭제하세요."
            )
        elif e.can_become_evidence:
            self.evidence_note.setText(
                "결론이 났습니다. '근거로 등록하고 재분석'을 누르면 이 결과가 근거가 되고 "
                "판단이 갱신됩니다. 근거 유형은 실험 유형이 결정합니다."
            )
        else:
            self.evidence_note.setText(
                "근거로 등록하려면 진행 상태를 '완료'로 바꾸고 결론을 고르세요. "
                "'판단 불가'는 근거가 되지 않습니다 — 표본이나 설계를 보완해 다시 하세요."
            )

    # -- 동작 -------------------------------------------------------------
    def _start(self, suggestion) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None:
            return
        try:
            exp = ctx.service.create_experiment_from_suggestion(ctx.project.id, suggestion)
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return
        self._selected = exp
        self.status_message.emit(f"'{exp.title}' 실험을 시작했습니다.")
        self.data_changed.emit()

    def _save(self) -> None:
        ctx, e = self._ctx, self._selected
        if ctx is None or e is None:
            return
        try:
            ctx.service.update_experiment(
                e.id,
                status=self.status_combo.currentData(),
                actual_sample=self.sample_spin.value() or None,
                quantitative_result=self.quant_edit.text().strip(),
                qualitative_summary=self.qual_edit.toPlainText().strip(),
                conclusion=self.conclusion_combo.currentData(),
                next_experiment=self.next_edit.text().strip(),
            )
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return
        self.status_message.emit("실험 결과를 저장했습니다.")
        self.data_changed.emit()

    def _to_evidence(self) -> None:
        ctx, e = self._ctx, self._selected
        if ctx is None or e is None:
            return
        self._save()  # 화면의 최신 입력을 먼저 반영한다
        try:
            dto = ctx.service.convert_experiment_to_evidence(e.id)
        except ServiceError as exc:
            QMessageBox.information(self, "근거로 등록할 수 없습니다", str(exc))
            return
        self.status_message.emit(
            f"근거로 등록했습니다: {dto.title} (신뢰도 {dto.effective_confidence:.2f}). "
            "'분석 실행'을 눌러 판단을 갱신하세요."
        )
        self.data_changed.emit()
        self.request_screen.emit("run_analysis")

    def _delete(self) -> None:
        ctx, e = self._ctx, self._selected
        if ctx is None or e is None:
            return
        answer = QMessageBox.question(
            self,
            "실험 삭제",
            f"'{e.title}'을(를) 삭제할까요?\n"
            + (
                "이미 등록된 근거는 함께 삭제되지 않습니다."
                if e.evidence_id
                else "되돌릴 수 없습니다."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            ctx.service.delete_experiment(e.id)
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return
        self._selected = None
        self.status_message.emit("실험을 삭제했습니다.")
        self.data_changed.emit()
