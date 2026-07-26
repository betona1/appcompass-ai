"""화면 H: 버전 비교.

주목적 하나 — 무엇이 왜 바뀌었고 그 결과 판단이 어떻게 달라졌는지 보는 것.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...services.app_service import ServiceError
from ..context import ScreenContext
from ..widgets import Banner, EmptyState, h1, hint
from .base import ScreenBase


class VersionsScreen(ScreenBase):
    title = "H. 버전 비교"
    purpose = "이전 버전과 현재 버전의 차이, 그리고 점수·판단의 변화를 확인합니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._loading = False

        self.empty = EmptyState(
            "비교할 버전이 2개 이상 필요합니다",
            "'A. 아이디어 입력'에서 내용을 수정해 새 버전을 만드세요.",
        )

        self.body = QWidget()
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        picker = QHBoxLayout()
        picker.addWidget(QLabel("이전"))
        self.left_combo = QComboBox()
        self.left_combo.currentIndexChanged.connect(self._compare)
        picker.addWidget(self.left_combo, 1)
        picker.addWidget(QLabel("→ 현재"))
        self.right_combo = QComboBox()
        self.right_combo.currentIndexChanged.connect(self._compare)
        picker.addWidget(self.right_combo, 1)
        layout.addLayout(picker)

        self.banner = Banner("", "info")
        layout.addWidget(self.banner)

        box = QGroupBox("변경 내용")
        b_layout = QVBoxLayout(box)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["항목", "변경", "이전", "현재"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        b_layout.addWidget(self.table)
        layout.addWidget(box, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.empty)
        outer.addWidget(self.body)

    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        if not ctx.has_project:
            self.empty.setVisible(True)
            self.body.setVisible(False)
            return

        versions = ctx.service.list_versions(ctx.project.id)
        enough = len(versions) >= 2
        self.empty.setVisible(not enough)
        self.body.setVisible(enough)
        if not enough:
            return

        self._loading = True
        for combo in (self.left_combo, self.right_combo):
            combo.clear()
            for v in versions:  # 최신 버전이 앞에 온다
                approved = "승인" if v.structure_approved else "미승인"
                combo.addItem(f"v{v.version_no} ({approved})", v.id)
        # 기본값: 직전 버전 → 최신 버전
        self.left_combo.setCurrentIndex(1)
        self.right_combo.setCurrentIndex(0)
        self._loading = False
        self._compare()

    def _compare(self) -> None:
        if self._loading or self._ctx is None:
            return
        left = self.left_combo.currentData()
        right = self.right_combo.currentData()
        if not left or not right:
            return
        if left == right:
            self.banner.set_text("같은 버전을 선택했습니다. 다른 버전을 고르세요.", "info")
            self.table.setRowCount(0)
            return

        try:
            rows = self._ctx.service.diff_versions(left, right)
        except ServiceError as exc:
            self.banner.set_text(str(exc), "critical")
            return

        changed = sum(1 for r in rows if r.changed)
        self.banner.set_text(
            f"{changed}개 항목이 변경되었습니다."
            if changed
            else "두 버전의 내용이 동일합니다.",
            "info",
        )

        self.table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for i, row in enumerate(rows):
            label_item = QTableWidgetItem(row.label)
            mark_item = QTableWidgetItem("● 변경됨" if row.changed else "· 동일")
            if row.changed:
                label_item.setFont(bold)
                mark_item.setForeground(QColor("#2f6fed"))
            self.table.setItem(i, 0, label_item)
            self.table.setItem(i, 1, mark_item)
            self.table.setItem(i, 2, QTableWidgetItem(row.before))
            self.table.setItem(i, 3, QTableWidgetItem(row.after))
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        for col in (2, 3):
            if self.table.columnWidth(col) > 380:
                self.table.setColumnWidth(col, 380)
