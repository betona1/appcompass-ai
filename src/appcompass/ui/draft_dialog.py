"""AI 초안 검토 창.

이 창의 존재 이유 하나 — **사용자가 칸마다 직접 고르게 하는 것**.

'전부 적용' 버튼만 있으면 사용자는 내용을 읽지 않고 누른다. 그러면 AI가 추측한
문장이 그대로 기획서가 되고, 이후 모든 진단이 그 위에서 돌아간다.
그래서 기본값은 '체크 안 됨'이고, 추측(INFERRED)인 칸은 눈에 띄게 표시한다.

이미 사용자가 쓴 값이 있는 칸은 좌우로 나란히 보여 준다.
무엇을 잃게 되는지 보지 않고 덮어쓰는 일이 없어야 한다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..llm.service import StructureDraft
from .widgets import BulletList, h2, hint, scrollable

#: 화면 B의 라벨과 같은 문구를 쓴다. 두 화면에서 이름이 다르면 사용자가 헷갈린다.
FIELD_LABELS: dict[str, str] = {
    "target_user": "사용자",
    "payer": "구매자",
    "influencer": "영향자",
    "problem_situation": "문제 상황",
    "current_solution": "현재 대체 방법",
    "current_solution_problem": "대체 방법의 한계",
    "core_action": "핵심 행동",
    "expected_result": "기대 결과",
    "first_success": "첫 성공 경험",
    "retention_reason": "재방문 이유",
    "revenue_model": "수익 모델",
    "distribution_channel": "유입 경로",
}

_BASIS_STYLE = {
    "FROM_RAW_TEXT": "#1b5e20",
    "INFERRED": "#b26a00",
    "MISSING": "#5a6068",
}


class StructureDraftDialog(QDialog):
    """초안을 보여 주고, 채택할 칸의 키 목록을 돌려준다."""

    def __init__(
        self,
        draft: StructureDraft,
        current: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 초안 검토")
        self.setMinimumSize(880, 640)
        self._draft = draft
        self._checks: dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)

        outer.addWidget(
            hint(
                f"{draft.assist.model} 이(가) 원문을 읽고 만든 <b>초안</b>입니다. "
                "아직 아무것도 저장되지 않았습니다.<br>"
                "체크한 칸만 편집 화면에 채워지며, 채운 뒤에도 자유롭게 고칠 수 있습니다. "
                "<b>AI는 이 내용으로 점수를 매기거나 판단하지 않습니다.</b>"
            )
        )

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)

        inferred = 0
        for key, label in FIELD_LABELS.items():
            value = (draft.fields.get(key) or "").strip()
            note = draft.note_for(key)
            if not value:
                continue  # 비워 둔 칸은 고를 것이 없다
            if note is not None and note.needs_review:
                inferred += 1
            body_layout.addWidget(
                self._field_row(key, label, value, current.get(key, ""), note)
            )

        if not self._checks:
            body_layout.addWidget(
                hint(
                    "AI가 채울 수 있는 칸이 없었습니다. 원문이 너무 짧으면 이렇게 됩니다. "
                    "'A. 아이디어 입력'에 상황을 조금 더 적고 다시 시도해 보세요."
                )
            )

        if draft.unknowns:
            box = QGroupBox("확인이 필요한 것 (unknowns)")
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(
                hint(
                    "원문만으로는 알 수 없어 사용자에게 직접 물어봐야 하는 것들입니다. "
                    "채택하면 이 버전의 언노운 목록에 함께 들어갑니다."
                )
            )
            box_layout.addWidget(BulletList(list(draft.unknowns), "없음"))
            body_layout.addWidget(box)

        body_layout.addStretch(1)
        outer.addWidget(scrollable(body), 1)

        if inferred:
            outer.addWidget(
                hint(
                    f"<b style='color:#b26a00'>추측 {inferred}건</b> — "
                    "원문에 없는 내용을 AI가 지어낸 칸입니다. "
                    "사실인지 확인하기 전에는 채택하지 마세요."
                )
            )

        row = QHBoxLayout()
        select_evidenced = QPushButton("원문에 있는 칸만 선택")
        select_evidenced.setToolTip(
            "AI가 추측한 칸은 빼고, 원문에서 그대로 옮겨온 칸만 고릅니다."
        )
        select_evidenced.clicked.connect(self._select_evidenced)
        select_all = QPushButton("전부 선택")
        clear_all = QPushButton("전부 해제")
        select_all.clicked.connect(lambda: self._set_all(True))
        clear_all.clicked.connect(lambda: self._set_all(False))
        row.addWidget(select_evidenced)
        row.addWidget(select_all)
        row.addWidget(clear_all)
        row.addStretch(1)
        outer.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.button(QDialogButtonBox.Ok).setText("선택한 칸 채우기")
        buttons.button(QDialogButtonBox.Cancel).setText("쓰지 않기")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # -- 구성 -------------------------------------------------------------
    def _field_row(
        self, key: str, label: str, value: str, current: str, note
    ) -> QGroupBox:
        basis = note.basis if note else "FROM_RAW_TEXT"
        color = _BASIS_STYLE.get(basis, "#5a6068")
        basis_label = note.basis_label if note else "원문에 있음"

        box = QGroupBox()
        layout = QVBoxLayout(box)

        check = QCheckBox(label)
        # 기본은 체크 해제. 읽지 않고 누르는 것을 구조적으로 막는다.
        check.setChecked(False)
        self._checks[key] = check

        header = QHBoxLayout()
        header.addWidget(check)
        tag = QLabel(f"<span style='color:{color}'>● {basis_label}</span>")
        header.addWidget(tag)
        header.addStretch(1)
        layout.addLayout(header)

        if note is not None and note.reason:
            layout.addWidget(hint(f"근거: {note.reason}"))

        columns = QHBoxLayout()
        if current.strip():
            columns.addWidget(_column("지금 입력된 값 (덮어씀)", current, "#5a6068"), 1)
        columns.addWidget(_column("AI 초안", value, "#1a1c1e"), 1)
        layout.addLayout(columns)

        if current.strip():
            layout.addWidget(
                hint("이 칸에는 이미 적은 내용이 있습니다. 체크하면 위 초안으로 바뀝니다.")
            )
        return box

    # -- 동작 -------------------------------------------------------------
    def _set_all(self, checked: bool) -> None:
        for check in self._checks.values():
            check.setChecked(checked)

    def _select_evidenced(self) -> None:
        for key, check in self._checks.items():
            note = self._draft.note_for(key)
            check.setChecked(note is None or not note.needs_review)

    def accepted_fields(self) -> tuple[str, ...]:
        return tuple(key for key, check in self._checks.items() if check.isChecked())


def _column(title: str, text: str, color: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(h2(title))
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setStyleSheet(f"color: {color};")
    layout.addWidget(label)
    layout.addStretch(1)
    return widget
