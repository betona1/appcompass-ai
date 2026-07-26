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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import DomainCode, Severity
from ...core.models import IdeaStructure, RawIdeaInput
from ...core.rules import dedupe_warnings, detect_warnings, missing_required_fields
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
    purpose = (
        "원문을 구조화 필드로 옮기고 경고를 해소한 뒤 승인합니다. "
        "빨간 별표(*)가 붙은 항목은 필수이며, 채워야 승인·분석이 가능합니다."
    )

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

        self.required_banner = Banner("", "critical")
        left_layout.addWidget(self.required_banner)

        box = QGroupBox("구조화 결과")
        form = QFormLayout(box)
        self._field_labels: dict[str, QLabel] = {}
        for key, label, tip, height in _FIELDS:
            editor = labeled_text_area(tip, height)
            editor.textChanged.connect(self._schedule_validation)
            self._editors[key] = editor
            field_label = QLabel(label)
            field_label.setWordWrap(True)
            self._field_labels[key] = field_label
            form.addRow(field_label, editor)
        left_layout.addWidget(box)

        row = QHBoxLayout()
        # 승인된 버전을 고치려면 새 버전이 필요하다.
        # 구매자·첫 성공 경험·재방문 이유는 이 화면에만 있는 항목이라
        # 이 버튼이 없으면 승인 후 고칠 방법이 사실상 없다.
        self.new_version_button = QPushButton("이 내용으로 새 버전 만들어 수정하기")
        self.new_version_button.setObjectName("Primary")
        self.new_version_button.clicked.connect(self._create_new_version)
        self.save_button = QPushButton("임시 저장")
        self.save_button.clicked.connect(self._save)
        self.approve_button = QPushButton("승인하고 분석 실행")
        self.approve_button.setObjectName("Primary")
        self.approve_button.clicked.connect(self._approve)
        row.addStretch(1)
        row.addWidget(self.new_version_button)
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

        self._apply_required_marks()

        approved = ctx.version.structure_approved
        self.save_button.setVisible(not approved)
        self.new_version_button.setVisible(approved)
        self.approve_button.setText(
            "분석 다시 실행" if approved else "승인하고 분석 실행"
        )
        for editor in self._editors.values():
            editor.setReadOnly(approved)
            # 읽기 전용인데 겉모습이 같으면 사용자는 입력이 고장 났다고 생각한다.
            editor.style().unpolish(editor)
            editor.style().polish(editor)

        if approved:
            self.banner.set_text(
                f"v{ctx.version.version_no}은(는) 승인되어 잠겨 있습니다. "
                "무엇이 언제 왜 바뀌었는지 추적하기 위해 승인된 버전은 고치지 않습니다. "
                "수정하려면 아래 '새 버전 만들어 수정하기'를 누르세요.",
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

    def _required_spec(self) -> tuple[tuple[str, str, str], ...]:
        """공통 필수 항목 + 도메인 필수 항목."""
        from ...core.rules import REQUIRED_STRUCTURE_FIELDS

        ctx = self._ctx
        extra = ()
        if ctx is not None and ctx.project is not None:
            extra = get_domain(ctx.project.domain_code).required_fields()
        return tuple(REQUIRED_STRUCTURE_FIELDS) + tuple(extra)

    def _apply_required_marks(self) -> None:
        """필수 항목 라벨에 * 를 붙인다. 어디를 채워야 하는지 한눈에 보이게."""
        required_keys = {k for k, _l, _w in self._required_spec()}
        for key, label, _tip, _h in _FIELDS:
            widget = self._field_labels.get(key)
            if widget is None:
                continue
            if key in required_keys:
                widget.setText(f"{label} <span style='color:#b3261e'>*</span>")
                widget.setToolTip("필수 항목입니다. 채워야 승인할 수 있습니다.")
            else:
                widget.setText(label)
                widget.setToolTip("")

    def _validate(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.project is None:
            return
        idea = self._current_idea()
        domain_code = ctx.project.domain_code

        # --- 필수 항목 ---
        missing = missing_required_fields(
            idea, get_domain(domain_code).required_fields()
        )
        approved = bool(ctx.version and ctx.version.structure_approved)
        self.required_banner.setVisible(bool(missing) and not approved)
        if missing and not approved:
            self.required_banner.set_text(
                "필수 항목 "
                + f"{len(missing)}개가 비어 있어 승인할 수 없습니다 — "
                + ", ".join(label for _k, label, _w in missing)
                + "\n"
                + "\n".join(f"· {label}: {why}" for _k, label, why in missing),
                "critical",
            )
        self.approve_button.setEnabled(approved or not missing)
        self.approve_button.setToolTip(
            ""
            if (approved or not missing)
            else "필수 항목을 모두 채워야 승인할 수 있습니다: "
            + ", ".join(label for _k, label, _w in missing)
        )
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

    def _create_new_version(self) -> None:
        """승인된 버전의 내용을 그대로 복사해 수정 가능한 새 버전을 만든다.

        원문(raw_input)은 그대로 물려받는다. 여기서 바꾸는 것은 구조화 결과뿐이며,
        A화면의 원문을 건드리지 않는다.
        """
        ctx = self._ctx
        if ctx is None or ctx.version is None or ctx.project is None:
            return

        reason, ok = QInputDialog.getText(
            self,
            "새 버전 만들기",
            "이 버전을 만드는 이유를 적으세요.\n"
            "(버전 비교 화면에서 '왜 바뀌었는지'를 추적하는 데 쓰입니다)",
            text=f"v{ctx.version.version_no} 구조화 결과 보완",
        )
        if not ok:
            return

        try:
            version = ctx.service.create_version(
                ctx.project.id,
                RawIdeaInput.from_dict(ctx.version.raw_input),
                self._current_idea(),
                change_reason=reason,
            )
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return

        self.status_message.emit(
            f"v{version.version_no}을(를) 만들었습니다. 이제 수정할 수 있습니다."
        )
        self.data_changed.emit()

    def _approve(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.version is None:
            return

        if not ctx.version.structure_approved:
            idea = self._current_idea()

            # 버튼이 비활성이지만 단축키·자동화 경로로 들어올 수 있다.
            missing = missing_required_fields(
                idea, get_domain(ctx.project.domain_code).required_fields()
            )
            if missing:
                QMessageBox.warning(
                    self,
                    "필수 항목이 비어 있습니다",
                    "아래 항목을 채워야 승인할 수 있습니다.\n\n"
                    + "\n".join(f"· {label} — {why}" for _k, label, why in missing),
                )
                return

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
