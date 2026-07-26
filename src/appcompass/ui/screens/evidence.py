"""화면: 근거 등록.

주목적 하나 — 실제 근거를 등록해 판단의 신뢰도를 올리는 것.

CLAUDE.md §11: "AI는 근거를 생성하지 않는다. AI는 등록된 근거를 요약하고 해석한다."
따라서 이 화면에는 자동 생성 버튼이 없다. 전부 사람이 입력한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.domains.registry import get_domain
from ...core.enums import DIMENSION_LABELS, DimensionCode, EvidenceType
from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..widgets import Banner, EmptyState, h1, h2, hint, labeled_text_area, scrollable
from .base import ScreenBase

EVIDENCE_LABELS: dict[EvidenceType, str] = {
    EvidenceType.FOUNDER_ASSUMPTION: "창업자 가정 (가장 약함)",
    EvidenceType.DESK_RESEARCH: "데스크 리서치",
    EvidenceType.USER_INTERVIEW: "사용자 인터뷰",
    EvidenceType.PROTOTYPE_TEST: "프로토타입 테스트",
    EvidenceType.BEHAVIOR_DATA: "실제 행동 데이터 (가장 강함)",
    EvidenceType.EXPERT_REVIEW: "전문가 검토",
}


class EvidenceScreen(ScreenBase):
    title = "근거"
    purpose = "AI는 근거를 만들지 않습니다. 여기 등록된 것만 신뢰도에 반영됩니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._support_boxes: dict[DimensionCode, QCheckBox] = {}
        self._contradict_boxes: dict[DimensionCode, QCheckBox] = {}

        self.empty = EmptyState(
            "선택된 프로젝트가 없습니다", "왼쪽에서 프로젝트를 선택하세요."
        )

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        self.banner = Banner("", "info")
        layout.addWidget(self.banner)

        # --- 등록 폼 ---
        form_box = QGroupBox("근거 등록")
        form_layout = QVBoxLayout(form_box)
        form = QFormLayout()

        self.type_combo = QComboBox()
        for etype, label in EVIDENCE_LABELS.items():
            self.type_combo.addItem(label, etype)
        self.type_combo.currentIndexChanged.connect(self._update_confidence_hint)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("예: 비개발자 6명 인터뷰 (2026-01)")
        self.summary_edit = labeled_text_area(
            "무엇을 관찰했는지. 해석이 아니라 관찰된 사실을 적습니다.", 80
        )
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("출처 또는 원본 위치 (파일명, URL, 노트 등)")

        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(0, 1_000_000)
        self.sample_spin.setSpecialValueText("미기재")

        self.observed_edit = QDateEdit()
        self.observed_edit.setCalendarPopup(True)
        self.observed_edit.setDate(QDate.currentDate())

        override_row = QWidget()
        override_layout = QHBoxLayout(override_row)
        override_layout.setContentsMargins(0, 0, 0, 0)
        self.override_check = QCheckBox("신뢰도 직접 지정")
        self.override_spin = QDoubleSpinBox()
        self.override_spin.setRange(0.0, 1.0)
        self.override_spin.setSingleStep(0.05)
        self.override_spin.setValue(0.5)
        self.override_spin.setEnabled(False)
        self.override_check.toggled.connect(self.override_spin.setEnabled)
        override_layout.addWidget(self.override_check)
        override_layout.addWidget(self.override_spin)
        override_layout.addStretch(1)

        self.confidence_hint = QLabel("-")
        self.confidence_hint.setObjectName("Hint")

        form.addRow("근거 유형", self.type_combo)
        form.addRow("", self.confidence_hint)
        form.addRow("제목", self.title_edit)
        form.addRow("요약", self.summary_edit)
        form.addRow("출처", self.source_edit)
        form.addRow("표본 수", self.sample_spin)
        form.addRow("관측 시각", self.observed_edit)
        form.addRow("신뢰도", override_row)
        form_layout.addLayout(form)

        form_layout.addWidget(h2("이 근거가 지지하는 평가 항목"))
        form_layout.addWidget(
            hint("하나 이상 선택해야 저장됩니다. 어떤 항목의 신뢰도를 올릴지 정하는 것입니다.")
        )
        form_layout.addWidget(self._build_dimension_grid(self._support_boxes))

        form_layout.addWidget(h2("이 근거가 반박하는 평가 항목"))
        form_layout.addWidget(
            hint("지지와 반박이 함께 있으면 신뢰도를 낮추고 상충 경고를 표시합니다.")
        )
        form_layout.addWidget(self._build_dimension_grid(self._contradict_boxes))

        row = QHBoxLayout()
        self.example_button = QPushButton("예시로 양식 채우기 ▾")
        self.example_menu = QMenu(self.example_button)
        self.example_button.setMenu(self.example_menu)
        self.example_button.setToolTip(
            "양식을 어떻게 쓰는지 보여주는 예시입니다. 근거가 아닙니다.\n"
            "채운 뒤 실제로 관찰한 내용으로 바꿔서 등록하세요."
        )
        self.clear_button = QPushButton("양식 비우기")
        self.clear_button.clicked.connect(self._clear_form)
        row.addWidget(self.example_button)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        self.add_button = QPushButton("근거 등록")
        self.add_button.setObjectName("Primary")
        self.add_button.clicked.connect(self._add)
        row.addWidget(self.add_button)
        form_layout.addLayout(row)
        layout.addWidget(form_box)

        # --- 목록 ---
        list_box = QGroupBox("등록된 근거")
        list_layout = QVBoxLayout(list_box)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["유형", "제목", "표본", "신뢰도", "지지", "반박", "출처"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(200)
        list_layout.addWidget(self.table)

        del_row = QHBoxLayout()
        del_row.addStretch(1)
        self.delete_button = QPushButton("선택한 근거 삭제")
        self.delete_button.setObjectName("Danger")
        self.delete_button.clicked.connect(self._delete)
        del_row.addWidget(self.delete_button)
        list_layout.addLayout(del_row)
        layout.addWidget(list_box)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scrollable(inner)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll)

        self._update_confidence_hint()

    @staticmethod
    def _build_dimension_grid(store: dict[DimensionCode, QCheckBox]) -> QWidget:
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, code in enumerate(DimensionCode):
            box = QCheckBox(f"{code} {DIMENSION_LABELS[code]}")
            store[code] = box
            grid.addWidget(box, i // 3, i % 3)
        return holder

    # -- 예시 -------------------------------------------------------------
    def _rebuild_example_menu(self, domain_code: str) -> None:
        """도메인에 맞는 예시 목록을 메뉴에 채운다."""
        self.example_menu.clear()
        examples = get_domain(domain_code).evidence_examples()
        for ex in examples:
            action = self.example_menu.addAction(ex.label)
            action.setToolTip(ex.note)
            action.triggered.connect(lambda _=False, e=ex: self._fill_example(e))
        self.example_button.setEnabled(bool(examples))

    def _fill_example(self, example) -> None:
        """예시로 양식을 채운다. 등록은 하지 않는다."""
        index = self.type_combo.findData(example.evidence_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.title_edit.setText(example.title)
        self.summary_edit.setPlainText(example.summary)
        self.source_edit.setText(example.source_reference or "")
        self.sample_spin.setValue(example.sample_size or 0)
        self.override_check.setChecked(False)

        for code, box in self._support_boxes.items():
            box.setChecked(code in example.supports)
        for code, box in self._contradict_boxes.items():
            box.setChecked(code in example.contradicts)

        self.banner.set_text(
            "예시로 양식을 채웠습니다. 이건 근거가 아니라 '이렇게 쓰세요'라는 예시입니다.\n"
            "실제로 관찰하거나 들은 내용으로 바꾼 뒤 등록하세요. "
            "예시 그대로 등록하면 자기 진단을 스스로 속이는 셈이 되어 판단이 무의미해집니다."
            + (f"\n\n· {example.note}" if example.note else ""),
            "critical",
        )

    def _clear_form(self) -> None:
        self.title_edit.clear()
        self.summary_edit.clear()
        self.source_edit.clear()
        self.sample_spin.setValue(0)
        self.override_check.setChecked(False)
        for box in list(self._support_boxes.values()) + list(self._contradict_boxes.values()):
            box.setChecked(False)
        self.banner.set_text("양식을 비웠습니다.", "info")

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        self.empty.setVisible(not ctx.has_project)
        self.scroll.setVisible(ctx.has_project)
        if not ctx.has_project:
            return

        self._rebuild_example_menu(ctx.project.domain_code)

        items = ctx.service.list_evidence(ctx.project.id)
        self.table.setRowCount(len(items))
        for i, e in enumerate(items):
            self.table.setItem(i, 0, QTableWidgetItem(EVIDENCE_LABELS.get(
                EvidenceType(e.evidence_type), e.evidence_type)))
            title_item = QTableWidgetItem(e.title)
            title_item.setData(Qt.UserRole, e.id)
            self.table.setItem(i, 1, title_item)
            self.table.setItem(
                i, 2, QTableWidgetItem(str(e.sample_size) if e.sample_size else "-")
            )
            self.table.setItem(
                i, 3, QTableWidgetItem(f"{e.effective_confidence:.2f}")
            )
            self.table.setItem(i, 4, QTableWidgetItem(", ".join(e.supports) or "-"))
            self.table.setItem(i, 5, QTableWidgetItem(", ".join(e.contradicts) or "-"))
            self.table.setItem(i, 6, QTableWidgetItem(e.source_reference or "-"))
        self.table.resizeColumnsToContents()
        self.delete_button.setEnabled(bool(items))

        if not items:
            self.banner.set_text(
                "등록된 근거가 없습니다. 근거가 없으면 모든 항목의 신뢰도가 0.20으로 "
                "고정되고 판단은 HOLD가 됩니다.",
                "critical",
            )
        else:
            self.banner.set_text(
                f"근거 {len(items)}건이 등록되어 있습니다. 근거를 추가하거나 삭제하면 "
                "분석을 다시 실행해야 판단에 반영됩니다.",
                "ok",
            )

    def _update_confidence_hint(self) -> None:
        from ...core.policy import DEFAULT_EVIDENCE_CONFIDENCE

        etype = self.type_combo.currentData()
        if etype is None:
            return
        value = DEFAULT_EVIDENCE_CONFIDENCE.get(etype, 0.0)
        self.confidence_hint.setText(
            f"기본 신뢰도 {value:.2f} (정책 화면에서 변경 가능). "
            "표본이 3명 미만이면 계산 시 추가로 낮아집니다."
        )

    # -- 동작 -------------------------------------------------------------
    def _add(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None:
            return
        supports = [c for c, box in self._support_boxes.items() if box.isChecked()]
        contradicts = [c for c, box in self._contradict_boxes.items() if box.isChecked()]
        qdate = self.observed_edit.date()
        observed = datetime(
            qdate.year(), qdate.month(), qdate.day(), tzinfo=timezone.utc
        )
        try:
            ctx.service.add_evidence(
                ctx.project.id,
                evidence_type=self.type_combo.currentData(),
                title=self.title_edit.text(),
                summary=self.summary_edit.toPlainText(),
                source_reference=self.source_edit.text(),
                sample_size=self.sample_spin.value() or None,
                observed_at=observed,
                confidence_override=(
                    self.override_spin.value() if self.override_check.isChecked() else None
                ),
                supports=supports,
                contradicts=contradicts,
            )
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return

        self.title_edit.clear()
        self.summary_edit.clear()
        self.source_edit.clear()
        self.sample_spin.setValue(0)
        for box in list(self._support_boxes.values()) + list(self._contradict_boxes.values()):
            box.setChecked(False)
        self.status_message.emit("근거를 등록했습니다. 분석을 다시 실행하세요.")
        self.data_changed.emit()

    def _delete(self) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        row = self.table.currentRow()
        if row < 0:
            self.banner.set_text("삭제할 근거를 목록에서 선택하세요.", "info")
            return
        item = self.table.item(row, 1)
        evidence_id = item.data(Qt.UserRole)
        answer = QMessageBox.question(
            self,
            "근거 삭제",
            f"'{item.text()}'을(를) 삭제할까요?\n삭제 기록은 감사 로그에 남습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            ctx.service.delete_evidence(evidence_id)
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return
        self.status_message.emit("근거를 삭제했습니다.")
        self.data_changed.emit()
