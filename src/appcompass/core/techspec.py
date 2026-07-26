"""분석 결과 → 구현 가능한 기술 명세(TECHSPEC) 생성.

목적은 "기획 진단"과 "실제 개발" 사이의 빈칸을 없애는 것이다.
진단 결과에는 P0/P1 기능, 가설, 측정 이벤트, 사용자 흐름이 이미 들어 있는데
그것만으로는 개발을 시작할 수 없다. 각 기능이 무엇을 입력받고 무엇을 내놓는지,
실패하면 어떻게 되는지, 무엇을 만족해야 끝난 것인지가 없기 때문이다.

이 모듈은 그 골격을 채워 준다. 다만 **모르는 것을 지어내지 않는다.**
분석 결과에서 도출할 수 없는 항목은 `[결정 필요]`로 남긴다.
CLAUDE.md §10.2 "근거 없이 최종 사업성 확정 금지"와 같은 이유다.
사실처럼 적힌 빈 명세는 빈칸보다 위험하다.
"""

from __future__ import annotations

from typing import Sequence

from .enums import DimensionCode, DomainCode, PivotDecision, Severity
from .models import AnalysisResult, EvidenceItem

TODO = "`[결정 필요]`"

TECHSPEC_VERSION = "techspec-0.1.0"

# 도메인별로 반드시 명세에 박아 두어야 하는 제약.
_DOMAIN_CONSTRAINTS: dict[DomainCode, tuple[str, ...]] = {
    DomainCode.VIBEQUEST: (
        "문제는 실제 작업 상황과 연결되어야 한다. 용어 정의만 묻는 문항은 만들지 않는다.",
        "짧은 수준 진단으로 난이도를 나눈다. 초보자와 현업 개발자를 같은 난이도로 두지 않는다.",
        "학습 성공은 정답률이 아니라 '막혔던 작업의 재개'로 측정한다.",
        "사용자의 프로젝트 코드를 저장하지 않는다.",
        "검증되지 않은 생성형 AI 자유채점을 쓰지 않는다. 키워드 채점 등 재현 가능한 방식만 쓴다.",
    ),
    DomainCode.EXAMATH: (
        "한 화면에는 한 가지 판단만 둔다.",
        "구체물 → 그림 → 숫자 순서로 표현을 전환한다. 단계를 건너뛰지 않는다.",
        "피드백은 즉각적이고 비처벌적이어야 한다. 실패 표현이 수학 불안을 키우지 않게 한다.",
        "아이를 정답률로 평가하지 않는다. 오류 유형으로 진단한다.",
        "어린이 개인정보를 최소 수집한다. 익명 또는 가명 ID만 쓰고 공개 프로필을 만들지 않는다.",
        "광고, 가챠, 실시간 랭킹, 공개 채팅을 넣지 않는다.",
        "부모용 결과에 낙인 표현을 쓰지 않는다.",
    ),
}

# 화면 흐름 단계 → 반드시 정의해야 하는 상태
_REQUIRED_STATES = ("정상", "로딩", "빈 상태", "오류", "권한 거부")


def render_techspec(
    result: AnalysisResult,
    evidence: Sequence[EvidenceItem] = (),
    project_name: str = "",
    version_no: int | None = None,
) -> str:
    """분석 결과를 구현용 기술 명세 Markdown으로 변환한다."""

    idea = result.idea
    mvp = result.mvp
    diag = result.diagnosis
    pivot = result.pivot
    meta = result.meta

    out: list[str] = []
    add = out.append

    app_name = idea.app_name or project_name or "이름 없는 제품"

    # ------------------------------------------------------------------
    add(f"# {app_name} 기술 명세 (MVP)")
    add("")
    add("| 항목 | 값 |")
    add("|---|---|")
    add(f"| 프로젝트 | {project_name or '-'} |")
    add(f"| 기획 버전 | v{version_no if version_no is not None else '-'} |")
    add(f"| 도메인 | {meta.domain_code} |")
    add(f"| 생성 시각 | {meta.created_at.isoformat() if meta.created_at else '-'} |")
    add(f"| 명세 형식 버전 | {TECHSPEC_VERSION} |")
    add(f"| 판정 엔진 | {meta.engine} {meta.engine_version} |")
    add(f"| 평가 정책 | {meta.policy_version} |")
    add(f"| 기획 진단 총점 | {diag.total_score:.1f} / 100 |")
    add(f"| 근거 신뢰도 | {diag.overall_confidence:.2f} |")
    add(f"| 기획 판단 | {pivot.decision} |")
    add("")

    # ------------------------------------------------------------------
    add("## 0. 이 문서를 읽는 법")
    add("")
    add(
        "이 문서는 기획 진단 결과에서 자동 생성되었습니다. "
        "**진단에서 도출할 수 있는 것만** 채워져 있고, "
        f"도출할 수 없는 항목은 {TODO}로 남겨 두었습니다."
    )
    add("")
    add(f"- {TODO} 가 하나라도 남아 있으면 구현을 시작하지 마세요. 먼저 사람이 결정해야 합니다.")
    add("- 각 기능의 **완료 기준**을 만족해야 그 기능이 끝난 것입니다.")
    add("- **측정 이벤트가 연결되지 않은 기능은 만들지 않습니다.**")
    add("")

    _add_readiness_warning(add, pivot, diag)

    # ------------------------------------------------------------------
    add("## 1. 제품 정의")
    add("")
    # 여러 문장짜리 필드를 한 문장으로 이어 붙이면 한국어가 깨진다.
    # 라벨을 붙여 그대로 보여주는 편이 정확하고 읽기도 낫다.
    add("```text")
    for label, value in (
        ("사용자", idea.target_user),
        ("겪는 상황", idea.problem_situation),
        ("현재 대체 방법", idea.current_solution),
        ("그 방법이 부족한 이유", idea.current_solution_problem),
        ("핵심 행동", idea.core_action),
        ("측정 가능한 변화", idea.expected_result),
    ):
        add(f"[{label}]")
        add(value.strip() if value else "[결정 필요]")
        add("")
    add("```")
    add("")

    add("### 역할 분리")
    add("")
    add("| 역할 | 대상 | 이 역할이 판단하는 기준 |")
    add("|---|---|---|")
    add(f"| 사용자 (실제로 쓰는 사람) | {idea.target_user or TODO} | {TODO} |")
    add(f"| 구매자 (결제 결정) | {idea.payer or TODO} | {TODO} |")
    add(f"| 영향자 (추천·관리) | {idea.influencer or TODO} | {TODO} |")
    add("")
    if not idea.payer:
        add(
            "> 구매자가 정의되지 않았습니다. 사용자와 구매자가 같다면 "
            "'사용자와 동일'이라고 명시하세요. 다르다면 두 사람의 화면이 달라야 합니다."
        )
        add("")

    # ------------------------------------------------------------------
    add("## 2. 이 MVP가 검증할 가설")
    add("")
    add(
        "MVP는 기능 축소판이 아니라 **가설 검증 도구**입니다. "
        "아래 가설이 참인지 거짓인지 판별되면 이 MVP는 성공한 것입니다."
    )
    add("")
    add("| ID | 가설 | 검증 지표 | 성공 기준 |")
    add("|---|---|---|---|")
    for hid, label, text in (
        ("H-PROBLEM", "문제", mvp.problem_hypothesis),
        ("H-BEHAVIOR", "행동", mvp.behavior_hypothesis),
        ("H-VALUE", "가치", mvp.value_hypothesis),
        ("H-RETENTION", "재방문", mvp.retention_hypothesis),
        ("H-REVENUE", "수익", mvp.revenue_hypothesis or ""),
    ):
        if not text:
            add(f"| {hid} | {label}: {TODO} | {TODO} | {TODO} |")
        else:
            add(f"| {hid} | {_cell(text)} | {TODO} | {TODO} |")
    add("")
    add(f"> 핵심 가설: {mvp.core_hypothesis}")
    add("")

    # ------------------------------------------------------------------
    add("## 3. MVP 범위")
    add("")
    add("### 3.1 만든다 (P0 — 핵심 문제 해결)")
    add("")
    _add_feature_specs(add, mvp.p0_features, "P0", mvp, idea)

    add("### 3.2 만든다 (P1 — 핵심 행동 완료율)")
    add("")
    if mvp.p1_features:
        _add_feature_specs(add, mvp.p1_features, "P1", mvp, idea)
    else:
        add("P1 기능이 없습니다. P0만으로 첫 성공 경험이 완결되는지 확인하세요.")
        add("")

    add("### 3.3 이번에는 만들지 않는다")
    add("")
    add("아래 항목을 구현하자는 요청이 오면 이 문서를 근거로 거절합니다.")
    add("")
    for item in mvp.excluded_features:
        add(f"- {item}")
    add("")

    # ------------------------------------------------------------------
    add("## 4. 화면과 흐름")
    add("")
    add("### 4.1 핵심 사용자 흐름")
    add("")
    add("```text")
    for i, step in enumerate(mvp.core_user_flow, 1):
        add(f"{i}. {step}")
    add("```")
    add("")
    add(f"첫 성공 경험: **{mvp.first_success_experience}**")
    add("")

    add("### 4.2 화면 명세")
    add("")
    add("화면 하나에는 주목적 하나만 둡니다. 모든 화면은 아래 상태를 전부 구현해야 합니다.")
    add("")
    add("| 화면 | 주목적 | 진입 조건 | 이탈(성공) 조건 | 구현할 상태 |")
    add("|---|---|---|---|---|")
    for i, step in enumerate(mvp.core_user_flow, 1):
        add(
            f"| S-{i:02d} {_cell(step)} | {TODO} | {TODO} | {TODO} | "
            f"{' / '.join(_REQUIRED_STATES)} |"
        )
    add("")
    add(
        "> 색만으로 상태를 구분하지 않습니다. 성공·실패·경고는 반드시 "
        "텍스트나 아이콘을 함께 씁니다."
    )
    add("")

    # ------------------------------------------------------------------
    add("## 5. 측정 이벤트")
    add("")
    add(
        "측정 없는 기능은 만들지 않습니다. 아래 이벤트는 **출시 전에** 심어야 하며, "
        "각 이벤트가 어떤 가설을 검증하는지 연결되어야 합니다."
    )
    add("")
    add("| 이벤트 이름 | 발생 시점 | 필수 속성 | 검증하는 가설 |")
    add("|---|---|---|---|")
    for name in mvp.metrics:
        add(f"| `{name}` | {TODO} | {TODO} | {_guess_hypothesis(name)} |")
    add("")
    add("공통 속성 (모든 이벤트에 포함):")
    add("")
    add("```text")
    add("anonymous_user_id   익명 또는 가명 ID")
    add("occurred_at         timezone-aware 시각")
    add("app_version")
    add("session_id")
    add("```")
    add("")

    # ------------------------------------------------------------------
    add("## 6. 데이터 모델")
    add("")
    add(
        "진단 결과에서 데이터 모델을 도출할 수는 없습니다. "
        "아래는 핵심 행동을 기록하기 위한 최소 골격이며, 실제 필드는 사람이 결정합니다."
    )
    add("")
    add("| 엔티티 | 목적 | 필수 필드 | 비고 |")
    add("|---|---|---|---|")
    add(f"| User | 사용자 식별 | id, created_at | {_privacy_note(meta.domain_code)} |")
    add(
        "| CoreActionRecord | 핵심 행동 1회 기록 | "
        f"id, user_id, started_at, completed_at, result | {TODO} |"
    )
    add(f"| Event | 측정 이벤트 적재 | id, name, user_id, occurred_at, properties | - |")
    add(f"| {TODO} | {TODO} | {TODO} | {TODO} |")
    add("")

    # ------------------------------------------------------------------
    add("## 7. 비기능 요구사항")
    add("")
    add("| 항목 | 기준 |")
    add("|---|---|")
    add(f"| 첫 성공까지 걸리는 시간 | {TODO} (첫 성공 경험 정의에 맞춰 목표를 정하세요) |")
    add(f"| 주요 화면 응답 시간 | {TODO} |")
    add(f"| 오프라인 동작 | {TODO} |")
    add(f"| 지원 플랫폼·버전 | {TODO} |")
    add(f"| 접근성 | 색 단독 구분 금지, 최소 글자 크기 {TODO} |")
    add("")
    _add_domain_constraints(add, meta.domain_code)

    # ------------------------------------------------------------------
    add("## 8. 위험과 대응")
    add("")
    add("| 위험 | 심각도 | 대응 | 확인 방법 |")
    add("|---|---|---|---|")
    critical = {r for r in diag.critical_risks}
    for risk in mvp.risks:
        sev = "치명" if any(risk in c for c in critical) else "주의"
        add(f"| {_cell(risk)} | {sev} | {TODO} | {TODO} |")
    for w in diag.warnings:
        if w.severity == Severity.CRITICAL:
            add(
                f"| [{w.code}] {_cell(w.message)} | 치명 | "
                f"{_cell(w.recommended_action)} | {TODO} |"
            )
    add("")

    # ------------------------------------------------------------------
    add("## 9. 아직 모르는 것 (언노운)")
    add("")
    add("구현 중에 답이 나오지 않습니다. 사용자에게 물어야 합니다.")
    add("")
    for u in diag.unknowns:
        add(f"- [ ] {u}")
    add("")

    # ------------------------------------------------------------------
    add("## 10. 근거 현황")
    add("")
    if not evidence:
        add(
            "**등록된 근거가 없습니다.** 이 명세는 전부 가정 위에 서 있습니다. "
            "구현 전에 최소 5명 인터뷰를 권합니다."
        )
    else:
        add("| 유형 | 제목 | 표본 | 지지 항목 |")
        add("|---|---|---|---|")
        for e in evidence:
            add(
                f"| {e.evidence_type} | {_cell(e.title)} | "
                f"{e.sample_size if e.sample_size is not None else '-'} | "
                f"{', '.join(str(s) for s in e.supports) or '-'} |"
            )
    add("")
    weak = [d for d in diag.dimensions if d.raw_score <= 2]
    if weak:
        add("가장 약한 항목 (구현 전에 보강 권장):")
        add("")
        for d in weak:
            add(f"- **{d.label}** {d.raw_score}/5 — {d.recommended_action}")
        add("")

    # ------------------------------------------------------------------
    add("## 11. 구현 순서")
    add("")
    add("```text")
    add("1. 측정 이벤트 정의와 수집 경로 (가장 먼저. 나중에 심으면 데이터가 비어 있다)")
    add("2. P0 핵심 행동 한 줄기 (해피 패스만)")
    add("3. 첫 성공 경험까지의 흐름 완결")
    add("4. 실패·빈 상태·오류 화면")
    add("5. P1 기능")
    add("6. 검증 실험 세팅")
    add("```")
    add("")

    add("## 12. 완료의 정의 (전체)")
    add("")
    for item in (
        "P0 기능이 전부 동작한다",
        "첫 성공 경험까지 끊김 없이 도달한다",
        "모든 화면에 로딩·빈 상태·오류·권한 거부 화면이 있다",
        "측정 이벤트가 실제로 수집되는 것을 확인했다",
        "MVP 제외 목록의 기능이 들어가지 않았다",
        "위 언노운 중 최소 3개에 대해 사용자 답변을 확보했다",
        f"{TODO} 표시가 이 문서에 남아 있지 않다",
    ):
        add(f"- [ ] {item}")
    add("")

    add("---")
    add("")
    add(
        f"이 문서는 기획 진단 v{version_no if version_no is not None else '-'} "
        f"({meta.engine} {meta.engine_version}, 정책 {meta.policy_version})에서 생성되었습니다. "
        "기획이 바뀌면 새 버전에서 다시 생성하세요. 이 파일을 직접 고치면 추적이 끊깁니다."
    )

    return "\n".join(out)


# ---------------------------------------------------------------------------
# 보조 함수
# ---------------------------------------------------------------------------


def _cell(text: str) -> str:
    """표 셀에 넣을 수 있게 파이프와 줄바꿈을 정리한다."""
    return (text or "").replace("|", "/").replace("\n", " ").strip() or "-"


def _add_readiness_warning(add, pivot, diag) -> None:
    if pivot.decision == PivotDecision.HOLD:
        add("> ## ⚠ 구현 착수 전 확인")
        add(">")
        add(
            f"> 기획 판단이 **HOLD**입니다. 근거 신뢰도가 "
            f"{diag.overall_confidence:.2f}로 판단을 확정할 수 없는 상태입니다."
        )
        if pivot.would_be_decision:
            add(f">")
            add(f"> 근거가 충분했다면 판단은 **{pivot.would_be_decision}** 이었을 것입니다.")
        add(">")
        add(
            "> 이 명세대로 만들어도 되지만, **무엇을 만들지가 아니라 무엇이 틀렸는지를 "
            "빨리 알아내는 것이 목적**임을 잊지 마세요. 가능하면 구현 전에 인터뷰 5건을 먼저 하세요."
        )
        add("")
    elif pivot.decision in (
        PivotDecision.PROBLEM_PIVOT,
        PivotDecision.TARGET_PIVOT,
        PivotDecision.SOLUTION_PIVOT,
    ):
        add("> ## ⚠ 구현 착수 전 확인")
        add(">")
        add(f"> 기획 판단이 **{pivot.decision}** 입니다. {pivot.rationale}")
        add(">")
        add("> 방향을 먼저 정리한 뒤 이 명세를 다시 생성하는 편이 낫습니다.")
        add("")


def _add_feature_specs(add, features: Sequence[str], prefix: str, mvp, idea) -> None:
    if not features:
        add("정의된 기능이 없습니다.")
        add("")
        return

    for i, feature in enumerate(features, 1):
        fid = f"{prefix}-{i:02d}"
        add(f"#### {fid} {feature}")
        add("")
        add("| 항목 | 내용 |")
        add("|---|---|")
        add(f"| 목적 | {TODO} |")
        add(f"| 검증하는 가설 | {_guess_hypothesis_for_feature(feature)} |")
        add(f"| 입력 | {TODO} |")
        add(f"| 출력 | {TODO} |")
        add(f"| 정상 흐름 | {TODO} |")
        add(f"| 실패·예외 | {TODO} |")
        add(f"| 빈 상태 | {TODO} |")
        add(f"| 측정 이벤트 | {_guess_metric_for_feature(feature, mvp.metrics)} |")
        add(f"| 완료 기준 | {TODO} |")
        add("")


def _guess_hypothesis_for_feature(feature: str) -> str:
    text = feature.lower()
    if "첫 성공" in feature or "활성화" in feature:
        return "H-BEHAVIOR"
    if "재방문" in feature or "복습" in feature or "요약" in feature:
        return "H-RETENTION"
    if "핵심 행동" in feature:
        return "H-VALUE"
    if "결제" in feature or "구독" in feature:
        return "H-REVENUE"
    return TODO


def _guess_metric_for_feature(feature: str, metrics: Sequence[str]) -> str:
    """기능 이름과 이벤트 이름이 명확히 대응될 때만 연결한다. 애매하면 사람이 정한다."""
    pairs = (
        ("첫 성공", ("activation_complete", "first_mission_complete")),
        ("핵심 행동", ("core_action_complete",)),
        ("진단", ("diagnostic_complete",)),
        ("구체물", ("manipulative_action_complete", "concrete_problem_complete")),
        ("10 만들기", ("make_ten_complete",)),
        ("복습", ("wrong_concept_review_complete", "retry_after_error")),
        ("주간 요약", ("parent_weekly_summary_view",)),
        ("재방문", ("day1_return", "daily_mission_return")),
        ("오답 유형", ("error_type_detected",)),
        ("전환", ("concrete_to_symbol_transfer", "symbol_problem_complete")),
    )
    for keyword, candidates in pairs:
        if keyword in feature:
            hit = [c for c in candidates if c in metrics]
            if hit:
                return ", ".join(f"`{h}`" for h in hit)
    return TODO


def _guess_hypothesis(metric: str) -> str:
    if metric.endswith("_return") or "weekly" in metric:
        return "H-RETENTION"
    if "activation" in metric or "first_" in metric or "diagnostic" in metric:
        return "H-BEHAVIOR"
    if "complete" in metric or "transfer" in metric:
        return "H-VALUE"
    return TODO


def _privacy_note(domain: DomainCode) -> str:
    if domain == DomainCode.EXAMATH:
        return "어린이 대상: 익명·가명 ID만. 실명·생년월일·학교명 수집 금지"
    return "개인정보 최소 수집"


def _add_domain_constraints(add, domain: DomainCode) -> None:
    constraints = _DOMAIN_CONSTRAINTS.get(domain)
    if not constraints:
        return
    add(f"### 도메인 제약 ({domain})")
    add("")
    add("아래는 협상 대상이 아닙니다. 위반하면 제품의 존재 이유가 사라집니다.")
    add("")
    for c in constraints:
        add(f"- {c}")
    add("")
