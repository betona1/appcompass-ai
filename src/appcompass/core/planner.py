"""타깃 후보와 MVP 계획 생성 (TECHSPEC F-060, F-070).

Phase 1은 LLM을 쓰지 않는다. 후보는 두 곳에서만 나온다.
1) 도메인 모듈이 가진 문서 근거 기반 후보 (seed_target_candidates)
2) 사용자가 이미 입력한 구조화 결과에서 파생한 후보

근거가 부족하면 추천하지 않고 비교만 제공한다 (TECHSPEC F-060 규칙).
"""

from __future__ import annotations

from typing import Sequence

from .domains.base import DomainModule
from .enums import DimensionCode, WarningCode
from .models import (
    DiagnosisResult,
    IdeaStructure,
    MvpPlan,
    TargetCandidate,
    TargetCandidateSet,
)
from .policy import EvaluationPolicy
from .textsignals import has_text


def build_target_candidates(
    idea: IdeaStructure,
    diagnosis: DiagnosisResult,
    domain: DomainModule,
    policy: EvaluationPolicy,
) -> TargetCandidateSet:
    candidates: list[TargetCandidate] = list(domain.seed_target_candidates(idea))

    current = _current_target_as_candidate(idea, diagnosis)
    if current is not None:
        candidates.insert(0, current)

    if not candidates:
        return TargetCandidateSet(
            candidates=(),
            recommended_candidate_index=None,
            recommendation_reason=(
                "도메인 지식과 입력 근거가 모두 부족해 타깃 후보를 제시하지 않습니다. "
                "먼저 타깃을 상황 + 현재 행동 + 중단 원인으로 다시 작성하세요."
            ),
            source="RULE",
        )

    # 추천은 근거가 충분할 때만 한다.
    if diagnosis.overall_confidence < policy.hold_threshold:
        reason = (
            f"전체 근거 신뢰도가 {diagnosis.overall_confidence:.2f}로 기준 "
            f"{policy.hold_threshold:.2f} 미만이라 하나를 추천하지 않습니다. "
            "세 후보를 비교한 뒤 스크리닝 인터뷰로 직접 고르세요."
        )
        return TargetCandidateSet(
            candidates=tuple(candidates[:4]),
            recommended_candidate_index=None,
            recommendation_reason=reason,
            source="RULE",
        )

    # 현재 타깃이 넓다면 도메인 후보 중 첫 번째를 추천한다.
    if diagnosis.has_warning(WarningCode.BROAD_TARGET) and len(candidates) > 1:
        index = 1 if current is not None else 0
        reason = (
            "현재 타깃에 넓은 표현이 있어 그대로 검증하기 어렵습니다. "
            f"'{candidates[index].name}'는 중단 시점이 명확해 실험 설계가 가능합니다."
        )
    else:
        index = 0
        reason = (
            "현재 타깃이 상황 기반으로 정의되어 있고 근거 신뢰도가 기준을 넘겨 "
            "그대로 유지한 채 검증을 진행할 수 있습니다."
        )

    return TargetCandidateSet(
        candidates=tuple(candidates[:4]),
        recommended_candidate_index=index,
        recommendation_reason=reason,
        source="RULE",
    )


def _current_target_as_candidate(
    idea: IdeaStructure, diagnosis: DiagnosisResult
) -> TargetCandidate | None:
    if not has_text(idea.target_user, 2):
        return None

    risks: list[str] = []
    if diagnosis.has_warning(WarningCode.BROAD_TARGET):
        risks.append("타깃 표현이 넓어 실험 대상을 특정할 수 없습니다.")
    if diagnosis.dimension(DimensionCode.D04).raw_score <= 2:
        risks.append("사용자와 구매자가 분리되지 않았습니다.")
    if not has_text(idea.current_solution, 2):
        risks.append("현재 대체 방법이 없어 문제 존재 여부를 확인할 수 없습니다.")

    return TargetCandidate(
        name="현재 입력된 타깃",
        user=idea.target_user,
        payer=idea.payer,
        influencer=idea.influencer,
        trigger_situation=idea.problem_situation,
        problem=idea.current_solution_problem or idea.problem_situation,
        current_alternative=idea.current_solution,
        why_promising=("사용자가 직접 정의한 타깃이라 즉시 접촉 가능성이 있습니다.",),
        risks=tuple(risks) or ("확인된 위험 없음. 근거로 검증 필요.",),
        validation_questions=(
            "이 타깃에 해당하는 사람을 이번 주에 5명 만날 수 있는가",
            "그 사람들은 지금 이 문제를 어떻게 넘기고 있는가",
        ),
        recommended_experiment="스크리닝 질문 3개로 해당 타깃 5명을 찾아 인터뷰",
    )


def build_mvp_plan(
    idea: IdeaStructure,
    diagnosis: DiagnosisResult,
    domain: DomainModule,
) -> MvpPlan:
    """구조화 결과에서 MVP 초안을 만든다.

    CLAUDE.md §2.5: MVP 범위는 P0 + 최소한의 P1.
    측정 이벤트가 없는 기능은 넣지 않는다 (§2.6).
    """

    core_action = idea.core_action.strip() or "(핵심 행동 미정의)"
    expected = idea.expected_result.strip() or "(기대 결과 미정의)"

    p0: list[str] = []
    if has_text(idea.core_action, 2):
        p0.append(f"핵심 행동: {core_action}")
    if has_text(idea.first_success, 2):
        p0.append(f"첫 성공 경험: {idea.first_success.strip()}")
    else:
        p0.append("첫 성공 경험 설계 (3분 이내 완료 가능한 최소 성공)")
    p0.append("핵심 행동 완료 이벤트 기록")

    p1: list[str] = []
    if has_text(idea.retention_reason, 2):
        p1.append(f"재방문 장치: {idea.retention_reason.strip()}")
    p1.append("실패·빈 상태·권한 거부 화면")
    p1.append("결과 요약 화면 (점수보다 이유와 다음 행동 우선)")

    excluded: list[str] = [
        "P2/P3 편의·장식·확장 기능",
        "측정 이벤트가 연결되지 않은 모든 기능",
    ]

    metrics: list[str] = ["activation_complete", "core_action_complete", "day1_return"]

    risks: list[str] = list(diagnosis.critical_risks)

    plan = MvpPlan(
        core_hypothesis=(
            f"{idea.target_user.strip() or '(타깃 미정의)'}는 "
            f"{core_action}을(를) 통해 {expected}을(를) 얻는다."
        ),
        problem_hypothesis=idea.problem_situation.strip() or "(문제 상황 미정의)",
        behavior_hypothesis=f"사용자는 첫 세션에서 {core_action}을(를) 끝까지 완료한다.",
        value_hypothesis=f"핵심 행동을 마치면 {expected}이(가) 실제로 발생한다.",
        retention_hypothesis=(
            idea.retention_reason.strip()
            if has_text(idea.retention_reason, 2)
            else "재방문 이유가 아직 정의되지 않아 가설을 세울 수 없다."
        ),
        revenue_hypothesis=(
            idea.revenue_model.strip() if has_text(idea.revenue_model, 2) else None
        ),
        p0_features=tuple(dict.fromkeys(p0)),
        p1_features=tuple(dict.fromkeys(p1)),
        excluded_features=tuple(dict.fromkeys(excluded)),
        first_success_experience=(
            idea.first_success.strip()
            if has_text(idea.first_success, 2)
            else "미정의 — 활성화 지점을 먼저 정해야 합니다."
        ),
        core_user_flow=(
            "진입",
            "상황 선택 또는 짧은 진단",
            f"핵심 행동 수행: {core_action}",
            "즉각 피드백",
            "결과 요약과 다음 행동 제시",
        ),
        metrics=tuple(metrics),
        risks=tuple(risks),
        source="RULE",
    )

    return domain.constrain_mvp(plan, idea)
