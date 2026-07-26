"""고정 시나리오 회귀 테스트 (TECHSPEC §15.3, CLAUDE.md §12).

두 도메인의 고정 입력이 문서에 적힌 기대 결과를 만족하는지 확인한다.
이 테스트가 깨지면 판정 규칙이 문서와 어긋난 것이다.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from appcompass.core.enums import (
    DimensionCode,
    DomainCode,
    EvidenceType,
    PivotDecision,
    WarningCode,
)
from appcompass.core.models import EvidenceItem
from appcompass.core.pipeline import run_analysis
from appcompass.core.policy import EvaluationPolicy
from appcompass.core.schema import validate_analysis_result

from conftest import fixture_idea

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def analyze(path: str, domain: DomainCode, evidence=(), policy=None):
    return run_analysis(
        fixture_idea(path),
        domain_code=domain,
        policy=policy or EvaluationPolicy(),
        evidence=evidence,
        now=FIXED_NOW,
    )


# ==========================================================================
# VibeQuest 고정 시나리오
# ==========================================================================


def test_vibequest_broad_target_scenario():
    result = analyze("vibequest/broad_target.json", DomainCode.VIBEQUEST)

    # 1) BROAD_TARGET 경고
    assert result.diagnosis.has_warning(WarningCode.BROAD_TARGET)

    # 2) TARGET_PIVOT 또는 신뢰도 부족 시 HOLD
    assert result.pivot.decision in (PivotDecision.TARGET_PIVOT, PivotDecision.HOLD)
    if result.pivot.decision == PivotDecision.HOLD:
        assert result.pivot.would_be_decision is not None, (
            "HOLD면 근거가 충분했을 때의 판단을 함께 제시해야 합니다."
        )

    # 3) 초보 프로젝트 제작자 후보 포함
    users = " ".join(c.user for c in result.targets.candidates)
    assert "처음" in users and ("비개발자" in users or "초보" in users)

    # 4) 일반 용어 퀴즈 차별성 위험이 드러남
    assert result.diagnosis.has_warning(WarningCode.NO_REAL_TASK_CONTEXT)

    # 5) 실제 상황형 문제가 다음 행동으로 제안됨
    joined = " ".join(
        [c.recommended_experiment for c in result.targets.candidates]
        + list(result.next_actions)
        + [w.recommended_action for w in result.diagnosis.warnings]
    )
    assert "실제" in joined or "상황" in joined


def test_vibequest_refined_scenario_has_no_broad_target():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    assert not result.diagnosis.has_warning(WarningCode.BROAD_TARGET)
    assert result.diagnosis.total_score > 60
    assert result.diagnosis.dimension(DimensionCode.D03).raw_score >= 4


def test_vibequest_excluded_features_are_enforced():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    excluded = " ".join(result.mvp.excluded_features)
    for banned in ("유료 루트박스", "실시간 PvP", "실시간 전체 랭킹"):
        assert banned in excluded


def test_vibequest_domain_metrics_present():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    assert "concept_to_task_transfer" in result.mvp.metrics
    assert "first_mission_complete" in result.mvp.metrics


# ==========================================================================
# examath 고정 시나리오
# ==========================================================================


def test_examath_broad_child_scenario():
    result = analyze("examath/broad_child.json", DomainCode.EXAMATH)

    # 1) 사용자·구매자 분리 경고
    assert result.diagnosis.has_warning(WarningCode.NO_PAYER_DEFINED)

    # 2) 초등 2학년 받아내림 후보
    users = " ".join(c.user for c in result.targets.candidates)
    assert "2학년" in users and "받아내림" in users

    # 3) 오류 유형 진단 제안
    p0 = " ".join(result.mvp.p0_features)
    assert "오류 유형" in p0 or "진단" in p0

    # 4) 구체물 → 그림 → 숫자 전환
    p_all = " ".join(result.mvp.p0_features + result.mvp.p1_features)
    assert "구체물" in p_all and "그림" in p_all and "숫자" in p_all

    # 5) 광고·가챠·실시간 랭킹 제외
    excluded = " ".join(result.mvp.excluded_features)
    for banned in ("광고", "가챠", "실시간 랭킹"):
        assert banned in excluded


def test_examath_broad_child_warns_about_grade_and_scope():
    result = analyze("examath/broad_child.json", DomainCode.EXAMATH)
    assert result.diagnosis.has_warning(WarningCode.NO_GRADE_SPECIFIED)
    assert result.diagnosis.has_warning(WarningCode.BROAD_TARGET)


def test_examath_child_safety_violation_forces_solution_pivot():
    """광고·가챠·랭킹이 포함되면 신뢰도가 충분해도 SOLUTION_PIVOT으로 막는다."""
    from appcompass.core.models import IdeaStructure

    idea = IdeaStructure.from_dict(
        {
            **fixture_idea("examath/refined_target.json").to_dict(),
            "revenue_model": "광고와 가챠 뽑기로 수익을 낸다",
            "retention_reason": "실시간 랭킹으로 친구와 경쟁하게 한다",
        }
    )
    evidence = [
        EvidenceItem(
            id=f"e{i}",
            evidence_type=EvidenceType.BEHAVIOR_DATA,
            title="행동 데이터",
            sample_size=200,
            supports=(code,),
        )
        for i, code in enumerate(DimensionCode)
    ]
    result = run_analysis(
        idea,
        domain_code=DomainCode.EXAMATH,
        policy=EvaluationPolicy(),
        evidence=evidence,
        now=FIXED_NOW,
    )
    assert result.diagnosis.overall_confidence >= EvaluationPolicy().hold_threshold
    assert result.pivot.decision == PivotDecision.SOLUTION_PIVOT
    assert "EM_CHILD_SAFETY_VIOLATION" in result.pivot.reason_codes


def test_examath_refined_scenario_separates_roles():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    assert not result.diagnosis.has_warning(WarningCode.NO_PAYER_DEFINED)
    assert result.diagnosis.dimension(DimensionCode.D04).raw_score == 5


# ==========================================================================
# 공통
# ==========================================================================


@pytest.mark.parametrize(
    "path,domain",
    [
        ("vibequest/broad_target.json", DomainCode.VIBEQUEST),
        ("vibequest/refined_target.json", DomainCode.VIBEQUEST),
        ("examath/broad_child.json", DomainCode.EXAMATH),
        ("examath/refined_target.json", DomainCode.EXAMATH),
    ],
)
def test_analysis_result_passes_json_schema(path, domain):
    result = analyze(path, domain)
    validate_analysis_result(result.to_dict())  # 실패 시 예외


@pytest.mark.parametrize(
    "path,domain",
    [
        ("vibequest/refined_target.json", DomainCode.VIBEQUEST),
        ("examath/refined_target.json", DomainCode.EXAMATH),
    ],
)
def test_same_input_same_output(path, domain):
    a = analyze(path, domain).to_dict()
    b = analyze(path, domain).to_dict()
    assert a == b, "동일 입력인데 결과가 달라졌습니다. 판정이 재현 불가능합니다."


def test_meta_records_engine_and_policy_version():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    assert result.meta.engine == "RULE_ENGINE"
    assert result.meta.policy_version == EvaluationPolicy().version
    assert result.meta.model_name is None, "Phase 1은 LLM을 쓰지 않습니다."
