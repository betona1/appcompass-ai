"""화면 G: 피벗 보고서.

주목적 하나 — 판단 결과를 문서로 확인하고 내보내는 것.
보고서는 분석 시점에 고정되며 나중에 수정하지 않는다 (TECHSPEC F-100).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import (
    APPROVAL_STATUS_LABELS,
    REPORT_FORMAT_LABELS,
    REPORT_FORMAT_SUFFIX,
    ApprovalStatus,
    ReportFormat,
)
from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..theme import decision_label
from ..widgets import Banner, BulletList, EmptyState, h1, h2, hint, scrollable
from .base import ScreenBase


class ReportScreen(ScreenBase):
    title = "G. 피벗 보고서"
    purpose = "판단·유지·변경·삭제와 다음 실험을 문서로 확인하고 내보냅니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._decision = None

        self.empty = EmptyState(
            "보고서가 없습니다", "분석을 실행하면 Markdown/HTML 보고서가 함께 생성됩니다."
        )

        self.body = QWidget()
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        self.banner = Banner("", "info")
        layout.addWidget(self.banner)

        # --- 사람의 승인 (TECHSPEC F-090) ---
        approval_box = QGroupBox("사람의 결정")
        a_layout = QVBoxLayout(approval_box)
        a_layout.addWidget(
            hint(
                "시스템은 판단을 제안할 뿐 적용하지 않습니다. 승인하거나 거절하면 기록으로 남습니다.\n"
                "거절할 때는 사유가 필요합니다 — 왜 다르게 판단했는지 남겨야 나중에 되짚을 수 있습니다."
            )
        )
        self.approval_state = QLabel("-")
        self.approval_state.setWordWrap(True)
        a_layout.addWidget(self.approval_state)

        self.approval_note = QLineEdit()
        self.approval_note.setPlaceholderText(
            "결정 사유 (거절 시 필수, 승인 시 선택) — 예: 타깃 피벗 대신 문제 정의부터 다시 하기로 함"
        )
        a_layout.addWidget(self.approval_note)

        a_row = QHBoxLayout()
        a_row.addStretch(1)
        self.reject_button = QPushButton("거절")
        self.reject_button.setObjectName("Danger")
        self.reject_button.clicked.connect(self._reject)
        self.approve_button = QPushButton("승인")
        self.approve_button.setObjectName("Primary")
        self.approve_button.clicked.connect(self._approve)
        a_row.addWidget(self.reject_button)
        a_row.addWidget(self.approve_button)
        a_layout.addLayout(a_row)

        a_layout.addWidget(h2("판단 이력"))
        self.history = BulletList([], "아직 판단 이력이 없습니다")
        a_layout.addWidget(self.history)
        layout.addWidget(approval_box)

        kcr = QHBoxLayout()
        for title, attr, empty in (
            ("유지", "keep", "유지 항목 없음"),
            ("변경", "change", "변경 항목 없음"),
            ("삭제", "remove", "삭제 항목 없음"),
        ):
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            widget = BulletList([], empty)
            setattr(self, attr, widget)
            # 항목이 길어 고정 높이에 넣으면 잘린다. 내용을 줄이는 대신 스크롤한다.
            area = scrollable(widget)
            area.setMinimumHeight(210)
            box_layout.addWidget(area)
            kcr.addWidget(box, 1)
        layout.addLayout(kcr)

        preview_box = QGroupBox("보고서 미리보기")
        p_layout = QVBoxLayout(preview_box)

        control = QHBoxLayout()
        control.addWidget(QLabel("형식"))
        self.format_combo = QComboBox()
        for fmt in (
            ReportFormat.MARKDOWN,
            ReportFormat.HTML,
            ReportFormat.TECHSPEC,
            ReportFormat.IMPROVEMENT,
            ReportFormat.XLSX,
        ):
            self.format_combo.addItem(REPORT_FORMAT_LABELS[fmt], str(fmt))
        self.format_combo.currentIndexChanged.connect(self._render_preview)
        control.addWidget(self.format_combo)
        control.addStretch(1)
        self.checksum_label = QLabel("-")
        self.checksum_label.setObjectName("Hint")
        control.addWidget(self.checksum_label)
        self.export_button = QPushButton("파일로 내보내기")
        self.export_button.setObjectName("Primary")
        self.export_button.clicked.connect(self._export)
        control.addWidget(self.export_button)
        p_layout.addLayout(control)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setMinimumHeight(420)
        p_layout.addWidget(self.preview)
        layout.addWidget(preview_box, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.empty)
        outer.addWidget(self.body)

        self._reports: dict[str, object] = {}

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        result = ctx.result
        self.empty.setVisible(result is None)
        self.body.setVisible(result is not None)
        if result is None or ctx.run is None:
            return

        pivot = result["pivot"]
        self.keep.set_items(pivot["keep"])
        self.change.set_items(pivot["change"])
        self.remove.set_items(pivot["remove"])

        approval = (
            "이 판단은 사람의 승인이 필요합니다. 시스템이 자동으로 적용하지 않습니다."
            if pivot["requires_human_approval"]
            else "자동 적용 가능한 판단입니다."
        )
        self.banner.set_text(
            f"v{ctx.run.version_no} 기준 · {pivot['decision']} · "
            f"신뢰도 {pivot['confidence']:.2f} · {approval}",
            "critical" if pivot["decision"] == "HOLD" else "ok",
        )

        self._render_approval(ctx)

        try:
            self._reports = {r.format: r for r in ctx.service.get_reports(ctx.run.id)}
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            self._reports = {}
        self._render_preview()

    # -- 승인 -------------------------------------------------------------
    def _render_approval(self, ctx: ScreenContext) -> None:
        self._decision = None
        history = ctx.service.list_pivot_decisions(ctx.project.id)

        # 지금 보고 있는 분석의 판단만 승인 대상이다.
        self._decision = next(
            (d for d in history if d.run_id == ctx.run.id), None
        )

        if self._decision is None:
            self.approval_state.setText(
                "이 분석에는 판단 기록이 없습니다. '분석 실행'을 다시 누르면 생성됩니다."
            )
            self.approve_button.setEnabled(False)
            self.reject_button.setEnabled(False)
            self.approval_note.setEnabled(False)
        else:
            d = self._decision
            status = ApprovalStatus(d.approval_status)
            pending = status == ApprovalStatus.PENDING
            self.approve_button.setEnabled(pending)
            self.reject_button.setEnabled(pending)
            self.approval_note.setEnabled(pending)
            self.approval_note.setText("" if pending else d.approval_note)

            if pending:
                self.approval_state.setText(
                    f"<b>검토 대기</b> — 시스템 판단 {decision_label(d.decision)} 에 대해 "
                    "승인 또는 거절해 주세요."
                )
            else:
                when = d.approved_at.strftime("%Y-%m-%d %H:%M") if d.approved_at else "-"
                note = f"<br>사유: {d.approval_note}" if d.approval_note else ""
                self.approval_state.setText(
                    f"<b>{APPROVAL_STATUS_LABELS[status]}</b> ({when}) — "
                    f"{decision_label(d.decision)}{note}"
                )

        items: list[str] = []
        for d in history:
            status = ApprovalStatus(d.approval_status)
            when = d.created_at.strftime("%m-%d %H:%M")
            line = (
                f"{when}  v{d.version_no}  {decision_label(d.decision)}  "
                f"(신뢰도 {d.confidence:.2f}, 총점 {d.total_score:.1f})  "
                f"→ {APPROVAL_STATUS_LABELS[status]}"
            )
            if d.approval_note:
                line += f"  — {d.approval_note}"
            items.append(line)
        self.history.set_items(items)

    def _approve(self) -> None:
        if self._ctx is None or self._decision is None:
            return
        try:
            self._ctx.service.approve_pivot(
                self._decision.id, self.approval_note.text()
            )
        except ServiceError as exc:
            QMessageBox.warning(self, "승인할 수 없습니다", str(exc))
            return
        self.status_message.emit("판단을 승인했습니다.")
        self.data_changed.emit()

    def _reject(self) -> None:
        if self._ctx is None or self._decision is None:
            return
        try:
            self._ctx.service.reject_pivot(
                self._decision.id, self.approval_note.text()
            )
        except ServiceError as exc:
            QMessageBox.warning(self, "거절할 수 없습니다", str(exc))
            return
        self.status_message.emit("판단을 거절했습니다. 사유가 기록되었습니다.")
        self.data_changed.emit()

    def _render_preview(self) -> None:
        fmt = self.format_combo.currentData()

        if fmt == str(ReportFormat.XLSX):
            # 엑셀은 미리보기를 만들 수 없다. 무엇이 들어가는지라도 알려 준다.
            self.export_button.setEnabled(self._ctx is not None and self._ctx.run is not None)
            self.checksum_label.setText("내보낼 때 생성됩니다")
            self.preview.setPlainText(
                "작업용 엑셀 (.xlsx)\n"
                "─────────────────────────────────────────\n"
                "미리보기를 제공하지 않습니다. 내보낸 뒤 엑셀에서 여세요.\n\n"
                "시트 구성\n"
                "  요약           총점·신뢰도·판단·엔진/정책 버전\n"
                "  평가 점수      10개 항목, 점수 이유, 부족한 근거 (정렬·필터용)\n"
                "  경고           심각도·코드·권장 행동\n"
                "  할 일          다음 행동·유지·변경·삭제·언노운 (담당/기한 칸 비어 있음)\n"
                "  타깃 후보      후보별 사용자·구매자·위험·검증 질문\n"
                "  MVP 백로그     P0/P1/제외 기능에 ID 부여 (담당·규모·완료 기준 칸 비어 있음)\n"
                "  MVP 가설·흐름  가설, 사용자 흐름, 위험\n"
                "  측정 이벤트    이벤트 목록 (발생 시점·속성 칸 비어 있음)\n"
                "  근거           등록된 근거 전체\n\n"
                "빈 칸은 사람이 채우라고 일부러 비워 둔 것입니다."
            )
            return

        if fmt == str(ReportFormat.IMPROVEMENT):
            # 구현 상태가 바뀌면 내용이 달라지므로 볼 때마다 새로 만든다.
            if self._ctx is None or self._ctx.run is None:
                self.preview.setPlainText("분석 결과가 없습니다.")
                self.export_button.setEnabled(False)
                return
            try:
                content = self._ctx.service.build_improvement(self._ctx.run.id)
            except ServiceError as exc:
                self.preview.setPlainText(str(exc))
                self.export_button.setEnabled(False)
                return
            self.preview.setPlainText(content)
            self.checksum_label.setText("구현 상태에 따라 매번 새로 생성됩니다")
            self.export_button.setEnabled(True)
            return

        report = self._reports.get(fmt)
        if report is None:
            self.preview.setPlainText(
                "이 형식의 보고서가 없습니다.\n"
                "이전 버전에서 만든 분석이라면 '분석 실행'을 다시 눌러 생성하세요."
            )
            self.checksum_label.setText("-")
            self.export_button.setEnabled(False)
            return

        self.export_button.setEnabled(True)
        self.checksum_label.setText(f"checksum {report.checksum[:12]}…")
        if fmt == str(ReportFormat.HTML):
            self.preview.setHtml(report.content)
        else:
            self.preview.setPlainText(report.content)

    # -- 동작 -------------------------------------------------------------
    def _export(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.run is None:
            return
        fmt = ReportFormat(self.format_combo.currentData())
        suffix = REPORT_FORMAT_SUFFIX[fmt]
        default_name = (
            f"{(ctx.project.name if ctx.project else 'appcompass')}"
            f"_v{ctx.run.version_no}{suffix}"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"{REPORT_FORMAT_LABELS[fmt]} 내보내기",
            default_name,
            f"{REPORT_FORMAT_LABELS[fmt]} (*{suffix.split('.')[-1]});;모든 파일 (*)",
        )
        if not path:
            return
        try:
            ctx.service.export_report(ctx.run.id, fmt, path)
        except (ServiceError, OSError) as exc:
            self.banner.set_text(f"내보내기 실패: {exc}", "critical")
            return
        self.status_message.emit(f"{REPORT_FORMAT_LABELS[fmt]} 저장 완료: {path}")
