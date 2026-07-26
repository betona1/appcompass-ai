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
