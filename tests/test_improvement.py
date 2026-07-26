"""개선 명세(IMPROVEMENT) 테스트.

TECHSPEC이 '무엇을 만들까'라면 개선 명세는 '무엇을 고칠까'다.
결정적 차이는 구현 상태를 안다는 것이므로, 그 구분이 실제로 반영되는지를 본다.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from appcompass.core.enums import (
    DimensionCode,
    DomainCode,
    EvidenceType,
    HypothesisStatus,
    ImplementationStatus,
    ReportFormat,
)
from appcompass.core.improvement import TODO, judge_hypotheses, render_improvement
from appcompass.core.models import EvidenceItem, FeatureImplementation, feature_key
from appcompass.core.pipeline import run_analysis
from appcompass.core.policy import EvaluationPolicy

from conftest import fixture_idea, fixture_raw

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def analyze(path, domain, evidence=()):
    return run_analysis(
        fixture_idea(path),
        domain_code=domain,
        policy=EvaluationPolicy(),
        evidence=evidence,
        now=FIXED_NOW,
    )


def make_features(result, built_count=2):
    """앞쪽 N개를 구현됨으로, 나머지를 미구현으로 표시한다."""
    out = []
    for i, text in enumerate(result.mvp.p0_features):
        out.append(
            FeatureImplementation(
                key=feature_key(text),
                text=text,
                priority="P0",
                status=(
                    ImplementationStatus.DONE
                    if i < built_count
                    else ImplementationStatus.NOT_STARTED
                ),
                note="첫 세션 이탈이 잦음" if i == 0 else "",
            )
        )
    return out


# ==========================================================================
# 가설 판정
# ==========================================================================


def test_no_evidence_makes_every_hypothesis_insufficient():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    verdicts = judge_hypotheses(result, [], EvaluationPolicy())
    assert len(verdicts) == 5
    assert all(v.status == HypothesisStatus.INSUFFICIENT for v in verdicts)


def test_strong_evidence_supports_hypothesis():
    evidence = [
        EvidenceItem(
            id="e1",
            evidence_type=EvidenceType.BEHAVIOR_DATA,
            title="핵심 행동 완료 로그",
            sample_size=300,
            supports=(DimensionCode.D06, DimensionCode.D10),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    verdicts = {v.id: v for v in judge_hypotheses(result, evidence, EvaluationPolicy())}
    assert verdicts["H-BEHAVIOR"].status == HypothesisStatus.SUPPORTED
    assert verdicts["H-RETENTION"].status == HypothesisStatus.INSUFFICIENT


def test_contradicting_evidence_refutes_hypothesis():
    evidence = [
        EvidenceItem(
            id="e1",
            evidence_type=EvidenceType.PROTOTYPE_TEST,
            title="재방문 테스트",
            sample_size=20,
            contradicts=(DimensionCode.D07,),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    verdicts = {v.id: v for v in judge_hypotheses(result, evidence, EvaluationPolicy())}
    assert verdicts["H-RETENTION"].status == HypothesisStatus.REFUTED


def test_both_directions_yield_conflicted():
    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.USER_INTERVIEW, title="지지",
            sample_size=8, supports=(DimensionCode.D07,),
        ),
        EvidenceItem(
            id="e2", evidence_type=EvidenceType.BEHAVIOR_DATA, title="반박",
            sample_size=200, contradicts=(DimensionCode.D07,),
        ),
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    verdicts = {v.id: v for v in judge_hypotheses(result, evidence, EvaluationPolicy())}
    assert verdicts["H-RETENTION"].status == HypothesisStatus.CONFLICTED


def test_partial_coverage_is_not_supported():
    """가설이 여러 항목에 걸쳐 있으면 전부 뒷받침돼야 지지로 본다.

    수익 가설은 D04(구매자가 누구인가)와 D08(왜 이걸 사는가)이 모두 필요하다.
    구매자만 확인하고 '수익 가설 검증됨'이라고 하면 과잉 주장이다.
    """
    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.USER_INTERVIEW, title="학부모 인터뷰",
            sample_size=8, supports=(DimensionCode.D04,),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    verdicts = {v.id: v for v in judge_hypotheses(result, evidence, EvaluationPolicy())}
    assert verdicts["H-REVENUE"].status == HypothesisStatus.INSUFFICIENT
    assert "D08" in verdicts["H-REVENUE"].reason

    # 둘 다 채우면 지지됨
    evidence.append(
        EvidenceItem(
            id="e2", evidence_type=EvidenceType.USER_INTERVIEW, title="지불의사 인터뷰",
            sample_size=8, supports=(DimensionCode.D08,),
        )
    )
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    verdicts = {v.id: v for v in judge_hypotheses(result, evidence, EvaluationPolicy())}
    assert verdicts["H-REVENUE"].status == HypothesisStatus.SUPPORTED


def test_keep_section_has_no_scoring_trace():
    """'건드리지 말 것' 목록에 채점 흔적(+1 …)이 들어가면 읽을 수 없다."""
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    doc = render_improvement(result, make_features(result))
    keep = doc[doc.index("## 2. 유지") : doc.index("## 3. 고칠 것")]
    assert "+1 " not in keep and "+2 " not in keep


def test_weak_evidence_is_not_enough_to_support():
    """창업자 가정으로는 가설이 지지되지 않는다."""
    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.FOUNDER_ASSUMPTION,
            title="가정", supports=(DimensionCode.D07,),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    verdicts = {v.id: v for v in judge_hypotheses(result, evidence, EvaluationPolicy())}
    assert verdicts["H-RETENTION"].status == HypothesisStatus.INSUFFICIENT


# ==========================================================================
# 문서 생성
# ==========================================================================


def test_improvement_has_required_sections():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    doc = render_improvement(result, make_features(result), project_name="examath")
    for section in (
        "## 1. 가설 검증 현황",
        "## 2. 유지",
        "## 3. 고칠 것",
        "## 4. 뺄 것",
        "## 5. 아직 안 만든 기능",
        "## 6. 다음에 검증할 것",
        "## 7. 다음 버전 범위 제안",
        "## 8. 완료의 정의",
    ):
        assert section in doc, f"개선 명세에 {section} 이 없습니다."


def test_only_built_features_become_improvement_targets():
    """만들지 않은 기능을 개선하라고 하면 안 된다."""
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    features = make_features(result, built_count=2)
    doc = render_improvement(result, features, project_name="examath")

    built = [f for f in features if f.status == ImplementationStatus.DONE]
    not_built = [f for f in features if f.status == ImplementationStatus.NOT_STARTED]

    improve_section = doc[doc.index("## 3. 고칠 것") : doc.index("## 4. 뺄 것")]
    for f in built:
        assert f.text in improve_section, f"구현된 기능이 개선 대상에 없습니다: {f.text}"
    for f in not_built:
        assert f.text not in improve_section, (
            f"미구현 기능이 개선 대상에 들어갔습니다: {f.text}"
        )

    review_section = doc[doc.index("## 5. 아직 안 만든 기능") : doc.index("## 6.")]
    for f in not_built:
        assert f.text in review_section


def test_improvement_warns_when_no_evidence():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    doc = render_improvement(result, make_features(result), evidence=[])
    assert "근거가 없습니다" in doc
    assert "실제 사용 결과가 아니라" in doc


def test_improvement_warns_when_no_behavior_data():
    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.USER_INTERVIEW, title="인터뷰",
            sample_size=5, supports=(DimensionCode.D01,),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    doc = render_improvement(result, make_features(result), evidence=evidence)
    assert "행동 데이터가 없습니다" in doc


def test_improvement_warns_when_nothing_marked_built():
    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.BEHAVIOR_DATA, title="로그",
            sample_size=100, supports=(DimensionCode.D01,),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    features = make_features(result, built_count=0)
    doc = render_improvement(result, features, evidence=evidence)
    assert "구현 상태가 표시되지 않았습니다" in doc


def test_refuted_hypothesis_appears_in_removal_section():
    evidence = [
        EvidenceItem(
            id="e1", evidence_type=EvidenceType.BEHAVIOR_DATA, title="재방문 로그",
            sample_size=200, contradicts=(DimensionCode.D07,),
        )
    ]
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH, evidence)
    doc = render_improvement(result, make_features(result), evidence=evidence)
    removal = doc[doc.index("## 4. 뺄 것") : doc.index("## 5.")]
    assert "H-RETENTION" in removal
    assert "반박된 가설이 있습니다" in doc


def test_improvement_marks_underivable_fields():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    doc = render_improvement(result, make_features(result))
    assert TODO in doc


def test_improvement_is_deterministic():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    features = make_features(result)
    assert render_improvement(result, features) == render_improvement(result, features)


def test_feature_key_is_stable_and_text_sensitive():
    assert feature_key("핵심 행동: 문제를 푼다") == feature_key(" 핵심 행동:  문제를 푼다 ")
    assert feature_key("기능 A") != feature_key("기능 B")


# ==========================================================================
# 서비스 통합
# ==========================================================================


def _setup(service, fixture="examath/refined_target.json", domain=DomainCode.EXAMATH):
    project = service.create_project("개선", domain_code=domain)
    version = service.create_version(
        project.id, fixture_raw(fixture), fixture_idea(fixture)
    )
    service.approve_structure(version.id)
    run = service.run_analysis(version.id)
    return project, run


def test_feature_status_defaults_to_not_started(service):
    project, _ = _setup(service)
    features = service.list_feature_status(project.id)
    assert features
    assert all(f.status == ImplementationStatus.NOT_STARTED for f in features)
    assert {f.priority for f in features} <= {"P0", "P1"}


def test_feature_status_persists_across_reanalysis(service):
    project, run = _setup(service)
    features = service.list_feature_status(project.id)
    target = features[0]
    service.set_feature_status(
        project.id, target, ImplementationStatus.DONE, "이탈 잦음"
    )

    # 근거를 추가해 새 분석을 만든다
    service.add_evidence(
        project.id, EvidenceType.USER_INTERVIEW, "인터뷰", sample_size=5,
        supports=[DimensionCode.D01],
    )
    version = service.latest_version(project.id)
    service.run_analysis(version.id)

    after = {f.key: f for f in service.list_feature_status(project.id)}
    assert after[target.key].status == ImplementationStatus.DONE, (
        "분석을 다시 실행했더니 구현 상태가 사라졌습니다."
    )
    assert after[target.key].note == "이탈 잦음"


def test_export_improvement_reflects_status(service, tmp_path):
    project, run = _setup(service)
    features = service.list_feature_status(project.id)
    service.set_feature_status(
        project.id, features[0], ImplementationStatus.DONE, "첫 세션 이탈"
    )

    target = tmp_path / "improve.md"
    service.export_report(run.id, ReportFormat.IMPROVEMENT, str(target))
    text = target.read_text(encoding="utf-8")

    assert "개선 명세" in text
    assert features[0].text in text
    assert "첫 세션 이탈" in text
    assert "REPORT_EXPORTED" in [a.action for a in service.list_audit_logs()]


def test_improvement_not_stored_as_report(service):
    """개선 명세는 구현 상태에 따라 달라지므로 분석 시점에 고정 저장하지 않는다."""
    project, run = _setup(service)
    formats = {r.format for r in service.get_reports(run.id)}
    assert str(ReportFormat.IMPROVEMENT) not in formats
    # 그래도 생성은 된다
    assert "개선 명세" in service.build_improvement(run.id)
