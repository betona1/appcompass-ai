"""서비스 계층 테스트: 권한, 감사 로그, idempotency, 보고서 버전 추적."""

from __future__ import annotations

import pytest

from appcompass.core.enums import (
    DimensionCode,
    DomainCode,
    EvidenceType,
    ReportFormat,
)
from appcompass.core.policy import EvaluationPolicy
from appcompass.services.app_service import AppService, PermissionDenied, ServiceError
from appcompass.storage.db import Database

from conftest import fixture_idea, fixture_raw


def make_project(service: AppService, fixture: str, domain: DomainCode):
    project = service.create_project("테스트 프로젝트", domain_code=domain)
    version = service.create_version(
        project.id,
        fixture_raw(fixture),
        fixture_idea(fixture),
        change_reason="최초 버전",
    )
    return project, version


def test_analysis_requires_structure_approval(service):
    project, version = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    with pytest.raises(ServiceError, match="승인"):
        service.run_analysis(version.id)


def test_full_flow_produces_reports(service):
    project, version = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    service.approve_structure(version.id)
    run = service.run_analysis(version.id)

    assert run.status == "COMPLETED"
    assert run.result is not None
    assert run.policy_version == EvaluationPolicy().version

    reports = {r.format: r for r in service.get_reports(run.id)}
    assert str(ReportFormat.MARKDOWN) in reports
    assert str(ReportFormat.HTML) in reports
    assert reports[str(ReportFormat.MARKDOWN)].checksum
    assert "진단 보고서" in reports[str(ReportFormat.MARKDOWN)].content
    assert "<html" in reports[str(ReportFormat.HTML)].content


def test_idempotency_prevents_duplicate_runs(service):
    project, version = make_project(
        service, "examath/refined_target.json", DomainCode.EXAMATH
    )
    service.approve_structure(version.id)
    first = service.run_analysis(version.id)
    second = service.run_analysis(version.id)
    assert first.id == second.id, "동일 입력인데 분석이 중복 생성되었습니다."
    assert len(service.list_runs(project.id)) == 1


def test_adding_evidence_creates_new_run(service):
    project, version = make_project(
        service, "examath/refined_target.json", DomainCode.EXAMATH
    )
    service.approve_structure(version.id)
    first = service.run_analysis(version.id)

    service.add_evidence(
        project.id,
        EvidenceType.USER_INTERVIEW,
        "학부모 인터뷰 8명",
        summary="받아내림에서 멈춘다는 진술 확인",
        sample_size=8,
        supports=[DimensionCode.D01, DimensionCode.D02],
    )
    second = service.run_analysis(version.id)
    assert first.id != second.id, "근거가 추가되면 새 분석이 실행되어야 합니다."
    assert (
        second.result["diagnosis"]["overall_confidence"]
        > first.result["diagnosis"]["overall_confidence"]
    )


def test_evidence_requires_dimension_link(service):
    project, _ = make_project(
        service, "examath/refined_target.json", DomainCode.EXAMATH
    )
    with pytest.raises(ServiceError, match="지지하거나 반박"):
        service.add_evidence(project.id, EvidenceType.DESK_RESEARCH, "출처 없는 메모")


def test_approved_version_cannot_be_edited(service):
    project, version = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    service.approve_structure(version.id)
    with pytest.raises(ServiceError, match="승인된 버전"):
        service.update_version(version.id, change_reason="수정 시도")


def test_permission_denied_for_other_owner(service, tmp_path):
    project, _ = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    other = AppService(service.db, actor_email="other@appcompass")
    with pytest.raises(PermissionDenied):
        other.get_project(project.id)


def test_audit_log_records_key_actions(service):
    project, version = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)

    actions = [a.action for a in service.list_audit_logs()]
    for expected in (
        "PROJECT_CREATED",
        "VERSION_CREATED",
        "STRUCTURE_APPROVED",
        "ANALYSIS_REQUESTED",
        "ANALYSIS_COMPLETED",
    ):
        assert expected in actions, f"감사 로그에 {expected}가 없습니다."


def test_analytics_events_recorded(service):
    project, version = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)
    names = [e[0] for e in service.list_events()]
    assert "project_created" in names
    assert "analysis_requested" in names
    assert "analysis_completed" in names


def test_version_diff_tracks_changes(service):
    project, v1 = make_project(
        service, "vibequest/broad_target.json", DomainCode.VIBEQUEST
    )
    service.approve_structure(v1.id)
    service.run_analysis(v1.id)

    v2 = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
        change_reason="타깃을 상황 기반으로 좁힘",
    )
    service.approve_structure(v2.id)
    service.run_analysis(v2.id)

    rows = {r.label: r for r in service.diff_versions(v1.id, v2.id)}
    assert rows["사용자"].changed is True
    assert rows["총점"].changed is True
    assert float(rows["총점"].after) > float(rows["총점"].before)


def test_policy_change_is_persisted_and_audited(service):
    updated = EvaluationPolicy(version="policy-custom", hold_threshold=0.5)
    service.save_policy(updated)
    loaded = service.get_policy()
    assert loaded.version == "policy-custom"
    assert loaded.hold_threshold == 0.5
    assert "POLICY_UPDATED" in [a.action for a in service.list_audit_logs()]


def test_policy_change_affects_analysis(service):
    project, version = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    service.approve_structure(version.id)
    baseline = service.run_analysis(version.id)

    service.save_policy(EvaluationPolicy(version="policy-lenient", hold_threshold=0.05))
    changed = service.run_analysis(version.id)

    assert baseline.result["pivot"]["decision"] == "HOLD"
    assert changed.result["pivot"]["decision"] != "HOLD"
    assert changed.policy_version == "policy-lenient"


def test_export_report_writes_file(service, tmp_path):
    project, version = make_project(
        service, "examath/refined_target.json", DomainCode.EXAMATH
    )
    service.approve_structure(version.id)
    run = service.run_analysis(version.id)

    target = tmp_path / "report.md"
    service.export_report(run.id, ReportFormat.MARKDOWN, str(target))
    assert target.exists()
    assert "판단" in target.read_text(encoding="utf-8")
    assert "REPORT_EXPORTED" in [a.action for a in service.list_audit_logs()]


def test_delete_project_is_audited(service):
    project, _ = make_project(
        service, "vibequest/refined_target.json", DomainCode.VIBEQUEST
    )
    service.delete_project(project.id)
    assert "PROJECT_DELETED" in [a.action for a in service.list_audit_logs()]
    assert project.id not in [p.id for p in service.list_projects()]
