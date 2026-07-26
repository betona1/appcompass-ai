"""평가 정책.

CLAUDE.md §11 "이 값은 초기 정책이며 관리자 화면에서 변경 가능해야 한다."
TECHSPEC §5.10 "임계치는 전역 상수가 아니라 EvaluationPolicy에서 관리한다."

따라서 가중치·신뢰도·임계치는 모두 이 객체에 모으고,
엔진 함수는 정책을 인자로 받는다. 모듈 전역 상수로 흩뿌리지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from .enums import DimensionCode, EvidenceType


class PolicyError(ValueError):
    """정책값이 불변식을 위반했을 때."""


DEFAULT_WEIGHTS: Mapping[DimensionCode, int] = {
    DimensionCode.D01: 15,
    DimensionCode.D02: 10,
    DimensionCode.D03: 10,
    DimensionCode.D04: 5,
    DimensionCode.D05: 10,
    DimensionCode.D06: 10,
    DimensionCode.D07: 10,
    DimensionCode.D08: 10,
    DimensionCode.D09: 10,
    DimensionCode.D10: 10,
}

DEFAULT_EVIDENCE_CONFIDENCE: Mapping[EvidenceType, float] = {
    EvidenceType.FOUNDER_ASSUMPTION: 0.20,
    EvidenceType.DESK_RESEARCH: 0.35,
    EvidenceType.USER_INTERVIEW: 0.50,
    EvidenceType.PROTOTYPE_TEST: 0.70,
    EvidenceType.BEHAVIOR_DATA: 1.00,
    EvidenceType.EXPERT_REVIEW: 0.45,  # 관리자 설정값
}

WEIGHT_TOTAL = 100


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    """점수·신뢰도·피벗 판정에 쓰이는 모든 정책값."""

    version: str = "policy-0.1.0"
    weights: Mapping[DimensionCode, int] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )
    evidence_confidence: Mapping[EvidenceType, float] = field(
        default_factory=lambda: dict(DEFAULT_EVIDENCE_CONFIDENCE)
    )

    # --- 신뢰도 ---
    no_evidence_confidence_cap: float = 0.20
    """근거가 없는 항목은 이 값을 초과할 수 없다 (TECHSPEC F-050)."""

    conflict_penalty: float = 0.30
    """지지 근거와 반박 근거가 함께 있을 때 신뢰도에 곱하는 감쇠 계수의 크기."""

    hold_threshold: float = 0.35
    """overall_confidence가 이 값 미만이면 HOLD (CLAUDE.md §2.4)."""

    # --- 피벗 임계치 (0~5 척도) ---
    problem_pivot_threshold: float = 2.0
    target_pivot_threshold: float = 3.0
    solution_pivot_threshold: float = 2.5
    retention_pivot_threshold: float = 2.5
    channel_pivot_threshold: float = 2.0
    revenue_pivot_threshold: float = 2.0

    # --- 총점 임계치 (0~100) ---
    keep_score_threshold: float = 75.0
    """총점이 이 값 이상이고 큰 위험이 없으면 KEEP, 아니면 REFINE."""

    def __post_init__(self) -> None:
        self.validate()

    # -- 검증 -------------------------------------------------------------
    def validate(self) -> None:
        missing = set(DimensionCode) - set(self.weights)
        if missing:
            raise PolicyError(
                f"가중치가 정의되지 않은 평가 항목: {sorted(str(m) for m in missing)}"
            )
        total = sum(self.weights.values())
        if total != WEIGHT_TOTAL:
            raise PolicyError(f"가중치 합계는 {WEIGHT_TOTAL}이어야 한다. 현재: {total}")
        for code, w in self.weights.items():
            if w < 0:
                raise PolicyError(f"가중치는 음수가 될 수 없다: {code}={w}")
        for etype, c in self.evidence_confidence.items():
            if not 0.0 <= c <= 1.0:
                raise PolicyError(f"근거 신뢰도는 0~1이어야 한다: {etype}={c}")
        if not 0.0 <= self.hold_threshold <= 1.0:
            raise PolicyError("hold_threshold는 0~1이어야 한다.")
        if not 0.0 <= self.no_evidence_confidence_cap <= 1.0:
            raise PolicyError("no_evidence_confidence_cap은 0~1이어야 한다.")

    def weight_of(self, code: DimensionCode) -> int:
        return self.weights[code]

    def confidence_of(self, evidence_type: EvidenceType) -> float:
        return self.evidence_confidence[evidence_type]

    # -- 직렬화 -----------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "weights": {str(k): v for k, v in self.weights.items()},
            "evidence_confidence": {
                str(k): v for k, v in self.evidence_confidence.items()
            },
            "no_evidence_confidence_cap": self.no_evidence_confidence_cap,
            "conflict_penalty": self.conflict_penalty,
            "hold_threshold": self.hold_threshold,
            "problem_pivot_threshold": self.problem_pivot_threshold,
            "target_pivot_threshold": self.target_pivot_threshold,
            "solution_pivot_threshold": self.solution_pivot_threshold,
            "retention_pivot_threshold": self.retention_pivot_threshold,
            "channel_pivot_threshold": self.channel_pivot_threshold,
            "revenue_pivot_threshold": self.revenue_pivot_threshold,
            "keep_score_threshold": self.keep_score_threshold,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvaluationPolicy:
        data = dict(data or {})
        weights = {
            DimensionCode(k): int(v) for k, v in (data.pop("weights", None) or {}).items()
        } or dict(DEFAULT_WEIGHTS)
        ev = {
            EvidenceType(k): float(v)
            for k, v in (data.pop("evidence_confidence", None) or {}).items()
        } or dict(DEFAULT_EVIDENCE_CONFIDENCE)
        allowed = set(cls.__slots__) - {"weights", "evidence_confidence"}
        kwargs = {k: v for k, v in data.items() if k in allowed}
        return cls(weights=weights, evidence_confidence=ev, **kwargs)

    def with_changes(self, **changes: Any) -> EvaluationPolicy:
        """정책 수정본을 만든다. 원본은 불변으로 유지한다."""
        return replace(self, **changes)


DEFAULT_POLICY = EvaluationPolicy()
