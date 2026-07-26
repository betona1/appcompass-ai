"""LLM 어댑터 계층.

계층 규칙: `ui → services → llm → core`.
이 패키지는 core의 값 객체와 스키마만 import한다. storage·ui·services를 모르며,
반대로 core는 이 패키지를 모른다. 그래서 LLM을 통째로 들어내도 core는 그대로 돈다.

무엇을 하는가 (CLAUDE.md §10.1 허용 범위):
    - 자유 입력 → 구조화 초안
    - 타깃 후보 초안
    - 언노운(확인이 필요한 것) 생성

무엇을 하지 않는가 (§10.2 금지, ADR-0002):
    - 점수 계산
    - 신뢰도 계산
    - 피벗 상태 결정
    - 근거 생성 (근거는 사람이 등록한 것만 존재한다, §11)

이 금지는 문서가 아니라 구조로 막혀 있다. 이 패키지의 반환 타입에는
점수·신뢰도·피벗 필드가 아예 없고, 출력 JSON Schema가 additionalProperties=false라
모델이 그런 값을 끼워 넣으면 스키마 검증에서 떨어진다.
"""

from __future__ import annotations

from .config import LLMConfig, LLMSettingsError, load_config, save_api_key
from .errors import LLMError, LLMNotConfigured, LLMRefused, LLMSchemaFailed
from .service import DraftAssistant, StructureDraft, TargetDraft, build_assistant

__all__ = [
    "LLMConfig",
    "LLMSettingsError",
    "load_config",
    "save_api_key",
    "LLMError",
    "LLMNotConfigured",
    "LLMRefused",
    "LLMSchemaFailed",
    "DraftAssistant",
    "StructureDraft",
    "TargetDraft",
    "build_assistant",
]
