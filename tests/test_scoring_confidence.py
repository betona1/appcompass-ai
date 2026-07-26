"""점수·신뢰도 계산 테스트 (CLAUDE.md §12)."""

from __future__ import annotations

from datetime import datetime, timezone

from appcompass.core.confidence import compute_confidence
from appcompass.core.enums import DimensionCode, EvidenceType
from appcompass.core.models import EvidenceItem, IdeaStructure
from appcompass.core.policy import EvaluationPolicy
from appcompass.core.rules import detect_warnings
from appcompass.core.scoring import score_dimensions, total_score

from conftest import fixture_idea


def _score(idea: IdeaStructure, evidence=(), policy=None):
    policy = policy or EvaluationPolicy()
    warnings = detect_warnings(idea)
    conf = compute_confidence(evidence, policy)
    return score_dimensions(
        idea, warnings, evidence, policy, confidences=conf.per_dimension
    )


def test_normalized_score_is_weight_times_ratio():
    dims = _score(fixture_idea("vibequest/refined_target.json"))
    for d in dims:
        assert d.normalized_score == (d.raw_score / 5) * d.weight


def test_total_score_within_range():
    for path in (
        "vibequest/broad_target.json",
        "vibequest/refined_target.json",
        "examath/broad_child.json",
        "examath/refined_target.json",
    ):
        dims = _score(fixture_idea(path))
        assert 0.0 <= total_score(dims) <= 100.0


def test_empty_idea_scores_zero():
    dims = _score(IdeaStructure())
    assert total_score(dims) == 0.0
    assert all(d.raw_score == 0 for d in dims)


def test_refined_input_scores_higher_than_broad():
    broad = total_score(_score(fixture_idea("vibequest/broad_target.json")))
    refined = total_score(_score(fixture_idea("vibequest/refined_target.json")))
    assert refined > broad + 20, (
        f"타깃과 문제를 구체화했는데 점수 차이가 작습니다: {broad:.1f} -> {refined:.1f}"
    )


def test_broad_target_caps_d03():
    dims = {d.code: d for d in _score(fixture_idea("vibequest/broad_target.json"))}
    assert dims[DimensionCode.D03].raw_score <= 2, "넓은 타깃인데 타깃 명확성이 3점 이상입니다."


def test_scoring_is_deterministic():
    idea = fixture_idea("examath/refined_target.json")
    first = [d.to_dict() for d in _score(idea)]
    second = [d.to_dict() for d in _score(idea)]
    assert first == second


# --- 신뢰도 -------------------------------------------------------------


def test_no_evidence_confidence_is_capped():
    policy = EvaluationPolicy()
    result = compute_confidence([], policy)
    for code in DimensionCode:
        assert result.per_dimension[code] <= policy.no_evidence_confidence_cap
    assert result.overall <= policy.no_evidence_confidence_cap


def test_behavior_data_raises_confidence():
    policy = EvaluationPolicy()
    evidence = [
        EvidenceItem(
            id="e1",
            evidence_type=EvidenceType.BEHAVIOR_DATA,
            title="핵심 행동 완료 로그",
            sample_size=200,
            supports=(DimensionCode.D02,),
        )
    ]
    result = compute_confidence(evidence, policy)
    assert result.per_dimension[DimensionCode.D02] > 0.9
    assert result.per_dimension[DimensionCode.D01] <= policy.no_evidence_confidence_cap


def test_conflicting_evidence_lowers_confidence_and_warns():
    policy = EvaluationPolicy()
    supporting = EvidenceItem(
        id="e1",
        evidence_type=EvidenceType.USER_INTERVIEW,
        title="지지 인터뷰",
        sample_size=8,
        supports=(DimensionCode.D01,),
    )
    contradicting = EvidenceItem(
        id="e2",
        evidence_type=EvidenceType.PROTOTYPE_TEST,
        title="반박 프로토타입",
        sample_size=8,
        contradicts=(DimensionCode.D01,),
    )
    only_support = compute_confidence([supporting], policy)
    with_conflict = compute_confidence([supporting, contradicting], policy)

    assert with_conflict.per_dimension[DimensionCode.D01] < only_support.per_dimension[
        DimensionCode.D01
    ]
    assert any(w.code.value == "CONFLICTING_EVIDENCE" for w in with_conflict.warnings)


def test_sample_size_alone_does_not_exceed_type_ceiling():
    policy = EvaluationPolicy()
    huge = EvidenceItem(
        id="e1",
        evidence_type=EvidenceType.FOUNDER_ASSUMPTION,
        title="창업자 가정",
        sample_size=100000,
        supports=(DimensionCode.D01,),
    )
    result = compute_confidence([huge], policy)
    assert result.per_dimension[DimensionCode.D01] <= policy.confidence_of(
        EvidenceType.FOUNDER_ASSUMPTION
    )


def test_confidence_override_is_respected():
    policy = EvaluationPolicy()
    item = EvidenceItem(
        id="e1",
        evidence_type=EvidenceType.EXPERT_REVIEW,
        title="전문가 검토",
        confidence_override=0.9,
        sample_size=10,
        supports=(DimensionCode.D08,),
    )
    result = compute_confidence([item], policy)
    assert abs(result.per_dimension[DimensionCode.D08] - 0.9) < 1e-6


def test_overall_confidence_is_weighted_average():
    policy = EvaluationPolicy()
    evidence = [
        EvidenceItem(
            id=f"e{i}",
            evidence_type=EvidenceType.BEHAVIOR_DATA,
            title="행동 데이터",
            sample_size=100,
            supports=(code,),
        )
        for i, code in enumerate(DimensionCode)
    ]
    result = compute_confidence(evidence, policy)
    expected = (
        sum(result.per_dimension[c] * policy.weight_of(c) for c in DimensionCode) / 100.0
    )
    assert abs(result.overall - expected) < 1e-6
