"""화면 B: 구조화 검토.

주목적 하나 — 원문을 구조화 필드로 옮기고, 규칙 엔진의 경고를 보며 다듬은 뒤 승인하는 것.

CLAUDE.md §2.2, §2.3의 규칙(넓은 타깃 금지, 사용자·구매자·영향자 분리)이
입력하는 동안 실시간으로 표시된다. 승인 전에는 분석을 실행할 수 없다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import DomainCode, Severity
from ...core.models import IdeaStructure
from ...core.rules import dedupe_warnings, detect_warnings
from ...core.domains.registry import get_domain
from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..widgets import (
    Banner,
    EmptyState,
    WarningList,
    h1,
    h2,
    hint,
    labeled_text_area,
    scrollable,
)
from .base import ScreenBase

_FIELDS: tuple[tuple[str, str, str, int], ...] = (
    ("target_user", "사용자", "상황 + 문제 + 현재 행동 + 중단 원인을 함께 적습니다. 나이·직업만으로는 부족합니다.", 80),
    ("payer", "구매자", "결제를 결정하는 사람. 사용자와 같으면 '사용자와 동일'이라고 적습니다.", 50),
    ("influencer", "영향자", "추천하거나 관리하는 사람 (교사, 팀장 등).", 50),
    ("problem_situation", "문제 상황", "언제, 무엇을 하다가 문제가 생기는지.", 90),
    ("current_solution", "현재 대체 방법", "지금은 이 문제를 어떻게 넘기고 있는지 (방치도 답입니다).", 60),
    ("current_solution_problem", "대체 방법의 한계", "시간·복잡성·실패·불안·비용 중 무엇 때문에 부족한지.", 70),
    ("core_action", "핵심 행동", "사용자가 반드시 완료해야 하는 행동 하나.", 60),
    ("expected_result", "기대 결과", "핵심 행동 후 측정 가능하게 달라지는 것 (몇 %, 몇 분, 몇 회).", 60),
    ("first_success", "첫 성공 경험", "처음 진입한 사용자가 몇 분 안에 무엇을 해내는지.", 60),
    ("retention_reason", "재방문 이유", "내일 다시 열 이유.", 60),
    ("revenue_model", "수익 모델", "누가 무엇에 지불하는지.", 50),
    ("distribution_channel", "유입 경로", "첫 100명을 어디서 데려올지.", 50),
)


class StructureReviewScreen(ScreenBase):
    title = "B. 구조화 검토"
    purpose = "원문을 구조화 필드로 옮기고 경고를 해소한 뒤 승인합니다. 승인해야 분석을 실행할 수 있습니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._editors: dict[str, object] = {}

        self.empty = EmptyState(
            "저장된 버전이 없습니다",
            "먼저 'A. 아이디어 입력'에서 원문을 저장하세요.",
        )

        # --- 좌: 편집 폼 ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 14, 12, 14)
        left_layout.addWidget(h1(self.title))
        left_layout.addWidget(hint(self.purpose))

        self.banner = Banner("", "info")
        left_layout.addWidget(self.banner)

        box = QGroupBox("구조화 결과")
        form = QFormLayout(box)
        for key, label, tip, height in _FIELDS:
            editor = labeled_text_area(tip, height)
            editor.textChanged.connect(self._schedule_validation)
            self._editors[key] = editor
            form.addRow(label, editor)
        left_layout.addWidget(box)

        row = QHBoxLayout()
        self.save_button = QPushButton("임시 저장")
        self.save_button.clicked.connect(self._save)
        self.approve_button = QPushButton("승인하고 분석 실행")
        self.approve_button.setObjectName("Primary")
        self.approve_button.clicked.connect(self._approve)
        row.addStretch(1)
        row.addWidget(self.save_button)
        row.addWidget(self.approve_button)
        left_layout.addLayout(row)
        left_layout.addStretch(1)

        # --- 우: 원문 + 경고 ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 14, 16, 14)
        right_layout.addWidget(h2("원문 (수정되지 않음)"))
        self.raw_view = QTextBrowser()
        self.raw_view.setMinimumHeight(150)
        right_layout.addWidget(self.raw_view)

        right_layout.addWidget(h2("규칙 엔진 경고"))
        right_layout.addWidget(
            hint("입력하는 동안 실시간으로 갱신됩니다. 이 경고는 AI가 아니라 규칙이 만든 것입니다.")
        )
        self.warning_list = WarningList()
        right_layout.addWidget(scrollable(self.warning_list), 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scrollable(left))
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.splitter = splitter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.empty)
        layout.addWidget(splitter)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._validate)

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        available = ctx.has_version
        self.empty.setVisible(not available)
        self.splitter.setVisible(available)
        if not available:
            return

        idea = IdeaStructure.from_dict(ctx.version.structured_idea)
        for key, _label, _tip, _h in _FIELDS:
            editor = self._editors[key]
            editor.blockSignals(True)
            editor.setPlainText(getattr(idea, key) or "")
            editor.blockSignals(False)

        raw = ctx.version.raw_input or {}
        self.raw_view.setPlainText(
            "\n".join(
                filter(
                    None,
                    [
                        f"[앱 이름] {raw.get('app_name') or '-'}",
                        f"[아이디어] {raw.get('raw_idea') or '-'}",
                        f"[예상 사용자] {raw.get('target_user_raw') or '-'}",
                        f"[문제 상황] {raw.get('problem_raw') or '-'}",
                        f"[해결 방법] {raw.get('solution_raw') or '-'}",
                        f"[수익 모델] {raw.get('revenue_model_raw') or '-'}",
                        f"[유입 경로] {raw.get('distribution_channel_raw') or '-'}",
                    ],
                )
            )
        )

        approved = ctx.version.structure_approved
        self.save_button.setEnabled(not approved)
        self.approve_button.setEnabled(True)
        self.approve_button.setText(
            "분석 다시 실행" if approved else "승인하고 분석 실행"
        )
        for editor in self._editors.values():
            editor.setReadOnly(approved)

        if approved:
            self.banner.set_text(
                f"v{ctx.version.version_no}은(는) 이미 승인되었습니다. "
                "내용을 바꾸려면 'A. 아이디어 입력'에서 새 버전을 만드세요.",
                "ok",
            )
        else:
            self.banner.set_text(
                "아직 승인되지 않았습니다. 경고를 확인하고 다듬은 뒤 승인하세요.", "info"
            )
        self._validate()

    # -- 검증 -------------------------------------------------------------
    def _schedule_validation(self) -> None:
        self._debounce.start()

    def _current_idea(self) -> IdeaStructure:
        values = {
            key: (self._editors[key].toPlainText().strip() or None)
            for key, _l, _t, _h in _FIELDS
        }
        app_name = ""
        if self._ctx and self._ctx.version:
            app_name = (self._ctx.version.structured_idea or {}).get("app_name", "")
        return IdeaStructure(
            app_name=app_name,
            target_user=values["target_user"] or "",
            payer=values["payer"],
            influencer=values["influencer"],
            problem_situation=values["problem_situation"] or "",
            current_solution=values["current_solution"],
            current_solution_problem=values["current_solution_problem"],
            core_action=values["core_action"] or "",
            expected_result=values["expected_result"] or "",
            first_success=values["first_success"],
            retention_reason=values["retention_reason"],
            revenue_model=values["revenue_model"],
            distribution_channel=values["distribution_channel"],
        )

    def _validate(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None:
            return
        idea = self._current_idea()
        domain_code = ctx.project.domain_code
        # 분석 파이프라인과 동일한 규칙·동일한 중복 제거를 쓴다.
        # 여기 결과와 분석 결과가 달라지면 사용자가 시스템을 믿지 못한다.
        warnings = dedupe_warnings(
            detect_warnings(idea, DomainCode(domain_code))
            + get_domain(domain_code).validate_input(idea)
        )
        self.warning_list.set_warnings([w.to_dict() for w in warnings])

        criticals = sum(1 for w in warnings if w.severity == Severity.CRITICAL)
        if criticals and not (ctx.version and ctx.version.structure_approved):
            self.banner.set_text(
                f"치명 경고 {criticals}건이 남아 있습니다. 승인해도 분석은 되지만 "
                "판단이 HOLD로 나올 가능성이 높습니다.",
                "critical",
            )

    # -- 동작 -------------------------------------------------------------
    def _save(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.version is None:
            return
        try:
            ctx.service.update_version(ctx.version.id, idea=self._current_idea())
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return
        self.status_message.emit("구조화 결과를 저장했습니다.")
        self.data_changed.emit()

    def _approve(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.version is None:
            return

        if not ctx.version.structure_approved:
            idea = self._current_idea()
            criticals = [
                w
                for w in dedupe_warnings(
                    detect_warnings(idea, DomainCode(ctx.project.domain_code))
                    + get_domain(ctx.project.domain_code).validate_input(idea)
                )
                if w.severity == Severity.CRITICAL
            ]
            if criticals:
                answer = QMessageBox.question(
                    self,
                    "치명 경고가 남아 있습니다",
                    f"치명 경고 {len(criticals)}건이 해소되지 않았습니다.\n\n"
                    + "\n".join(f"· {w.message}" for w in criticals[:5])
                    + "\n\n승인하면 이 버전은 더 이상 수정할 수 없습니다. 계속할까요?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return
            try:
                ctx.service.update_version(ctx.version.id, idea=idea)
                ctx.service.approve_structure(ctx.version.id)
            except ServiceError as exc:
                self.banner.set_text(str(exc), "critical")
                return

        self.data_changed.emit()
        self.request_screen.emit("run_analysis")
