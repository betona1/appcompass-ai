"""도메인 콘텐츠 진단 (TECHSPEC Phase 4).

지금까지의 진단은 **기획**을 본다. 이 모듈은 **콘텐츠 자체**를 본다.

    기획 진단 : "타깃이 넓다", "첫 성공 경험이 없다"
    콘텐츠 진단: "이 문항은 정의 암기형이라 실제 작업에 전이되지 않는다"
                "이 아이의 오답은 받아내림 개념이 아니라 뒤로 세기 문제다"

CLAUDE.md §4.6~4.7(VibeQuest 문제 유형과 위험), §5.5(examath 오류 유형)를
코드로 옮긴 것이다. 도메인마다 입력도 판정도 다르므로 계약만 여기 두고
실제 규칙은 각 도메인 모듈이 갖는다.

판정은 규칙이다. 같은 입력이면 항상 같은 결과가 나온다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import Severity


@dataclass(frozen=True, slots=True)
class ContentField:
    """콘텐츠 진단 입력 칸 하나."""

    key: str
    label: str
    hint: str = ""
    multiline: bool = False
    required: bool = True
    numeric: bool = False


@dataclass(frozen=True, slots=True)
class ContentSpec:
    """도메인이 요구하는 콘텐츠 진단 양식."""

    title: str
    description: str
    fields: tuple[ContentField, ...]
    example: dict[str, str] = field(default_factory=dict)
    example_label: str = "예시 채우기"


@dataclass(frozen=True, slots=True)
class ContentFinding:
    """콘텐츠에서 발견한 것 하나."""

    code: str
    message: str
    severity: Severity = Severity.WARN
    recommended_action: str = ""


@dataclass(frozen=True, slots=True)
class ContentDiagnosis:
    """콘텐츠 진단 결과.

    classification은 '무엇인가'이고 findings는 '무엇이 문제인가'다.
    분류가 안 되면 UNKNOWN으로 두고 지어내지 않는다.
    """

    classification: str
    classification_label: str
    summary: str
    findings: tuple[ContentFinding, ...] = ()
    suggestions: tuple[str, ...] = ()
    limits: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "classification_label": self.classification_label,
            "summary": self.summary,
            "findings": [
                {
                    "code": f.code,
                    "message": f.message,
                    "severity": str(f.severity),
                    "recommended_action": f.recommended_action,
                }
                for f in self.findings
            ],
            "suggestions": list(self.suggestions),
            "limits": self.limits,
            "detail": dict(self.detail),
        }


#: 규칙 기반 판정의 한계를 항상 함께 알린다.
#: 분류가 확정처럼 보이면 사용자가 관찰을 멈춘다.
DEFAULT_LIMITS = (
    "이 분류는 입력한 내용만 보고 규칙으로 판정한 것입니다. "
    "실제 원인은 아이(사용자)를 직접 관찰해야 확인됩니다. "
    "분류가 맞는지 반드시 사람이 확인하세요."
)
