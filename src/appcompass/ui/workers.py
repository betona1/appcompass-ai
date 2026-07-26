"""백그라운드 작업.

규칙 엔진은 빠르지만 UI를 막지 않고 실행한다.
LLM 초안은 실제로 수 초~수십 초가 걸리므로 반드시 이쪽을 거친다
(TECHSPEC §14: 분석 생성은 비동기).
"""

from __future__ import annotations

from typing import Callable

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


class LlmDraftWorker(QThread):
    """AI 초안 생성 스레드.

    실패 시그널에 '다음에 할 행동'을 함께 보낸다. LLM 실패는 원인마다
    사용자가 해야 할 일이 달라서(키 설정 / 재시도 / 직접 입력),
    오류 문구만 던지면 사용자가 막힌다.
    """

    finished_ok = Signal(object)  # StructureDraft | TargetDraft
    failed = Signal(str, str)  # (메시지, 다음 행동)

    def __init__(self, task: Callable[[], object], parent: QObject | None = None):
        super().__init__(parent)
        self._task = task

    def run(self) -> None:  # noqa: D102 - QThread 진입점
        from ..llm.errors import LLMError

        try:
            draft = self._task()
        except LLMError as exc:
            self.failed.emit(str(exc), exc.next_action)
        except ServiceError as exc:
            self.failed.emit(str(exc), "")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(
                f"예상치 못한 오류: {type(exc).__name__}: {exc}",
                "문제가 계속되면 초안 없이 직접 채우세요.",
            )
        else:
            self.finished_ok.emit(draft)
