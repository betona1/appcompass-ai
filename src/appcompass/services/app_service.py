"""AppService — UI와 (미래의) REST API가 함께 쓰는 파사드.

이 클래스는 PySide6를 import하지 않는다.
웹으로 옮길 때 Django view가 이 메서드들을 그대로 호출하면 된다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence

from ..core.enums import (
    AnalysisStatus,
    AuditAction,
    DimensionCode,
    DomainCode,
    EvidenceType,
    ProjectStage,
    ProjectStatus,
    ReportFormat,
)
from ..core.models import AnalysisResult, EvidenceItem, IdeaStructure, RawIdeaInput
from ..core.pipeline import run_analysis
from ..core.policy import EvaluationPolicy
from ..core.exports import save_workbook
from ..core.report import checksum as report_checksum
from ..core.report import render_html, render_markdown
from ..core.techspec import render_techspec
from ..core.schema import SchemaValidationError, validate_analysis_result
from ..storage.db import Database
from ..storage.orm import (
    AnalysisRun,
    Evidence,
    Project,
    ProjectVersion,
    utcnow,
)
from ..storage.repository import Repository
from .dto import (
    AuditLogDTO,
    EvidenceDTO,
    ProjectDTO,
    ReportDTO,
    RunDTO,
    VersionDTO,
    VersionDiffRow,
)


class ServiceError(RuntimeError):
    """사용자에게 그대로 보여줄 수 있는 오류."""


class PermissionDenied(ServiceError):
    pass


DEFAULT_LOCAL_EMAIL = "local@appcompass"


class AppService:
    def __init__(self, db: Database, actor_email: str = DEFAULT_LOCAL_EMAIL) -> None:
        self.db = db
        self.db.create_all()
        self.actor_email = actor_email
        with self.db.transaction() as s:
            repo = Repository(s)
            user = repo.get_or_create_local_user(actor_email, "로컬 사용자")
            self.actor_id = user.id

    # ==================================================================
    # 정책
    # ==================================================================
    def get_policy(self) -> EvaluationPolicy:
        with self.db.transaction() as s:
            row = Repository(s).active_policy()
            if row is None:
                return EvaluationPolicy()
            return EvaluationPolicy.from_dict(row.payload)

    def save_policy(self, policy: EvaluationPolicy) -> EvaluationPolicy:
        policy.validate()  # 가중치 합계 100 등 불변식 재확인
        with self.db.transaction() as s:
            repo = Repository(s)
            before = repo.active_policy()
            repo.save_policy(policy.version, policy.to_dict())
            repo.audit(
                self.actor_id,
                AuditAction.POLICY_UPDATED,
                "EvaluationPolicy",
                policy.version,
                before=before.payload if before else None,
                after=policy.to_dict(),
            )
        return policy

    # ==================================================================
    # 프로젝트
    # ==================================================================
    def create_project(
        self,
        name: str,
        app_name: str = "",
        description: str = "",
        domain_code: DomainCode = DomainCode.GENERIC,
        stage: ProjectStage = ProjectStage.IDEA,
    ) -> ProjectDTO:
        if not name.strip():
            raise ServiceError("프로젝트 이름을 입력하세요.")
        with self.db.transaction() as s:
            repo = Repository(s)
            project = repo.create_project(
                owner_id=self.actor_id,
                name=name.strip(),
                app_name=app_name.strip(),
                description=description.strip(),
                domain_code=str(domain_code),
                stage=str(stage),
                status=str(ProjectStatus.ACTIVE),
            )
            repo.audit(
                self.actor_id,
                AuditAction.PROJECT_CREATED,
                "Project",
                project.id,
                after={"name": project.name, "domain_code": project.domain_code},
            )
            repo.track("project_created", project.id, {"domain_code": project.domain_code})
            return self._project_dto(repo, project)

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        app_name: str | None = None,
        description: str | None = None,
        domain_code: DomainCode | None = None,
        stage: ProjectStage | None = None,
    ) -> ProjectDTO:
        with self.db.transaction() as s:
            repo = Repository(s)
            project = self._require_project(repo, project_id)
            before = {
                "name": project.name,
                "app_name": project.app_name,
                "domain_code": project.domain_code,
                "stage": project.stage,
            }
            if name is not None:
                project.name = name.strip()
            if app_name is not None:
                project.app_name = app_name.strip()
            if description is not None:
                project.description = description.strip()
            if domain_code is not None:
                project.domain_code = str(domain_code)
            if stage is not None:
                project.stage = str(stage)
            repo.audit(
                self.actor_id,
                AuditAction.PROJECT_UPDATED,
                "Project",
                project.id,
                before=before,
                after={
                    "name": project.name,
                    "app_name": project.app_name,
                    "domain_code": project.domain_code,
                    "stage": project.stage,
                },
            )
            return self._project_dto(repo, project)

    def archive_project(self, project_id: str) -> None:
        with self.db.transaction() as s:
            repo = Repository(s)
            project = self._require_project(repo, project_id)
            project.status = str(ProjectStatus.ARCHIVED)
            repo.audit(
                self.actor_id, AuditAction.PROJECT_ARCHIVED, "Project", project.id
            )

    def delete_project(self, project_id: str) -> None:
        """파괴적 작업. UI는 반드시 확인 단계를 거쳐 호출한다."""
        with self.db.transaction() as s:
            repo = Repository(s)
            project = self._require_project(repo, project_id)
            repo.audit(
                self.actor_id,
                AuditAction.PROJECT_DELETED,
                "Project",
                project.id,
                before={"name": project.name},
            )
            repo.delete_project(project)

    def list_projects(self, include_archived: bool = False) -> list[ProjectDTO]:
        with self.db.transaction() as s:
            repo = Repository(s)
            return [
                self._project_dto(repo, p)
                for p in repo.list_projects(self.actor_id, include_archived)
            ]

    def get_project(self, project_id: str) -> ProjectDTO:
        with self.db.transaction() as s:
            repo = Repository(s)
            return self._project_dto(repo, self._require_project(repo, project_id))

    # ==================================================================
    # 버전 / 아이디어
    # ==================================================================
    def create_version(
        self,
        project_id: str,
        raw: RawIdeaInput,
        idea: IdeaStructure,
        change_reason: str = "",
        approved: bool = False,
    ) -> VersionDTO:
        with self.db.transaction() as s:
            repo = Repository(s)
            project = self._require_project(repo, project_id)
            version = repo.create_version(
                project_id=project.id,
                version_no=repo.next_version_no(project.id),
                raw_input=raw.to_dict(),
                structured_idea=idea.to_dict(),
                structure_approved=approved,
                change_reason=change_reason.strip(),
                created_by=self.actor_id,
            )
            project.latest_version_id = version.id
            if idea.app_name and not project.app_name:
                project.app_name = idea.app_name
            repo.audit(
                self.actor_id,
                AuditAction.VERSION_CREATED,
                "ProjectVersion",
                version.id,
                after={"version_no": version.version_no, "reason": version.change_reason},
            )
            repo.track(
                "idea_input_completed", project.id, {"version_no": version.version_no}
            )
            return self._version_dto(version)

    def update_version(
        self,
        version_id: str,
        *,
        raw: RawIdeaInput | None = None,
        idea: IdeaStructure | None = None,
        change_reason: str | None = None,
    ) -> VersionDTO:
        """승인 전 버전의 내용을 수정한다. 승인된 버전은 수정하지 않고 새 버전을 만든다."""
        with self.db.transaction() as s:
            repo = Repository(s)
            version = repo.get_version(version_id)
            if version is None:
                raise ServiceError("버전을 찾을 수 없습니다.")
            self._require_project(repo, version.project_id)
            if version.structure_approved:
                raise ServiceError(
                    "이미 승인된 버전은 수정할 수 없습니다. 새 버전을 만드세요."
                )
            if raw is not None:
                version.raw_input = raw.to_dict()
            if idea is not None:
                version.structured_idea = idea.to_dict()
            if change_reason is not None:
                version.change_reason = change_reason.strip()
            return self._version_dto(version)

    def approve_structure(self, version_id: str) -> VersionDTO:
        with self.db.transaction() as s:
            repo = Repository(s)
            version = repo.get_version(version_id)
            if version is None:
                raise ServiceError("버전을 찾을 수 없습니다.")
            self._require_project(repo, version.project_id)
            version.structure_approved = True
            repo.audit(
                self.actor_id,
                AuditAction.STRUCTURE_APPROVED,
                "ProjectVersion",
                version.id,
            )
            repo.track("structure_reviewed", version.project_id)
            return self._version_dto(version)

    def list_versions(self, project_id: str) -> list[VersionDTO]:
        with self.db.transaction() as s:
            repo = Repository(s)
            self._require_project(repo, project_id)
            return [self._version_dto(v) for v in repo.list_versions(project_id)]

    def latest_version(self, project_id: str) -> VersionDTO | None:
        with self.db.transaction() as s:
            repo = Repository(s)
            self._require_project(repo, project_id)
            version = repo.latest_version(project_id)
            return self._version_dto(version) if version else None

    # ==================================================================
    # 근거
    # ==================================================================
    def add_evidence(
        self,
        project_id: str,
        evidence_type: EvidenceType,
        title: str,
        summary: str = "",
        source_reference: str | None = None,
        sample_size: int | None = None,
        observed_at: datetime | None = None,
        confidence_override: float | None = None,
        supports: Sequence[DimensionCode] = (),
        contradicts: Sequence[DimensionCode] = (),
    ) -> EvidenceDTO:
        if not title.strip():
            raise ServiceError("근거 제목을 입력하세요.")
        if not supports and not contradicts:
            raise ServiceError(
                "이 근거가 어떤 평가 항목을 지지하거나 반박하는지 하나 이상 선택하세요."
            )
        if confidence_override is not None and not 0.0 <= confidence_override <= 1.0:
            raise ServiceError("신뢰도 직접 지정 값은 0.0~1.0 이어야 합니다.")

        with self.db.transaction() as s:
            repo = Repository(s)
            self._require_project(repo, project_id)
            item = repo.add_evidence(
                project_id=project_id,
                evidence_type=str(evidence_type),
                title=title.strip(),
                summary=summary.strip(),
                source_reference=(source_reference or "").strip() or None,
                sample_size=sample_size,
                observed_at=observed_at,
                confidence_override=confidence_override,
                supports=[str(c) for c in supports],
                contradicts=[str(c) for c in contradicts],
                created_by=self.actor_id,
            )
            repo.audit(
                self.actor_id,
                AuditAction.EVIDENCE_ADDED,
                "Evidence",
                item.id,
                after={"type": item.evidence_type, "title": item.title},
            )
            repo.track("evidence_added", project_id, {"type": item.evidence_type})
            return self._evidence_dto(item, self.get_policy())

    def delete_evidence(self, evidence_id: str) -> None:
        with self.db.transaction() as s:
            repo = Repository(s)
            item = repo.get_evidence(evidence_id)
            if item is None:
                raise ServiceError("근거를 찾을 수 없습니다.")
            self._require_project(repo, item.project_id)
            repo.audit(
                self.actor_id,
                AuditAction.EVIDENCE_DELETED,
                "Evidence",
                item.id,
                before={"type": item.evidence_type, "title": item.title},
            )
            repo.delete_evidence(item)

    def list_evidence(self, project_id: str) -> list[EvidenceDTO]:
        policy = self.get_policy()
        with self.db.transaction() as s:
            repo = Repository(s)
            self._require_project(repo, project_id)
            return [
                self._evidence_dto(e, policy) for e in repo.list_evidence(project_id)
            ]

    # ==================================================================
    # 분석
    # ==================================================================
    def run_analysis(self, version_id: str) -> RunDTO:
        """분석을 실행하고 결과를 저장한다.

        같은 (버전 내용 + 정책 버전) 조합이면 idempotency key가 같아
        중복 분석을 만들지 않는다 (TECHSPEC §14 '동일 입력 중복 분석 방지').
        """
        policy = self.get_policy()

        with self.db.transaction() as s:
            repo = Repository(s)
            version = repo.get_version(version_id)
            if version is None:
                raise ServiceError("버전을 찾을 수 없습니다.")
            project = self._require_project(repo, version.project_id)

            if not version.structure_approved:
                raise ServiceError(
                    "구조화 결과를 먼저 승인해야 분석을 실행할 수 있습니다. (화면 B)"
                )

            evidence_rows = repo.list_evidence(project.id)
            key = self._idempotency_key(version, policy, evidence_rows)

            existing = repo.find_run_by_idempotency_key(key)
            if existing is not None and existing.status == str(AnalysisStatus.COMPLETED):
                return self._run_dto(existing, version.version_no)

            run = repo.create_run(
                project_id=project.id,
                project_version_id=version.id,
                status=str(AnalysisStatus.RUNNING),
                idempotency_key=key,
                policy_version=policy.version,
            )
            repo.audit(
                self.actor_id, AuditAction.ANALYSIS_REQUESTED, "AnalysisRun", run.id
            )
            repo.track("analysis_requested", project.id, {"run_id": run.id})

            idea = IdeaStructure.from_dict(version.structured_idea)
            evidence = [self._evidence_item(e) for e in evidence_rows]
            domain_code = DomainCode(project.domain_code)
            version_no = version.version_no
            project_name = project.name

            try:
                result = run_analysis(
                    idea,
                    domain_code=domain_code,
                    policy=policy,
                    evidence=evidence,
                    now=datetime.now(timezone.utc),
                )
                payload = result.to_dict()
                validate_analysis_result(payload)
            except SchemaValidationError as exc:
                run.status = str(AnalysisStatus.FAILED_SCHEMA)
                run.error_code = "FAILED_SCHEMA"
                run.error_detail = str(exc)
                run.completed_at = utcnow()
                repo.audit(
                    self.actor_id,
                    AuditAction.ANALYSIS_FAILED,
                    "AnalysisRun",
                    run.id,
                    after={"error_code": run.error_code},
                )
                repo.track("analysis_failed", project.id, {"error": "FAILED_SCHEMA"})
                return self._run_dto(run, version_no)
            except Exception as exc:  # noqa: BLE001 - 분석 실패를 상태로 남긴다
                run.status = str(AnalysisStatus.FAILED_INTERNAL)
                run.error_code = "FAILED_INTERNAL"
                run.error_detail = f"{type(exc).__name__}: {exc}"
                run.completed_at = utcnow()
                repo.audit(
                    self.actor_id,
                    AuditAction.ANALYSIS_FAILED,
                    "AnalysisRun",
                    run.id,
                    after={"error_code": run.error_code},
                )
                repo.track("analysis_failed", project.id, {"error": "FAILED_INTERNAL"})
                return self._run_dto(run, version_no)

            run.status = str(AnalysisStatus.COMPLETED)
            run.result = payload
            run.engine = result.meta.engine
            run.engine_version = result.meta.engine_version
            run.schema_version = result.meta.schema_version
            run.model_name = result.meta.model_name
            run.prompt_version = result.meta.prompt_version
            run.completed_at = utcnow()
            repo.add_scores(run, payload["diagnosis"]["dimensions"])

            # 보고서를 함께 생성해 버전 고정 (TECHSPEC F-100)
            # 엑셀은 텍스트가 아니라 여기 저장하지 않고 내보낼 때 만든다.
            documents = {
                ReportFormat.MARKDOWN: render_markdown(
                    result, evidence, project_name=project_name, version_no=version_no
                ),
                ReportFormat.HTML: render_html(
                    result, evidence, project_name=project_name, version_no=version_no
                ),
                ReportFormat.TECHSPEC: render_techspec(
                    result, evidence, project_name=project_name, version_no=version_no
                ),
            }
            for fmt, content in documents.items():
                repo.add_report(
                    analysis_run_id=run.id,
                    format=str(fmt),
                    content=content,
                    checksum=report_checksum(content),
                )

            repo.audit(
                self.actor_id,
                AuditAction.ANALYSIS_COMPLETED,
                "AnalysisRun",
                run.id,
                after={
                    "decision": payload["pivot"]["decision"],
                    "total_score": payload["diagnosis"]["total_score"],
                },
            )
            repo.track(
                "analysis_completed",
                project.id,
                {
                    "run_id": run.id,
                    "decision": payload["pivot"]["decision"],
                    "total_score": payload["diagnosis"]["total_score"],
                    "policy_version": policy.version,
                },
            )
            return self._run_dto(run, version_no)

    def latest_run(self, project_id: str) -> RunDTO | None:
        with self.db.transaction() as s:
            repo = Repository(s)
            self._require_project(repo, project_id)
            run = repo.latest_run(project_id)
            if run is None:
                return None
            version = repo.get_version(run.project_version_id)
            return self._run_dto(run, version.version_no if version else 0)

    def list_runs(self, project_id: str) -> list[RunDTO]:
        with self.db.transaction() as s:
            repo = Repository(s)
            self._require_project(repo, project_id)
            out: list[RunDTO] = []
            for run in repo.list_runs(project_id):
                version = repo.get_version(run.project_version_id)
                out.append(self._run_dto(run, version.version_no if version else 0))
            return out

    def get_run(self, run_id: str) -> RunDTO:
        with self.db.transaction() as s:
            repo = Repository(s)
            run = repo.get_run(run_id)
            if run is None:
                raise ServiceError("분석 실행을 찾을 수 없습니다.")
            self._require_project(repo, run.project_id)
            version = repo.get_version(run.project_version_id)
            return self._run_dto(run, version.version_no if version else 0)

    # ==================================================================
    # 보고서
    # ==================================================================
    def get_reports(self, run_id: str) -> list[ReportDTO]:
        with self.db.transaction() as s:
            repo = Repository(s)
            run = repo.get_run(run_id)
            if run is None:
                raise ServiceError("분석 실행을 찾을 수 없습니다.")
            self._require_project(repo, run.project_id)
            return [
                ReportDTO(
                    id=r.id,
                    run_id=r.analysis_run_id,
                    format=r.format,
                    content=r.content,
                    checksum=r.checksum,
                    created_at=r.created_at,
                )
                for r in repo.list_reports(run_id)
            ]

    def export_report(self, run_id: str, fmt: ReportFormat, path: str) -> str:
        """보고서를 파일로 내보낸다.

        텍스트 형식은 분석 시점에 고정된 내용을 그대로 쓴다.
        엑셀은 바이너리라 DB에 두지 않고 저장된 분석 결과에서 그때 만든다.
        어느 쪽이든 원본은 분석 결과이므로 내용이 달라지지 않는다.
        """
        fmt = ReportFormat(fmt)

        if fmt == ReportFormat.XLSX:
            checksum_value = self._export_xlsx(run_id, path)
            report_id = None
        else:
            reports = {r.format: r for r in self.get_reports(run_id)}
            report = reports.get(str(fmt))
            if report is None:
                raise ServiceError(
                    f"{fmt} 형식 보고서가 없습니다. 분석을 다시 실행하면 생성됩니다."
                )
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report.content)
            checksum_value = report.checksum
            report_id = report.id

        with self.db.transaction() as s:
            repo = Repository(s)
            run = repo.get_run(run_id)
            repo.audit(
                self.actor_id,
                AuditAction.REPORT_EXPORTED,
                "Report",
                report_id or run_id,
                after={"format": str(fmt), "checksum": checksum_value},
            )
            if run:
                repo.track("report_exported", run.project_id, {"format": str(fmt)})
        return path

    def _export_xlsx(self, run_id: str, path: str) -> str:
        """저장된 분석 결과로 엑셀 파일을 만든다."""
        with self.db.transaction() as s:
            repo = Repository(s)
            run = repo.get_run(run_id)
            if run is None:
                raise ServiceError("분석 실행을 찾을 수 없습니다.")
            project = self._require_project(repo, run.project_id)
            if not run.result:
                raise ServiceError("완료된 분석 결과가 없어 엑셀을 만들 수 없습니다.")
            version = repo.get_version(run.project_version_id)
            evidence = [self._evidence_item(e) for e in repo.list_evidence(project.id)]
            payload = dict(run.result)
            project_name = project.name
            version_no = version.version_no if version else None

        result = AnalysisResult.from_dict(payload)
        save_workbook(
            path, result, evidence, project_name=project_name, version_no=version_no
        )
        return report_checksum(str(sorted(payload.items())))

    # ==================================================================
    # 버전 비교 (화면 H)
    # ==================================================================
    def diff_versions(self, version_a_id: str, version_b_id: str) -> list[VersionDiffRow]:
        labels = [
            ("target_user", "사용자"),
            ("payer", "구매자"),
            ("influencer", "영향자"),
            ("problem_situation", "문제 상황"),
            ("current_solution", "현재 대체 방법"),
            ("current_solution_problem", "대체 방법의 한계"),
            ("core_action", "핵심 행동"),
            ("expected_result", "기대 결과"),
            ("first_success", "첫 성공 경험"),
            ("retention_reason", "재방문 이유"),
            ("revenue_model", "수익 모델"),
            ("distribution_channel", "유입 경로"),
        ]
        with self.db.transaction() as s:
            repo = Repository(s)
            a = repo.get_version(version_a_id)
            b = repo.get_version(version_b_id)
            if a is None or b is None:
                raise ServiceError("비교할 버전을 찾을 수 없습니다.")
            self._require_project(repo, a.project_id)
            rows = [
                VersionDiffRow(
                    label="변경 사유",
                    before=a.change_reason or "-",
                    after=b.change_reason or "-",
                    changed=(a.change_reason or "") != (b.change_reason or ""),
                )
            ]
            for key, label in labels:
                before = str(a.structured_idea.get(key) or "-")
                after = str(b.structured_idea.get(key) or "-")
                rows.append(
                    VersionDiffRow(
                        label=label, before=before, after=after, changed=before != after
                    )
                )

            run_a = self._run_for_version(repo, a.id)
            run_b = self._run_for_version(repo, b.id)
            rows.append(
                VersionDiffRow(
                    label="총점",
                    before=self._score_text(run_a),
                    after=self._score_text(run_b),
                    changed=self._score_text(run_a) != self._score_text(run_b),
                )
            )
            rows.append(
                VersionDiffRow(
                    label="판단",
                    before=self._decision_text(run_a),
                    after=self._decision_text(run_b),
                    changed=self._decision_text(run_a) != self._decision_text(run_b),
                )
            )
            return rows

    # ==================================================================
    # 감사 로그 / 이벤트
    # ==================================================================
    def list_audit_logs(self, limit: int = 200) -> list[AuditLogDTO]:
        with self.db.transaction() as s:
            return [
                AuditLogDTO(
                    id=a.id,
                    actor_id=a.actor_id,
                    action=a.action,
                    object_type=a.object_type,
                    object_id=a.object_id,
                    created_at=a.created_at,
                )
                for a in Repository(s).list_audit_logs(limit)
            ]

    def list_events(self, limit: int = 200) -> list[tuple[str, str | None, datetime]]:
        with self.db.transaction() as s:
            return [
                (e.event_name, e.project_id, e.occurred_at)
                for e in Repository(s).list_events(limit)
            ]

    # ==================================================================
    # 내부 헬퍼
    # ==================================================================
    def _require_project(self, repo: Repository, project_id: str) -> Project:
        project = repo.get_project(project_id)
        if project is None:
            raise ServiceError("프로젝트를 찾을 수 없습니다.")
        if project.owner_id != self.actor_id:
            # 데스크톱 단일 사용자에서도 검사한다. 웹 이전 시 그대로 권한 검사가 된다.
            raise PermissionDenied("이 프로젝트에 접근할 권한이 없습니다.")
        return project

    @staticmethod
    def _idempotency_key(
        version: ProjectVersion,
        policy: EvaluationPolicy,
        evidence: Sequence[Evidence],
    ) -> str:
        material = json.dumps(
            {
                "version_id": version.id,
                "structured_idea": version.structured_idea,
                "policy": policy.to_dict(),
                "evidence": sorted(
                    [
                        {
                            "id": e.id,
                            "type": e.evidence_type,
                            "supports": sorted(e.supports or []),
                            "contradicts": sorted(e.contradicts or []),
                            "sample_size": e.sample_size,
                            "confidence_override": e.confidence_override,
                        }
                        for e in evidence
                    ],
                    key=lambda d: d["id"],
                ),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _evidence_item(row: Evidence) -> EvidenceItem:
        return EvidenceItem(
            id=row.id,
            evidence_type=EvidenceType(row.evidence_type),
            title=row.title,
            summary=row.summary,
            source_reference=row.source_reference,
            sample_size=row.sample_size,
            observed_at=row.observed_at,
            confidence_override=row.confidence_override,
            supports=tuple(DimensionCode(c) for c in (row.supports or [])),
            contradicts=tuple(DimensionCode(c) for c in (row.contradicts or [])),
        )

    @staticmethod
    def _evidence_dto(row: Evidence, policy: EvaluationPolicy) -> EvidenceDTO:
        effective = (
            row.confidence_override
            if row.confidence_override is not None
            else policy.confidence_of(EvidenceType(row.evidence_type))
        )
        return EvidenceDTO(
            id=row.id,
            project_id=row.project_id,
            evidence_type=row.evidence_type,
            title=row.title,
            summary=row.summary,
            source_reference=row.source_reference,
            sample_size=row.sample_size,
            observed_at=row.observed_at,
            confidence_override=row.confidence_override,
            supports=tuple(row.supports or []),
            contradicts=tuple(row.contradicts or []),
            effective_confidence=effective,
            created_at=row.created_at,
        )

    @staticmethod
    def _version_dto(v: ProjectVersion) -> VersionDTO:
        return VersionDTO(
            id=v.id,
            project_id=v.project_id,
            version_no=v.version_no,
            raw_input=dict(v.raw_input or {}),
            structured_idea=dict(v.structured_idea or {}),
            structure_approved=v.structure_approved,
            change_reason=v.change_reason,
            created_at=v.created_at,
        )

    @staticmethod
    def _run_dto(run: AnalysisRun, version_no: int) -> RunDTO:
        return RunDTO(
            id=run.id,
            project_id=run.project_id,
            version_id=run.project_version_id,
            version_no=version_no,
            status=run.status,
            engine=run.engine,
            engine_version=run.engine_version,
            policy_version=run.policy_version,
            schema_version=run.schema_version,
            model_name=run.model_name,
            result=dict(run.result) if run.result else None,
            error_code=run.error_code,
            error_detail=run.error_detail,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )

    def _project_dto(self, repo: Repository, project: Project) -> ProjectDTO:
        versions = repo.list_versions(project.id)
        latest_run = repo.latest_run(project.id)
        decision = None
        if latest_run and latest_run.result:
            decision = latest_run.result.get("pivot", {}).get("decision")
        return ProjectDTO(
            id=project.id,
            name=project.name,
            app_name=project.app_name,
            description=project.description,
            domain_code=DomainCode(project.domain_code),
            stage=ProjectStage(project.stage),
            status=ProjectStatus(project.status),
            latest_version_no=versions[0].version_no if versions else None,
            version_count=len(versions),
            evidence_count=len(repo.list_evidence(project.id)),
            latest_decision=decision,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    def _run_for_version(repo: Repository, version_id: str) -> AnalysisRun | None:
        return repo.latest_completed_run_for_version(version_id)

    @staticmethod
    def _score_text(run: AnalysisRun | None) -> str:
        if run is None or not run.result:
            return "분석 없음"
        return f"{run.result['diagnosis']['total_score']:.1f}"

    @staticmethod
    def _decision_text(run: AnalysisRun | None) -> str:
        if run is None or not run.result:
            return "분석 없음"
        return run.result["pivot"]["decision"]
