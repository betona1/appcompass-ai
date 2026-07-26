"""신뢰도 계산 (TECHSPEC F-050).

원칙:
- 같은 점수라도 근거 수준에 따라 판단 강도를 다르게 한다.
- 근거가 없는 항목은 policy.no_evidence_confidence_cap(기본 0.20)을 넘을 수 없다.
- 지지 근거와 반박 근거가 함께 있으면 신뢰도를 낮추고 경고를 남긴다.
- 표본 수만으로 자동 확정하지 않는다. 표본은 보정 계수일 뿐 상한을 올리지 못한다.

AI는 근거를 생성하지 않는다. 여기 들어오는 EvidenceItem은 전부 사람이 등록한 것이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .enums import DimensionCode, Severity, WarningCode
from .models import DiagnosisWarning, EvidenceItem
from .policy import EvaluationPolicy


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    per_dimension: dict[DimensionCode, float]
    overall: float
    warnings: tuple[DiagnosisWarning, ...]


def _evidence_confidence(item: EvidenceItem, policy: EvaluationPolicy) -> float:
    if item.confidence_override is not None:
        return max(0.0, min(1.0, item.confidence_override))
    return policy.confidence_of(item.evidence_type)


def _sample_factor(sample_size: int | None) -> float:
    """표본 보정 계수 (0.6~1.0).

    표본이 작으면 신뢰도를 깎지만, 표본이 크다고 근거 유형의 상한을 넘기지는 않는다.
    """
    if sample_size is None or sample_size <= 0:
        return 0.8
    if sample_size < 3:
        return 0.6
    if sample_size < 5:
        return 0.8
    if sample_size < 10:
        return 0.9
    return 1.0


def compute_confidence(
    evidence: Sequence[EvidenceItem],
    policy: EvaluationPolicy,
) -> ConfidenceResult:
    """항목별 신뢰도와 전체 신뢰도를 계산한다."""

    per_dimension: dict[DimensionCode, float] = {}
    warnings: list[DiagnosisWarning] = []

    for code in DimensionCode:
        supporting = [e for e in evidence if code in e.supports]
        contradicting = [e for e in evidence if code in e.contradicts]

        if not supporting:
            # 근거 없음 → 상한 적용. 반박만 있으면 그마저도 절반으로 본다.
            base = policy.no_evidence_confidence_cap
            if contradicting:
                base *= 0.5
            per_dimension[code] = round(base, 4)
            continue

        # 근거 신뢰도의 가중 평균 (가중치 = 근거 신뢰도 자체 × 표본 보정)
        numerator = 0.0
        denominator = 0.0
        for item in supporting:
            conf = _evidence_confidence(item, policy)
            weight = conf * _sample_factor(item.sample_size)
            numerator += conf * weight
            denominator += weight
        value = numerator / denominator if denominator else policy.no_evidence_confidence_cap

        if contradicting:
            strongest_contra = max(
                _evidence_confidence(e, policy) for e in contradicting
            )
            value *= max(0.0, 1.0 - policy.conflict_penalty * strongest_contra / 1.0)
            warnings.append(
                DiagnosisWarning(
                    code=WarningCode.CONFLICTING_EVIDENCE,
                    message=(
                        f"{code} 항목에 지지 근거 {len(supporting)}건과 "
                        f"반박 근거 {len(contradicting)}건이 함께 있습니다."
                    ),
                    severity=Severity.WARN,
                    field=str(code),
                    recommended_action="상충 원인을 좁히는 실험을 먼저 설계합니다.",
                )
            )

        per_dimension[code] = round(max(0.0, min(1.0, value)), 4)

    overall = sum(
        per_dimension[code] * policy.weight_of(code) for code in DimensionCode
    ) / 100.0
    overall = round(max(0.0, min(1.0, overall)), 4)

    if overall < policy.hold_threshold:
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.LOW_EVIDENCE,
                message=(
                    f"전체 근거 신뢰도가 {overall:.2f}로 기준치 "
                    f"{policy.hold_threshold:.2f} 미만입니다. 판단을 확정할 수 없습니다."
                ),
                severity=Severity.CRITICAL,
                recommended_action="가장 약한 항목부터 인터뷰·프로토타입 근거를 등록합니다.",
            )
        )

    return ConfidenceResult(
        per_dimension=per_dimension,
        overall=overall,
        warnings=tuple(warnings),
    )
