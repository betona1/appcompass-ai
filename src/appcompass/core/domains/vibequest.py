"""VibeQuest 도메인 모듈 (CLAUDE.md §4, TECHSPEC §6.2)."""

from __future__ import annotations

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

# CLAUDE.md §4.2 금지되는 타깃 표현
FORBIDDEN_TARGET_PHRASES: tuple[str, ...] = (
    "바이브코딩에 관심 있는 모든 사람",
    "바이브코딩에 관심있는 모든 사람",
    "ai에 관심 있는 사람",
    "ai에 관심있는 사람",
    "개발을 배우고 싶은 사람 전체",
    "개발을 배우고 싶은 모든 사람",
)

REAL_TASK_SIGNALS: tuple[str, ...] = (
    "프로젝트", "작업", "만들다가", "만들면서", "빌드", "배포", "에러",
    "오류", "터미널", "커밋", "api 호출", "실제 상황", "화면", "코드",
)

DIFFICULTY_SIGNALS: tuple[str, ...] = (
    "수준", "난이도", "진단", "레벨", "초보", "숙련", "단계별", "선행",
)

TRANSFER_SIGNALS: tuple[str, ...] = (
    "전이", "적용", "재개", "실제 작업", "다시 진행", "복귀", "해결",
)

# CLAUDE.md §4.5 제외 항목
EXCLUDED_FEATURES: tuple[str, ...] = (
    "기본 십자낱말",
    "유료 루트박스",
    "실시간 PvP",
    "실시간 전체 랭킹",
    "복잡한 길드",
    "검증되지 않은 생성형 AI 자유채점",
    "사용자의 프로젝트 코드를 무단 저장하는 기능",
)


class VibeQuestDomain:
    code = DomainCode.VIBEQUEST
    label = "VibeQuest (바이브코딩 용어 학습)"

    # -- 필수 항목 ---------------------------------------------------------
    def required_fields(self) -> tuple[tuple[str, str, str], ...]:
        # 실제 작업 상황이 없으면 일반 용어 퀴즈와 구분되지 않지만,
        # 그것은 경고(NO_REAL_TASK_CONTEXT)로 잡는다.
        # 승인 자체를 막을 만큼 기계적으로 판정할 수 있는 항목은 없다.
        return ()

    # -- 경고 -------------------------------------------------------------
    def validate_input(self, idea: IdeaStructure) -> list[DiagnosisWarning]:
        w: list[DiagnosisWarning] = []
        target = normalize(idea.target_user)

        for phrase in FORBIDDEN_TARGET_PHRASES:
            if phrase in target:
                w.append(
                    DiagnosisWarning(
                        code=WarningCode.BROAD_TARGET,
                        message=f"VibeQuest에서 금지된 타깃 표현입니다: '{phrase}'",
                        severity=Severity.CRITICAL,
                        field="target_user",
                        recommended_action=(
                            "'AI 코딩 도구로 처음 앱을 만들고 있지만 API·DB·Git·토큰 같은 용어를 "
                            "몰라 작업이 자주 중단되는 비개발자'처럼 상황 기반으로 다시 씁니다."
                        ),
                    )
                )
                break

        combined = f"{idea.problem_situation} {idea.core_action} {idea.expected_result}"
        if not has_signal(combined, REAL_TASK_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.NO_REAL_TASK_CONTEXT,
                    message=(
                        "실제 작업 상황이 드러나지 않습니다. 용어 정의만 다루면 일반 퀴즈 앱과 구분되지 않습니다."
                    ),
                    severity=Severity.CRITICAL,
                    field="problem_situation",
                    recommended_action="사용자가 어떤 프로젝트 단계에서 어떤 용어 때문에 멈추는지 적습니다.",
                )
            )

        if not has_signal(combined + " " + (idea.first_success or ""), DIFFICULTY_SIGNALS):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.NO_DIFFICULTY_SPLIT,
                    message="난이도 구분이 없습니다. 초보자와 현업 개발자의 난이도가 충돌합니다.",
                    severity=Severity.WARN,
                    field="core_action",
                    recommended_action="짧은 수준 진단으로 난이도를 나누는 구조를 명시합니다.",
                )
            )

        if not has_signal(
            f"{idea.expected_result} {idea.retention_reason or ''}", TRANSFER_SIGNALS
        ):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.NO_TRANSFER_METRIC,
                    message=(
                        "학습 전이 측정이 없습니다. 용어를 외웠는지가 아니라 "
                        "실제 작업을 다시 진행했는지를 측정해야 합니다."
                    ),
                    severity=Severity.WARN,
                    field="expected_result",
                    recommended_action="'학습 후 막혔던 작업을 재개했는가'를 지표로 추가합니다.",
                )
            )

        if has_signal(f"{idea.core_action} {idea.expected_result}", ("ai가 채점", "자유채점", "생성형 채점")):
            w.append(
                DiagnosisWarning(
                    code=WarningCode.UNSUPPORTED_CLAIM,
                    message="검증되지 않은 생성형 AI 자유채점은 MVP 제외 항목입니다.",
                    severity=Severity.WARN,
                    field="core_action",
                    recommended_action="키워드 채점 등 검증 가능한 방식으로 대체합니다.",
                )
            )
        return w

    # -- 언노운 -----------------------------------------------------------
    def enrich_unknowns(self, idea: IdeaStructure) -> list[str]:
        return [
            "사용자가 실제로 막히는 용어는 무엇인가",
            "막히는 프로젝트 단계는 어디인가",
            "초보자의 선행지식 수준은 어디까지인가",
            "학습 후 실제 작업을 재개했는가",
            "재방문 이유는 무엇인가",
            "유료 전환 이유는 무엇인가",
        ]

    # -- 점수 보정 ---------------------------------------------------------
    def score_adjustments(
        self, idea: IdeaStructure, warnings: Sequence[DiagnosisWarning]
    ) -> list[ScoreAdjustment]:
        codes = {w.code for w in warnings}
        adj: list[ScoreAdjustment] = []
        if WarningCode.NO_REAL_TASK_CONTEXT in codes:
            adj.append(
                ScoreAdjustment(
                    DimensionCode.D08,
                    -2,
                    "실제 작업 상황이 없어 일반 용어 퀴즈와 차별되지 않음",
                )
            )
        if WarningCode.NO_TRANSFER_METRIC in codes:
            adj.append(
                ScoreAdjustment(
                    DimensionCode.D05, -1, "학습 전이 측정이 없어 가치 검증이 불가"
                )
            )
        if WarningCode.NO_DIFFICULTY_SPLIT in codes:
            adj.append(
                ScoreAdjustment(
                    DimensionCode.D06, -1, "난이도 진단이 없어 첫 성공 경험이 흔들림"
                )
            )
        return adj

    # -- 타깃 후보 ---------------------------------------------------------
    def seed_target_candidates(self, idea: IdeaStructure) -> list[TargetCandidate]:
        return [
            TargetCandidate(
                name="첫 프로젝트 중단형 비개발자",
                user=(
                    "AI 코딩 도구로 처음 앱이나 자동화 프로그램을 만들고 있지만, "
                    "API·DB·Git·토큰 같은 용어를 이해하지 못해 작업이 자주 중단되는 비개발자"
                ),
                payer="본인",
                influencer="같은 도구를 쓰는 커뮤니티 동료",
                trigger_situation="AI가 준 답변에 모르는 용어가 나와 다음 단계를 못 정할 때",
                problem="용어를 몰라 AI에게 무엇을 다시 물어야 할지 결정하지 못하고 작업이 멈춘다.",
                current_alternative="검색, AI에게 되묻기, 유튜브 강의 몰아보기",
                why_promising=(
                    "중단 시점이 명확해 학습 트리거를 특정할 수 있다.",
                    "학습 성공 여부를 '작업 재개'로 측정할 수 있다.",
                ),
                risks=(
                    "선행지식 편차가 커서 난이도 설계가 어렵다.",
                    "급할 때는 학습보다 AI에게 다시 묻는 쪽을 택할 수 있다.",
                ),
                validation_questions=(
                    "최근 일주일에 용어 때문에 멈춘 순간이 몇 번 있었는가",
                    "그때 실제로 무엇을 했는가",
                    "멈춘 작업을 결국 끝냈는가",
                ),
                recommended_experiment="막힌 용어 3개를 3분 미션으로 만들어 작업 재개율을 측정",
            ),
            TargetCandidate(
                name="배포·운영 단계 진입 실패형 초보 개발자",
                user=(
                    "AI 코딩 도구로 로컬에서 동작하는 앱은 만들었지만, "
                    "배포·환경변수·인증 용어에서 막혀 출시로 넘어가지 못하는 초보 개발자"
                ),
                payer="본인",
                influencer="사이드프로젝트 커뮤니티",
                trigger_situation="로컬에서는 되는데 배포 단계에서 오류 메시지의 용어를 이해하지 못할 때",
                problem="오류 메시지의 용어를 몰라 원인 범위를 좁히지 못한다.",
                current_alternative="오류 메시지 전문을 AI에 붙여넣고 시도-실패 반복",
                why_promising=(
                    "실패 지점이 좁고 반복적이라 문제 유형이 정형화된다.",
                    "출시라는 명확한 목표가 있어 지불 의사가 상대적으로 높다.",
                ),
                risks=(
                    "이미 검색 능력이 있어 학습 앱 없이 해결할 수 있다.",
                    "1차 타깃(비개발자)과 난이도가 충돌한다.",
                ),
                validation_questions=(
                    "배포 시도에서 며칠을 소모했는가",
                    "어떤 오류 용어에서 가장 오래 멈췄는가",
                ),
                recommended_experiment="배포 오류 용어 지도를 랜딩 페이지로 만들어 신청률 측정",
            ),
            TargetCandidate(
                name="비개발 직군 사내 도입 담당자",
                user=(
                    "업무 자동화를 위해 AI 코딩 도구를 도입했지만, "
                    "팀원들이 기본 용어를 몰라 도입이 정체된 비개발 직군 담당자"
                ),
                payer="회사(팀 예산)",
                influencer="팀장, 교육 담당자",
                trigger_situation="도구를 배포했는데 팀원 질문이 전부 기초 용어에 몰릴 때",
                problem="개별 질문에 반복 응대하느라 담당자의 시간이 소모된다.",
                current_alternative="사내 위키 정리, 1:1 설명",
                why_promising=(
                    "구매자와 사용자가 분리되어 B2B 지불 근거가 생긴다.",
                    "진도 리포트라는 명확한 구매자 가치가 있다.",
                ),
                risks=(
                    "MVP 범위를 벗어난 관리 기능이 필요해질 수 있다.",
                    "영업 사이클이 길어 초기 검증 속도가 느리다.",
                ),
                validation_questions=(
                    "반복 질문에 주당 몇 시간을 쓰는가",
                    "교육 예산 결정권은 누구에게 있는가",
                ),
                recommended_experiment="팀 진도 요약 화면 목업으로 담당자 인터뷰 5건",
            ),
        ]

    # -- MVP 제약 ----------------------------------------------------------
    def constrain_mvp(self, plan: MvpPlan, idea: IdeaStructure) -> MvpPlan:
        from dataclasses import replace

        excluded = tuple(dict.fromkeys(plan.excluded_features + EXCLUDED_FEATURES))
        risks = tuple(
            dict.fromkeys(
                plan.risks
                + (
                    "일반적인 퀴즈 앱으로 보일 수 있음",
                    "용어 암기만 되고 실제 작업에 전이되지 않을 수 있음",
                    "초보자와 현업 개발자의 난이도 충돌",
                    "AI가 만든 부정확한 문제",
                    "게임 요소가 많아 학습 흐름이 끊길 수 있음",
                )
            )
        )
        metrics = tuple(
            dict.fromkeys(plan.metrics + tuple(m.event_name for m in self.domain_metrics()))
        )
        return replace(plan, excluded_features=excluded, risks=risks, metrics=metrics)

    # -- 지표 -------------------------------------------------------------
    def domain_metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition("diagnostic_complete", "수준 진단 완료"),
            MetricDefinition("first_mission_complete", "첫 3분 미션 완료"),
            MetricDefinition("scenario_question_complete", "실제 상황형 문제 완료"),
            MetricDefinition("wrong_concept_review_complete", "틀린 개념 복습 완료"),
            MetricDefinition("project_stage_selected", "프로젝트 단계 선택"),
            MetricDefinition("concept_to_task_transfer", "학습 후 실제 작업 재개"),
            MetricDefinition("daily_mission_return", "다음 날 미션 재방문"),
        ]

    # -- 피벗 규칙 ---------------------------------------------------------
    def domain_pivot_rules(self) -> list[PivotRule]:
        def no_real_task(d: DiagnosisResult) -> bool:
            # 일반 용어는 다루지만 실제 상황 문제가 없는 경우
            return d.has_warning(WarningCode.NO_REAL_TASK_CONTEXT) and (
                d.dimension(DimensionCode.D01).raw_score >= 3
            )

        return [
            PivotRule(
                code="VQ_NO_REAL_TASK_CONTEXT",
                decision=PivotDecision.SOLUTION_PIVOT,
                predicate=no_real_task,
                rationale=(
                    "문제 인식은 있으나 실제 작업 상황형 문제가 없습니다. "
                    "일반 용어 퀴즈로는 차별성이 생기지 않으므로 해결책 형태를 바꿔야 합니다."
                ),
                priority=10,
            )
        ]
