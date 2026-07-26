"""피벗 엔진 (TECHSPEC F-090).

TECHSPEC §9.2: 피벗 상태 결정은 규칙 엔진이 한다. LLM은 보조 역할만 한다.
CLAUDE.md §2.4: 근거가 부족하면 HOLD를 우선한다.

우선순위(TECHSPEC 5.10):
    1. 신뢰도 부족            → HOLD
    2. 문제 강도 부족          → PROBLEM_PIVOT
    3. 타깃 불명확            → TARGET_PIVOT
    4. 관심은 있으나 핵심 행동 실패 → SOLUTION_PIVOT
    5. 핵심 행동 성공, 재방문 실패  → RETENTION_REDESIGN
    6. 유지율 양호, 유입 실패     → CHANNEL_PIVOT
    7. 사용 양호, 지불 실패      → REVENUE_PIVOT
    8. 큰 문제 없음           → KEEP 또는 REFINE

HOLD로 막히더라도 "근거가 충분했다면 무엇이었을지"를 would_be_decision에 남긴다.
사용자가 지금 무엇을 검증해야 하는지 알아야 하기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .enums import DimensionCode, PivotDecision, WarningCode
from .models import DiagnosisResult, EvidenceItem, PivotResult
from .policy import EvaluationPolicy


@dataclass(frozen=True, slots=True)
class PivotRule:
    """도메인 모듈이 추가하는 규칙.

    predicate가 True를 반환하면 해당 판단으로 확정한다.
    공통 규칙보다 먼저 평가되며, priority가 낮을수록 먼저 본다.
    """

    code: str
    decision: PivotDecision
    predicate: Callable[[DiagnosisResult], bool]
    rationale: str
    priority: int = 100


def _avg(diagnosis: DiagnosisResult, *codes: DimensionCode) -> float:
    scores = [diagnosis.dimension(c).raw_score for c in codes]
    return sum(scores) / len(scores) if scores else 0.0


def _decide_without_confidence(
    diagnosis: DiagnosisResult,
    policy: EvaluationPolicy,
    domain_rules: Sequence[PivotRule] = (),
) -> tuple[PivotDecision, list[str], str]:
    """신뢰도를 제외한 내용 기반 판단. HOLD 판단과 분리해 재사용한다."""

    reason_codes: list[str] = []

    for rule in sorted(domain_rules, key=lambda r: r.priority):
        if rule.predicate(diagnosis):
            return rule.decision, [rule.code], rule.rationale

    problem = _avg(diagnosis, DimensionCode.D01, DimensionCode.D02)
    if problem < policy.problem_pivot_threshold:
        reason_codes.append("WEAK_PROBLEM")
        return (
            PivotDecision.PROBLEM_PIVOT,
            reason_codes,
            f"문제 구체성·강도 평균이 {problem:.1f}로 기준 "
            f"{policy.problem_pivot_threshold:.1f} 미만입니다. 해결책보다 문제를 다시 정의해야 합니다.",
        )

    target = diagnosis.dimension(DimensionCode.D03).raw_score
    if diagnosis.has_warning(WarningCode.BROAD_TARGET) or target < policy.target_pivot_threshold:
        if diagnosis.has_warning(WarningCode.BROAD_TARGET):
            reason_codes.append(str(WarningCode.BROAD_TARGET))
        if target < policy.target_pivot_threshold:
            reason_codes.append("UNCLEAR_TARGET")
        return (
            PivotDecision.TARGET_PIVOT,
            reason_codes,
            "문제는 살아 있으나 타깃이 넓거나 행동으로 정의되지 않았습니다. "
            "먼저 좁은 타깃 하나를 골라 검증해야 합니다.",
        )

    behavior = _avg(diagnosis, DimensionCode.D05, DimensionCode.D06)
    if behavior < policy.solution_pivot_threshold:
        reason_codes.append("CORE_ACTION_NOT_COMPLETED")
        return (
            PivotDecision.SOLUTION_PIVOT,
            reason_codes,
            f"가치 제안·첫 성공 평균이 {behavior:.1f}입니다. "
            "관심은 있으나 핵심 행동이 완료되지 않는 구조입니다.",
        )

    retention = diagnosis.dimension(DimensionCode.D07).raw_score
    if retention < policy.retention_pivot_threshold:
        reason_codes.append("LOW_RETENTION")
        return (
            PivotDecision.RETENTION_REDESIGN,
            reason_codes,
            "핵심 행동은 성립하지만 다시 돌아올 이유가 약합니다. 재방문 장치를 재설계해야 합니다.",
        )

    channel = diagnosis.dimension(DimensionCode.D09).raw_score
    if channel < policy.channel_pivot_threshold:
        reason_codes.append("WEAK_CHANNEL")
        return (
            PivotDecision.CHANNEL_PIVOT,
            reason_codes,
            "유지 조건은 갖췄으나 유입 경로가 약합니다. 채널을 먼저 검증해야 합니다.",
        )

    differentiation = diagnosis.dimension(DimensionCode.D08).raw_score
    if differentiation < policy.revenue_pivot_threshold:
        reason_codes.append("WEAK_DIFFERENTIATION")
        return (
            PivotDecision.REVENUE_PIVOT,
            reason_codes,
            "사용은 성립하지만 대체재 대비 차별성이 약해 지불 근거가 부족합니다.",
        )

    if diagnosis.total_score >= policy.keep_score_threshold:
        return (
            PivotDecision.KEEP,
            ["NO_CRITICAL_RISK"],
            f"총점 {diagnosis.total_score:.1f}로 기준 {policy.keep_score_threshold:.1f} 이상이며 "
            "우선 처리할 위험이 없습니다. 현재 방향을 유지하고 실행 품질을 높입니다.",
        )

    return (
        PivotDecision.REFINE,
        ["MINOR_GAPS"],
        f"치명적 위험은 없으나 총점 {diagnosis.total_score:.1f}로 보완 여지가 있습니다. "
        "가장 낮은 항목부터 다듬습니다.",
    )


def decide_pivot(
    diagnosis: DiagnosisResult,
    policy: EvaluationPolicy,
    evidence: Sequence[EvidenceItem] = (),
    domain_rules: Sequence[PivotRule] = (),
) -> PivotResult:
    """최종 피벗 판정. 결정론적이며 LLM을 호출하지 않는다."""

    content_decision, reason_codes, rationale = _decide_without_confidence(
        diagnosis, policy, domain_rules
    )

    keep, change, remove, next_actions = _build_action_lists(diagnosis, content_decision)
    evidence_ids = tuple(e.id for e in evidence)

    if diagnosis.overall_confidence < policy.hold_threshold:
        hold_reasons = [str(WarningCode.LOW_EVIDENCE), *reason_codes]
        return PivotResult(
            decision=PivotDecision.HOLD,
            confidence=diagnosis.overall_confidence,
            reason_codes=tuple(dict.fromkeys(hold_reasons)),
            rationale=(
                f"전체 근거 신뢰도 {diagnosis.overall_confidence:.2f}가 기준 "
                f"{policy.hold_threshold:.2f} 미만이라 판단을 확정하지 않습니다. "
                f"현재 내용만 보면 {content_decision} 방향이며, 사유는 다음과 같습니다. {rationale}"
            ),
            would_be_decision=content_decision,
            evidence_ids=evidence_ids,
            keep=keep,
            change=change,
            remove=remove,
            next_actions=(
                "판단을 확정하려면 근거를 먼저 등록합니다.",
                *next_actions,
            ),
            requires_human_approval=True,
        )

    return PivotResult(
        decision=content_decision,
        confidence=diagnosis.overall_confidence,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        rationale=rationale,
        would_be_decision=None,
        evidence_ids=evidence_ids,
        keep=keep,
        change=change,
        remove=remove,
        next_actions=next_actions,
        requires_human_approval=True,
    )


def _build_action_lists(
    diagnosis: DiagnosisResult, decision: PivotDecision
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """유지/변경/삭제/다음 행동 목록을 점수에서 도출한다."""

    keep = tuple(
        f"{d.label}: {d.reason}" for d in diagnosis.dimensions if d.raw_score >= 4
    )
    change = tuple(
        f"{d.label}: {d.recommended_action}"
        for d in diagnosis.dimensions
        if 1 <= d.raw_score <= 3
    )
    remove: list[str] = []
    for w in diagnosis.warnings:
        if w.code == WarningCode.BROAD_TARGET:
            remove.append("넓은 타깃 표현을 기획서에서 제거합니다.")
        if w.code == WarningCode.FEATURE_FIRST_IDEA:
            remove.append("문제와 연결되지 않은 기능 서술을 제거합니다.")

    next_actions_map = {
        PivotDecision.PROBLEM_PIVOT: (
            "대상 5명에게 문제 발생 빈도와 최근 사례를 묻는 인터뷰를 진행합니다.",
            "문제 정의 문장을 다시 작성하고 새 버전을 만듭니다.",
        ),
        PivotDecision.TARGET_PIVOT: (
            "타깃 후보 3개 중 하나를 골라 스크리닝 인터뷰를 진행합니다.",
            "선택한 타깃으로 문제 정의를 다시 씁니다.",
        ),
        PivotDecision.SOLUTION_PIVOT: (
            "핵심 행동만 남긴 클릭더미로 완료율을 측정합니다.",
            "첫 성공 경험을 3분 이내로 다시 설계합니다.",
        ),
        PivotDecision.RETENTION_REDESIGN: (
            "재방문 이유를 제품 내 장치로 설계하고 코호트 유지율을 측정합니다.",
        ),
        PivotDecision.CHANNEL_PIVOT: (
            "채널 한 곳을 정해 랜딩 페이지 유입 테스트를 진행합니다.",
        ),
        PivotDecision.REVENUE_PIVOT: (
            "대체재 대비 차별점을 근거와 함께 정리하고 가격 반응을 테스트합니다.",
        ),
        PivotDecision.KEEP: ("현재 가설을 유지한 채 실행 품질과 측정 이벤트를 점검합니다.",),
        PivotDecision.REFINE: ("가장 낮은 평가 항목 두 개를 보완한 새 버전을 만듭니다.",),
        PivotDecision.HOLD: (),
    }

    return keep, change, tuple(dict.fromkeys(remove)), next_actions_map.get(decision, ())
