"""core 계층의 값 객체(dataclass).

ORM 모델이 아니다. 저장 계층과 독립적으로 존재하며,
storage 계층이 이 값 객체를 JSON으로 직렬화해 보관한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from .enums import (
    DimensionCode,
    DomainCode,
    EvidenceType,
    HypothesisStatus,
    ImplementationStatus,
    PivotDecision,
    ProjectStage,
    Severity,
    WarningCode,
)

__all__ = [
    "RawIdeaInput",
    "IdeaStructure",
    "EvidenceItem",
    "DiagnosisWarning",
    "ScoreAdjustment",
    "DimensionScore",
    "DiagnosisResult",
    "TargetCandidate",
    "TargetCandidateSet",
    "MvpPlan",
    "PivotResult",
    "LlmAssist",
    "AnalysisMeta",
    "AnalysisResult",
    "EvidenceExample",
    "FeatureImplementation",
    "HypothesisVerdict",
    "MetricDefinition",
    "feature_key",
]


# ---------------------------------------------------------------------------
# 입력
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RawIdeaInput:
    """TECHSPEC F-020 입력 필드. 사용자가 쓴 원문이며 절대 덮어쓰지 않는다."""

    app_name: str = ""
    raw_idea: str = ""
    target_user_raw: str = ""
    problem_raw: str = ""
    solution_raw: str = ""
    revenue_model_raw: str = ""
    distribution_channel_raw: str = ""
    current_stage: ProjectStage = ProjectStage.IDEA

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["current_stage"] = str(self.current_stage)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RawIdeaInput:
        data = dict(data or {})
        stage = data.pop("current_stage", ProjectStage.IDEA)
        known = {k: v for k, v in data.items() if k in cls.__slots__}
        return cls(current_stage=ProjectStage(stage), **known)


@dataclass(frozen=True, slots=True)
class IdeaStructure:
    """TECHSPEC F-020 구조화 결과.

    Phase 1에서는 사람이 직접 채우고 규칙 엔진이 검증한다.
    이후 LLM(StructurerPort)이 초안을 채우더라도 사용자 승인 전에는 반영하지 않는다.
    """

    app_name: str = ""
    target_user: str = ""
    payer: str | None = None
    influencer: str | None = None
    problem_situation: str = ""
    current_solution: str | None = None
    current_solution_problem: str | None = None
    core_action: str = ""
    expected_result: str = ""
    first_success: str | None = None
    retention_reason: str | None = None
    revenue_model: str | None = None
    distribution_channel: str | None = None
    unknowns: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["unknowns"] = list(self.unknowns)
        d["warnings"] = list(self.warnings)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IdeaStructure:
        data = dict(data or {})
        data["unknowns"] = tuple(data.get("unknowns") or ())
        data["warnings"] = tuple(data.get("warnings") or ())
        known = {k: v for k, v in data.items() if k in cls.__slots__}
        return cls(**known)


# ---------------------------------------------------------------------------
# 근거
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """TECHSPEC F-040 Evidence.

    supports/contradicts는 평가 항목(DimensionCode)에 연결한다.
    AI는 근거를 생성하지 않는다. 사람이 등록한 것만 존재한다.
    """

    id: str
    evidence_type: EvidenceType
    title: str
    summary: str = ""
    source_reference: str | None = None
    sample_size: int | None = None
    observed_at: datetime | None = None
    confidence_override: float | None = None
    supports: tuple[DimensionCode, ...] = ()
    contradicts: tuple[DimensionCode, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "evidence_type": str(self.evidence_type),
            "title": self.title,
            "summary": self.summary,
            "source_reference": self.source_reference,
            "sample_size": self.sample_size,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "confidence_override": self.confidence_override,
            "supports": [str(c) for c in self.supports],
            "contradicts": [str(c) for c in self.contradicts],
        }


# ---------------------------------------------------------------------------
# 진단
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DiagnosisWarning:
    """규칙 엔진이 만든 경고. LLM이 아니라 결정론적 규칙의 산출물이다."""

    code: WarningCode
    message: str
    severity: Severity = Severity.WARN
    field: str | None = None
    recommended_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": str(self.code),
            "message": self.message,
            "severity": str(self.severity),
            "field": self.field,
            "recommended_action": self.recommended_action,
        }


@dataclass(frozen=True, slots=True)
class ScoreAdjustment:
    """도메인 모듈이 제안하는 점수 보정. 이유가 없으면 적용하지 않는다."""

    code: DimensionCode
    delta: int
    reason: str


@dataclass(frozen=True, slots=True)
class DimensionScore:
    code: DimensionCode
    label: str
    raw_score: int  # 0~5
    weight: int
    normalized_score: float  # (raw/5) * weight
    reason: str
    missing_evidence: tuple[str, ...] = ()
    recommended_action: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": str(self.code),
            "label": self.label,
            "raw_score": self.raw_score,
            "weight": self.weight,
            "normalized_score": round(self.normalized_score, 4),
            "reason": self.reason,
            "missing_evidence": list(self.missing_evidence),
            "recommended_action": self.recommended_action,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    total_score: float
    overall_confidence: float
    dimensions: tuple[DimensionScore, ...]
    warnings: tuple[DiagnosisWarning, ...]
    critical_risks: tuple[str, ...]
    unknowns: tuple[str, ...]

    def dimension(self, code: DimensionCode) -> DimensionScore:
        for d in self.dimensions:
            if d.code == code:
                return d
        raise KeyError(code)

    def has_warning(self, code: WarningCode) -> bool:
        return any(w.code == code for w in self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": round(self.total_score, 2),
            "overall_confidence": round(self.overall_confidence, 4),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "warnings": [w.to_dict() for w in self.warnings],
            "critical_risks": list(self.critical_risks),
            "unknowns": list(self.unknowns),
        }


# ---------------------------------------------------------------------------
# 타깃 후보 / MVP
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TargetCandidate:
    """TECHSPEC F-060. 인구통계만 다른 후보는 만들지 않는다."""

    name: str
    user: str
    payer: str | None = None
    influencer: str | None = None
    trigger_situation: str = ""
    problem: str = ""
    current_alternative: str | None = None
    why_promising: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    validation_questions: tuple[str, ...] = ()
    recommended_experiment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "user": self.user,
            "payer": self.payer,
            "influencer": self.influencer,
            "trigger_situation": self.trigger_situation,
            "problem": self.problem,
            "current_alternative": self.current_alternative,
            "why_promising": list(self.why_promising),
            "risks": list(self.risks),
            "validation_questions": list(self.validation_questions),
            "recommended_experiment": self.recommended_experiment,
        }


@dataclass(frozen=True, slots=True)
class TargetCandidateSet:
    candidates: tuple[TargetCandidate, ...]
    recommended_candidate_index: int | None
    recommendation_reason: str
    source: str = "RULE"  # RULE | LLM | HUMAN

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "recommended_candidate_index": self.recommended_candidate_index,
            "recommendation_reason": self.recommendation_reason,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class MvpPlan:
    """TECHSPEC F-070."""

    core_hypothesis: str = ""
    problem_hypothesis: str = ""
    behavior_hypothesis: str = ""
    value_hypothesis: str = ""
    retention_hypothesis: str = ""
    revenue_hypothesis: str | None = None
    p0_features: tuple[str, ...] = ()
    p1_features: tuple[str, ...] = ()
    excluded_features: tuple[str, ...] = ()
    first_success_experience: str = ""
    core_user_flow: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    source: str = "RULE"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in (
            "p0_features",
            "p1_features",
            "excluded_features",
            "core_user_flow",
            "metrics",
            "risks",
        ):
            d[key] = list(getattr(self, key))
        return d


# ---------------------------------------------------------------------------
# 피벗
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PivotResult:
    """TECHSPEC F-090.

    would_be_decision: 신뢰도가 충분했다면 내려졌을 판단.
    HOLD가 근거 부족 때문인지, 실제로 문제가 없어서인지 구분하기 위해 함께 기록한다.
    """

    decision: PivotDecision
    confidence: float
    reason_codes: tuple[str, ...]
    rationale: str
    would_be_decision: PivotDecision | None = None
    evidence_ids: tuple[str, ...] = ()
    keep: tuple[str, ...] = ()
    change: tuple[str, ...] = ()
    remove: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    requires_human_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": str(self.decision),
            "confidence": round(self.confidence, 4),
            "reason_codes": list(self.reason_codes),
            "rationale": self.rationale,
            "would_be_decision": (
                str(self.would_be_decision) if self.would_be_decision else None
            ),
            "evidence_ids": list(self.evidence_ids),
            "keep": list(self.keep),
            "change": list(self.change),
            "remove": list(self.remove),
            "next_actions": list(self.next_actions),
            "requires_human_approval": self.requires_human_approval,
        }


# ---------------------------------------------------------------------------
# 분석 결과 묶음
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LlmAssist:
    """LLM이 이 버전의 어느 칸을 채웠는지에 대한 기록 (CLAUDE.md §7.3).

    LLM은 초안만 만든다. 사용자가 실제로 채택한 칸만 accepted_fields에 남는다.
    초안을 받아 놓고 전부 직접 고쳐 썼다면 accepted_fields는 비어 있고,
    그 버전은 사실상 사람이 쓴 것이므로 보고서에도 그렇게 표기된다.

    점수·신뢰도·피벗에는 이 기록이 어떤 영향도 주지 않는다. 표기 전용이다.
    """

    provider: str
    model: str
    prompt_version: str
    task: str  # "IDEA_STRUCTURE" | "TARGET_CANDIDATES"
    accepted_fields: tuple[str, ...] = ()
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "task": self.task,
            "accepted_fields": list(self.accepted_fields),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> LlmAssist | None:
        if not data:
            return None
        created = data.get("created_at")
        return cls(
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            prompt_version=data.get("prompt_version", ""),
            task=data.get("task", ""),
            accepted_fields=tuple(data.get("accepted_fields") or ()),
            created_at=datetime.fromisoformat(created) if created else None,
        )


@dataclass(frozen=True, slots=True)
class AnalysisMeta:
    """CLAUDE.md §7.3 '모든 AI 응답에는 모델·프롬프트 버전 기록'.

    Phase 1은 LLM을 쓰지 않으므로 engine="RULE_ENGINE", model_name=None이다.
    LLM을 붙이는 순간 같은 필드에 값이 채워지고 보고서에 그대로 표기된다.
    """

    engine: str
    engine_version: str
    policy_version: str
    schema_version: str
    domain_code: DomainCode
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "policy_version": self.policy_version,
            "schema_version": self.schema_version,
            "domain_code": str(self.domain_code),
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    meta: AnalysisMeta
    idea: IdeaStructure
    diagnosis: DiagnosisResult
    targets: TargetCandidateSet
    mvp: MvpPlan
    pivot: PivotResult
    next_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "idea": self.idea.to_dict(),
            "diagnosis": self.diagnosis.to_dict(),
            "targets": self.targets.to_dict(),
            "mvp": self.mvp.to_dict(),
            "pivot": self.pivot.to_dict(),
            "next_actions": list(self.next_actions),
        }


    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisResult:
        """저장된 JSON을 다시 객체로 되돌린다.

        엑셀처럼 분석 시점에 만들어 두지 않는 산출물을 나중에 생성할 때 쓴다.
        to_dict()의 역함수이며, JSON Schema를 통과한 payload만 들어온다고 가정한다.
        """
        m = data["meta"]
        meta = AnalysisMeta(
            engine=m["engine"],
            engine_version=m["engine_version"],
            policy_version=m["policy_version"],
            schema_version=m["schema_version"],
            domain_code=DomainCode(m["domain_code"]),
            model_provider=m.get("model_provider"),
            model_name=m.get("model_name"),
            prompt_version=m.get("prompt_version"),
            created_at=(
                datetime.fromisoformat(m["created_at"]) if m.get("created_at") else None
            ),
        )

        d = data["diagnosis"]
        diagnosis = DiagnosisResult(
            total_score=d["total_score"],
            overall_confidence=d["overall_confidence"],
            dimensions=tuple(
                DimensionScore(
                    code=DimensionCode(x["code"]),
                    label=x["label"],
                    raw_score=x["raw_score"],
                    weight=x["weight"],
                    normalized_score=x["normalized_score"],
                    reason=x["reason"],
                    missing_evidence=tuple(x.get("missing_evidence") or ()),
                    recommended_action=x.get("recommended_action", ""),
                    confidence=x.get("confidence", 0.0),
                )
                for x in d["dimensions"]
            ),
            warnings=tuple(
                DiagnosisWarning(
                    code=WarningCode(x["code"]),
                    message=x["message"],
                    severity=Severity(x["severity"]),
                    field=x.get("field"),
                    recommended_action=x.get("recommended_action", ""),
                )
                for x in d["warnings"]
            ),
            critical_risks=tuple(d.get("critical_risks") or ()),
            unknowns=tuple(d.get("unknowns") or ()),
        )

        t = data["targets"]
        targets = TargetCandidateSet(
            candidates=tuple(
                TargetCandidate(
                    name=c["name"],
                    user=c["user"],
                    payer=c.get("payer"),
                    influencer=c.get("influencer"),
                    trigger_situation=c.get("trigger_situation", ""),
                    problem=c.get("problem", ""),
                    current_alternative=c.get("current_alternative"),
                    why_promising=tuple(c.get("why_promising") or ()),
                    risks=tuple(c.get("risks") or ()),
                    validation_questions=tuple(c.get("validation_questions") or ()),
                    recommended_experiment=c.get("recommended_experiment", ""),
                )
                for c in t["candidates"]
            ),
            recommended_candidate_index=t.get("recommended_candidate_index"),
            recommendation_reason=t.get("recommendation_reason", ""),
            source=t.get("source", "RULE"),
        )

        mv = data["mvp"]
        mvp = MvpPlan(
            core_hypothesis=mv.get("core_hypothesis", ""),
            problem_hypothesis=mv.get("problem_hypothesis", ""),
            behavior_hypothesis=mv.get("behavior_hypothesis", ""),
            value_hypothesis=mv.get("value_hypothesis", ""),
            retention_hypothesis=mv.get("retention_hypothesis", ""),
            revenue_hypothesis=mv.get("revenue_hypothesis"),
            p0_features=tuple(mv.get("p0_features") or ()),
            p1_features=tuple(mv.get("p1_features") or ()),
            excluded_features=tuple(mv.get("excluded_features") or ()),
            first_success_experience=mv.get("first_success_experience", ""),
            core_user_flow=tuple(mv.get("core_user_flow") or ()),
            metrics=tuple(mv.get("metrics") or ()),
            risks=tuple(mv.get("risks") or ()),
            source=mv.get("source", "RULE"),
        )

        p = data["pivot"]
        pivot = PivotResult(
            decision=PivotDecision(p["decision"]),
            confidence=p["confidence"],
            reason_codes=tuple(p.get("reason_codes") or ()),
            rationale=p["rationale"],
            would_be_decision=(
                PivotDecision(p["would_be_decision"])
                if p.get("would_be_decision")
                else None
            ),
            evidence_ids=tuple(p.get("evidence_ids") or ()),
            keep=tuple(p.get("keep") or ()),
            change=tuple(p.get("change") or ()),
            remove=tuple(p.get("remove") or ()),
            next_actions=tuple(p.get("next_actions") or ()),
            requires_human_approval=p.get("requires_human_approval", True),
        )

        return cls(
            meta=meta,
            idea=IdeaStructure.from_dict(data["idea"]),
            diagnosis=diagnosis,
            targets=targets,
            mvp=mvp,
            pivot=pivot,
            next_actions=tuple(data.get("next_actions") or ()),
        )


def feature_key(text: str) -> str:
    """기능 문구로부터 안정적인 키를 만든다.

    기능 목록은 분석할 때마다 다시 생성되므로 순서 기반 ID(P0-01)는 흔들린다.
    문구를 정규화한 해시를 쓰면 같은 기능이 같은 키를 유지한다.
    문구를 바꾸면 다른 기능으로 취급되는데, 그게 맞다 — 내용이 바뀌었으면
    구현 상태를 다시 확인해야 한다.
    """
    import hashlib
    import re

    normalized = re.sub(r"\s+", " ", (text or "").strip()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class FeatureImplementation:
    """MVP 기능 하나의 구현 상태."""

    key: str
    text: str
    priority: str  # "P0" | "P1"
    status: ImplementationStatus = ImplementationStatus.NOT_STARTED
    note: str = ""

    @property
    def is_built(self) -> bool:
        return self.status in (
            ImplementationStatus.DONE,
            ImplementationStatus.IN_PROGRESS,
        )


@dataclass(frozen=True, slots=True)
class HypothesisVerdict:
    """가설 하나의 검증 현황. 등록된 근거에서 규칙으로 도출한다."""

    id: str
    label: str
    statement: str
    status: HypothesisStatus
    dimensions: tuple[DimensionCode, ...]
    supporting_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceExample:
    """근거 입력 양식을 어떻게 채우는지 보여주는 예시.

    이것은 **양식 예시**이지 근거가 아니다. 사용자가 이 내용을 그대로 등록하면
    자기 진단을 스스로 속이는 셈이 된다. UI는 반드시 그 사실을 함께 알려야 한다.
    AI는 근거를 생성하지 않는다는 원칙(CLAUDE.md §11)은 그대로 유지된다.
    """

    label: str  # 메뉴에 보일 이름
    evidence_type: EvidenceType
    title: str
    summary: str
    supports: tuple[DimensionCode, ...]
    contradicts: tuple[DimensionCode, ...] = ()
    source_reference: str | None = None
    sample_size: int | None = None
    note: str = ""  # 이 예시가 무엇을 보여주는지


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """도메인 모듈이 요구하는 측정 이벤트."""

    event_name: str
    description: str
    required: bool = True
