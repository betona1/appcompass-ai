"""규칙 엔진: 구조화 결과의 누락과 위험 표현을 경고로 바꾼다.

TECHSPEC §10. 이 모듈은 LLM을 호출하지 않으며 결정론적이다.
경고는 점수와 피벗 판정의 입력이 되므로 코드가 안정적이어야 한다.
"""

from __future__ import annotations

from typing import Sequence

from .enums import DomainCode, Severity, WarningCode
from .models import DiagnosisWarning, IdeaStructure
from .textsignals import (
    CHILD_SIGNALS,
    FEATURE_FIRST_SIGNALS,
    MEASURABLE_SIGNALS,
    PAIN_SIGNALS,
    broad_target_hits,
    has_signal,
    has_text,
    target_specificity_score,
)


#: 이것이 없으면 분석 자체가 성립하지 않는 항목.
#: 나머지 빈칸은 경고로 남긴다. 전부 강제하면 "빈칸을 발견하게 한다"는
#: 이 도구의 목적이 사라진다. 초안 단계의 아이디어도 기록할 수 있어야 한다.
REQUIRED_STRUCTURE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("target_user", "사용자", "누가 겪는 문제인지 없으면 타깃 평가가 전부 0점이 됩니다."),
    ("problem_situation", "문제 상황", "문제가 없으면 진단할 대상이 없습니다."),
    ("core_action", "핵심 행동", "무엇을 하게 할지 없으면 MVP를 만들 수 없습니다."),
    ("expected_result", "기대 결과", "무엇이 달라지는지 없으면 성공을 판정할 수 없습니다."),
)

#: 필수 검사는 "비었는가"만 본다. 내용이 충분한지는 경고와 점수가 판정한다.
#: 여기서 긴 길이를 요구하면 '부모', '본인' 같은 정당한 짧은 답이 막힌다.
MIN_REQUIRED_LENGTH = 2


def missing_required_fields(
    idea: IdeaStructure,
    extra_required: Sequence[tuple[str, str, str]] = (),
) -> list[tuple[str, str, str]]:
    """비어 있는 필수 항목을 (필드명, 라벨, 이유)로 돌려준다.

    extra_required로 도메인 전용 필수 항목을 더할 수 있다.
    예: examath는 어린이가 쓰고 부모가 결제하므로 구매자가 필수다.
    """
    missing: list[tuple[str, str, str]] = []
    for key, label, why in tuple(REQUIRED_STRUCTURE_FIELDS) + tuple(extra_required):
        if not has_text(getattr(idea, key, None), MIN_REQUIRED_LENGTH):
            missing.append((key, label, why))
    return missing


def detect_warnings(
    idea: IdeaStructure,
    domain_code: DomainCode = DomainCode.GENERIC,
) -> list[DiagnosisWarning]:
    """구조화 결과에서 공통 경고를 찾는다. 도메인 전용 경고는 도메인 모듈이 추가한다."""

    warnings: list[DiagnosisWarning] = []

    # --- BROAD_TARGET ---------------------------------------------------
    hits = broad_target_hits(idea.target_user)
    specificity = target_specificity_score(idea.target_user)
    if hits:
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.BROAD_TARGET,
                message=(
                    f"타깃 정의에 넓은 표현이 있습니다: {', '.join(hits)}. "
                    "나이·직업만이 아니라 상황 + 문제 + 현재 행동 + 중단 원인을 포함해야 합니다."
                ),
                severity=Severity.CRITICAL,
                field="target_user",
                recommended_action="타깃을 '어떤 상황에서 무엇을 하다가 왜 멈추는 사람'으로 다시 씁니다.",
            )
        )
    elif has_text(idea.target_user) and specificity <= 1:
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.BROAD_TARGET,
                message=(
                    "넓은 표현은 없지만 타깃 문장에 상황·현재 행동·중단 원인이 거의 없습니다. "
                    "행동으로 정의된 타깃으로 보기 어렵습니다."
                ),
                severity=Severity.WARN,
                field="target_user",
                recommended_action="타깃이 지금 무엇을 하고 있고 어디서 멈추는지 한 문장을 추가합니다.",
            )
        )

    # --- 필수 누락 (TECHSPEC §10.2) -------------------------------------
    if not has_text(idea.problem_situation, 5):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_TRIGGER_SITUATION,
                message="문제가 발생하는 구체적인 상황이 없습니다.",
                severity=Severity.CRITICAL,
                field="problem_situation",
                recommended_action="'언제, 무엇을 하다가' 문제가 생기는지 상황을 적습니다.",
            )
        )
    elif not has_signal(
        idea.problem_situation, ("때", "중", "하다가", "하면서", "상황", "과정", "단계", "후")
    ):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_TRIGGER_SITUATION,
                message="문제 서술은 있으나 문제가 발생하는 시점(트리거)이 드러나지 않습니다.",
                severity=Severity.WARN,
                field="problem_situation",
                recommended_action="문제가 터지는 순간을 시간·행동 기준으로 명시합니다.",
            )
        )

    if not has_text(idea.current_solution, 2):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_CURRENT_ALTERNATIVE,
                message="사용자가 지금 쓰고 있는 대체 방법이 없습니다. 대체재가 없다면 문제가 없을 가능성이 큽니다.",
                severity=Severity.WARN,
                field="current_solution",
                recommended_action="지금은 이 문제를 어떻게 넘기고 있는지 적습니다(검색, 지인, 수기, 방치 포함).",
            )
        )

    if not has_text(idea.core_action, 2):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.FEATURE_FIRST_IDEA,
                message="핵심 행동이 정의되지 않았습니다.",
                severity=Severity.CRITICAL,
                field="core_action",
                recommended_action="사용자가 앱에서 반드시 완료해야 하는 행동 하나를 적습니다.",
            )
        )

    if not has_text(idea.expected_result, 2):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_MEASURABLE_RESULT,
                message="핵심 행동 후의 기대 결과가 없습니다.",
                severity=Severity.CRITICAL,
                field="expected_result",
                recommended_action="핵심 행동을 마치면 사용자에게 무엇이 달라지는지 적습니다.",
            )
        )
    elif not has_signal(idea.expected_result, MEASURABLE_SIGNALS):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_MEASURABLE_RESULT,
                message="기대 결과가 측정 가능한 표현이 아닙니다. 추천 기능은 지표와 연결되어야 합니다.",
                severity=Severity.WARN,
                field="expected_result",
                recommended_action="기대 결과를 '무엇이 몇 % / 몇 분 / 몇 회 달라지는가'로 바꿉니다.",
            )
        )

    if not has_text(idea.first_success, 2):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_FIRST_SUCCESS,
                message="첫 성공 경험이 정의되지 않았습니다. 활성화 지점이 없으면 이탈 원인을 못 찾습니다.",
                severity=Severity.WARN,
                field="first_success",
                recommended_action="처음 진입한 사용자가 몇 분 안에 무엇을 해내야 하는지 적습니다.",
            )
        )

    if not has_text(idea.retention_reason, 2):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.NO_RETENTION_REASON,
                message="다시 돌아올 이유가 없습니다.",
                severity=Severity.WARN,
                field="retention_reason",
                recommended_action="사용자가 내일 다시 열어야 하는 이유를 적습니다.",
            )
        )

    # --- 결제자 분리 -----------------------------------------------------
    child_context = has_signal(idea.target_user, CHILD_SIGNALS) or has_signal(
        idea.problem_situation, CHILD_SIGNALS
    )
    if not has_text(idea.payer, 2):
        if child_context or domain_code == DomainCode.EXAMATH:
            warnings.append(
                DiagnosisWarning(
                    code=WarningCode.NO_PAYER_DEFINED,
                    message=(
                        "어린이·교육 맥락인데 사용자와 구매자가 분리되지 않았습니다. "
                        "쓰는 사람과 결제하는 사람이 다릅니다."
                    ),
                    severity=Severity.CRITICAL,
                    field="payer",
                    recommended_action="사용자(아이), 구매자(부모), 영향자(교사)를 각각 적습니다.",
                )
            )
        else:
            warnings.append(
                DiagnosisWarning(
                    code=WarningCode.NO_PAYER_DEFINED,
                    message="구매자가 정의되지 않았습니다. 사용자와 결제자가 같은지 확인이 필요합니다.",
                    severity=Severity.WARN,
                    field="payer",
                    recommended_action="결제 결정을 내리는 주체를 명시합니다. 같다면 '사용자와 동일'로 적습니다.",
                )
            )

    # --- 기능 우선 아이디어 ---------------------------------------------
    if has_signal(idea.core_action, FEATURE_FIRST_SIGNALS) and not has_signal(
        idea.problem_situation, PAIN_SIGNALS
    ):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.FEATURE_FIRST_IDEA,
                message="문제의 고통 신호 없이 기능·기술 중심으로 서술되어 있습니다.",
                severity=Severity.WARN,
                field="core_action",
                recommended_action="기능 대신 사용자가 겪는 손해를 먼저 씁니다.",
            )
        )

    # --- 차별성 근거 없는 단정 ------------------------------------------
    if has_text(idea.current_solution, 2) and not has_text(idea.current_solution_problem, 5):
        warnings.append(
            DiagnosisWarning(
                code=WarningCode.UNSUPPORTED_CLAIM,
                message="대체 방법은 있으나 그것이 왜 부족한지가 없습니다. 차별성 주장이 근거 없이 남습니다.",
                severity=Severity.WARN,
                field="current_solution_problem",
                recommended_action="현재 방법이 시간·복잡성·실패·불안·비용 중 무엇 때문에 부족한지 적습니다.",
            )
        )

    return warnings


_SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARN: 1, Severity.INFO: 2}


def dedupe_warnings(warnings: Sequence[DiagnosisWarning]) -> list[DiagnosisWarning]:
    """같은 (코드, 필드) 조합은 가장 심각한 것 하나만 남긴다.

    공통 규칙과 도메인 규칙이 같은 코드를 낼 수 있다. 이때 도메인의 더 구체적인
    치명 경고가 공통 규칙의 주의 경고에 가려지면 안 된다.
    UI의 실시간 검증과 분석 파이프라인이 반드시 같은 함수를 써야 결과가 일치한다.
    """
    best: dict[tuple[str, str | None], DiagnosisWarning] = {}
    for w in warnings:
        key = (str(w.code), w.field)
        current = best.get(key)
        if current is None or _SEVERITY_ORDER[w.severity] < _SEVERITY_ORDER[current.severity]:
            best[key] = w
    return list(best.values())


def base_unknowns(idea: IdeaStructure) -> list[str]:
    """공통 언노운. 도메인 모듈이 여기에 도메인 전용 언노운을 더한다."""
    unknowns: list[str] = []
    if not has_text(idea.current_solution, 2):
        unknowns.append("사용자가 지금 이 문제를 실제로 어떻게 넘기고 있는가")
    if not has_text(idea.first_success, 2):
        unknowns.append("첫 진입 사용자가 몇 분 안에 무엇을 성공해야 남는가")
    if not has_text(idea.retention_reason, 2):
        unknowns.append("사용자가 다음 날 다시 열 이유는 무엇인가")
    if not has_text(idea.payer, 2):
        unknowns.append("결제를 결정하는 주체는 누구이며 무엇을 보고 결정하는가")
    if not has_text(idea.distribution_channel, 2):
        unknowns.append("첫 100명의 사용자를 어디서 데려올 것인가")
    unknowns.append("이 문제가 실제로 얼마나 자주, 얼마나 크게 발생하는가")
    return list(dict.fromkeys(unknowns))
