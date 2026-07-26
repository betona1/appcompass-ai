"""이미 만든 MVP를 위한 개선 명세 생성.

TECHSPEC은 "처음 만들 때" 문서다. 이 모듈은 그 다음을 맡는다.
이미 만들었고 사용자가 쓰고 있을 때, 무엇을 유지하고 무엇을 고칠지 정리한다.

두 문서의 결정적 차이는 **구현 상태를 안다는 것**이다.
만들지도 않은 기능을 개선하라고 할 수는 없다. 그래서
- 구현된 기능 → 근거에 비추어 유지/변경/삭제 판단
- 미구현 기능 → 지금도 필요한지 재검토 (그 사이 판단이 바뀌었을 수 있다)
로 나눠서 다룬다.

TECHSPEC과 같은 원칙을 따른다. 분석에서 도출할 수 없는 것은 지어내지 않고
`[결정 필요]`로 남긴다.
"""

from __future__ import annotations

from typing import Sequence

from .enums import (
    HYPOTHESIS_STATUS_LABELS,
    IMPLEMENTATION_STATUS_LABELS,
    DimensionCode,
    EvidenceType,
    HypothesisStatus,
    ImplementationStatus,
    PivotDecision,
    Severity,
)
from .models import (
    AnalysisResult,
    EvidenceItem,
    FeatureImplementation,
    HypothesisVerdict,
)
from .policy import EvaluationPolicy

TODO = "`[결정 필요]`"
IMPROVEMENT_VERSION = "improvement-0.1.0"

#: 가설 → 그 가설을 뒷받침/반박하는 평가 항목.
#: 근거는 항목에 붙으므로, 가설 검증 현황은 이 대응을 통해 도출한다.
HYPOTHESIS_DIMENSIONS: tuple[tuple[str, str, tuple[DimensionCode, ...]], ...] = (
    ("H-PROBLEM", "문제 가설", (DimensionCode.D01, DimensionCode.D02)),
    ("H-BEHAVIOR", "행동 가설", (DimensionCode.D06, DimensionCode.D10)),
    ("H-VALUE", "가치 가설", (DimensionCode.D05,)),
    ("H-RETENTION", "재방문 가설", (DimensionCode.D07,)),
    ("H-REVENUE", "수익 가설", (DimensionCode.D04, DimensionCode.D08)),
)

#: 이 수준 이상의 근거라야 가설을 "지지됨"으로 본다.
SUPPORT_CONFIDENCE_FLOOR = 0.50


def judge_hypotheses(
    result: AnalysisResult,
    evidence: Sequence[EvidenceItem],
    policy: EvaluationPolicy,
) -> list[HypothesisVerdict]:
    """가설별 검증 현황을 규칙으로 판정한다. LLM을 쓰지 않는다."""

    mvp = result.mvp
    statements = {
        "H-PROBLEM": mvp.problem_hypothesis,
        "H-BEHAVIOR": mvp.behavior_hypothesis,
        "H-VALUE": mvp.value_hypothesis,
        "H-RETENTION": mvp.retention_hypothesis,
        "H-REVENUE": mvp.revenue_hypothesis or "",
    }

    verdicts: list[HypothesisVerdict] = []
    for hid, label, dims in HYPOTHESIS_DIMENSIONS:
        supporting = [
            e for e in evidence if any(d in e.supports for d in dims)
        ]
        contradicting = [
            e for e in evidence if any(d in e.contradicts for d in dims)
        ]

        def conf(item: EvidenceItem) -> float:
            if item.confidence_override is not None:
                return item.confidence_override
            return policy.confidence_of(item.evidence_type)

        strong_support = [e for e in supporting if conf(e) >= SUPPORT_CONFIDENCE_FLOOR]

        # 가설이 여러 항목에 걸쳐 있으면 **전부** 뒷받침돼야 지지로 본다.
        # 예: 수익 가설은 '구매자가 누구인가'(D04)와 '왜 이걸 사는가'(D08)가 모두 필요하다.
        # 구매자만 확인하고 "수익 가설 검증됨"이라고 하면 과잉 주장이다.
        covered = {d for e in strong_support for d in e.supports if d in dims}
        uncovered = [d for d in dims if d not in covered]

        if contradicting and strong_support:
            status = HypothesisStatus.CONFLICTED
            reason = (
                f"지지 근거 {len(strong_support)}건과 반박 근거 {len(contradicting)}건이 "
                "함께 있습니다. 어느 쪽이 맞는지 좁히는 실험이 먼저입니다."
            )
        elif contradicting:
            status = HypothesisStatus.REFUTED
            reason = (
                f"반박 근거 {len(contradicting)}건이 있고 이를 뒤집을 만한 지지 근거가 없습니다."
            )
        elif strong_support and not uncovered:
            status = HypothesisStatus.SUPPORTED
            reason = (
                f"인터뷰 이상 수준의 지지 근거 {len(strong_support)}건이 "
                f"{', '.join(str(d) for d in dims)} 전부를 뒷받침합니다."
            )
        elif strong_support:
            status = HypothesisStatus.INSUFFICIENT
            reason = (
                f"지지 근거는 있으나 {', '.join(str(d) for d in uncovered)}에 대한 "
                "근거가 없어 확정할 수 없습니다."
            )
        elif supporting:
            status = HypothesisStatus.INSUFFICIENT
            reason = (
                f"지지 근거 {len(supporting)}건이 있으나 전부 신뢰도 "
                f"{SUPPORT_CONFIDENCE_FLOOR:.2f} 미만입니다. 확정하기에 약합니다."
            )
        else:
            status = HypothesisStatus.INSUFFICIENT
            reason = "이 가설에 연결된 근거가 없습니다. 아직 검증되지 않았습니다."

        verdicts.append(
            HypothesisVerdict(
                id=hid,
                label=label,
                statement=statements.get(hid) or "",
                status=status,
                dimensions=dims,
                supporting_evidence=tuple(e.title for e in supporting),
                contradicting_evidence=tuple(e.title for e in contradicting),
                reason=reason,
            )
        )
    return verdicts


def render_improvement(
    result: AnalysisResult,
    features: Sequence[FeatureImplementation],
    evidence: Sequence[EvidenceItem] = (),
    policy: EvaluationPolicy | None = None,
    project_name: str = "",
    version_no: int | None = None,
) -> str:
    """이미 만든 MVP의 개선 명세를 Markdown으로 만든다."""

    policy = policy or EvaluationPolicy()
    idea = result.idea
    diag = result.diagnosis
    pivot = result.pivot
    meta = result.meta

    built = [f for f in features if f.status == ImplementationStatus.DONE]
    in_progress = [f for f in features if f.status == ImplementationStatus.IN_PROGRESS]
    not_started = [f for f in features if f.status == ImplementationStatus.NOT_STARTED]
    dropped = [f for f in features if f.status == ImplementationStatus.DROPPED]

    verdicts = judge_hypotheses(result, evidence, policy)
    has_behavior_data = any(
        e.evidence_type == EvidenceType.BEHAVIOR_DATA for e in evidence
    )

    out: list[str] = []
    add = out.append
    app_name = idea.app_name or project_name or "이름 없는 제품"

    add(f"# {app_name} 개선 명세")
    add("")
    add("| 항목 | 값 |")
    add("|---|---|")
    add(f"| 프로젝트 | {project_name or '-'} |")
    add(f"| 기획 버전 | v{version_no if version_no is not None else '-'} |")
    add(f"| 도메인 | {meta.domain_code} |")
    add(f"| 생성 시각 | {meta.created_at.isoformat() if meta.created_at else '-'} |")
    add(f"| 명세 형식 버전 | {IMPROVEMENT_VERSION} |")
    add(f"| 판정 엔진 | {meta.engine} {meta.engine_version} |")
    add(f"| 평가 정책 | {meta.policy_version} |")
    add(f"| 진단 총점 | {diag.total_score:.1f} / 100 |")
    add(f"| 근거 신뢰도 | {diag.overall_confidence:.2f} |")
    add(f"| 판단 | {pivot.decision} |")
    add(
        f"| 구현 현황 | 구현됨 {len(built)} · 구현 중 {len(in_progress)} · "
        f"미구현 {len(not_started)} · 제외 {len(dropped)} |"
    )
    add("")

    # ------------------------------------------------------------------
    add("## 0. 이 문서를 읽는 법")
    add("")
    add(
        "이 문서는 **이미 만든 MVP**를 전제로 합니다. "
        "`TECHSPEC.md`가 '무엇을 만들까'라면 이 문서는 '무엇을 고칠까'입니다."
    )
    add("")
    add("- 구현된 기능만 개선 대상입니다. 미구현 기능은 §5에서 따로 재검토합니다.")
    add(f"- 도출할 수 없는 항목은 {TODO}로 남겨 두었습니다. 사람이 결정해야 합니다.")
    add("- 우선순위는 **근거가 뒷받침하는 순서**입니다. 감이 아니라 등록된 근거 기준입니다.")
    add("")

    _add_data_warning(add, evidence, has_behavior_data, built)

    # ------------------------------------------------------------------
    add("## 1. 가설 검증 현황")
    add("")
    add(
        "MVP는 가설 검증 도구입니다. 아래가 이 MVP가 실제로 알아낸 것입니다."
    )
    add("")
    add("| ID | 가설 | 현황 | 근거 | 판단 이유 |")
    add("|---|---|---|---|---|")
    for v in verdicts:
        ev_text = ""
        if v.supporting_evidence:
            ev_text += "지지: " + ", ".join(v.supporting_evidence[:2])
        if v.contradicting_evidence:
            ev_text += (" / " if ev_text else "") + "반박: " + ", ".join(
                v.contradicting_evidence[:2]
            )
        add(
            f"| {v.id} | {_cell(v.statement) or TODO} | "
            f"**{HYPOTHESIS_STATUS_LABELS[v.status]}** | {_cell(ev_text) or '없음'} | "
            f"{_cell(v.reason)} |"
        )
    add("")

    refuted = [v for v in verdicts if v.status == HypothesisStatus.REFUTED]
    conflicted = [v for v in verdicts if v.status == HypothesisStatus.CONFLICTED]
    if refuted:
        add("> **반박된 가설이 있습니다.** 그 가설 위에 세운 기능은 고치는 게 아니라 "
            "**빼거나 다시 설계**해야 할 수 있습니다. §4를 먼저 보세요.")
        add("")
    if conflicted:
        add("> **상충하는 가설이 있습니다.** 기능을 고치기 전에 어느 쪽이 맞는지 "
            "좁히는 실험이 먼저입니다. §6을 보세요.")
        add("")

    # ------------------------------------------------------------------
    add("## 2. 유지 (건드리지 말 것)")
    add("")
    add(
        "잘 되고 있는 것을 건드리면 손해입니다. 개선한다며 여기부터 손대는 일이 흔합니다."
    )
    add("")
    supported_ids = {v.id for v in verdicts if v.status == HypothesisStatus.SUPPORTED}
    if supported_ids:
        add("**검증된 가설 — 이 전제는 유지합니다**")
        add("")
        for v in verdicts:
            if v.status == HypothesisStatus.SUPPORTED:
                add(f"- [{v.id}] {v.statement}")
        add("")
    # pivot.keep은 채점 흔적(+1 …)까지 담고 있어 "건드리지 말 것" 목록에는 노이즈다.
    # 여기서는 항목과 점수만 보여준다. 상세 이유는 C화면에 있다.
    strong = [d for d in diag.dimensions if d.raw_score >= 4]
    if strong:
        add("**강한 평가 항목 — 현재 수준을 떨어뜨리지 않습니다**")
        add("")
        for d in sorted(strong, key=lambda x: (-x.raw_score, str(x.code))):
            add(f"- {d.label} ({d.raw_score}/5)")
        add("")
    if not supported_ids and not strong:
        add("아직 '유지할 것'으로 확정된 항목이 없습니다. 근거가 쌓이면 채워집니다.")
        add("")

    # ------------------------------------------------------------------
    add("## 3. 고칠 것 (구현된 기능)")
    add("")
    if not built and not in_progress:
        add(
            "구현됐다고 표시된 기능이 없습니다. "
            "`E. MVP` 화면에서 각 기능의 구현 상태를 표시하면 여기에 개선 대상이 나옵니다."
        )
        add("")
    else:
        add("이미 만든 기능만 대상입니다. 우선순위는 근거가 가리키는 순서입니다.")
        add("")
        targets = built + in_progress
        for i, f in enumerate(targets, 1):
            add(f"### C-{i:02d} {f.text}")
            add("")
            add("| 항목 | 내용 |")
            add("|---|---|")
            add(f"| 현재 상태 | {IMPLEMENTATION_STATUS_LABELS[f.status]} |")
            add(f"| 우선순위 | {f.priority} |")
            linked = _linked_hypothesis(f.text, verdicts)
            add(f"| 연결된 가설 | {linked} |")
            add(f"| 관찰된 문제 | {_cell(f.note) or TODO} |")
            add(f"| 고칠 내용 | {TODO} |")
            add(f"| 성공 기준 | {TODO} |")
            add(f"| 회귀 확인 | {TODO} (이 변경으로 §2가 깨지지 않는지) |")
            add("")

    if pivot.change:
        add("### 진단이 지목한 개선 지점")
        add("")
        for item in pivot.change:
            add(f"- {item}")
        add("")

    # ------------------------------------------------------------------
    add("## 4. 뺄 것")
    add("")
    removals: list[str] = list(pivot.remove)
    for v in verdicts:
        if v.status == HypothesisStatus.REFUTED and v.statement:
            removals.append(
                f"[{v.id}] 반박된 가설에 의존하는 기능 — {v.statement}"
            )
    for f in built:
        if any(banned in f.text for banned in result.mvp.excluded_features):
            removals.append(f"MVP 제외 목록에 있는데 구현되어 있음 — {f.text}")
    if removals:
        for item in dict.fromkeys(removals):
            add(f"- {item}")
    else:
        add("현재 근거로는 빼야 할 것이 확인되지 않았습니다.")
    add("")

    # ------------------------------------------------------------------
    add("## 5. 아직 안 만든 기능 — 지금도 필요한가")
    add("")
    if not not_started:
        add("미구현으로 표시된 기능이 없습니다.")
        add("")
    else:
        add(
            "계획 당시와 판단이 달라졌을 수 있습니다. "
            "만들기 전에 지금 근거로 다시 확인하세요."
        )
        add("")
        add("| 기능 | 우선순위 | 연결된 가설 | 지금도 필요한가 |")
        add("|---|---|---|---|")
        for f in not_started:
            add(
                f"| {_cell(f.text)} | {f.priority} | "
                f"{_linked_hypothesis(f.text, verdicts)} | {TODO} |"
            )
        add("")

    if dropped:
        add("**제외한 기능** (기록용)")
        add("")
        for f in dropped:
            add(f"- {f.text}" + (f" — {f.note}" if f.note else ""))
        add("")

    # ------------------------------------------------------------------
    add("## 6. 다음에 검증할 것")
    add("")
    add("고치기 전에 알아야 하는 것들입니다. 구현으로는 답이 나오지 않습니다.")
    add("")
    unresolved = [
        v for v in verdicts
        if v.status in (HypothesisStatus.INSUFFICIENT, HypothesisStatus.CONFLICTED)
    ]
    if unresolved:
        add("**검증되지 않은 가설**")
        add("")
        for v in unresolved:
            add(f"- [ ] [{v.id}] {v.label} — {v.reason}")
        add("")
    add("**남은 언노운**")
    add("")
    for u in diag.unknowns:
        add(f"- [ ] {u}")
    add("")

    missing_dims = [d for d in diag.dimensions if d.missing_evidence]
    if missing_dims:
        add("**근거가 비어 있는 평가 항목**")
        add("")
        add("| 항목 | 점수 | 필요한 근거 |")
        add("|---|---:|---|")
        for d in sorted(missing_dims, key=lambda x: x.raw_score):
            add(f"| {d.label} | {d.raw_score}/5 | {', '.join(d.missing_evidence)} |")
        add("")

    # ------------------------------------------------------------------
    add("## 7. 다음 버전 범위 제안")
    add("")
    add("```text")
    add("1. §4 '뺄 것'을 먼저 제거한다 (더 만들기 전에 줄인다)")
    add("2. §6에서 가장 싼 검증부터 실행한다 (인터뷰 5건 > 기능 개발)")
    add("3. 검증 결과를 '근거' 화면에 등록하고 분석을 다시 실행한다")
    add("4. 판단이 바뀌면 이 문서를 다시 생성한다")
    add("5. 그 뒤에 §3 '고칠 것'을 착수한다")
    add("```")
    add("")
    add(
        f"현재 판단은 **{pivot.decision}** 입니다. {pivot.rationale}"
    )
    add("")

    critical = [w for w in diag.warnings if w.severity == Severity.CRITICAL]
    if critical:
        add("**먼저 해소할 치명 항목**")
        add("")
        for w in critical:
            add(f"- [{w.code}] {w.message}")
            if w.recommended_action:
                add(f"  - → {w.recommended_action}")
        add("")

    # ------------------------------------------------------------------
    add("## 8. 완료의 정의 (이번 개선)")
    add("")
    for item in (
        "§4의 '뺄 것'이 실제로 제거되었다",
        "§3의 각 항목에 성공 기준이 채워지고 그 기준을 만족한다",
        "§2의 유지 항목이 이번 변경으로 나빠지지 않았다 (회귀 확인)",
        "§6의 검증 항목 중 최소 1개에 대해 근거를 등록했다",
        "분석을 다시 실행해 점수·판단 변화를 확인했다",
        f"{TODO} 표시가 이 문서에 남아 있지 않다",
    ):
        add(f"- [ ] {item}")
    add("")

    add("---")
    add("")
    add(
        f"이 문서는 기획 진단 v{version_no if version_no is not None else '-'}와 "
        f"현재 구현 상태에서 생성되었습니다 "
        f"({meta.engine} {meta.engine_version}, 정책 {meta.policy_version}). "
        "구현 상태나 근거가 바뀌면 다시 생성하세요."
    )

    return "\n".join(out)


# ---------------------------------------------------------------------------


def _cell(text: str) -> str:
    return (text or "").replace("|", "/").replace("\n", " ").strip()


def _linked_hypothesis(feature_text: str, verdicts: Sequence[HypothesisVerdict]) -> str:
    """기능 문구에서 명확히 대응되는 가설만 연결한다. 애매하면 사람이 정한다."""
    pairs = (
        ("첫 성공", "H-BEHAVIOR"),
        ("활성화", "H-BEHAVIOR"),
        ("핵심 행동", "H-VALUE"),
        ("재방문", "H-RETENTION"),
        ("복습", "H-RETENTION"),
        ("요약", "H-RETENTION"),
        ("결제", "H-REVENUE"),
        ("구독", "H-REVENUE"),
    )
    by_id = {v.id: v for v in verdicts}
    for keyword, hid in pairs:
        if keyword in feature_text and hid in by_id:
            v = by_id[hid]
            return f"{hid} ({HYPOTHESIS_STATUS_LABELS[v.status]})"
    return TODO


def _add_data_warning(add, evidence, has_behavior_data, built) -> None:
    if not evidence:
        add("> ## ⚠ 근거가 없습니다")
        add(">")
        add(
            "> 등록된 근거가 하나도 없어, 이 문서의 '유지'와 '고칠 것'은 "
            "**실제 사용 결과가 아니라 기획서 서술만 보고 나온 것**입니다."
        )
        add(">")
        add(
            "> 이미 만들어서 사용자가 쓰고 있다면, 그 행동 데이터를 '근거' 화면에 "
            "`실제 행동 데이터`로 등록하세요. 그게 이 문서의 정확도를 가장 크게 올립니다."
        )
        add("")
    elif not has_behavior_data:
        add("> ## ⚠ 행동 데이터가 없습니다")
        add(">")
        add(
            "> 인터뷰나 리서치는 있지만 **실제 사용 로그가 없습니다.** "
            "이미 출시했다면 '무엇을 말했는가'보다 '무엇을 했는가'가 훨씬 강한 근거입니다."
        )
        add(">")
        add(
            "> 핵심 행동 완료율, 첫 세션 이탈 지점, 재방문율을 "
            "`실제 행동 데이터`(신뢰도 1.00)로 등록하세요."
        )
        add("")
    elif not built:
        add("> ## ⚠ 구현 상태가 표시되지 않았습니다")
        add(">")
        add(
            "> `E. MVP` 화면에서 각 기능을 '구현됨'으로 표시해야 "
            "개선 대상이 이 문서에 나옵니다."
        )
        add("")
