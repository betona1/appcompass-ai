"""분석 오케스트레이터 (TECHSPEC §4, §9.1).

RAW_INPUT → IDEA_STRUCTURE → VALIDATION → RULE_SCORING → CONFIDENCE
          → TARGET_CANDIDATES → MVP_PLAN → PIVOT_DECISION → REPORT

Phase 1은 LLM 단계를 건너뛴다. 순서와 경계는 그대로 유지해서
나중에 LLM 단계를 끼워 넣을 때 구조를 바꾸지 않아도 되게 한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from .confidence import compute_confidence
from .domains.base import DomainModule
from .domains.registry import get_domain
from .enums import DomainCode, Severity
from .models import (
    AnalysisMeta,
    AnalysisResult,
    DiagnosisResult,
    DiagnosisWarning,
    EvidenceItem,
    IdeaStructure,
    LlmAssist,
)
from .pivot import decide_pivot
from .planner import build_mvp_plan, build_target_candidates
from .policy import EvaluationPolicy
from .rules import base_unknowns, dedupe_warnings, detect_warnings
from .scoring import score_dimensions, total_score

ENGINE_NAME = "RULE_ENGINE"
ENGINE_VERSION = "0.1.0"
SCHEMA_VERSION = "analysis-result-0.1.0"


def run_analysis(
    idea: IdeaStructure,
    *,
    domain_code: DomainCode | str = DomainCode.GENERIC,
    policy: EvaluationPolicy | None = None,
    evidence: Sequence[EvidenceItem] = (),
    now: datetime | None = None,
    assist: LlmAssist | None = None,
) -> AnalysisResult:
    """전체 분석을 실행한다.

    순수 함수에 가깝다. now를 주입하면 완전히 결정론적이며,
    회귀 테스트에서 동일 입력 → 동일 출력을 검증할 수 있다.

    assist는 '이 버전의 구조화 초안을 LLM이 도왔다'는 표기용 기록이다.
    분기에 쓰지 않는다 — assist가 있든 없든 점수·신뢰도·피벗은 완전히 동일하다.
    (ADR-0002, 회귀 테스트 test_llm_assist_does_not_change_judgement)
    """

    policy = policy or EvaluationPolicy()
    domain: DomainModule = get_domain(domain_code)
    created_at = now or datetime.now(timezone.utc)

    # 1. VALIDATION -------------------------------------------------------
    warnings: list[DiagnosisWarning] = detect_warnings(idea, DomainCode(domain_code))
    warnings.extend(domain.validate_input(idea))
    warnings = dedupe_warnings(warnings)

    # 2. CONFIDENCE -------------------------------------------------------
    conf = compute_confidence(evidence, policy)
    warnings.extend(conf.warnings)
    warnings = dedupe_warnings(warnings)

    # 3. RULE_SCORING -----------------------------------------------------
    adjustments = domain.score_adjustments(idea, warnings)
    dimensions = score_dimensions(
        idea=idea,
        warnings=warnings,
        evidence=evidence,
        policy=policy,
        adjustments=adjustments,
        confidences=conf.per_dimension,
    )

    unknowns = base_unknowns(idea) + list(domain.enrich_unknowns(idea))
    unknowns = list(dict.fromkeys(unknowns))

    critical_risks = tuple(
        f"[{w.code}] {w.message}" for w in warnings if w.severity == Severity.CRITICAL
    )

    diagnosis = DiagnosisResult(
        total_score=total_score(dimensions),
        overall_confidence=conf.overall,
        dimensions=tuple(dimensions),
        warnings=tuple(warnings),
        critical_risks=critical_risks,
        unknowns=tuple(unknowns),
    )

    # 4. TARGET_CANDIDATES / MVP_PLAN -------------------------------------
    targets = build_target_candidates(idea, diagnosis, domain, policy)
    mvp = build_mvp_plan(idea, diagnosis, domain)

    # 5. PIVOT_DECISION ---------------------------------------------------
    pivot = decide_pivot(
        diagnosis=diagnosis,
        policy=policy,
        evidence=evidence,
        domain_rules=domain.domain_pivot_rules(),
    )

    meta = AnalysisMeta(
        engine=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        policy_version=policy.version,
        schema_version=SCHEMA_VERSION,
        domain_code=DomainCode(domain_code),
        # 엔진은 언제나 RULE_ENGINE이다. 아래 세 칸은 '초안을 누가 도왔는가'일 뿐,
        # 판정 주체가 아니다. 보고서에도 그렇게 구분해서 적는다.
        model_provider=assist.provider if assist else None,
        model_name=assist.model if assist else None,
        prompt_version=assist.prompt_version if assist else None,
        created_at=created_at,
    )

    return AnalysisResult(
        meta=meta,
        idea=idea,
        diagnosis=diagnosis,
        targets=targets,
        mvp=mvp,
        pivot=pivot,
        next_actions=_next_actions(diagnosis, pivot.next_actions),
    )


def _next_actions(
    diagnosis: DiagnosisResult, pivot_actions: Sequence[str]
) -> tuple[str, ...]:
    """사용자가 지금 할 일. 점수가 아니라 행동을 먼저 보여준다."""
    actions: list[str] = list(pivot_actions)

    weakest = sorted(diagnosis.dimensions, key=lambda d: (d.raw_score, d.code))[:2]
    for d in weakest:
        actions.append(f"[{d.label}] {d.recommended_action}")

    if diagnosis.critical_risks:
        actions.insert(0, "치명 위험으로 표시된 항목을 먼저 해소합니다.")

    return tuple(dict.fromkeys(actions))
