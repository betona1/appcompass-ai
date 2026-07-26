from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ..context import ScreenContext


class ScreenBase(QWidget):
    """모든 화면의 공통 인터페이스.

    refresh(ctx)는 현재 상태를 화면에 반영한다.
    데이터가 없을 때 빈 상태를 보여주는 책임도 각 화면에 있다.
    """

    data_changed = Signal()  # 저장/변경 후 MainWindow가 다시 로드하도록 알린다
    request_screen = Signal(str)  # 다른 화면으로 이동 요청 (키: 화면 id)
    status_message = Signal(str)

    title: str = ""
    purpose: str = ""

    def refresh(self, ctx: ScreenContext) -> None:  # pragma: no cover - 하위에서 구현
        raise NotImplementedError
