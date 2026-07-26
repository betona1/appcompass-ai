"""다음 할 일 판정 테스트.

이 기능의 핵심은 **한 번에 하나만 시키는 것**이다.
순서가 틀리면(예: 문제 정의가 비었는데 유입 경로를 고민하라고 하면)
사용자를 엉뚱한 곳으로 보낸다. 그 순서를 테스트로 고정한다.
"""

from __future__ import annotations

import pytest

from appcompass.core.enums import (
    DimensionCode,
    DomainCode,
    EvidenceType,
    ImplementationStatus,
    ProjectStage,
)
from appcompass.core.models import IdeaStructure, RawIdeaInput
from appcompass.core.nextstep import JOURNEY, ProjectState, decide_next_step
from appcompass.core.policy import EvaluationPolicy

from conftest import fixture_idea, fixture_raw


# ==========================================================================
# 순수 규칙
# ==========================================================================


def test_no_project_asks_to_create_one():
    step = decide_next_step(ProjectState(has_project=False))
    assert step.step_id == "CREATE_PROJECT"
    assert step.stage_index == 0


def test_project_without_version_asks_for_idea():
    step = decide_next_step(ProjectState(has_project=True))
    assert step.step_id == "WRITE_IDEA"
    assert step.screen == "idea"


def test_missing_required_comes_before_approval():
    """필수 항목이 비었으면 승인하라고 하면 안 된다."""
    step = decide_next_step(
        ProjectState(
            has_project=True,
            has_version=True,
            missing_required=(("core_action", "핵심 행동", "없으면 MVP를 못 만듭니다"),),
            structure_approved=False,
        )
    )
    assert step.step_id == "FILL_REQUIRED"
    assert "핵심 행동" in step.title


def test_approval_comes_before_analysis():
    step = decide_next_step(
        ProjectState(has_project=True, has_version=True, structure_approved=False)
    )
    assert step.step_id == "APPROVE"


def test_approved_but_no_analysis_asks_to_run():
    step = decide_next_step(
        ProjectState(has_project=True, has_version=True, structure_approved=True)
    )
    assert step.step_id == "RUN_ANALYSIS"


def test_failed_analysis_is_surfaced():
    step = decide_next_step(
        ProjectState(
            has_project=True,
            has_version=True,
            structure_approved=True,
            analysis_failed=True,
            analysis_error="FAILED_SCHEMA: ...",
        )
    )
    assert step.step_id == "ANALYSIS_FAILED"
    assert "FAILED_SCHEMA" in step.why


def test_journey_has_no_gaps():
    """모든 단계 코드가 여정 목록에 있어야 진행률이 어긋나지 않는다."""
    codes = {code for code, _ in JOURNEY}
    for state in (
        ProjectState(),
        ProjectState(has_project=True),
        ProjectState(has_project=True, has_version=True),
        ProjectState(has_project=True, has_version=True, structure_approved=True),
    ):
        assert decide_next_step(state).stage_code in codes


# ==========================================================================
# 서비스 통합 — 실제 흐름을 따라가며 순서가 맞는지
# ==========================================================================


def test_full_journey_order(service):
    """빈 상태부터 마무리까지, 안내가 순서대로 바뀌는지 확인한다."""
    # 1) 프로젝트 없음
    assert service.next_step(None).step_id == "CREATE_PROJECT"

    project = service.create_project("여정", domain_code=DomainCode.VIBEQUEST)

    # 2) 버전 없음
    assert service.next_step(project.id).step_id == "WRITE_IDEA"

    # 3) 필수 항목 비어 있음
    service.create_version(
        project.id,
        RawIdeaInput(app_name="앱", raw_idea="아이디어만 적음"),
        IdeaStructure(app_name="앱"),
    )
    step = service.next_step(project.id)
    assert step.step_id == "FILL_REQUIRED"

    # 4) 필수 항목 채움 → 승인 요구
    version = service.latest_version(project.id)
    service.update_version(
        version.id, idea=fixture_idea("vibequest/refined_target.json")
    )
    assert service.next_step(project.id).step_id == "APPROVE"

    # 5) 승인 → 분석 요구
    service.approve_structure(version.id)
    assert service.next_step(project.id).step_id == "RUN_ANALYSIS"

    # 6) 분석 → 근거 요구 (근거 0건이므로)
    service.run_analysis(version.id)
    step = service.next_step(project.id)
    assert step.step_id in ("FIX_CRITICAL", "ADD_EVIDENCE")

    # 7) 근거를 충분히 등록하면 HOLD가 풀리고 마무리 단계로
    for code_set in (
        [DimensionCode.D01, DimensionCode.D02, DimensionCode.D03],
        [DimensionCode.D04, DimensionCode.D05, DimensionCode.D06],
        [DimensionCode.D07, DimensionCode.D08, DimensionCode.D09, DimensionCode.D10],
    ):
        service.add_evidence(
            project.id,
            EvidenceType.BEHAVIOR_DATA,
            f"행동 데이터 {code_set[0]}",
            sample_size=200,
            supports=code_set,
        )
    service.run_analysis(version.id)
    step = service.next_step(project.id)
    assert step.stage_code == "FINISH", f"마무리 단계가 아닙니다: {step.step_id}"
    assert step.is_done is True
    assert step.screen == "report"


def test_evidence_step_appears_when_hold(service):
    project = service.create_project("근거 안내", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)

    step = service.next_step(project.id)
    assert step.step_id == "ADD_EVIDENCE"
    assert step.screen == "experiments"
    assert "HOLD" in step.why or "판단 보류" in step.why


def test_critical_warning_comes_before_evidence(service):
    """치명 경고가 있으면 근거보다 먼저 고치라고 해야 한다."""
    project = service.create_project("치명", domain_code=DomainCode.EXAMATH)
    idea = IdeaStructure.from_dict(
        {
            **fixture_idea("examath/refined_target.json").to_dict(),
            "target_user": "수학을 배우는 아이 전체",  # BROAD_TARGET 치명
        }
    )
    version = service.create_version(
        project.id, fixture_raw("examath/refined_target.json"), idea
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)

    step = service.next_step(project.id)
    assert step.step_id == "FIX_CRITICAL"
    assert step.screen == "structure"


def test_mvp_stage_asks_to_mark_built_features(service):
    """이미 만든 단계면 구현 상태를 물어야 개선 명세를 줄 수 있다."""
    project = service.create_project(
        "출시함", domain_code=DomainCode.VIBEQUEST, stage=ProjectStage.MVP
    )
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
    )
    service.approve_structure(version.id)
    for code_set in (
        [DimensionCode.D01, DimensionCode.D02, DimensionCode.D03, DimensionCode.D04],
        [DimensionCode.D05, DimensionCode.D06, DimensionCode.D07],
        [DimensionCode.D08, DimensionCode.D09, DimensionCode.D10],
    ):
        service.add_evidence(
            project.id, EvidenceType.BEHAVIOR_DATA, f"로그 {code_set[0]}",
            sample_size=200, supports=code_set,
        )
    service.run_analysis(version.id)

    step = service.next_step(project.id)
    assert step.step_id == "MARK_BUILT"
    assert step.screen == "mvp"

    # 구현 상태를 표시하면 개선 명세로 넘어간다
    features = service.list_feature_status(project.id)
    service.set_feature_status(project.id, features[0], ImplementationStatus.DONE)
    step = service.next_step(project.id)
    assert step.step_id == "EXPORT_IMPROVEMENT"


def test_next_step_is_deterministic(service):
    project = service.create_project("결정론", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)
    a = service.next_step(project.id)
    b = service.next_step(project.id)
    assert a == b


def test_every_step_tells_what_to_do(service):
    """안내가 비어 있으면 막막함이 그대로다. 모든 단계에 why와 how가 있어야 한다."""
    states = [
        ProjectState(),
        ProjectState(has_project=True),
        ProjectState(has_project=True, has_version=True),
        ProjectState(
            has_project=True, has_version=True,
            missing_required=(("core_action", "핵심 행동", "이유"),),
        ),
        ProjectState(has_project=True, has_version=True, structure_approved=True),
        ProjectState(
            has_project=True, has_version=True, structure_approved=True,
            analysis_failed=True, analysis_error="오류",
        ),
    ]
    for state in states:
        step = decide_next_step(state)
        assert step.title, f"{step.step_id}: 제목 없음"
        assert step.why, f"{step.step_id}: 이유 없음"
        assert step.how, f"{step.step_id}: 방법 없음"
