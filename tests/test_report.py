"""보고서 렌더링 테스트 (TECHSPEC F-100, §13.2 escaping)."""

from __future__ import annotations

from datetime import datetime, timezone

from appcompass.core.enums import DimensionCode, DomainCode, EvidenceType
from appcompass.core.models import EvidenceItem, IdeaStructure
from appcompass.core.pipeline import run_analysis
from appcompass.core.policy import EvaluationPolicy
from appcompass.core.report import checksum, render_html, render_markdown

from conftest import fixture_idea

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def analyze(path, domain, evidence=()):
    return run_analysis(
        fixture_idea(path),
        domain_code=domain,
        policy=EvaluationPolicy(),
        evidence=evidence,
        now=FIXED_NOW,
    )


def test_markdown_contains_required_sections():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    md = render_markdown(result, project_name="examath")
    for section in (
        "## 판단",
        "## 지금 할 일",
        "## 구조화된 문제 정의",
        "## 핵심 위험",
        "## 평가 점수",
        "## 핵심 언노운",
        "## 타깃 후보",
        "## MVP 계획",
        "## 사용한 근거",
    ):
        assert section in md, f"보고서에 {section} 섹션이 없습니다."


def test_report_records_versions():
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    md = render_markdown(result, project_name="examath", version_no=3)
    assert "RULE_ENGINE" in md
    assert EvaluationPolicy().version in md
    assert "analysis-result-0.1.0" in md
    # LLM을 쓰지 않았다면 그 사실이 보고서에 드러나야 한다.
    assert "사람이 직접 작성" in md


def test_judgment_appears_before_score():
    """점수보다 이유와 다음 행동을 먼저 표시한다 (CLAUDE.md §9)."""
    result = analyze("examath/refined_target.json", DomainCode.EXAMATH)
    md = render_markdown(result)
    assert md.index("## 판단") < md.index("## 평가 점수")
    assert md.index("## 지금 할 일") < md.index("## 평가 점수")


def test_html_escapes_user_input():
    idea = IdeaStructure(
        app_name="<script>alert('xss')</script>",
        target_user="상황이 있는 사용자 <img src=x onerror=alert(1)>",
        problem_situation="작업 중에 막혀 중단된다",
        core_action="행동한다",
        expected_result="50% 개선된다",
    )
    result = run_analysis(idea, domain_code=DomainCode.GENERIC, now=FIXED_NOW)
    html_doc = render_html(result, project_name="xss test")

    assert "<script>alert" not in html_doc
    assert "&lt;script&gt;" in html_doc
    assert "onerror=alert(1)" not in html_doc or "&lt;img" in html_doc


def test_html_is_well_formed_document():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    html_doc = render_html(result, project_name="VibeQuest")
    assert html_doc.startswith("<!DOCTYPE html>")
    assert "</html>" in html_doc.strip()[-10:]
    assert "<table>" in html_doc


def test_no_evidence_is_stated_explicitly():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    md = render_markdown(result, evidence=[])
    assert "등록된 근거가 없습니다" in md


def test_evidence_table_lists_registered_evidence():
    evidence = [
        EvidenceItem(
            id="e1",
            evidence_type=EvidenceType.USER_INTERVIEW,
            title="비개발자 인터뷰 6명",
            sample_size=6,
            source_reference="2026-01 인터뷰 노트",
            supports=(DimensionCode.D01,),
        )
    ]
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST, evidence)
    md = render_markdown(result, evidence=evidence)
    assert "비개발자 인터뷰 6명" in md
    assert "USER_INTERVIEW" in md


def test_checksum_is_stable():
    result = analyze("vibequest/refined_target.json", DomainCode.VIBEQUEST)
    md = render_markdown(result)
    assert checksum(md) == checksum(md)
    assert len(checksum(md)) == 64
