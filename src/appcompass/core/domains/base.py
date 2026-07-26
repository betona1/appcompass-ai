"""DomainModule 인터페이스 (TECHSPEC §6.1).

도메인 모듈은 상태를 갖지 않는다. 모든 메서드는 입력만 보고 결과를 만든다.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..enums import DomainCode
from ..models import (
    DiagnosisResult,
    DiagnosisWarning,
    IdeaStructure,
    MetricDefinition,
    MvpPlan,
    ScoreAdjustment,
    TargetCandidate,
)
from ..pivot import PivotRule


@runtime_checkable
class DomainModule(Protocol):
    code: DomainCode
    label: str

    def validate_input(self, idea: IdeaStructure) -> list[DiagnosisWarning]:
        """도메인 전용 경고."""

    def enrich_unknowns(self, idea: IdeaStructure) -> list[str]:
        """도메인이 반드시 확인해야 할 언노운."""

    def score_adjustments(
        self, idea: IdeaStructure, warnings: Sequence[DiagnosisWarning]
    ) -> list[ScoreAdjustment]:
        """도메인 지식에 따른 점수 보정. 이유 없는 보정은 만들지 않는다."""

    def seed_target_candidates(self, idea: IdeaStructure) -> list[TargetCandidate]:
        """LLM 없이 제안 가능한 타깃 후보. 도메인 문서에 근거가 있는 후보만 넣는다."""

    def constrain_mvp(self, plan: MvpPlan, idea: IdeaStructure) -> MvpPlan:
        """도메인 MVP 제외 규칙을 적용한다."""

    def domain_metrics(self) -> list[MetricDefinition]:
        """도메인 필수 측정 이벤트."""

    def domain_pivot_rules(self) -> list[PivotRule]:
        """도메인 전용 피벗 규칙."""


class GenericDomain:
    """도메인이 지정되지 않은 프로젝트용 기본 모듈. 공통 규칙만 적용한다."""

    code = DomainCode.GENERIC
    label = "공통 (도메인 없음)"

    def validate_input(self, idea: IdeaStructure) -> list[DiagnosisWarning]:
        return []

    def enrich_unknowns(self, idea: IdeaStructure) -> list[str]:
        return []

    def score_adjustments(
        self, idea: IdeaStructure, warnings: Sequence[DiagnosisWarning]
    ) -> list[ScoreAdjustment]:
        return []

    def seed_target_candidates(self, idea: IdeaStructure) -> list[TargetCandidate]:
        return []

    def constrain_mvp(self, plan: MvpPlan, idea: IdeaStructure) -> MvpPlan:
        return plan

    def domain_metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition("activation_complete", "첫 성공 경험 완료"),
            MetricDefinition("core_action_complete", "핵심 행동 완료"),
            MetricDefinition("day1_return", "다음 날 재방문"),
        ]

    def domain_pivot_rules(self) -> list[PivotRule]:
        return []
