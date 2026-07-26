"""피벗 승인 워크플로 테스트 (TECHSPEC F-090, Phase 3).

핵심 원칙: **시스템은 판단을 제안할 뿐 적용하지 않는다.**
사람이 승인하거나 거절해야 하고, 특히 거절 사유가 남아야 한다.
왜 시스템과 다르게 판단했는지 기록되지 않으면 나중에 되짚을 수 없다.
"""

from __future__ import annotations

import pytest

from appcompass.core.enums import ApprovalStatus, DimensionCode, DomainCode, EvidenceType
from appcompass.services.app_service import ServiceError

from conftest import fixture_idea, fixture_raw


def _setup(service, path="examath/refined_target.json", domain=DomainCode.EXAMATH):
    project = service.create_project("승인", domain_code=domain)
    version = service.create_version(project.id, fixture_raw(path), fixture_idea(path))
    service.approve_structure(version.id)
    run = service.run_analysis(version.id)
    return project, version, run


def test_analysis_creates_pending_decision(service):
    project, _, run = _setup(service)
    d = service.latest_pivot_decision(project.id)
    assert d is not None
    assert d.run_id == run.id
    assert d.approval_status == str(ApprovalStatus.PENDING)
    assert d.decision == run.result["pivot"]["decision"]
    assert d.rationale


def test_approve_records_who_and_when(service):
    project, _, _ = _setup(service)
    d = service.latest_pivot_decision(project.id)
    approved = service.approve_pivot(d.id, "타깃을 좁히는 데 동의")

    assert approved.approval_status == str(ApprovalStatus.APPROVED)
    assert approved.approval_note == "타깃을 좁히는 데 동의"
    assert approved.approved_at is not None
    assert "PIVOT_APPROVED" in [a.action for a in service.list_audit_logs()]


def test_reject_requires_a_reason(service):
    """사유 없는 거절은 기록으로서 쓸모가 없다."""
    project, _, _ = _setup(service)
    d = service.latest_pivot_decision(project.id)

    with pytest.raises(ServiceError, match="거절 사유"):
        service.reject_pivot(d.id, "")
    with pytest.raises(ServiceError, match="거절 사유"):
        service.reject_pivot(d.id, "   ")

    rejected = service.reject_pivot(d.id, "타깃 피벗 대신 문제 정의부터 다시 하기로 함")
    assert rejected.approval_status == str(ApprovalStatus.REJECTED)
    assert "문제 정의부터" in rejected.approval_note
    assert "PIVOT_REJECTED" in [a.action for a in service.list_audit_logs()]


def test_cannot_decide_twice(service):
    project, _, _ = _setup(service)
    d = service.latest_pivot_decision(project.id)
    service.approve_pivot(d.id)
    with pytest.raises(ServiceError, match="이미"):
        service.approve_pivot(d.id)
    with pytest.raises(ServiceError, match="이미"):
        service.reject_pivot(d.id, "생각이 바뀜")


def test_new_analysis_supersedes_pending_but_keeps_decided(service):
    """검토하지 않은 판단은 밀려나고, 사람이 내린 결정은 남는다."""
    project, version, _ = _setup(service)

    first = service.latest_pivot_decision(project.id)
    service.approve_pivot(first.id, "동의함")

    # 근거를 추가해 새 분석 → 새 판단
    service.add_evidence(
        project.id, EvidenceType.USER_INTERVIEW, "인터뷰", sample_size=5,
        supports=[DimensionCode.D01, DimensionCode.D02],
    )
    service.run_analysis(version.id)
    second = service.latest_pivot_decision(project.id)
    assert second.id != first.id
    assert second.approval_status == str(ApprovalStatus.PENDING)

    # 또 새 분석 → 검토 안 한 second는 밀려난다
    service.add_evidence(
        project.id, EvidenceType.USER_INTERVIEW, "인터뷰2", sample_size=5,
        supports=[DimensionCode.D05],
    )
    service.run_analysis(version.id)

    history = {d.id: d for d in service.list_pivot_decisions(project.id)}
    assert history[first.id].approval_status == str(ApprovalStatus.APPROVED), (
        "사람이 내린 결정이 사라졌습니다."
    )
    assert history[second.id].approval_status == str(ApprovalStatus.SUPERSEDED)


def test_superseded_cannot_be_decided(service):
    project, version, _ = _setup(service)
    old = service.latest_pivot_decision(project.id)

    service.add_evidence(
        project.id, EvidenceType.USER_INTERVIEW, "인터뷰", sample_size=5,
        supports=[DimensionCode.D01],
    )
    service.run_analysis(version.id)

    with pytest.raises(ServiceError, match="대체된"):
        service.approve_pivot(old.id)


def test_history_is_newest_first_and_complete(service):
    project, version, _ = _setup(service)
    service.approve_pivot(service.latest_pivot_decision(project.id).id, "1차 동의")

    service.add_evidence(
        project.id, EvidenceType.USER_INTERVIEW, "인터뷰", sample_size=5,
        supports=[DimensionCode.D01, DimensionCode.D02],
    )
    service.run_analysis(version.id)
    service.reject_pivot(service.latest_pivot_decision(project.id).id, "2차 거절 사유")

    history = service.list_pivot_decisions(project.id)
    assert len(history) == 2
    assert history[0].created_at >= history[1].created_at
    notes = [d.approval_note for d in history]
    assert "2차 거절 사유" in notes and "1차 동의" in notes


def test_decision_records_score_and_confidence(service):
    """이력만 보고도 그때 상태를 알 수 있어야 한다."""
    project, _, run = _setup(service)
    d = service.latest_pivot_decision(project.id)
    assert d.confidence == pytest.approx(run.result["diagnosis"]["overall_confidence"])
    assert d.total_score == pytest.approx(run.result["diagnosis"]["total_score"])
    assert d.version_no == 1


def test_hold_decision_records_would_be(service):
    project, _, run = _setup(service)
    d = service.latest_pivot_decision(project.id)
    assert d.decision == "HOLD"
    assert d.would_be_decision == run.result["pivot"]["would_be_decision"]


def test_next_step_asks_for_approval_before_finishing(service):
    """근거가 충분해지면 마무리보다 승인을 먼저 물어야 한다."""
    project, version, _ = _setup(service)
    for codes in (
        [DimensionCode.D01, DimensionCode.D02, DimensionCode.D03],
        [DimensionCode.D04, DimensionCode.D05, DimensionCode.D06],
        [DimensionCode.D07, DimensionCode.D08, DimensionCode.D09, DimensionCode.D10],
    ):
        service.add_evidence(
            project.id, EvidenceType.BEHAVIOR_DATA, f"로그 {codes[0]}",
            sample_size=200, supports=codes,
        )
    service.run_analysis(version.id)

    step = service.next_step(project.id)
    assert step.step_id == "APPROVE_PIVOT"
    assert step.screen == "report"

    service.approve_pivot(service.latest_pivot_decision(project.id).id)
    assert service.next_step(project.id).stage_code == "FINISH"


def test_rejection_also_unblocks_next_step(service):
    """거절도 사람의 결정이므로 다음으로 넘어가야 한다."""
    project, version, _ = _setup(service)
    for codes in (
        [DimensionCode.D01, DimensionCode.D02, DimensionCode.D03],
        [DimensionCode.D04, DimensionCode.D05, DimensionCode.D06],
        [DimensionCode.D07, DimensionCode.D08, DimensionCode.D09, DimensionCode.D10],
    ):
        service.add_evidence(
            project.id, EvidenceType.BEHAVIOR_DATA, f"로그 {codes[0]}",
            sample_size=200, supports=codes,
        )
    service.run_analysis(version.id)
    service.reject_pivot(
        service.latest_pivot_decision(project.id).id, "사내 사정으로 이번 분기는 유지"
    )
    assert service.next_step(project.id).step_id != "APPROVE_PIVOT"
