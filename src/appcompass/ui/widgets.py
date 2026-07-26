"""공통 위젯.

로딩·오류·빈 상태를 매 화면에서 다시 만들지 않도록 여기에 모은다
(CLAUDE.md §9: "로딩, 오류, 빈 상태를 반드시 구현").
"""

from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.enums import Severity
from ..core.models import DiagnosisWarning
from .theme import SEVERITY_COLOR, SEVERITY_MARK


def clear_layout(layout) -> None:
    """레이아웃의 자식 위젯을 즉시 제거한다.

    deleteLater()만 쓰면 이벤트 루프가 돌기 전까지 위젯이 부모에 남아
    새 항목과 겹쳐 그려진다. 부모 연결을 먼저 끊어야 한다.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def h1(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("H1")
    label.setWordWrap(True)
    return label


def h2(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("H2")
    label.setWordWrap(True)
    return label


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


def body(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


class Banner(QFrame):
    """상단 안내/경고 배너. 색과 함께 텍스트 표식을 반드시 넣는다."""

    def __init__(self, text: str = "", kind: str = "info") -> None:
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._label, 1)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        self.setObjectName(
            {
                "critical": "BannerCritical",
                "ok": "BannerOk",
                "info": "Banner",
            }.get(kind, "Banner")
        )
        self.style().unpolish(self)
        self.style().polish(self)

    def set_text(self, text: str, kind: str | None = None) -> None:
        self._label.setText(text)
        if kind:
            self.set_kind(kind)


class EmptyState(QWidget):
    """빈 상태. 무엇이 없는지와 다음에 무엇을 할지 함께 보여준다."""

    def __init__(self, title: str, description: str, action_text: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        t = QLabel(title)
        t.setObjectName("H2")
        t.setAlignment(Qt.AlignCenter)
        d = QLabel(description)
        d.setObjectName("Hint")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        layout.addWidget(t)
        layout.addWidget(d)
        self.action_button: QPushButton | None = None
        if action_text:
            self.action_button = QPushButton(action_text)
            self.action_button.setObjectName("Primary")
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(self.action_button)
            row.addStretch(1)
            layout.addLayout(row)


class BulletList(QWidget):
    """글머리 목록. 항목이 없으면 '없음'을 명시한다."""

    def __init__(self, items: Sequence[str] = (), empty_text: str = "없음") -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self._empty_text = empty_text
        self.set_items(items)

    def set_items(self, items: Sequence[str]) -> None:
        clear_layout(self._layout)
        if not items:
            self._layout.addWidget(hint(f"— {self._empty_text}"))
            return
        for text in items:
            label = QLabel(f"•  {text}")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            # 줄바꿈 라벨은 세로 정책을 명시하지 않으면 부모가 높이를 덜 잡아
            # 글자 아랫부분이 잘린다.
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
            label.setMinimumHeight(label.fontMetrics().height() + 4)
            self._layout.addWidget(label)


class WarningTable(QTableWidget):
    """경고 목록. 심각도는 색 + 기호 + 한글 라벨로 함께 표시한다."""

    def __init__(self) -> None:
        super().__init__(0, 4)
        self.setHorizontalHeaderLabels(["심각도", "코드", "내용", "권장 행동"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setWordWrap(True)
        self.setAlternatingRowColors(True)
        # 좁은 패널에서도 가로 스크롤 없이 읽히도록 긴 텍스트 열을 늘린다.
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def set_warnings(self, warnings: Sequence[dict]) -> None:
        order = {str(Severity.CRITICAL): 0, str(Severity.WARN): 1, str(Severity.INFO): 2}
        rows = sorted(warnings, key=lambda w: order.get(w["severity"], 9))
        self.setRowCount(len(rows))
        for i, w in enumerate(rows):
            sev = Severity(w["severity"])
            sev_item = QTableWidgetItem(SEVERITY_MARK[sev])
            sev_item.setForeground(QColor(SEVERITY_COLOR[sev]))
            self.setItem(i, 0, sev_item)
            self.setItem(i, 1, QTableWidgetItem(w["code"]))
            self.setItem(i, 2, QTableWidgetItem(w["message"]))
            self.setItem(i, 3, QTableWidgetItem(w.get("recommended_action", "")))
        self.resizeRowsToContents()


class WarningList(QWidget):
    """좁은 패널용 경고 목록.

    표는 열이 4개라 좁은 폭에서 글자가 잘린다. 여기서는 카드로 쌓아
    긴 문장이 자연스럽게 줄바꿈되게 한다. 내용은 WarningTable과 동일하다.
    """

    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignTop)
        self.set_warnings([])

    def set_warnings(self, warnings: Sequence[dict]) -> None:
        clear_layout(self._layout)
        if not warnings:
            self._layout.addWidget(hint("— 경고 없음"))
            return

        order = {str(Severity.CRITICAL): 0, str(Severity.WARN): 1, str(Severity.INFO): 2}
        for w in sorted(warnings, key=lambda x: order.get(x["severity"], 9)):
            sev = Severity(w["severity"])
            card = QFrame()
            card.setObjectName(
                "BannerCritical" if sev == Severity.CRITICAL else "Banner"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(3)

            head = QLabel(f"<b>{SEVERITY_MARK[sev]}</b>　{w['code']}")
            head.setStyleSheet(f"color: {SEVERITY_COLOR[sev]};")
            head.setWordWrap(True)
            card_layout.addWidget(head)

            message = QLabel(w["message"])
            message.setWordWrap(True)
            message.setTextInteractionFlags(Qt.TextSelectableByMouse)
            card_layout.addWidget(message)

            action = w.get("recommended_action")
            if action:
                act = QLabel(f"→ {action}")
                act.setObjectName("Hint")
                act.setWordWrap(True)
                card_layout.addWidget(act)

            self._layout.addWidget(card)


def scrollable(inner: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(inner)
    return area


def labeled_text_area(placeholder: str, height: int = 90) -> QPlainTextEdit:
    editor = QPlainTextEdit()
    editor.setPlaceholderText(placeholder)
    editor.setFixedHeight(height)
    editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return editor
