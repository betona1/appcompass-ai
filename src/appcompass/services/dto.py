"""UI가 쓰는 읽기 전용 표현.

UI가 ORM 객체를 직접 만지면 세션 수명에 묶여 버린다.
서비스는 항상 detached DTO를 돌려준다. 웹으로 옮길 때 그대로 JSON 직렬화 대상이 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.enums import DomainCode, ProjectStage, ProjectStatus


@dataclass(frozen=True, slots=True)
class ProjectDTO:
    id: str
    name: str
    app_name: str
    description: str
    domain_code: DomainCode
    stage: ProjectStage
    status: ProjectStatus
    latest_version_no: int | None
    version_count: int
    evidence_count: int
    latest_decision: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VersionDTO:
    id: str
    project_id: str
    version_no: int
    raw_input: dict[str, Any]
    structured_idea: dict[str, Any]
    structure_approved: bool
    change_reason: str
    created_at: datetime
    #: LLM이 이 버전의 어느 칸을 도왔는지 (core.models.LlmAssist.to_dict()).
    #: None이면 사람이 전부 직접 썼다는 뜻이다.
    llm_assist: dict[str, Any] | None = None

    @property
    def llm_accepted_fields(self) -> tuple[str, ...]:
        return tuple((self.llm_assist or {}).get("accepted_fields") or ())


@dataclass(frozen=True, slots=True)
class RunDTO:
    id: str
    project_id: str
    version_id: str
    version_no: int
    status: str
    engine: str
    engine_version: str
    policy_version: str
    schema_version: str
    model_name: str | None
    result: dict[str, Any] | None
    error_code: str | None
    error_detail: str | None
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class EvidenceDTO:
    id: str
    project_id: str
    evidence_type: str
    title: str
    summary: str
    source_reference: str | None
    sample_size: int | None
    observed_at: datetime | None
    confidence_override: float | None
    supports: tuple[str, ...]
    contradicts: tuple[str, ...]
    effective_confidence: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReportDTO:
    id: str
    run_id: str
    format: str
    content: str
    checksum: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PivotDecisionDTO:
    id: str
    project_id: str
    run_id: str
    version_no: int
    decision: str
    would_be_decision: str | None
    confidence: float
    total_score: float
    reason_codes: tuple[str, ...]
    rationale: str
    approval_status: str
    approval_note: str
    approved_at: datetime | None
    created_at: datetime

    @property
    def is_pending(self) -> bool:
        return self.approval_status == "PENDING"


@dataclass(frozen=True, slots=True)
class AuditLogDTO:
    id: str
    actor_id: str | None
    action: str
    object_type: str
    object_id: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LLMStatusDTO:
    """AI 초안 기능이 지금 쓸 수 있는 상태인지.

    키 원본은 절대 담지 않는다. 화면에 보여줄 마스킹 값만 갖는다.
    """

    available: bool
    sdk_installed: bool
    key_configured: bool
    key_source: str
    masked_key: str
    model: str
    effort: str
    message: str


@dataclass(frozen=True, slots=True)
class VersionDiffRow:
    """버전 비교 화면(H)용 한 줄."""

    label: str
    before: str
    after: str
    changed: bool
