"""도메인 모듈.

공통 진단 엔진 위에 도메인 지식을 얹는다 (CLAUDE.md §3).
도메인 모듈은 core 엔진을 수정하지 않고 경고·언노운·점수보정·MVP제약·지표·피벗규칙만 추가한다.
"""

from .base import DomainModule, GenericDomain
from .registry import get_domain, available_domains

__all__ = ["DomainModule", "GenericDomain", "get_domain", "available_domains"]
