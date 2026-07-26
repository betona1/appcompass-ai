"""Anthropic API 호출 어댑터.

바깥에서 보이는 계약은 Transport 하나다. 서비스와 테스트는 이 프로토콜만 알면 되고,
Anthropic SDK를 몰라도 된다. 덕분에 테스트가 네트워크 없이 돈다.

여기서 하는 일은 세 가지뿐이다.
    1. 요청 조립 (구조화 출력 스키마를 붙인다)
    2. 응답에서 JSON 뽑기
    3. 실패를 우리 예외로 번역하기

스키마 검증과 재시도는 여기서 하지 않는다. service.py가 한다 —
'검증'과 '통신'을 한 클래스에 섞으면 둘 다 테스트하기 어려워진다.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from .config import LLMConfig
from .errors import LLMNotConfigured, LLMRefused, LLMTransportFailed

#: 정책 거절 시 서버가 대신 실행할 모델을 자동 선택한다.
#: 이 앱의 입력(앱 기획 원문)에서 거절이 날 일은 거의 없지만,
#: 났을 때 초안 기능이 통째로 죽는 것보다 다른 모델이 이어받는 편이 낫다.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@runtime_checkable
class Transport(Protocol):
    """LLM 한 번 호출. 스키마에 맞는 dict를 돌려주거나 예외를 던진다."""

    provider: str
    model: str

    def complete_json(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        schema_title: str,
    ) -> dict[str, Any]: ...


def _extract_json(text: str) -> dict[str, Any]:
    """구조화 출력이 켜져 있으면 text 전체가 JSON이다.

    그래도 방어적으로 파싱한다. 파싱 실패는 스키마 실패와 같은 취급을 받아야 하므로
    여기서는 ValueError로 올리고, service.py의 복구 프롬프트 경로가 이어받는다.
    """
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("응답이 비어 있습니다.")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON으로 읽을 수 없습니다: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("최상위가 객체(JSON object)가 아닙니다.")
    return parsed


class AnthropicTransport:
    """실제 API를 부르는 구현.

    SDK는 지연 import한다. anthropic 패키지가 없어도 앱 전체가 뜨고,
    'AI 도우미' 화면에서 설치 안내만 보이게 하기 위해서다.
    """

    provider = "anthropic"

    def __init__(self, config: LLMConfig) -> None:
        if not config.is_configured:
            raise LLMNotConfigured("API 키가 설정되지 않았습니다.")
        self._config = config
        self.model = config.model
        self._client = _make_client(config)
        # 조직/모델에 따라 fallbacks 베타를 쓸 수 없을 수 있다.
        # 한 번 거절당하면 이 프로세스에서는 다시 시도하지 않는다.
        self._use_fallbacks = True

    # -- 호출 -------------------------------------------------------------
    def complete_json(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        schema_title: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {
                "effort": self._config.effort,
                "format": {
                    "type": "json_schema",
                    "name": schema_title,
                    "schema": schema,
                },
            },
        }

        message = self._send(params)

        stop = getattr(message, "stop_reason", None)
        if stop == "refusal":
            detail = ""
            details = getattr(message, "stop_details", None)
            if details is not None:
                detail = f" (분류: {getattr(details, 'category', None) or '미상'})"
            raise LLMRefused(f"모델이 응답을 거절했습니다{detail}.")
        if stop == "max_tokens":
            raise LLMTransportFailed(
                "응답이 길이 제한에 걸려 잘렸습니다. 원문을 줄이고 다시 시도하세요."
            )

        text = "".join(
            block.text
            for block in getattr(message, "content", [])
            if getattr(block, "type", None) == "text"
        )
        return _extract_json(text)

    # -- 내부 -------------------------------------------------------------
    def _send(self, params: dict[str, Any]) -> Any:
        """스트리밍으로 보낸다.

        스트리밍을 쓰는 이유는 화면에 토큰을 뿌리기 위해서가 아니라,
        생각(thinking)이 길어질 때 HTTP 타임아웃으로 통째로 실패하는 것을 막기 위해서다.
        결과는 get_final_message()로 한 번에 받는다.
        """
        import anthropic

        if self._use_fallbacks:
            try:
                with self._client.beta.messages.stream(
                    betas=[FALLBACK_BETA], fallbacks="default", **params
                ) as stream:
                    return stream.get_final_message()
            except anthropic.BadRequestError as exc:
                # 베타를 쓸 수 없는 조직이면 기능 자체가 죽는 대신 그냥 물러난다.
                if not _is_fallback_rejection(exc):
                    raise LLMTransportFailed(_readable(exc)) from exc
                self._use_fallbacks = False
            except anthropic.APIError as exc:
                raise LLMTransportFailed(_readable(exc)) from exc

        try:
            with self._client.messages.stream(**params) as stream:
                return stream.get_final_message()
        except anthropic.APIError as exc:
            raise LLMTransportFailed(_readable(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - 원인을 화면에 그대로 보여준다
            raise LLMTransportFailed(f"{type(exc).__name__}: {exc}") from exc


def _make_client(config: LLMConfig) -> Any:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - 설치 여부에 따라 갈린다
        raise LLMNotConfigured(
            "anthropic 패키지가 설치되어 있지 않습니다.",
            next_action="pip install anthropic 을 실행한 뒤 앱을 다시 시작하세요.",
        ) from exc
    return anthropic.Anthropic(
        api_key=config.api_key,
        timeout=config.timeout_seconds,
        max_retries=2,
    )


def _is_fallback_rejection(exc: Exception) -> bool:
    text = str(exc).lower()
    return "fallback" in text or "beta" in text


def _readable(exc: Exception) -> str:
    """SDK 예외를 사람이 읽을 수 있는 한 줄로.

    키 값이 예외 메시지에 실려 나오는 일은 없지만, 그래도 원문을 그대로 던지지 않고
    상태 코드 중심으로 다시 쓴다.
    """
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "API 키가 올바르지 않습니다 (401)."
    if status == 403:
        return "이 API 키로는 해당 모델을 쓸 수 없습니다 (403)."
    if status == 404:
        return "모델 이름을 찾을 수 없습니다 (404). 'AI 도우미' 화면에서 모델명을 확인하세요."
    if status == 429:
        return "요청이 너무 잦습니다 (429). 잠시 후 다시 시도하세요."
    if status is not None and status >= 500:
        return f"서버 오류({status})입니다. 잠시 후 다시 시도하세요."
    message = getattr(exc, "message", None) or str(exc)
    return f"{type(exc).__name__}: {message}"
