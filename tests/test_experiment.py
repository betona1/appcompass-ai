"""실험 설계와 결과 테스트 (TECHSPEC F-080).

이 기능의 핵심은 순환을 닫는 것이다.
    가설 → 실험 → 결과 → 근거 → 재분석 → 판단 갱신
그 순환이 실제로 도는지, 그리고 중간에 신뢰도를 부풀릴 구멍이 없는지 본다.
"""

from __future__ import annotations

import pytest

from appcompass.core.enums import (
    DimensionCode,
    DomainCode,
    EvidenceType,
    HypothesisStatus,
)
from appcompass.core.experiment import (
    EXPERIMENT_EVIDENCE_TYPE,
    ExperimentConclusion,
    ExperimentStatus,
    ExperimentType,
    evidence_from_experiment,
    suggest_experiments,
)
from appcompass.core.improvement import judge_hypotheses
from appcompass.core.pipeline import run_analysis
from appcompass.core.policy import EvaluationPolicy
from appcompass.services.app_service import ServiceError

from conftest import fixture_idea, fixture_raw


def _verdicts(path, domain, evidence=()):
    result = run_analysis(
        fixture_idea(path), domain_code=domain,
        policy=EvaluationPolicy(), evidence=evidence,
    )
    return judge_hypotheses(result, evidence, EvaluationPolicy())


# ==========================================================================
# 제안 규칙
# ==========================================================================


def test_suggestions_follow_verification_order():
    """문제 가설이 안 풀렸는데 가격 테스트를 제안하면 안 된다."""
    verdicts = _verdicts("examath/refined_target.json", DomainCode.EXAMATH)
    sugs = suggest_experiments(verdicts, DomainCode.EXAMATH, limit=5)
    ids = [s.hypothesis_id for s in sugs]
    assert ids[0] == "H-PROBLEM"
    assert ids.index("H-PROBLEM") < ids.index("H-REVENUE")


def test_supported_hypothesis_is_not_suggested():
    from appcompass.core.models import EvidenceItem

    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.BEHAVIOR_DATA, title="로그",
            sample_size=200, supports=(DimensionCode.D01, DimensionCode.D02),
        )
    ]
    verdicts = _verdicts("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    assert {v.id: v.status for v in verdicts}["H-PROBLEM"] == HypothesisStatus.SUPPORTED
    sugs = suggest_experiments(verdicts, DomainCode.EXAMATH, limit=5)
    assert "H-PROBLEM" not in [s.hypothesis_id for s in sugs]


def test_suggestions_are_domain_specific():
    em = suggest_experiments(
        _verdicts("examath/refined_target.json", DomainCode.EXAMATH),
        DomainCode.EXAMATH,
    )[0]
    vq = suggest_experiments(
        _verdicts("vibequest/refined_target.json", DomainCode.VIBEQUEST),
        DomainCode.VIBEQUEST,
    )[0]
    assert em.title != vq.title
    assert "받아내림" in " ".join(em.procedure)
    assert "용어" in " ".join(vq.procedure)


def test_every_suggestion_is_actionable():
    for domain, path in (
        (DomainCode.EXAMATH, "examath/refined_target.json"),
        (DomainCode.VIBEQUEST, "vibequest/refined_target.json"),
        (DomainCode.GENERIC, "vibequest/refined_target.json"),
    ):
        for s in suggest_experiments(_verdicts(path, domain), domain, limit=5):
            assert s.procedure, f"{domain}/{s.hypothesis_id}: 절차 없음"
            assert s.success_metric, f"{domain}/{s.hypothesis_id}: 성공 기준 없음"
            assert s.target_value, f"{domain}/{s.hypothesis_id}: 목표값 없음"
            assert s.sample_goal > 0


def test_cheap_experiments_come_first():
    """인터뷰가 프로토타입 개발보다 먼저 제안돼야 한다."""
    sugs = suggest_experiments(
        _verdicts("examath/refined_target.json", DomainCode.EXAMATH),
        DomainCode.EXAMATH, limit=5,
    )
    assert sugs[0].experiment_type == ExperimentType.INTERVIEW


# ==========================================================================
# 실험 → 근거 변환
# ==========================================================================


def _completed(service, project_id, conclusion=ExperimentConclusion.SUPPORTS, **over):
    sug = service.suggest_experiments(project_id)[0]
    exp = service.create_experiment_from_suggestion(project_id, sug)
    payload = dict(
        status=ExperimentStatus.COMPLETED,
        actual_sample=5,
        quantitative_result="5명 중 4명 (80%)",
        qualitative_summary="전원 부모가 직접 설명",
        conclusion=conclusion,
    )
    payload.update(over)
    return service.update_experiment(exp.id, **payload)


def _setup(service, domain=DomainCode.EXAMATH, path="examath/refined_target.json"):
    project = service.create_project("실험", domain_code=domain)
    version = service.create_version(project.id, fixture_raw(path), fixture_idea(path))
    service.approve_structure(version.id)
    service.run_analysis(version.id)
    return project, version


def test_evidence_type_is_decided_by_experiment_type():
    """사용자가 근거 유형을 고르게 하면 인터뷰를 행동 데이터로 등록해 신뢰도를 부풀릴 수 있다."""
    assert EXPERIMENT_EVIDENCE_TYPE[ExperimentType.INTERVIEW] == EvidenceType.USER_INTERVIEW
    assert EXPERIMENT_EVIDENCE_TYPE[ExperimentType.MVP_RELEASE] == EvidenceType.BEHAVIOR_DATA
    assert EXPERIMENT_EVIDENCE_TYPE[ExperimentType.CLICK_DUMMY] == EvidenceType.PROTOTYPE_TEST


def test_inconclusive_cannot_become_evidence(service):
    project, _ = _setup(service)
    exp = _completed(service, project.id, ExperimentConclusion.INCONCLUSIVE)
    assert exp.can_become_evidence is False
    with pytest.raises(ServiceError, match="결론이 난 실험만"):
        service.convert_experiment_to_evidence(exp.id)


def test_incomplete_cannot_become_evidence(service):
    project, _ = _setup(service)
    sug = service.suggest_experiments(project.id)[0]
    exp = service.create_experiment_from_suggestion(project.id, sug)
    with pytest.raises(ServiceError):
        service.convert_experiment_to_evidence(exp.id)


def test_refuting_experiment_registers_as_contradiction(service):
    project, _ = _setup(service)
    exp = _completed(service, project.id, ExperimentConclusion.REFUTES)
    dto = service.convert_experiment_to_evidence(exp.id)
    assert dto.contradicts, "반박 실험인데 반박 항목이 비어 있습니다."
    assert not dto.supports


def test_cannot_register_same_experiment_twice(service):
    project, _ = _setup(service)
    exp = _completed(service, project.id)
    service.convert_experiment_to_evidence(exp.id)
    with pytest.raises(ServiceError, match="이미 근거로 등록"):
        service.convert_experiment_to_evidence(exp.id)


# ==========================================================================
# 순환 전체
# ==========================================================================


def test_experiment_loop_raises_confidence_and_flips_hypothesis(service):
    """가설 → 실험 → 결과 → 근거 → 재분석 → 판단 갱신이 실제로 돈다."""
    project, version = _setup(service)

    before = service.latest_run(project.id).result
    assert before["pivot"]["decision"] == "HOLD"
    assert {v.id: v.status for v in service.hypothesis_verdicts(project.id)}[
        "H-PROBLEM"
    ] == HypothesisStatus.INSUFFICIENT

    exp = _completed(service, project.id)
    dto = service.convert_experiment_to_evidence(exp.id)
    assert dto.evidence_type == str(EvidenceType.USER_INTERVIEW)
    assert dto.sample_size == 5
    assert "5명 중 4명" in dto.summary

    service.run_analysis(version.id)
    after = service.latest_run(project.id).result

    assert (
        after["diagnosis"]["overall_confidence"]
        > before["diagnosis"]["overall_confidence"]
    ), "실험을 근거로 등록했는데 신뢰도가 오르지 않았습니다."
    assert {v.id: v.status for v in service.hypothesis_verdicts(project.id)}[
        "H-PROBLEM"
    ] == HypothesisStatus.SUPPORTED


def test_registered_experiment_is_locked(service):
    project, _ = _setup(service)
    exp = _completed(service, project.id)
    service.convert_experiment_to_evidence(exp.id)
    locked = [e for e in service.list_experiments(project.id) if e.id == exp.id][0]
    assert locked.evidence_id is not None
    assert locked.can_become_evidence is False


def test_experiment_survives_reanalysis(service):
    project, version = _setup(service)
    exp = _completed(service, project.id)
    service.run_analysis(version.id)
    assert exp.id in [e.id for e in service.list_experiments(project.id)]


def test_experiment_actions_are_audited(service):
    project, _ = _setup(service)
    sug = service.suggest_experiments(project.id)[0]
    service.create_experiment_from_suggestion(project.id, sug)
    assert "EXPERIMENT_CREATED" in [a.action for a in service.list_audit_logs()]


def test_next_step_points_to_experiments_when_hold(service):
    project, _ = _setup(service)
    step = service.next_step(project.id)
    assert step.screen == "experiments"
    assert "실험" in " ".join(step.how)
