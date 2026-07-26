"""LLM 호출 실패를 사용자가 이해할 수 있는 형태로 나눈다.

실패를 뭉뚱그리면 사용자는 "AI가 안 돼요"밖에 말할 수 없다.
원인마다 다음에 할 행동이 다르므로 타입을 나눈다.
"""

from __future__ import annotations


class LLMError(RuntimeError):
    """LLM 관련 실패의 최상위. 메시지는 사용자에게 그대로 보여줄 수 있다."""

    #: 사용자가 지금 할 수 있는 행동. UI가 오류 아래에 그대로 표시한다.
    next_action: str = ""

    def __init__(self, message: str, next_action: str = "") -> None:
        super().__init__(message)
        if next_action:
            self.next_action = next_action


class LLMNotConfigured(LLMError):
    """API 키가 없거나 SDK가 설치되지 않았다. 호출 자체를 시도하지 않는다."""

    next_action = "'AI 도우미' 화면에서 API 키를 설정하세요."


class LLMSchemaFailed(LLMError):
    """스키마 검증에 두 번 실패했다 (CLAUDE.md §10.3).

    1회 복구 프롬프트 후에도 형식이 맞지 않으면 초안을 버린다.
    형식이 깨진 응답으로는 어떤 칸도 채우지 않는다.
    """

    next_action = "초안 없이 직접 채우거나, 원문을 조금 더 구체적으로 적고 다시 시도하세요."

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class LLMRefused(LLMError):
    """모델이 응답을 거절했다 (stop_reason='refusal')."""

    next_action = "원문 내용을 확인하고 다시 시도하세요. 반복되면 초안 없이 직접 채우세요."


class LLMTransportFailed(LLMError):
    """네트워크·인증·요금제 등 호출 자체가 실패했다."""

    next_action = "네트워크와 API 키를 확인한 뒤 다시 시도하세요."
