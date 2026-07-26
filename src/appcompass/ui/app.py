"""애플리케이션 진입점.

실행:
    python -m appcompass            (src를 PYTHONPATH에 넣거나 pip install -e . 후)
    python run_app.py               (저장소 루트에서 바로)
"""

from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from ..services.app_service import AppService
from ..storage.db import Database
from .main_window import MainWindow
from .theme import STYLESHEET


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    app = QApplication(argv)
    app.setApplicationName("AppCompass AI")
    app.setOrganizationName("AppCompass")
    app.setStyleSheet(STYLESHEET)

    try:
        db = Database()
        service = AppService(db)
    except Exception as exc:  # noqa: BLE001 - 기동 실패는 사용자에게 보여준다
        QMessageBox.critical(
            None,
            "시작 실패",
            f"데이터베이스를 열 수 없습니다.\n\n{type(exc).__name__}: {exc}\n\n"
            f"{traceback.format_exc(limit=3)}",
        )
        return 1

    window = MainWindow(service)
    window.show()
    try:
        return app.exec()
    finally:
        db.dispose()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
