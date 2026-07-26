"""백그라운드 작업.

Phase 1의 규칙 엔진은 빠르지만 UI를 막지 않고 실행한다.
LLM을 붙이면 같은 자리에서 수 초~수십 초가 걸리므로 구조를 미리 맞춰 둔다
(TECHSPEC §14: 분석 생성은 비동기).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from ..services.app_service import AppService, ServiceError
from ..services.dto import RunDTO


class AnalysisWorker(QThread):
    """분석 실행 스레드. 결과 또는 오류를 시그널로 돌려준다."""

    finished_ok = Signal(object)  # RunDTO
    failed = Signal(str)

    def __init__(self, service: AppService, version_id: str, parent: QObject | None = None):
        super().__init__(parent)
        self._service = service
        self._version_id = version_id

    def run(self) -> None:  # noqa: D102 - QThread 진입점
        try:
            run: RunDTO = self._service.run_analysis(self._version_id)
        except ServiceError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - UI에 원인을 보여준다
            self.failed.emit(f"예상치 못한 오류: {type(exc).__name__}: {exc}")
        else:
            self.finished_ok.emit(run)
