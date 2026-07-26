"""ORM 모델 (TECHSPEC §7).

SQLite에서 시작하지만 UUID(문자열), JSON, timezone-aware datetime을 써서
PostgreSQL 이전 시 스키마 변경을 최소화한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """timezone-aware UTC. CLAUDE.md §9 '시간은 timezone-aware 값 사용'."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """데스크톱 1차에서는 로컬 사용자 1명이지만, 웹 이전을 위해 테이블을 유지한다."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    app_name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    domain_code: Mapped[str] = mapped_column(String(32), default="GENERIC")
    stage: Mapped[str] = mapped_column(String(32), default="IDEA")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    latest_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    versions: Mapped[list["ProjectVersion"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectVersion.version_no",
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_projects_owner_status", "owner_id", "status"),)


class ProjectVersion(Base):
    __tablename__ = "project_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    version_no: Mapped[int] = mapped_column(Integer)
    raw_input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    structured_idea: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    structure_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    #: LLM이 이 버전의 구조화 초안을 도왔다는 기록 (core.models.LlmAssist).
    #: 표기 전용이다. 점수·신뢰도·피벗 계산에는 절대 쓰이지 않는다 (ADR-0002).
    llm_assist: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    change_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="versions")
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "version_no", name="uq_version_no_per_project"),
    )


class EvaluationPolicyRow(Base):
    """관리자가 수정 가능한 평가 정책 (CLAUDE.md §11)."""

    __tablename__ = "evaluation_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    project_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_versions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    engine: Mapped[str] = mapped_column(String(64), default="RULE_ENGINE")
    engine_version: Mapped[str] = mapped_column(String(32), default="")
    policy_version: Mapped[str] = mapped_column(String(64), default="")
    schema_version: Mapped[str] = mapped_column(String(64), default="")
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    version: Mapped[ProjectVersion] = relationship(back_populates="runs")
    scores: Mapped[list["EvaluationScore"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_analysis_idempotency"),
        Index("ix_runs_project_started", "project_id", "started_at"),
    )


class EvaluationScore(Base):
    """항목별 점수를 별도 행으로 저장한다. 버전 간 점수 변화 비교에 쓴다."""

    __tablename__ = "evaluation_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    dimension_code: Mapped[str] = mapped_column(String(8))
    raw_score: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float)
    normalized_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[AnalysisRun] = relationship(back_populates="scores")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    evidence_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    supports: Mapped[list[str]] = mapped_column(JSON, default=list)
    contradicts: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="evidence")


class FeatureStatus(Base):
    """MVP 기능의 구현 상태 (프로젝트 단위).

    분석은 다시 실행할 때마다 기능 목록을 새로 만들지만 구현 상태는 남아야 한다.
    그래서 분석이 아니라 프로젝트에 붙이고, 기능 문구 해시를 키로 쓴다.
    """

    __tablename__ = "feature_statuses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    feature_key: Mapped[str] = mapped_column(String(32))
    feature_text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(8), default="P0")
    status: Mapped[str] = mapped_column(String(24), default="NOT_STARTED")
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("project_id", "feature_key", name="uq_feature_per_project"),
    )


class ExperimentRow(Base):
    """실험 설계와 결과 (TECHSPEC F-080).

    가설 ID는 MVP 계획에서 도출된 것(H-PROBLEM 등)을 쓴다.
    별도 가설 테이블을 두지 않는 이유는, 가설이 분석 결과에서 나오기 때문이다.
    사람이 따로 관리하면 분석과 어긋난다.
    """

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(300))
    hypothesis_id: Mapped[str] = mapped_column(String(32))
    experiment_type: Mapped[str] = mapped_column(String(32))
    target_segment: Mapped[str] = mapped_column(Text, default="")
    procedure: Mapped[list[str]] = mapped_column(JSON, default=list)
    success_metric: Mapped[str] = mapped_column(Text, default="")
    target_value: Mapped[str] = mapped_column(String(120), default="")
    sample_goal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_sample: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantitative_result: Mapped[str] = mapped_column(Text, default="")
    qualitative_summary: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str | None] = mapped_column(String(24), nullable=True)
    next_experiment: Mapped[str] = mapped_column(Text, default="")
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (Index("ix_experiments_project", "project_id", "status"),)


class PivotDecisionRow(Base):
    """피벗 판단과 사람의 승인 기록 (TECHSPEC F-090, §7.8).

    시스템 판단을 분석 결과 안에만 두면 "사람이 무엇을 승인했는지"가 남지 않는다.
    특히 **거절 사유**가 중요하다. 왜 시스템과 다르게 판단했는지를 남겨야
    나중에 그 판단이 옳았는지 되짚을 수 있다.
    """

    __tablename__ = "pivot_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    version_no: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str] = mapped_column(String(32))
    would_be_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(24), default="PENDING")
    approval_note: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("analysis_run_id", name="uq_pivot_per_run"),
        Index("ix_pivot_project_created", "project_id", "created_at"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    format: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[AnalysisRun] = relationship(back_populates="reports")


class AuditLog(Base):
    """감사 로그 (TECHSPEC §7.10). 민감정보는 기록하지 않는다."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_audit_object", "object_type", "object_id"),)


class AnalyticsEvent(Base):
    """분석 이벤트 (TECHSPEC §12). 데스크톱에서는 로컬에만 쌓인다."""

    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_name: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_events_name_time", "event_name", "occurred_at"),)
