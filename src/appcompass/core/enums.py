"""프로젝트 전역 Enum.

CLAUDE.md §9 "Enum과 상수를 문자열로 흩뿌리지 않음" 규칙에 따라
모든 상태값은 이 모듈에서만 정의한다.
"""

from __future__ import annotations

from enum import StrEnum


class DomainCode(StrEnum):
    """도메인 모듈 코드."""

    GENERIC = "GENERIC"
    VIBEQUEST = "VIBEQUEST"
    EXAMATH = "EXAMATH"


class ProjectStage(StrEnum):
    """TECHSPEC F-010 프로젝트 단계."""

    IDEA = "IDEA"
    RESEARCH = "RESEARCH"
    PROTOTYPE = "PROTOTYPE"
    MVP = "MVP"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AnalysisStatus(StrEnum):
    """TECHSPEC 7.3 AnalysisRun 상태."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED_SCHEMA = "FAILED_SCHEMA"
    FAILED_PROVIDER = "FAILED_PROVIDER"
    FAILED_INTERNAL = "FAILED_INTERNAL"
    CANCELLED = "CANCELLED"


class PivotDecision(StrEnum):
    """CLAUDE.md §6 공통 진단 결과 상태."""

    KEEP = "KEEP"
    REFINE = "REFINE"
    TARGET_PIVOT = "TARGET_PIVOT"
    PROBLEM_PIVOT = "PROBLEM_PIVOT"
    SOLUTION_PIVOT = "SOLUTION_PIVOT"
    CHANNEL_PIVOT = "CHANNEL_PIVOT"
    REVENUE_PIVOT = "REVENUE_PIVOT"
    RETENTION_REDESIGN = "RETENTION_REDESIGN"
    HOLD = "HOLD"


class EvidenceType(StrEnum):
    """TECHSPEC F-040 근거 유형."""

    FOUNDER_ASSUMPTION = "FOUNDER_ASSUMPTION"
    DESK_RESEARCH = "DESK_RESEARCH"
    USER_INTERVIEW = "USER_INTERVIEW"
    PROTOTYPE_TEST = "PROTOTYPE_TEST"
    BEHAVIOR_DATA = "BEHAVIOR_DATA"
    EXPERT_REVIEW = "EXPERT_REVIEW"


class DimensionCode(StrEnum):
    """TECHSPEC F-030 평가 항목."""

    D01 = "D01"  # 문제 구체성
    D02 = "D02"  # 문제 강도·빈도
    D03 = "D03"  # 타깃 명확성
    D04 = "D04"  # 사용자·구매자 구분
    D05 = "D05"  # 가치 제안
    D06 = "D06"  # 첫 성공 경험
    D07 = "D07"  # 반복 사용 이유
    D08 = "D08"  # 차별성
    D09 = "D09"  # 유입 가능성
    D10 = "D10"  # 구현 가능성


DIMENSION_LABELS: dict[DimensionCode, str] = {
    DimensionCode.D01: "문제 구체성",
    DimensionCode.D02: "문제 강도·빈도",
    DimensionCode.D03: "타깃 명확성",
    DimensionCode.D04: "사용자·구매자 구분",
    DimensionCode.D05: "가치 제안",
    DimensionCode.D06: "첫 성공 경험",
    DimensionCode.D07: "반복 사용 이유",
    DimensionCode.D08: "차별성",
    DimensionCode.D09: "유입 가능성",
    DimensionCode.D10: "구현 가능성",
}


class WarningCode(StrEnum):
    """TECHSPEC §10.3 경고 코드."""

    BROAD_TARGET = "BROAD_TARGET"
    NO_TRIGGER_SITUATION = "NO_TRIGGER_SITUATION"
    NO_CURRENT_ALTERNATIVE = "NO_CURRENT_ALTERNATIVE"
    NO_PAYER_DEFINED = "NO_PAYER_DEFINED"
    NO_FIRST_SUCCESS = "NO_FIRST_SUCCESS"
    NO_RETENTION_REASON = "NO_RETENTION_REASON"
    NO_MEASURABLE_RESULT = "NO_MEASURABLE_RESULT"
    FEATURE_FIRST_IDEA = "FEATURE_FIRST_IDEA"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    LOW_EVIDENCE = "LOW_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    CHILD_DATA_RISK = "CHILD_DATA_RISK"
    # 도메인 모듈 전용
    NO_REAL_TASK_CONTEXT = "NO_REAL_TASK_CONTEXT"
    NO_DIFFICULTY_SPLIT = "NO_DIFFICULTY_SPLIT"
    NO_TRANSFER_METRIC = "NO_TRANSFER_METRIC"
    NO_GRADE_SPECIFIED = "NO_GRADE_SPECIFIED"
    ACCURACY_ONLY_EVALUATION = "ACCURACY_ONLY_EVALUATION"
    EXCESSIVE_COMPETITION = "EXCESSIVE_COMPETITION"


class Severity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class ImplementationStatus(StrEnum):
    """MVP 기능의 구현 상태.

    '이미 만든 것'과 '아직 안 만든 것'을 구분해야 개선 명세를 만들 수 있다.
    만들지도 않은 기능을 개선하라고 할 수는 없다.
    """

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    DROPPED = "DROPPED"


IMPLEMENTATION_STATUS_LABELS: dict[ImplementationStatus, str] = {
    ImplementationStatus.NOT_STARTED: "미구현",
    ImplementationStatus.IN_PROGRESS: "구현 중",
    ImplementationStatus.DONE: "구현됨",
    ImplementationStatus.DROPPED: "제외함",
}


class HypothesisStatus(StrEnum):
    """가설 검증 결과. 근거에서 규칙으로 도출한다."""

    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT = "INSUFFICIENT"


HYPOTHESIS_STATUS_LABELS: dict[HypothesisStatus, str] = {
    HypothesisStatus.SUPPORTED: "지지됨",
    HypothesisStatus.REFUTED: "반박됨",
    HypothesisStatus.CONFLICTED: "상충",
    HypothesisStatus.INSUFFICIENT: "근거 부족",
}


class ApprovalStatus(StrEnum):
    """피벗 판단에 대한 사람의 결정 (TECHSPEC F-090).

    시스템은 판단을 제안할 뿐 적용하지 않는다.
    사람이 승인하거나 거절해야 하고, 그 기록이 남아야 한다.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"  # 새 분석이 나와 이 판단은 더 이상 최신이 아님


APPROVAL_STATUS_LABELS: dict[ApprovalStatus, str] = {
    ApprovalStatus.PENDING: "검토 대기",
    ApprovalStatus.APPROVED: "승인함",
    ApprovalStatus.REJECTED: "거절함",
    ApprovalStatus.SUPERSEDED: "지난 판단",
}


class ReportFormat(StrEnum):
    MARKDOWN = "MARKDOWN"
    HTML = "HTML"
    TECHSPEC = "TECHSPEC"  # 구현용 기술 명세 (Markdown)
    IMPROVEMENT = "IMPROVEMENT"  # 이미 만든 MVP의 개선 명세 (Markdown)
    XLSX = "XLSX"  # 엑셀. 텍스트가 아니라 내보낼 때 생성한다.


#: 텍스트라서 분석 시점에 생성해 DB에 보관하는 형식.
#: IMPROVEMENT는 구현 상태가 바뀔 때마다 달라지므로 내보낼 때 생성한다.
STORED_REPORT_FORMATS: tuple[ReportFormat, ...] = (
    ReportFormat.MARKDOWN,
    ReportFormat.HTML,
    ReportFormat.TECHSPEC,
)

REPORT_FORMAT_LABELS: dict[ReportFormat, str] = {
    ReportFormat.MARKDOWN: "진단 보고서 (Markdown)",
    ReportFormat.HTML: "진단 보고서 (HTML)",
    ReportFormat.TECHSPEC: "기술 명세 TECHSPEC (Markdown)",
    ReportFormat.IMPROVEMENT: "개선 명세 — 이미 만든 MVP용 (Markdown)",
    ReportFormat.XLSX: "작업용 엑셀 (.xlsx)",
}

REPORT_FORMAT_SUFFIX: dict[ReportFormat, str] = {
    ReportFormat.MARKDOWN: ".md",
    ReportFormat.HTML: ".html",
    ReportFormat.TECHSPEC: ".TECHSPEC.md",
    ReportFormat.IMPROVEMENT: ".IMPROVEMENT.md",
    ReportFormat.XLSX: ".xlsx",
}


class AuditAction(StrEnum):
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    PROJECT_ARCHIVED = "PROJECT_ARCHIVED"
    PROJECT_DELETED = "PROJECT_DELETED"
    VERSION_CREATED = "VERSION_CREATED"
    STRUCTURE_APPROVED = "STRUCTURE_APPROVED"
    ANALYSIS_REQUESTED = "ANALYSIS_REQUESTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    EVIDENCE_DELETED = "EVIDENCE_DELETED"
    EXPERIMENT_CREATED = "EXPERIMENT_CREATED"
    EXPERIMENT_DELETED = "EXPERIMENT_DELETED"
    PIVOT_APPROVED = "PIVOT_APPROVED"
    PIVOT_REJECTED = "PIVOT_REJECTED"
    POLICY_UPDATED = "POLICY_UPDATED"
    REPORT_EXPORTED = "REPORT_EXPORTED"
    # LLM은 초안만 만든다. 요청과 채택을 따로 남겨야
    # "AI가 제안했지만 사람이 안 썼다"를 나중에 구분할 수 있다.
    LLM_DRAFT_REQUESTED = "LLM_DRAFT_REQUESTED"
    LLM_DRAFT_APPLIED = "LLM_DRAFT_APPLIED"
