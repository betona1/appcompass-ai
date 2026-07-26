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
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import ReportFormat
from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..widgets import Banner, BulletList, EmptyState, h1, h2, hint
from .base import ScreenBase


class ReportScreen(ScreenBase):
    title = "G. 피벗 보고서"
    purpose = "판단·유지·변경·삭제와 다음 실험을 문서로 확인하고 내보냅니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None

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
            box_layout.addWidget(widget)
            box_layout.addStretch(1)
            kcr.addWidget(box, 1)
        layout.addLayout(kcr)

        preview_box = QGroupBox("보고서 미리보기")
        p_layout = QVBoxLayout(preview_box)

        control = QHBoxLayout()
        control.addWidget(QLabel("형식"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("Markdown", str(ReportFormat.MARKDOWN))
        self.format_combo.addItem("HTML", str(ReportFormat.HTML))
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

        try:
            self._reports = {r.format: r for r in ctx.service.get_reports(ctx.run.id)}
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            self._reports = {}
        self._render_preview()

    def _render_preview(self) -> None:
        fmt = self.format_combo.currentData()
        report = self._reports.get(fmt)
        if report is None:
            self.preview.setPlainText("이 형식의 보고서가 없습니다.")
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
        fmt = self.format_combo.currentData()
        suffix = ".md" if fmt == str(ReportFormat.MARKDOWN) else ".html"
        default_name = (
            f"{(ctx.project.name if ctx.project else 'appcompass')}"
            f"_v{ctx.run.version_no}{suffix}"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "보고서 내보내기",
            default_name,
            f"보고서 (*{suffix})",
        )
        if not path:
            return
        try:
            ctx.service.export_report(ctx.run.id, ReportFormat(fmt), path)
        except (ServiceError, OSError) as exc:
            self.banner.set_text(f"내보내기 실패: {exc}", "critical")
            return
        self.status_message.emit(f"보고서를 저장했습니다: {path}")
