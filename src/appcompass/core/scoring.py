"""점수 엔진.

CLAUDE.md §9 "점수 계산은 순수 함수로 구현", §7.3 "점수와 피벗 판정은 재현 가능해야 함".
TECHSPEC §9.2 "점수 계산: LLM X / 규칙 엔진 O".

각 항목은 0~5점이며, 어떤 조건으로 몇 점이 붙었는지를 reason에 남긴다.
사용자에게 점수보다 이유를 먼저 보여주기 위해서다 (CLAUDE.md §9 Frontend).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .enums import DimensionCode, DIMENSION_LABELS, EvidenceType, WarningCode
from .models import (
    DiagnosisWarning,
    DimensionScore,
    EvidenceItem,
    IdeaStructure,
    ScoreAdjustment,
)
from .policy import EvaluationPolicy
from .textsignals import (
    CHANNEL_SIGNALS,
    FREQUENCY_SIGNALS,
    MEASURABLE_SIGNALS,
    PAIN_SIGNALS,
    RETENTION_SIGNALS,
    has_signal,
    has_text,
    normalize,
    target_specificity_score,
)

MAX_RAW_SCORE = 5


@dataclass(slots=True)
class _Trace:
    """점수 산정 근거 누적기."""

    points: int = 0
    notes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []

    def add(self, condition: bool, delta: int, note: str) -> None:
        if condition:
            self.points += delta
            self.notes.append(f"+{delta} {note}")

    def cap(self, ceiling: int, note: str) -> None:
        if self.points > ceiling:
            self.points = ceiling
            self.notes.append(f"상한 {ceiling} 적용: {note}")

    def zero(self, note: str) -> None:
        self.points = 0
        self.notes.clear()
        self.notes.append(f"0점: {note}")

    def result(self) -> tuple[int, str]:
        score = max(0, min(MAX_RAW_SCORE, self.points))
        return score, " / ".join(self.notes) if self.notes else "판단 근거 없음"


def _evidence_for(
    evidence: Sequence[EvidenceItem], code: DimensionCode
) -> list[EvidenceItem]:
    return [e for e in evidence if code in e.supports]


def _has_strong_evidence(
    evidence: Sequence[EvidenceItem],
    code: DimensionCode,
    policy: EvaluationPolicy,
    minimum: float = 0.50,
) -> bool:
    for e in _evidence_for(evidence, code):
        conf = e.confidence_override
        if conf is None:
            conf = policy.confidence_of(e.evidence_type)
        if conf >= minimum:
            return True
    return False


# ---------------------------------------------------------------------------
# 항목별 채점기
# ---------------------------------------------------------------------------


def _score_d01(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D01 문제 구체성."""
    t = _Trace()
    if not has_text(idea.problem_situation, 5):
        t.zero("문제 상황이 비어 있음")
        return t.result()
    text = idea.problem_situation
    t.add(True, 1, "문제 상황 서술 있음")
    t.add(len(text.strip()) >= 30, 1, "문제 서술이 30자 이상")
    t.add(len(text.strip()) >= 80, 1, "문제 서술이 80자 이상으로 구체적")
    t.add(has_text(idea.current_solution_problem, 5), 1, "현재 방법의 한계가 서술됨")
    t.add(has_signal(text, PAIN_SIGNALS), 1, "고통 신호(중단·실패·불안 등) 포함")
    if WarningCode.NO_TRIGGER_SITUATION in warns:
        t.cap(3, "문제 발생 트리거가 불명확")
    return t.result()


def _score_d02(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D02 문제 강도·빈도."""
    t = _Trace()
    if not has_text(idea.problem_situation, 5):
        t.zero("문제 상황이 비어 있어 강도를 판단할 수 없음")
        return t.result()
    t.add(True, 1, "문제 서술 있음")
    t.add(has_signal(idea.problem_situation, FREQUENCY_SIGNALS), 1, "발생 빈도 신호 포함")
    t.add(has_signal(idea.problem_situation, PAIN_SIGNALS), 1, "심각도 신호 포함")
    t.add(bool(_evidence_for(ev, DimensionCode.D02)), 1, "문제 강도를 지지하는 근거 등록됨")
    t.add(
        _has_strong_evidence(ev, DimensionCode.D02, policy),
        1,
        "인터뷰 이상 수준의 근거 존재",
    )
    return t.result()


def _score_d03(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D03 타깃 명확성."""
    t = _Trace()
    if not has_text(idea.target_user, 2):
        t.zero("타깃이 비어 있음")
        return t.result()
    spec = target_specificity_score(idea.target_user)
    t.add(True, 1, "타깃 서술 있음")
    t.add(spec >= 2, 1, f"구체성 신호 {spec}개")
    t.add(spec >= 3, 1, "상황·행동·중단 원인이 함께 드러남")
    t.add(has_text(idea.current_solution, 2), 1, "현재 행동(대체 방법)이 정의됨")
    t.add(WarningCode.BROAD_TARGET not in warns, 1, "넓은 타깃 표현 없음")
    if WarningCode.BROAD_TARGET in warns:
        t.cap(2, "넓은 타깃 경고 발생")
    return t.result()


def _score_d04(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D04 사용자·구매자 구분."""
    t = _Trace()
    if not has_text(idea.target_user, 2):
        t.zero("사용자가 비어 있음")
        return t.result()
    t.add(True, 2, "사용자 정의됨")
    t.add(has_text(idea.payer, 2), 2, "구매자 정의됨")
    t.add(has_text(idea.influencer, 2), 1, "영향자 정의됨")
    if not has_text(idea.payer, 2):
        t.cap(2, "구매자 미정의")
    return t.result()


def _score_d05(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D05 가치 제안."""
    t = _Trace()
    if not has_text(idea.core_action, 2):
        t.zero("핵심 행동이 비어 있음")
        return t.result()
    t.add(True, 2, "핵심 행동 정의됨")
    t.add(len(idea.core_action.strip()) >= 15, 1, "핵심 행동이 구체적")
    t.add(has_text(idea.expected_result, 2), 1, "기대 결과 정의됨")
    t.add(has_signal(idea.expected_result, MEASURABLE_SIGNALS), 1, "기대 결과가 측정 가능")
    return t.result()


def _score_d06(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D06 첫 성공 경험."""
    t = _Trace()
    if not has_text(idea.first_success, 2):
        t.zero("첫 성공 경험이 정의되지 않음")
        return t.result()
    t.add(True, 2, "첫 성공 경험 정의됨")
    t.add(len(idea.first_success.strip()) >= 20, 1, "첫 성공 서술이 구체적")
    t.add(
        has_signal(idea.first_success, ("분", "초", "단계", "첫", "한 번", "바로", "즉시")),
        1,
        "도달 시점이 명시됨",
    )
    t.add(has_text(idea.core_action, 2), 1, "핵심 행동과 연결 가능")
    return t.result()


def _score_d07(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D07 반복 사용 이유."""
    t = _Trace()
    if not has_text(idea.retention_reason, 2):
        t.zero("재방문 이유가 정의되지 않음")
        return t.result()
    t.add(True, 2, "재방문 이유 정의됨")
    t.add(len(idea.retention_reason.strip()) >= 20, 1, "재방문 이유가 구체적")
    t.add(has_signal(idea.retention_reason, RETENTION_SIGNALS), 1, "반복 사용 장치 포함")
    t.add(bool(_evidence_for(ev, DimensionCode.D07)), 1, "재방문을 지지하는 근거 등록됨")
    return t.result()


def _score_d08(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D08 차별성."""
    t = _Trace()
    if not has_text(idea.current_solution, 2):
        t.zero("대체 방법이 없어 차별성을 판단할 수 없음")
        return t.result()
    t.add(True, 1, "대체 방법 정의됨")
    t.add(has_text(idea.current_solution_problem, 5), 1, "대체 방법의 한계 서술됨")
    t.add(
        has_text(idea.current_solution_problem, 30),
        1,
        "대체 방법의 한계가 30자 이상으로 구체적",
    )
    t.add(bool(_evidence_for(ev, DimensionCode.D08)), 1, "차별성을 지지하는 근거 등록됨")
    t.add(
        _has_strong_evidence(ev, DimensionCode.D08, policy, minimum=0.35),
        1,
        "데스크리서치 이상 수준의 근거 존재",
    )
    return t.result()


def _score_d09(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D09 유입 가능성."""
    t = _Trace()
    if not has_text(idea.distribution_channel, 2):
        t.zero("유입 경로가 정의되지 않음")
        return t.result()
    t.add(True, 2, "유입 경로 정의됨")
    t.add(len(idea.distribution_channel.strip()) >= 15, 1, "유입 경로가 구체적")
    t.add(has_signal(idea.distribution_channel, CHANNEL_SIGNALS), 1, "식별 가능한 채널 언급")
    t.add(bool(_evidence_for(ev, DimensionCode.D09)), 1, "유입을 지지하는 근거 등록됨")
    return t.result()


def _score_d10(idea: IdeaStructure, warns: set[WarningCode], ev, policy) -> tuple[int, str]:
    """D10 구현 가능성. 범위가 좁을수록 높다."""
    t = _Trace()
    if not has_text(idea.core_action, 2):
        t.zero("핵심 행동이 없어 구현 범위를 판단할 수 없음")
        return t.result()
    t.add(True, 2, "핵심 행동이 있어 범위 산정 가능")
    t.add(has_text(idea.expected_result, 2), 1, "완료 조건이 정의됨")
    t.add(has_text(idea.first_success, 2), 1, "첫 성공 기준으로 범위를 좁힐 수 있음")
    t.add(
        len(idea.core_action.strip()) <= 120,
        1,
        "핵심 행동이 하나로 압축되어 있음",
    )
    return t.result()


_SCORERS: dict[DimensionCode, Callable[..., tuple[int, str]]] = {
    DimensionCode.D01: _score_d01,
    DimensionCode.D02: _score_d02,
    DimensionCode.D03: _score_d03,
    DimensionCode.D04: _score_d04,
    DimensionCode.D05: _score_d05,
    DimensionCode.D06: _score_d06,
    DimensionCode.D07: _score_d07,
    DimensionCode.D08: _score_d08,
    DimensionCode.D09: _score_d09,
    DimensionCode.D10: _score_d10,
}


_MISSING_EVIDENCE_HINTS: dict[DimensionCode, tuple[str, ...]] = {
    DimensionCode.D01: ("문제 상황을 직접 관찰하거나 진술한 인터뷰",),
    DimensionCode.D02: ("문제 발생 빈도와 심각도를 물은 인터뷰", "이탈·중단 행동 데이터"),
    DimensionCode.D03: ("타깃 후보별 스크리닝 인터뷰",),
    DimensionCode.D04: ("결제 결정자 인터뷰",),
    DimensionCode.D05: ("가치 제안 문구 반응 테스트",),
    DimensionCode.D06: ("첫 세션 완료율 프로토타입 테스트",),
    DimensionCode.D07: ("재방문 코호트 행동 데이터",),
    DimensionCode.D08: ("경쟁·대체재 데스크리서치", "대체재 사용자 인터뷰"),
    DimensionCode.D09: ("채널별 유입 테스트(랜딩 페이지 등)",),
    DimensionCode.D10: ("기술 검증 프로토타입",),
}


_RECOMMENDED_ACTIONS: dict[DimensionCode, str] = {
    DimensionCode.D01: "문제가 발생하는 순간을 시간·행동 단위로 다시 씁니다.",
    DimensionCode.D02: "대상 5명에게 '최근 한 달에 몇 번 겪었는지'를 직접 묻습니다.",
    DimensionCode.D03: "타깃을 상황 + 현재 행동 + 중단 원인으로 다시 정의합니다.",
    DimensionCode.D04: "사용자·구매자·영향자를 분리해 각각의 판단 기준을 적습니다.",
    DimensionCode.D05: "핵심 행동 하나와 그 결과를 측정 가능한 문장으로 씁니다.",
    DimensionCode.D06: "첫 3분 안에 끝나는 성공 경험 하나를 설계합니다.",
    DimensionCode.D07: "다음 날 다시 열 이유를 제품 안의 장치로 만듭니다.",
    DimensionCode.D08: "현재 대체재가 실패하는 지점을 근거와 함께 정리합니다.",
    DimensionCode.D09: "첫 100명을 만날 채널 한 곳을 정하고 소규모로 테스트합니다.",
    DimensionCode.D10: "MVP를 P0 + 최소한의 P1로 잘라냅니다.",
}


def score_dimensions(
    idea: IdeaStructure,
    warnings: Sequence[DiagnosisWarning],
    evidence: Sequence[EvidenceItem],
    policy: EvaluationPolicy,
    adjustments: Sequence[ScoreAdjustment] = (),
    confidences: dict[DimensionCode, float] | None = None,
) -> list[DimensionScore]:
    """10개 평가 항목을 채점한다. 순수 함수이며 동일 입력에 동일 출력을 낸다."""

    warn_codes = {w.code for w in warnings}
    confidences = confidences or {}
    by_code: dict[DimensionCode, list[ScoreAdjustment]] = {}
    for adj in adjustments:
        by_code.setdefault(adj.code, []).append(adj)

    results: list[DimensionScore] = []
    for code in DimensionCode:
        raw, reason = _SCORERS[code](idea, warn_codes, evidence, policy)

        for adj in by_code.get(code, []):
            before = raw
            raw = max(0, min(MAX_RAW_SCORE, raw + adj.delta))
            if raw != before:
                reason += f" / 도메인 보정 {adj.delta:+d}: {adj.reason}"

        weight = policy.weight_of(code)
        normalized = (raw / MAX_RAW_SCORE) * weight

        missing = (
            _MISSING_EVIDENCE_HINTS.get(code, ())
            if not _evidence_for(evidence, code)
            else ()
        )

        results.append(
            DimensionScore(
                code=code,
                label=DIMENSION_LABELS[code],
                raw_score=raw,
                weight=weight,
                normalized_score=normalized,
                reason=reason,
                missing_evidence=missing,
                recommended_action=_RECOMMENDED_ACTIONS[code],
                confidence=confidences.get(code, 0.0),
            )
        )
    return results


def total_score(dimensions: Sequence[DimensionScore]) -> float:
    """정규화 총점 (0~100)."""
    return sum(d.normalized_score for d in dimensions)
