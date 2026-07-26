"""보고서 생성 (TECHSPEC F-100).

규칙:
- 분석 버전, 정책 버전, 엔진/모델 버전을 반드시 명시한다.
- 사용한 근거를 표시한다.
- 점수보다 이유와 다음 행동을 먼저 배치한다.
- HTML 출력은 모든 사용자 입력을 escape한다 (TECHSPEC §13.2).
"""

from __future__ import annotations

import hashlib
import html
from typing import Sequence

from .enums import DimensionCode, PivotDecision, Severity
from .models import AnalysisResult, EvidenceItem

PIVOT_LABELS: dict[PivotDecision, str] = {
    PivotDecision.KEEP: "유지 (KEEP)",
    PivotDecision.REFINE: "보완 (REFINE)",
    PivotDecision.TARGET_PIVOT: "타깃 피벗 (TARGET_PIVOT)",
    PivotDecision.PROBLEM_PIVOT: "문제 피벗 (PROBLEM_PIVOT)",
    PivotDecision.SOLUTION_PIVOT: "해결책 피벗 (SOLUTION_PIVOT)",
    PivotDecision.CHANNEL_PIVOT: "채널 피벗 (CHANNEL_PIVOT)",
    PivotDecision.REVENUE_PIVOT: "수익 피벗 (REVENUE_PIVOT)",
    PivotDecision.RETENTION_REDESIGN: "재방문 재설계 (RETENTION_REDESIGN)",
    PivotDecision.HOLD: "판단 보류 (HOLD)",
}

SEVERITY_LABELS: dict[Severity, str] = {
    Severity.CRITICAL: "치명",
    Severity.WARN: "주의",
    Severity.INFO: "참고",
}


def _bullets(items: Sequence[str], empty: str = "없음") -> str:
    if not items:
        return f"- {empty}\n"
    return "".join(f"- {i}\n" for i in items)


def render_markdown(
    result: AnalysisResult,
    evidence: Sequence[EvidenceItem] = (),
    project_name: str = "",
    version_no: int | None = None,
) -> str:
    """Markdown 보고서. 섹션 순서는 TECHSPEC F-100을 따른다."""

    m = result.meta
    d = result.diagnosis
    p = result.pivot
    idea = result.idea

    lines: list[str] = []
    add = lines.append

    # 1. 프로젝트 개요
    add(f"# {idea.app_name or project_name or '이름 없는 프로젝트'} 기획 진단 보고서\n")
    add("| 항목 | 값 |")
    add("|---|---|")
    add(f"| 프로젝트 | {project_name or '-'} |")
    add(f"| 버전 | {version_no if version_no is not None else '-'} |")
    add(f"| 도메인 | {m.domain_code} |")
    add(f"| 생성 시각 | {m.created_at.isoformat() if m.created_at else '-'} |")
    add(f"| 판정 엔진 | {m.engine} {m.engine_version} |")
    add(f"| 정책 버전 | {m.policy_version} |")
    add(f"| 스키마 버전 | {m.schema_version} |")
    add(f"| 초안 도움 모델 | {m.model_name or '사용 안 함 (사람이 직접 작성)'} |")
    add(f"| 프롬프트 버전 | {m.prompt_version or '-'} |")
    add("")
    if m.model_name:
        # 모델 이름이 표에 있으면 "AI가 판정했다"로 읽힐 수 있다. 명시적으로 부정한다.
        add(
            f"> `{m.model_name}` 은(는) 구조화 **초안**을 만드는 데만 쓰였고, "
            "사용자가 채택한 칸만 반영되었습니다. "
            f"점수·근거 신뢰도·피벗 판단은 전부 {m.engine} {m.engine_version}가 "
            "결정론적 규칙으로 계산한 것이며 모델이 관여하지 않았습니다.\n"
        )

    # 판단과 다음 행동을 점수보다 먼저 놓는다.
    add("## 판단\n")
    add(f"**{PIVOT_LABELS[p.decision]}**\n")
    if p.would_be_decision:
        add(
            f"> 근거가 충분했다면 내려졌을 판단: **{PIVOT_LABELS[p.would_be_decision]}**\n"
        )
    add(f"{p.rationale}\n")
    add(f"- 근거 신뢰도: {p.confidence:.2f}")
    add(f"- 사유 코드: {', '.join(p.reason_codes) if p.reason_codes else '-'}")
    add(f"- 사람 승인 필요: {'예' if p.requires_human_approval else '아니오'}")
    add("")

    add("## 지금 할 일\n")
    add(_bullets(result.next_actions, "다음 행동 없음"))

    # 2. 원본 아이디어 / 3. 구조화된 문제 정의
    add("## 구조화된 문제 정의\n")
    add(f"- 앱 이름: {idea.app_name or '-'}")
    add(f"- 사용자: {idea.target_user or '-'}")
    add(f"- 구매자: {idea.payer or '-'}")
    add(f"- 영향자: {idea.influencer or '-'}")
    add(f"- 문제 상황: {idea.problem_situation or '-'}")
    add(f"- 현재 대체 방법: {idea.current_solution or '-'}")
    add(f"- 대체 방법의 한계: {idea.current_solution_problem or '-'}")
    add(f"- 핵심 행동: {idea.core_action or '-'}")
    add(f"- 기대 결과: {idea.expected_result or '-'}")
    add(f"- 첫 성공 경험: {idea.first_success or '-'}")
    add(f"- 재방문 이유: {idea.retention_reason or '-'}")
    add(f"- 수익 모델: {idea.revenue_model or '-'}")
    add(f"- 유입 경로: {idea.distribution_channel or '-'}")
    add("")

    # 6. 핵심 위험
    add("## 핵심 위험\n")
    add(_bullets(d.critical_risks, "치명 위험 없음"))

    add("## 경고\n")
    if not d.warnings:
        add("- 경고 없음\n")
    else:
        add("| 심각도 | 코드 | 내용 | 권장 행동 |")
        add("|---|---|---|---|")
        for w in sorted(d.warnings, key=lambda x: x.severity):
            add(
                f"| {SEVERITY_LABELS[w.severity]} | {w.code} | "
                f"{w.message.replace('|', '/')} | {w.recommended_action.replace('|', '/')} |"
            )
        add("")

    # 5. 점수 및 이유
    add("## 평가 점수\n")
    add(f"총점 **{d.total_score:.1f} / 100** · 전체 근거 신뢰도 **{d.overall_confidence:.2f}**\n")
    add("| 코드 | 항목 | 점수 | 가중치 | 환산 | 신뢰도 | 이유 |")
    add("|---|---|---:|---:|---:|---:|---|")
    for dim in d.dimensions:
        add(
            f"| {dim.code} | {dim.label} | {dim.raw_score}/5 | {dim.weight} | "
            f"{dim.normalized_score:.1f} | {dim.confidence:.2f} | {dim.reason.replace('|', '/')} |"
        )
    add("")

    add("### 부족한 근거\n")
    missing_any = False
    for dim in d.dimensions:
        if dim.missing_evidence:
            missing_any = True
            add(f"- **{dim.label}**: {', '.join(dim.missing_evidence)}")
    if not missing_any:
        add("- 모든 항목에 최소 1건의 근거가 연결되어 있습니다.")
    add("")

    # 7. 언노운
    add("## 핵심 언노운\n")
    add(_bullets(d.unknowns, "언노운 없음"))

    # 8. 추천 타깃
    add("## 타깃 후보\n")
    t = result.targets
    add(f"{t.recommendation_reason}\n")
    for i, c in enumerate(t.candidates):
        mark = " ⬅ 추천" if t.recommended_candidate_index == i else ""
        add(f"### {i + 1}. {c.name}{mark}\n")
        add(f"- 사용자: {c.user}")
        add(f"- 구매자: {c.payer or '-'}")
        add(f"- 영향자: {c.influencer or '-'}")
        add(f"- 발생 상황: {c.trigger_situation or '-'}")
        add(f"- 문제: {c.problem or '-'}")
        add(f"- 현재 대안: {c.current_alternative or '-'}")
        add(f"- 유망한 이유:\n{_indent_bullets(c.why_promising)}")
        add(f"- 위험:\n{_indent_bullets(c.risks)}")
        add(f"- 검증 질문:\n{_indent_bullets(c.validation_questions)}")
        add(f"- 추천 실험: {c.recommended_experiment or '-'}")
        add("")

    # 9. MVP
    add("## MVP 계획\n")
    mvp = result.mvp
    add(f"- 핵심 가설: {mvp.core_hypothesis}")
    add(f"- 문제 가설: {mvp.problem_hypothesis}")
    add(f"- 행동 가설: {mvp.behavior_hypothesis}")
    add(f"- 가치 가설: {mvp.value_hypothesis}")
    add(f"- 재방문 가설: {mvp.retention_hypothesis}")
    add(f"- 수익 가설: {mvp.revenue_hypothesis or '-'}")
    add(f"- 첫 성공 경험: {mvp.first_success_experience}")
    add("")
    add("**P0 (핵심 문제 해결)**\n")
    add(_bullets(mvp.p0_features))
    add("**P1 (핵심 행동 완료율)**\n")
    add(_bullets(mvp.p1_features))
    add("**MVP 제외**\n")
    add(_bullets(mvp.excluded_features))
    add("**핵심 사용자 흐름**\n")
    add(_bullets(mvp.core_user_flow))
    add("**측정 이벤트**\n")
    add(_bullets(mvp.metrics))
    add("**위험**\n")
    add(_bullets(mvp.risks))

    # 11. 피벗 판단 상세
    add("## 유지 / 변경 / 삭제\n")
    add("**유지**\n")
    add(_bullets(p.keep))
    add("**변경**\n")
    add(_bullets(p.change))
    add("**삭제**\n")
    add(_bullets(p.remove))

    # 12. 근거와 신뢰도
    add("## 사용한 근거\n")
    if not evidence:
        add(
            "- 등록된 근거가 없습니다. 모든 항목의 신뢰도가 상한값으로 고정되어 "
            "판단을 확정할 수 없습니다.\n"
        )
    else:
        add("| 유형 | 제목 | 표본 | 관측 시각 | 지지 항목 | 출처 |")
        add("|---|---|---:|---|---|---|")
        for e in evidence:
            add(
                f"| {e.evidence_type} | {e.title.replace('|', '/')} | "
                f"{e.sample_size if e.sample_size is not None else '-'} | "
                f"{e.observed_at.isoformat() if e.observed_at else '-'} | "
                f"{', '.join(str(s) for s in e.supports) or '-'} | "
                f"{(e.source_reference or '-').replace('|', '/')} |"
            )
        add("")

    add("---\n")
    add(
        "이 보고서의 점수·신뢰도·피벗 판정은 규칙 엔진이 계산했습니다. "
        "동일한 입력과 동일한 정책 버전이면 항상 같은 결과가 나옵니다. "
        "최종 결정은 사람이 승인해야 합니다.\n"
    )

    return "\n".join(lines)


def _indent_bullets(items: Sequence[str]) -> str:
    if not items:
        return "  - 없음"
    return "\n".join(f"  - {i}" for i in items)


def render_html(
    result: AnalysisResult,
    evidence: Sequence[EvidenceItem] = (),
    project_name: str = "",
    version_no: int | None = None,
) -> str:
    """HTML 보고서. 모든 동적 값을 escape한다."""

    md = render_markdown(result, evidence, project_name, version_no)
    body = _markdown_to_html(md)
    title = html.escape(
        result.idea.app_name or project_name or "AppCompass 진단 보고서"
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{title} · AppCompass 진단 보고서</title>
<style>
  body {{ font-family: "Malgun Gothic", "Segoe UI", sans-serif; line-height: 1.7;
         max-width: 900px; margin: 0 auto; padding: 32px; color: #1c1c1e; }}
  h1 {{ border-bottom: 3px solid #2f6fed; padding-bottom: 8px; }}
  h2 {{ margin-top: 36px; border-left: 5px solid #2f6fed; padding-left: 10px; }}
  h3 {{ margin-top: 24px; color: #333; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }}
  th, td {{ border: 1px solid #d5d8dc; padding: 6px 9px; text-align: left;
            vertical-align: top; }}
  th {{ background: #f2f5fa; }}
  code {{ background: #f2f2f4; padding: 1px 5px; border-radius: 3px; }}
  blockquote {{ border-left: 4px solid #f0ad4e; background: #fffaf0;
                margin: 12px 0; padding: 8px 14px; }}
  .footer {{ margin-top: 40px; font-size: 13px; color: #666; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _markdown_to_html(md: str) -> str:
    """보고서가 쓰는 부분집합만 처리하는 최소 변환기.

    외부 마크다운 라이브러리를 쓰지 않는 이유는 임의 HTML 삽입 경로를 만들지 않기 위해서다.
    모든 입력은 먼저 escape되고, 그 뒤 정해진 문법만 태그로 바꾼다.
    """
    import re

    out: list[str] = []
    in_table = False
    in_list = False

    def close_blocks() -> None:
        nonlocal in_table, in_list
        if in_table:
            out.append("</table>")
            in_table = False
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw_line in md.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            close_blocks()
            continue

        if line.startswith("### "):
            close_blocks()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_blocks()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_blocks()
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("> "):
            close_blocks()
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        elif line.strip() == "---":
            close_blocks()
            out.append("<hr>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue  # 구분선
            if not in_table:
                close_blocks()
                out.append("<table>")
                in_table = True
                out.append(
                    "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells) + "</tr>"
                )
            else:
                out.append(
                    "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>"
                )
        elif line.lstrip().startswith("- "):
            if in_table:
                out.append("</table>")
                in_table = False
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line.lstrip()[2:])}</li>")
        else:
            close_blocks()
            out.append(f"<p>{_inline(line)}</p>")

    close_blocks()
    return "\n".join(out)


def _inline(text: str) -> str:
    """escape 후 **굵게** 와 `코드` 만 태그로 복원한다."""
    import re

    safe = html.escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
    return safe


def checksum(content: str) -> str:
    """보고서 무결성 확인용 (TECHSPEC §14 안정성)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
