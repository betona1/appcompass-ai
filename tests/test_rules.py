"""규칙 엔진 테스트 (CLAUDE.md §12: '모든 사람'을 넓은 타깃으로 감지, 사용자·구매자·영향자 분리)."""

from __future__ import annotations

import pytest

from appcompass.core.enums import DomainCode, Severity, WarningCode
from appcompass.core.models import IdeaStructure
from appcompass.core.rules import detect_warnings
from appcompass.core.textsignals import broad_target_hits


@pytest.mark.parametrize(
    "phrase",
    [
        "모든 사람",
        "누구나",
        "전 국민",
        "학생 전체",
        "AI에 관심 있는 사람",
        "개발을 배우고 싶은 사람",
        "수학을 배우는 아이 전체",
    ],
)
def test_broad_target_phrases_detected(phrase):
    assert broad_target_hits(phrase), f"'{phrase}'를 넓은 타깃으로 감지하지 못했습니다."


def test_broad_target_warning_is_critical():
    idea = IdeaStructure(target_user="바이브코딩에 관심 있는 모든 사람")
    warnings = detect_warnings(idea)
    broad = [w for w in warnings if w.code == WarningCode.BROAD_TARGET]
    assert broad, "BROAD_TARGET 경고가 없습니다."
    assert broad[0].severity == Severity.CRITICAL


def test_specific_target_does_not_trigger_broad_warning():
    idea = IdeaStructure(
        target_user=(
            "AI 코딩 도구로 처음 앱을 만들다가 API·토큰 용어를 몰라 "
            "작업이 중단되는 비개발자"
        ),
        current_solution="AI에게 되묻기",
    )
    warnings = detect_warnings(idea)
    assert not any(w.code == WarningCode.BROAD_TARGET for w in warnings)


def test_payer_missing_is_critical_for_child_context():
    idea = IdeaStructure(
        target_user="초등학교 2학년 어린이",
        problem_situation="받아내림 문제를 만나면 손을 놓는다",
    )
    warnings = detect_warnings(idea, DomainCode.GENERIC)
    payer = [w for w in warnings if w.code == WarningCode.NO_PAYER_DEFINED]
    assert payer
    assert payer[0].severity == Severity.CRITICAL, "어린이 맥락에서는 치명 경고여야 합니다."


def test_payer_missing_is_only_warn_for_adult_context():
    idea = IdeaStructure(
        target_user="AI 코딩 도구를 쓰는 1인 개발자",
        problem_situation="배포 단계에서 오류 메시지를 이해하지 못해 막힌다",
    )
    warnings = detect_warnings(idea)
    payer = [w for w in warnings if w.code == WarningCode.NO_PAYER_DEFINED]
    assert payer
    assert payer[0].severity == Severity.WARN


def test_role_separation_removes_payer_warning():
    idea = IdeaStructure(
        target_user="초등학교 2학년 어린이",
        payer="부모",
        influencer="초등교사",
        problem_situation="받아내림 문제를 만나면 손을 놓는다",
    )
    warnings = detect_warnings(idea)
    assert not any(w.code == WarningCode.NO_PAYER_DEFINED for w in warnings)


def test_missing_core_fields_are_reported():
    warnings = detect_warnings(IdeaStructure())
    codes = {w.code for w in warnings}
    assert WarningCode.NO_TRIGGER_SITUATION in codes
    assert WarningCode.FEATURE_FIRST_IDEA in codes  # 핵심 행동 없음
    assert WarningCode.NO_MEASURABLE_RESULT in codes
    assert WarningCode.NO_FIRST_SUCCESS in codes
    assert WarningCode.NO_RETENTION_REASON in codes


def test_unmeasurable_result_is_flagged():
    idea = IdeaStructure(
        target_user="상황이 있는 타깃 설명",
        problem_situation="작업 중에 막혀서 중단된다",
        core_action="미션을 완료한다",
        expected_result="용어를 잘 알게 된다",
    )
    warnings = detect_warnings(idea)
    assert any(w.code == WarningCode.NO_MEASURABLE_RESULT for w in warnings)


def test_dedupe_keeps_most_severe_not_first():
    """도메인의 치명 경고가 공통 규칙의 주의 경고에 가려지면 안 된다."""
    from appcompass.core.domains.registry import get_domain
    from appcompass.core.rules import dedupe_warnings

    idea = IdeaStructure(
        target_user="수학을 처음 배우는 꼬맹이들",
        problem_situation="뺄셈에서 막혀 수학을 싫어하게 된다",
        core_action="뺄셈 문제를 푼다",
        expected_result="뺄셈을 잘하게 된다",
    )
    merged = dedupe_warnings(
        detect_warnings(idea, DomainCode.EXAMATH)
        + get_domain(DomainCode.EXAMATH).validate_input(idea)
    )
    broad = [w for w in merged if w.code == WarningCode.BROAD_TARGET]
    assert len(broad) == 1
    assert broad[0].severity == Severity.CRITICAL
    assert "학년" in broad[0].recommended_action


def test_measurable_result_passes():
    idea = IdeaStructure(
        target_user="상황이 있는 타깃 설명",
        problem_situation="작업 중에 막혀서 중단된다",
        core_action="미션을 완료한다",
        expected_result="학습 후 작업 재개율이 50% 이상이 된다",
    )
    warnings = detect_warnings(idea)
    assert not any(w.code == WarningCode.NO_MEASURABLE_RESULT for w in warnings)
