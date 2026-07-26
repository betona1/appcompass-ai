"""피벗 우선순위 규칙 테스트 (CLAUDE.md §12: HOLD 우선 규칙 검증)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from appcompass.core.enums import DimensionCode, DomainCode, EvidenceType, PivotDecision
from appcompass.core.models import EvidenceItem, IdeaStructure
from appcompass.core.pipeline import run_analysis
from appcompass.core.policy import EvaluationPolicy

from conftest import fixture_idea

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def full_evidence(exclude: set[DimensionCode] | None = None) -> list[EvidenceItem]:
    """모든 항목에 행동 데이터를 붙여 신뢰도를 최대로 올린다."""
    exclude = exclude or set()
    return [
        EvidenceItem(
            id=f"e-{code}",
            evidence_type=EvidenceType.BEHAVIOR_DATA,
            title=f"{code} 행동 데이터",
            sample_size=300,
            supports=(code,),
        )
        for code in DimensionCode
        if code not in exclude
    ]


def analyze(idea: IdeaStructure, domain=DomainCode.GENERIC, evidence=(), policy=None):
    return run_analysis(
        idea,
        domain_code=domain,
        policy=policy or EvaluationPolicy(),
        evidence=evidence,
        now=FIXED_NOW,
    )


def test_hold_takes_priority_when_confidence_is_low():
    """근거가 없으면 내용이 아무리 좋아도 HOLD."""
    result = analyze(fixture_idea("vibequest/refined_target.json"), DomainCode.VIBEQUEST)
    assert result.pivot.decision == PivotDecision.HOLD
    assert result.diagnosis.overall_confidence < EvaluationPolicy().hold_threshold


def test_hold_still_reports_would_be_decision():
    result = analyze(fixture_idea("vibequest/broad_target.json"), DomainCode.VIBEQUEST)
    assert result.pivot.decision == PivotDecision.HOLD
    assert result.pivot.would_be_decision is not None
    assert "LOW_EVIDENCE" in result.pivot.reason_codes


def test_evidence_lifts_hold():
    result = analyze(
        fixture_idea("vibequest/refined_target.json"),
        DomainCode.VIBEQUEST,
        evidence=full_evidence(),
    )
    assert result.pivot.decision != PivotDecision.HOLD
    assert result.pivot.would_be_decision is None


def test_weak_problem_yields_problem_pivot():
    idea = IdeaStructure(
        target_user="특정 상황에서 특정 작업을 하다가 막히는 사용자 집단",
        payer="본인",
        problem_situation="가끔 불편",
        core_action="버튼을 누른다",
        expected_result="30% 개선된다",
        first_success="첫 화면에서 바로 결과를 본다",
        retention_reason="매일 기록이 누적된다",
        current_solution="수기로 처리",
        current_solution_problem="시간이 오래 걸리고 실패가 잦다",
        distribution_channel="커뮤니티와 검색",
    )
    # 문제 항목(D01/D02)만 근거가 비어 있고 나머지는 행동 데이터로 뒷받침되는 상황.
    result = analyze(
        idea, evidence=full_evidence(exclude={DimensionCode.D01, DimensionCode.D02})
    )
    assert result.pivot.decision == PivotDecision.PROBLEM_PIVOT
    assert "WEAK_PROBLEM" in result.pivot.reason_codes


def test_broad_target_yields_target_pivot_when_problem_is_strong():
    idea = IdeaStructure(
        target_user="누구나",
        payer="본인",
        problem_situation=(
            "매일 반복되는 작업 중에 같은 지점에서 막혀 중단되고 결국 포기하는 일이 "
            "자주 발생한다. 시간이 오래 걸리고 실패가 반복되어 불안이 커진다."
        ),
        current_solution="수기로 처리하거나 검색",
        current_solution_problem="상황에 맞지 않아 시간이 오래 걸리고 결국 다시 막힌다",
        core_action="막힌 지점을 골라 3분 안에 해결한다",
        expected_result="작업 재개율이 50% 이상이 된다",
        first_success="첫 3분 안에 한 건을 해결한다",
        retention_reason="매일 새 항목이 열리고 틀린 것이 복습으로 돌아온다",
        distribution_channel="커뮤니티와 오픈채팅 제휴",
    )
    result = analyze(idea, evidence=full_evidence())
    assert result.pivot.decision == PivotDecision.TARGET_PIVOT
    assert "BROAD_TARGET" in result.pivot.reason_codes


def test_low_retention_yields_retention_redesign():
    idea = IdeaStructure.from_dict(
        {
            **fixture_idea("vibequest/refined_target.json").to_dict(),
            "retention_reason": None,
        }
    )
    result = analyze(idea, DomainCode.VIBEQUEST, evidence=full_evidence())
    assert result.pivot.decision == PivotDecision.RETENTION_REDESIGN


def test_weak_channel_yields_channel_pivot():
    idea = IdeaStructure.from_dict(
        {
            **fixture_idea("vibequest/refined_target.json").to_dict(),
            "distribution_channel": None,
        }
    )
    result = analyze(idea, DomainCode.VIBEQUEST, evidence=full_evidence())
    assert result.pivot.decision == PivotDecision.CHANNEL_PIVOT


def test_pivot_always_requires_human_approval():
    result = analyze(
        fixture_idea("examath/refined_target.json"),
        DomainCode.EXAMATH,
        evidence=full_evidence(),
    )
    assert result.pivot.requires_human_approval is True


def test_hold_threshold_is_policy_driven():
    """임계치는 전역 상수가 아니라 정책값이다 (TECHSPEC §5.10)."""
    idea = fixture_idea("vibequest/refined_target.json")
    strict = analyze(idea, DomainCode.VIBEQUEST, policy=EvaluationPolicy(hold_threshold=0.9))
    lenient = analyze(
        idea, DomainCode.VIBEQUEST, policy=EvaluationPolicy(hold_threshold=0.05)
    )
    assert strict.pivot.decision == PivotDecision.HOLD
    assert lenient.pivot.decision != PivotDecision.HOLD


def test_next_actions_are_never_empty():
    result = analyze(fixture_idea("examath/broad_child.json"), DomainCode.EXAMATH)
    assert result.next_actions, "다음 행동이 비어 있으면 사용자가 할 일을 알 수 없습니다."
