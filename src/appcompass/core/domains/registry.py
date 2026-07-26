"""도메인 모듈 레지스트리.

새 도메인을 추가할 때 core 엔진을 수정하지 않고 여기에만 등록한다.
"""

from __future__ import annotations

from ..enums import DomainCode
from .base import DomainModule, GenericDomain
from .examath import ExamathDomain
from .vibequest import VibeQuestDomain

_REGISTRY: dict[DomainCode, DomainModule] = {
    DomainCode.GENERIC: GenericDomain(),
    DomainCode.VIBEQUEST: VibeQuestDomain(),
    DomainCode.EXAMATH: ExamathDomain(),
}


def get_domain(code: DomainCode | str) -> DomainModule:
    try:
        key = DomainCode(code)
    except ValueError as exc:  # pragma: no cover - 방어적 처리
        raise KeyError(f"알 수 없는 도메인 코드: {code}") from exc
    return _REGISTRY[key]


def available_domains() -> list[tuple[DomainCode, str]]:
    return [(code, module.label) for code, module in _REGISTRY.items()]
