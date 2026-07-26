"""examath 도메인 모듈 (CLAUDE.md §5, TECHSPEC §6.3).

어린이 대상 제품이므로 개인정보 최소화와 비처벌적 표현이 규칙에 포함된다.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Sequence

from ..enums import DimensionCode, DomainCode, PivotDecision, Severity, WarningCode
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
from ..textsignals import has_signal, has_text, normalize


class MathErrorType(StrEnum):
    """CLAUDE.md §5.5 / TECHSPEC §6.3 오류 분류."""

    SUBTRACTION_MEANING = "SUBTRACTION_MEANING"
    COUNTING_BACK = "COUNTING_BACK"
    NUMBER_COMPARISON = "NUMBER_COMPARISON"
    MAKE_TEN = "MAKE_TEN"
    PLACE_VALUE = "PLACE_VALUE"
    REGROUPING_CONCEPT = "REGROUPING_CONCEPT"
    PROCEDURE_ONLY = "PROCEDURE_ONLY"
    MATH_ANXIETY_AVOIDANCE = "MATH_ANXIETY_AVOIDANCE"
    CONCRETE_TO_SYMBOL_TRANSFER = "CONCRETE_TO_SYMBOL_TRANSFER"
    UNKNOWN = "UNKNOWN"


MATH_ERROR_LABELS: dict[MathErrorType, str] = {
    MathErrorType.SUBTRACTION_MEANING: "뺄셈의 의미를 모름",
    MathErrorType.COUNTING_BACK: "뒤로 세기가 어려움",
    MathErrorType.NUMBER_COMPARISON: "수의 크기를 비교하지 못함",
    MathErrorType.MAKE_TEN: "10을 만들고 쪼개지 못함",
    MathErrorType.PLACE_VALUE: "십의 자리와 일의 자리를 혼동함",
    MathErrorType.REGROUPING_CONCEPT: "받아내림의 의미를 이해하지 못함",
    MathErrorType.PROCEDURE_ONLY: "세로셈 절차만 외움",
    MathErrorType.MATH_ANXIETY_AVOIDANCE: "틀릴까 봐 시도하지 않음",
    MathErrorType.CONCRETE_TO_SYMBOL_TRANSFER: "구체물에서 숫자 문제로 전이하지 못함",
    MathErrorType.UNKNOWN: "분류 불가",
}

BROAD_CHILD_PHRASES: tuple[str, ...] = (
    "수학을 배우는 아이",
    "수학을 배우는 어린이",
    "수학을 처음 배우는",
    "꼬맹이",
    "아이들 전체",
    "모든 아이",
)

GRADE_SIGNALS: tuple[str, ...] = (
    "1학년", "2학년", "3학년", "4학년", "5학년", "6학년",
    "초1", "초2", "초3", "7세", "8세", "9세", "만 7", "만 8",
)

DIFFICULTY_TOPIC_SIGNALS: tuple[str, ...] = (
    "받아내림", "받아 내림", "받아올림", "두 자리", "한 자리",
    "10 만들기", "십의 자리", "일의 자리", "가르기", "모으기",
)

ACCURACY_ONLY_SIGNALS: tuple[str, ...] = ("정답률", "점수로 평가", "등수", "석차", "정답 개수")
COMPETITION_SIGNALS: tuple[str, ...] = ("랭킹", "순위", "경쟁", "대결", "리더보드", "pvp")
MONETIZATION_RISK_SIGNALS: tuple[str, ...] = ("광고", "가챠", "뽑기", "루트박스")
CHILD_DATA_SIGNALS: tuple[str, ...] = (
    "실명", "이름", "생년월일", "주소", "전화번호", "학교명", "사진", "프로필 공개",
)

EXCLUDED_FEATURES: tuple[str, ...] = (
    "광고",
    "가챠",
    "실시간 랭킹",
    "공개 채팅",
    "과도한 경쟁 요소",
    "어린이에게 불필요한 회원가입 정보",
    "정답률만으로 아이를 평가하는 기능",
    "수학 전 범위를 한 번에 포함하는 기능",
)


class ExamathDomain:
    code = DomainCode.EXAMATH
    label = "examath (초등 뺄셈 받아내림)"

    # -- 필수 항목 ---------------------------------------------------------
    def required_fields(self) -> tuple[tuple[str, str, str], ...]:
        # 어린이가 쓰고 부모가 결제한다. 구매자를 비워 두면
        # 부모용 가치 제안이 통째로 빠져 MVP가 성립하지 않는다 (CLAUDE.md 5.3).
        return (
            (
                "payer",
                "구매자",
                "아이가 쓰고 부모가 결제합니다. 구매자를 비우면 부모용 가치가 빠집니다.",
            ),
        )

    # -- 경고 -------------------------------------------------------------
    def validate_input(self, idea: IdeaStructure) -> list[DiagnosisWarning]:
        w: list[DiagnosisWarning] = []
        target = normalize(idea.target_user)

        if any(p in target for p in BROAD_CHILD_PHRASES):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.BROAD_TARGET,
                    message=(
                        "'수학을 배우는 아이 전체'류 표현입니다. 학년과 구체적 난관이 없으면 "
                        "학습 설계도 검증도 불가능합니다."
                    ),
                    severity=Severity.CRITICAL,
                    field="target_user",
                    recommended_action=(
                        "'초등 2학년 중 두 자리 수 받아내림을 피하는 어린이'처럼 학년 + 난관으로 좁힙니다."
                    ),
                )
            )

        if not has_signal(idea.target_user, GRADE_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.NO_GRADE_SPECIFIED,
                    message="학년 또는 연령이 명시되지 않았습니다.",
                    severity=Severity.WARN,
                    field="target_user",
                    recommended_action="대상 학년을 하나로 지정합니다.",
                )
            )

        combined = f"{idea.target_user} {idea.problem_situation} {idea.core_action}"
        if not has_signal(combined, DIFFICULTY_TOPIC_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.NO_TRIGGER_SITUATION,
                    message=(
                        "구체적인 난관(받아내림, 10 만들기 등)이 지정되지 않았습니다. "
                        "수학 전 범위를 다루면 일반 연산 문제집 앱이 됩니다."
                    ),
                    severity=Severity.CRITICAL,
                    field="problem_situation",
                    recommended_action="MVP 범위를 '두 자리 - 한 자리 받아내림' 하나로 좁힙니다.",
                )
            )

        if not has_text(idea.payer, 2):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.NO_PAYER_DEFINED,
                    message=(
                        "사용자(어린이)와 구매자(부모)가 분리되지 않았습니다. "
                        "설치와 결제를 결정하는 주체가 다릅니다."
                    ),
                    severity=Severity.CRITICAL,
                    field="payer",
                    recommended_action="사용자=초등 2학년, 구매자=부모, 영향자=교사로 분리해 적습니다.",
                )
            )

        all_text = " ".join(
            filter(
                None,
                [
                    idea.problem_situation,
                    idea.core_action,
                    idea.expected_result,
                    idea.first_success,
                    idea.retention_reason,
                    idea.revenue_model,
                    idea.distribution_channel,
                ],
            )
        )
        if has_signal(all_text, ACCURACY_ONLY_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.ACCURACY_ONLY_EVALUATION,
                    message="정답률 중심 평가 표현이 있습니다. 아이를 정답률만으로 평가하면 안 됩니다.",
                    severity=Severity.WARN,
                    field="expected_result",
                    recommended_action="오류 유형별 진단 결과로 대체하고 낙인 표현을 제거합니다.",
                )
            )
        if has_signal(all_text, COMPETITION_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.EXCESSIVE_COMPETITION,
                    message="랭킹·경쟁 요소가 포함되어 있습니다. MVP 제외 항목입니다.",
                    severity=Severity.CRITICAL,
                    field="core_action",
                    recommended_action="경쟁 대신 개인 진도와 비처벌적 피드백으로 대체합니다.",
                )
            )
        if has_signal(all_text, MONETIZATION_RISK_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.CHILD_DATA_RISK,
                    message="광고·가챠는 어린이 대상 MVP 제외 항목입니다.",
                    severity=Severity.CRITICAL,
                    field="revenue_model",
                    recommended_action="부모 대상 구독 등 어린이에게 직접 노출되지 않는 모델로 바꿉니다.",
                )
            )
        if has_signal(all_text, CHILD_DATA_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.CHILD_DATA_RISK,
                    message="어린이 개인정보를 수집하는 표현이 있습니다. 최소 수집 원칙을 위반할 수 있습니다.",
                    severity=Severity.CRITICAL,
                    field="core_action",
                    recommended_action="익명 또는 가명 ID만 사용하고 공개 프로필을 만들지 않습니다.",
                )
            )
        return w

    # -- 언노운 -----------------------------------------------------------
    def enrich_unknowns(self, idea: IdeaStructure) -> list[str]:
        return [
            "아이가 실제로 막히는 오류 유형은 무엇인가",
            "구체물에서 성공한 아이가 숫자 문제로 전이되는가",
            "부모가 설치한 뒤 아이의 첫 세션이 완료되는가",
            "부모가 계속 쓰게 하는 이유는 무엇인가",
            "교사·학원강사가 어떤 상황에서 추천하는가",
            "실패 표현이 아이의 수학 불안을 키우지 않는가",
        ]

    # -- 점수 보정 ---------------------------------------------------------
    def score_adjustments(
        self, idea: IdeaStructure, warnings: Sequence[DiagnosisWarning]
    ) -> list[ScoreAdjustment]:
        codes = {w.code for w in warnings}
        adj: list[ScoreAdjustment] = []
        if WarningCode.NO_GRADE_SPECIFIED in codes:
            adj.append(
                ScoreAdjustment(DimensionCode.D03, -1, "학년 미지정으로 타깃이 넓음")
            )
        if WarningCode.CHILD_DATA_RISK in codes:
            adj.append(
                ScoreAdjustment(
                    DimensionCode.D10, -2, "어린이 개인정보·수익모델 위험으로 출시 난이도 상승"
                )
            )
        if WarningCode.EXCESSIVE_COMPETITION in codes:
            adj.append(
                ScoreAdjustment(
                    DimensionCode.D07, -1, "경쟁 기반 재방문은 어린이 도메인에서 허용되지 않음"
                )
            )
        return adj

    # -- 타깃 후보 ---------------------------------------------------------
    def seed_target_candidates(self, idea: IdeaStructure) -> list[TargetCandidate]:
        return [
            TargetCandidate(
                name="받아내림 회피형 초2",
                user=(
                    "초등학교 2학년 중 두 자리 수에서 한 자리 수를 빼는 받아내림을 피하거나, "
                    "손가락 세기에서 다음 단계로 넘어가지 못하는 어린이"
                ),
                payer="부모",
                influencer="초등교사, 학원강사, 돌봄교사",
                trigger_situation="받아내림이 있는 문제를 만나면 문제를 건너뛰거나 손을 놓을 때",
                problem="받아내림의 의미를 이해하지 못한 채 절차만 외워 실패가 반복되고 회피가 굳어진다.",
                current_alternative="학습지 반복, 부모의 직접 설명, 손가락 세기",
                why_promising=(
                    "난관이 하나로 특정되어 오류 유형 진단과 개입 설계가 가능하다.",
                    "부모가 이미 문제를 인지하고 있어 구매 동기가 있다.",
                ),
                risks=(
                    "구체물에서 성공해도 숫자 문제로 전이되지 않을 수 있다.",
                    "실패 표현이 수학 불안을 강화할 수 있다.",
                ),
                validation_questions=(
                    "아이가 어떤 문제에서 멈추는지 최근 사례를 보여줄 수 있는가",
                    "지금은 그 상황을 어떻게 넘기는가",
                    "아이가 스스로 시도하는 빈도는 어느 정도인가",
                ),
                recommended_experiment="구체물 조작 3분 미션 프로토타입으로 첫 세션 완료율과 오류 유형 분포 측정",
            ),
            TargetCandidate(
                name="설명 실패 좌절형 학부모",
                user=(
                    "아이에게 받아내림을 설명하다 매번 갈등이 생겨 "
                    "설명을 포기한 초등 2학년 학부모"
                ),
                payer="부모(본인)",
                influencer="담임교사",
                trigger_situation="숙제를 봐주다가 같은 부분에서 아이가 막히고 감정이 상할 때",
                problem="부모가 개념을 어떻게 쪼개서 보여줘야 하는지 모른다.",
                current_alternative="유튜브 강의 검색, 학습지 추가 구매, 학원 상담",
                why_promising=(
                    "구매자 본인의 고통이 명확해 지불 의사가 높다.",
                    "주간 요약이라는 구매자 가치가 자연스럽다.",
                ),
                risks=(
                    "부모가 원하는 결과(점수)와 아이 경험이 충돌할 수 있다.",
                    "부모용 기능이 커지면 아이 경험이 뒤로 밀린다.",
                ),
                validation_questions=(
                    "설명을 포기한 순간이 최근 언제였는가",
                    "그때 무엇을 대신 했는가",
                    "무엇을 보면 효과가 있다고 믿겠는가",
                ),
                recommended_experiment="부모용 주간 요약 목업으로 인터뷰 5건, 지불 의사 확인",
            ),
            TargetCandidate(
                name="개별 지도 시간 부족형 교사",
                user=(
                    "한 반에서 받아내림 단계에 멈춘 소수 학생을 개별 지도할 시간이 없는 초등 2학년 담임교사"
                ),
                payer="학교 또는 학부모",
                influencer="교육청, 학년부장",
                trigger_situation="수업 중 진도를 나가야 하는데 일부 학생이 받아내림에서 멈춰 있을 때",
                problem="누가 어떤 오류 유형인지 파악할 시간이 없다.",
                current_alternative="쉬는 시간 개별 지도, 보충 학습지 배부",
                why_promising=(
                    "오류 유형 분류가 교사에게 즉시 실용적이다.",
                    "영향자에서 추천 경로가 생긴다.",
                ),
                risks=(
                    "학교 도입 절차가 길고 개인정보 요구사항이 엄격하다.",
                    "교실용 기능이 MVP 범위를 넘길 수 있다.",
                ),
                validation_questions=(
                    "한 반에 해당 학생이 몇 명인가",
                    "지금 그 학생들을 어떻게 파악하는가",
                ),
                recommended_experiment="오류 유형 리포트 한 장 목업으로 교사 인터뷰 5건",
            ),
        ]

    # -- MVP 제약 ----------------------------------------------------------
    def constrain_mvp(self, plan: MvpPlan, idea: IdeaStructure) -> MvpPlan:
        from dataclasses import replace

        excluded = tuple(dict.fromkeys(plan.excluded_features + EXCLUDED_FEATURES))
        p0 = tuple(
            dict.fromkeys(
                plan.p0_features
                + (
                    "짧은 진단으로 오류 유형 분류",
                    "구체물 조작(쪼개기·옮기기·덜어내기)",
                    "10 만들기와 쪼개기",
                    "한 화면에 한 가지 판단",
                    "즉각적이고 비처벌적인 피드백",
                )
            )
        )
        p1 = tuple(
            dict.fromkeys(
                plan.p1_features
                + (
                    "구체물 → 그림 → 숫자 표현 전환",
                    "오답 유형 자동 분류 결과 저장",
                    "부모용 간단 주간 요약",
                )
            )
        )
        risks = tuple(
            dict.fromkeys(
                plan.risks
                + (
                    "일반 연산 문제집 앱으로 보일 수 있음",
                    "애니메이션은 많지만 개념 이해가 없을 수 있음",
                    "구체물에서 숫자로 전이되지 않을 수 있음",
                    "부모가 원하는 결과와 아이 경험의 충돌",
                    "실패 표현이 수학 불안을 강화할 수 있음",
                    "어린이 데이터 과수집 위험",
                )
            )
        )
        metrics = tuple(
            dict.fromkeys(plan.metrics + tuple(m.event_name for m in self.domain_metrics()))
        )
        return replace(
            plan,
            p0_features=p0,
            p1_features=p1,
            excluded_features=excluded,
            risks=risks,
            metrics=metrics,
        )

    # -- 지표 -------------------------------------------------------------
    def domain_metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition("child_session_start", "아이 세션 시작"),
            MetricDefinition("diagnostic_complete", "짧은 진단 완료"),
            MetricDefinition("manipulative_action_complete", "구체물 조작 완료"),
            MetricDefinition("make_ten_complete", "10 만들기 완료"),
            MetricDefinition("concrete_problem_complete", "구체물 문제 완료"),
            MetricDefinition("pictorial_problem_complete", "그림 문제 완료"),
            MetricDefinition("symbol_problem_complete", "숫자 문제 완료"),
            MetricDefinition("hint_used", "힌트 사용", required=False),
            MetricDefinition("retry_after_error", "오답 후 재시도"),
            MetricDefinition("error_type_detected", "오류 유형 감지"),
            MetricDefinition("parent_weekly_summary_view", "부모 주간 요약 조회"),
        ]

    # -- 피벗 규칙 ---------------------------------------------------------
    def domain_pivot_rules(self) -> list[PivotRule]:
        def child_safety_blocked(d: DiagnosisResult) -> bool:
            return d.has_warning(WarningCode.CHILD_DATA_RISK) or d.has_warning(
                WarningCode.EXCESSIVE_COMPETITION
            )

        return [
            PivotRule(
                code="EM_CHILD_SAFETY_VIOLATION",
                decision=PivotDecision.SOLUTION_PIVOT,
                predicate=child_safety_blocked,
                rationale=(
                    "어린이 보호 원칙을 위반하는 요소(광고·가챠·랭킹·개인정보 수집)가 포함되어 있습니다. "
                    "해당 요소를 제거하지 않으면 다른 판단을 진행할 수 없습니다."
                ),
                priority=1,
            )
        ]
