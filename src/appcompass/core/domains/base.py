"""DomainModule 인터페이스 (TECHSPEC §6.1).

도메인 모듈은 상태를 갖지 않는다. 모든 메서드는 입력만 보고 결과를 만든다.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..enums import DomainCode
from ..enums import DimensionCode, EvidenceType
from ..models import (
    DiagnosisResult,
    DiagnosisWarning,
    EvidenceExample,
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

    def required_fields(self) -> tuple[tuple[str, str, str], ...]:
        """공통 필수 항목에 더할 도메인 전용 필수 항목.

        (필드명, 화면 라벨, 왜 필수인지) 형태.
        승인 자체를 막는 항목이므로 꼭 필요한 것만 넣는다.
        """

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

    def evidence_examples(self) -> list[EvidenceExample]:
        """근거 입력 양식을 어떻게 채우는지 보여주는 예시.

        근거 자체가 아니다. 사용자가 실제 관찰로 바꿔 써야 한다.
        """


class GenericDomain:
    """도메인이 지정되지 않은 프로젝트용 기본 모듈. 공통 규칙만 적용한다."""

    code = DomainCode.GENERIC
    label = "공통 (도메인 없음)"

    def required_fields(self) -> tuple[tuple[str, str, str], ...]:
        return ()

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

    def evidence_examples(self) -> list[EvidenceExample]:
        return [
            EvidenceExample(
                label="① 사용자 인터뷰 — 이 한 건으로 HOLD가 풀립니다",
                evidence_type=EvidenceType.USER_INTERVIEW,
                title="타깃 사용자 5명 인터뷰 (연-월)",
                summary=(
                    "5명 중 4명이 '문제 상황을 최근 한 달에 2~3회 겪었다'고 진술. "
                    "현재 대처는 전원 수기 처리이며, 2명은 도중에 포기했다고 답함. "
                    "스스로 다시 시도한 사례는 1건.\n"
                    "※ 해석이 아니라 관찰된 사실로 적으세요. "
                    "'힘들어한다'(X) / '5명 중 4명이 ~라고 진술했다'(O)"
                ),
                source_reference="interviews/2026-07-users.md",
                sample_size=5,
                supports=(
                    DimensionCode.D01,
                    DimensionCode.D02,
                    DimensionCode.D03,
                    DimensionCode.D04,
                    DimensionCode.D05,
                ),
                note="가중치 합계 50짜리 항목을 지지해 전체 신뢰도가 0.35에 도달합니다.",
            ),
            EvidenceExample(
                label="② 프로토타입 테스트 — 첫 성공 경험 검증",
                evidence_type=EvidenceType.PROTOTYPE_TEST,
                title="클릭더미 첫 세션 테스트 6명",
                summary=(
                    "6명 중 5명이 첫 핵심 행동을 스스로 완료(완료율 83%). "
                    "평균 소요 4분 20초로 목표 3분을 넘김. "
                    "2명은 다음 단계로 넘어가지 못해 이탈."
                ),
                sample_size=6,
                supports=(
                    DimensionCode.D05,
                    DimensionCode.D06,
                    DimensionCode.D10,
                ),
                contradicts=(DimensionCode.D08,),
                note="불리한 결과는 '반박 항목'에 넣습니다. 유리한 것만 넣으면 진단이 무의미합니다.",
            ),
            EvidenceExample(
                label="③ 데스크 리서치 — 차별성",
                evidence_type=EvidenceType.DESK_RESEARCH,
                title="경쟁·대체재 5종 기능 비교",
                summary=(
                    "상위 5종 확인. 4종이 같은 접근이고 우리가 핵심으로 잡은 방식은 1종뿐. "
                    "그 1종도 핵심 단계가 빠져 있음."
                ),
                source_reference="research/2026-07-competitors.md",
                supports=(DimensionCode.D08, DimensionCode.D09),
                note="데스크 리서치는 기본 신뢰도 0.35라 인터뷰보다 약합니다.",
            ),
        ]
