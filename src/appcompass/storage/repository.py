"""리포지토리.

SQL 접근을 이 계층에 가둔다. services는 ORM 쿼리를 직접 작성하지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..core.enums import AuditAction
from .orm import (
    AnalysisRun,
    AnalyticsEvent,
    AuditLog,
    EvaluationPolicyRow,
    EvaluationScore,
    Evidence,
    Project,
    ProjectVersion,
    Report,
    User,
    utcnow,
)


class Repository:
    """세션 하나에 묶인 리포지토리. 트랜잭션 경계는 호출자가 관리한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- 사용자 -----------------------------------------------------------
    def get_or_create_local_user(self, email: str, display_name: str = "") -> User:
        user = self.session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, display_name=display_name or email, is_admin=True)
            self.session.add(user)
            self.session.flush()
        return user

    def get_user(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    # -- 프로젝트 ---------------------------------------------------------
    def create_project(self, **kwargs: Any) -> Project:
        project = Project(**kwargs)
        self.session.add(project)
        self.session.flush()
        return project

    def get_project(self, project_id: str) -> Project | None:
        return self.session.get(Project, project_id)

    def list_projects(
        self, owner_id: str, include_archived: bool = False
    ) -> list[Project]:
        stmt = select(Project).where(Project.owner_id == owner_id)
        if not include_archived:
            stmt = stmt.where(Project.status != "ARCHIVED")
        stmt = stmt.order_by(desc(Project.updated_at))
        return list(self.session.scalars(stmt))

    def delete_project(self, project: Project) -> None:
        self.session.delete(project)

    # -- 버전 -------------------------------------------------------------
    def next_version_no(self, project_id: str) -> int:
        current = self.session.scalar(
            select(func.max(ProjectVersion.version_no)).where(
                ProjectVersion.project_id == project_id
            )
        )
        return (current or 0) + 1

    def create_version(self, **kwargs: Any) -> ProjectVersion:
        version = ProjectVersion(**kwargs)
        self.session.add(version)
        self.session.flush()
        return version

    def get_version(self, version_id: str) -> ProjectVersion | None:
        return self.session.get(ProjectVersion, version_id)

    def list_versions(self, project_id: str) -> list[ProjectVersion]:
        stmt = (
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(desc(ProjectVersion.version_no))
        )
        return list(self.session.scalars(stmt))

    def latest_version(self, project_id: str) -> ProjectVersion | None:
        stmt = (
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(desc(ProjectVersion.version_no))
            .limit(1)
        )
        return self.session.scalar(stmt)

    # -- 분석 -------------------------------------------------------------
    def create_run(self, **kwargs: Any) -> AnalysisRun:
        run = AnalysisRun(**kwargs)
        self.session.add(run)
        self.session.flush()
        return run

    def get_run(self, run_id: str) -> AnalysisRun | None:
        return self.session.get(AnalysisRun, run_id)

    def find_run_by_idempotency_key(self, key: str) -> AnalysisRun | None:
        return self.session.scalar(
            select(AnalysisRun).where(AnalysisRun.idempotency_key == key)
        )

    def latest_run(self, project_id: str) -> AnalysisRun | None:
        stmt = (
            select(AnalysisRun)
            .where(
                AnalysisRun.project_id == project_id,
                AnalysisRun.status == "COMPLETED",
            )
            .order_by(desc(AnalysisRun.started_at))
            .limit(1)
        )
        return self.session.scalar(stmt)

    def latest_completed_run_for_version(self, version_id: str) -> AnalysisRun | None:
        stmt = (
            select(AnalysisRun)
            .where(
                AnalysisRun.project_version_id == version_id,
                AnalysisRun.status == "COMPLETED",
            )
            .order_by(desc(AnalysisRun.started_at))
            .limit(1)
        )
        return self.session.scalar(stmt)

    def list_runs(self, project_id: str, limit: int = 50) -> list[AnalysisRun]:
        stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.project_id == project_id)
            .order_by(desc(AnalysisRun.started_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def add_scores(self, run: AnalysisRun, dimensions: Sequence[dict[str, Any]]) -> None:
        for d in dimensions:
            self.session.add(
                EvaluationScore(
                    analysis_run_id=run.id,
                    dimension_code=d["code"],
                    raw_score=float(d["raw_score"]),
                    weight=float(d["weight"]),
                    normalized_score=float(d["normalized_score"]),
                    confidence=float(d.get("confidence", 0.0)),
                    reason=d.get("reason", ""),
                )
            )

    # -- 근거 -------------------------------------------------------------
    def add_evidence(self, **kwargs: Any) -> Evidence:
        item = Evidence(**kwargs)
        self.session.add(item)
        self.session.flush()
        return item

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        return self.session.get(Evidence, evidence_id)

    def list_evidence(self, project_id: str) -> list[Evidence]:
        stmt = (
            select(Evidence)
            .where(Evidence.project_id == project_id)
            .order_by(desc(Evidence.created_at))
        )
        return list(self.session.scalars(stmt))

    def delete_evidence(self, item: Evidence) -> None:
        self.session.delete(item)

    # -- 보고서 -----------------------------------------------------------
    def add_report(self, **kwargs: Any) -> Report:
        report = Report(**kwargs)
        self.session.add(report)
        self.session.flush()
        return report

    def list_reports(self, run_id: str) -> list[Report]:
        stmt = (
            select(Report)
            .where(Report.analysis_run_id == run_id)
            .order_by(desc(Report.created_at))
        )
        return list(self.session.scalars(stmt))

    # -- 정책 -------------------------------------------------------------
    def active_policy(self) -> EvaluationPolicyRow | None:
        return self.session.scalar(
            select(EvaluationPolicyRow).where(EvaluationPolicyRow.is_active.is_(True))
        )

    def save_policy(self, version: str, payload: dict[str, Any]) -> EvaluationPolicyRow:
        existing = self.session.scalar(
            select(EvaluationPolicyRow).where(EvaluationPolicyRow.version == version)
        )
        for row in self.session.scalars(select(EvaluationPolicyRow)):
            row.is_active = False
        if existing is None:
            existing = EvaluationPolicyRow(version=version, payload=payload, is_active=True)
            self.session.add(existing)
        else:
            existing.payload = payload
            existing.is_active = True
        self.session.flush()
        return existing

    # -- 감사 로그 / 이벤트 ------------------------------------------------
    def audit(
        self,
        actor_id: str | None,
        action: AuditAction,
        object_type: str,
        object_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            action=str(action),
            object_type=object_type,
            object_id=object_id,
            before=before,
            after=after,
        )
        self.session.add(log)
        return log

    def list_audit_logs(self, limit: int = 200) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        return list(self.session.scalars(stmt))

    def track(
        self,
        event_name: str,
        project_id: str | None = None,
        properties: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> AnalyticsEvent:
        event = AnalyticsEvent(
            event_name=event_name,
            project_id=project_id,
            properties=properties or {},
            occurred_at=occurred_at or utcnow(),
        )
        self.session.add(event)
        return event

    def list_events(self, limit: int = 200) -> list[AnalyticsEvent]:
        stmt = (
            select(AnalyticsEvent).order_by(desc(AnalyticsEvent.occurred_at)).limit(limit)
        )
        return list(self.session.scalars(stmt))
