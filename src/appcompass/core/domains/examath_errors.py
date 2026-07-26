"""examath 오류 유형 분류기 (CLAUDE.md §5.5).

뺄셈은 수학적으로 검증 가능하다. 아이가 쓴 답을 보면 **어떤 절차를 밟았는지**
역추적할 수 있다. 그래서 이 분류는 추측이 아니라 계산이다.

예: 43 - 7 = 44 라고 답했다면
    각 자리에서 큰 수에서 작은 수를 뺐다 (7-3=4, 십의 자리 4는 그대로).
    받아내림 개념이 없고 절차만 외운 상태다. → REGROUPING_CONCEPT

다만 같은 답이 여러 원인에서 나올 수 있다. 그래서 관찰된 행동을 함께 받아
후보를 좁히고, **확정하지 않고 확인을 요구한다.**
"""

from __future__ import annotations

from ..content import DEFAULT_LIMITS, ContentDiagnosis, ContentFinding
from ..enums import Severity
from ..textsignals import has_signal, normalize

# examath.py의 MathErrorType을 재사용하기 위해 지연 import한다 (순환 방지).


BEHAVIOR_SIGNALS: dict[str, tuple[str, ...]] = {
    "AVOIDANCE": ("시도하지 않", "안 하려", "건너뛰", "연필을 놓", "포기", "울", "회피", "싫다"),
    "FINGER": ("손가락", "하나씩 세", "거꾸로 세", "뒤로 세", "세다가"),
    "CONCRETE_OK": ("블록", "구체물", "그림으로는", "손으로는", "교구"),
    "PROCEDURE": ("세로", "받아내림", "빌려", "절차", "외운", "공식"),
    "SLOW": ("오래", "한참", "시간이"),
}


def _smaller_from_larger(minuend: int, subtrahend: int) -> int | None:
    """각 자리에서 큰 수에서 작은 수를 뺀 결과. 초등에서 가장 흔한 오류."""
    if not (0 <= minuend <= 99 and 0 <= subtrahend <= 99):
        return None
    m_ones, m_tens = minuend % 10, minuend // 10
    s_ones, s_tens = subtrahend % 10, subtrahend // 10
    ones = abs(m_ones - s_ones)
    tens = abs(m_tens - s_tens)
    return tens * 10 + ones


def _ignored_borrow(minuend: int, subtrahend: int) -> int | None:
    """받아내림을 하지 않고 일의 자리를 0으로 둔 결과."""
    m_ones, m_tens = minuend % 10, minuend // 10
    s_ones = subtrahend % 10
    if m_ones >= s_ones:
        return None
    return m_tens * 10


def _borrowed_without_reducing_tens(minuend: int, subtrahend: int) -> int | None:
    """일의 자리는 10을 빌려 계산했으나 십의 자리를 1 줄이지 않은 결과."""
    m_ones, m_tens = minuend % 10, minuend // 10
    s_ones, s_tens = subtrahend % 10, subtrahend // 10
    if m_ones >= s_ones:
        return None
    ones = m_ones + 10 - s_ones
    tens = m_tens - s_tens
    if tens < 0:
        return None
    return tens * 10 + ones


def diagnose_subtraction(
    minuend: int,
    subtrahend: int,
    child_answer: int | None,
    observation: str = "",
) -> ContentDiagnosis:
    """뺄셈 오답 하나를 오류 유형으로 분류한다."""
    from .examath import MATH_ERROR_LABELS, MathErrorType

    correct = minuend - subtrahend
    obs = normalize(observation)
    findings: list[ContentFinding] = []
    suggestions: list[str] = []
    detail = {
        "problem": f"{minuend} - {subtrahend}",
        "correct": correct,
        "answer": child_answer,
        "needs_regrouping": (minuend % 10) < (subtrahend % 10),
    }

    def finding(code, message, severity=Severity.WARN, action=""):
        findings.append(
            ContentFinding(
                code=code, message=message, severity=severity, recommended_action=action
            )
        )

    # --- 시도조차 하지 않은 경우가 가장 먼저다 -------------------------
    # 답이 없는데 오답 유형을 따지는 건 순서가 틀렸다.
    if child_answer is None or has_signal(obs, BEHAVIOR_SIGNALS["AVOIDANCE"]):
        finding(
            str(MathErrorType.MATH_ANXIETY_AVOIDANCE),
            "답을 쓰지 않았거나 시도를 회피하는 행동이 관찰되었습니다. "
            "계산 능력보다 '틀릴까 봐 시도하지 않는' 상태가 먼저 해결되어야 합니다.",
            Severity.CRITICAL,
            "정답을 묻지 말고 구체물로 '해보기'만 시킵니다. 맞고 틀림을 평가하지 않습니다.",
        )
        return ContentDiagnosis(
            classification=str(MathErrorType.MATH_ANXIETY_AVOIDANCE),
            classification_label=MATH_ERROR_LABELS[MathErrorType.MATH_ANXIETY_AVOIDANCE],
            summary=(
                f"{minuend} - {subtrahend} 문제에서 시도 자체가 이루어지지 않았습니다. "
                "먼저 실패해도 안전하다는 경험이 필요합니다."
            ),
            findings=tuple(findings),
            suggestions=(
                "정답률을 보여주지 않습니다.",
                "구체물로 '옮겨보기'만 하게 하고 결과를 평가하지 않습니다.",
                "성공한 문제만 모아 다시 보여줍니다.",
            ),
            limits=DEFAULT_LIMITS,
            detail=detail,
        )

    # --- 정답 --------------------------------------------------------
    if child_answer == correct:
        if has_signal(obs, BEHAVIOR_SIGNALS["FINGER"]):
            finding(
                str(MathErrorType.COUNTING_BACK),
                "답은 맞았지만 손가락으로 하나씩 세는 방법에 머물러 있습니다. "
                "두 자리 수로 넘어가면 이 방법은 한계에 부딪힙니다.",
                Severity.WARN,
                "10을 한 번에 덜어내는 경험(10 만들기·가르기)으로 넘어가게 합니다.",
            )
        if has_signal(obs, BEHAVIOR_SIGNALS["SLOW"]):
            finding(
                str(MathErrorType.COUNTING_BACK),
                "정답이지만 시간이 오래 걸립니다. 절차가 자동화되지 않았습니다.",
                Severity.INFO,
                "같은 유형을 짧게 반복하되 문제 수를 늘리지 않습니다.",
            )
        label = "정답" if not findings else MATH_ERROR_LABELS[MathErrorType.COUNTING_BACK]
        return ContentDiagnosis(
            classification="CORRECT" if not findings else str(MathErrorType.COUNTING_BACK),
            classification_label=label,
            summary=(
                f"{minuend} - {subtrahend} = {correct}. 정답입니다."
                + ("" if not findings else " 다만 풀이 방법에 다음 단계가 남아 있습니다.")
            ),
            findings=tuple(findings),
            suggestions=tuple(),
            limits=DEFAULT_LIMITS,
            detail=detail,
        )

    # --- 오답 패턴 역추적 ----------------------------------------------
    # 후보를 모으는 순서가 곧 우선순위다.
    # 관찰된 행동 > 절차 역추적 > 일반적인 수 감각 순으로 본다.
    # "답이 처음 수보다 크다"는 사실이지만, 같은 답이 절차 오류로도 설명되면
    # 그쪽이 훨씬 구체적이고 개입 방법도 분명하다.
    candidates: list[tuple[MathErrorType, str, str]] = []

    if has_signal(obs, BEHAVIOR_SIGNALS["CONCRETE_OK"]):
        candidates.append(
            (
                MathErrorType.CONCRETE_TO_SYMBOL_TRANSFER,
                "구체물로는 해결하지만 숫자로 바뀌면 막힙니다. "
                "표현 전환 단계가 빠져 있습니다.",
                "구체물 → 그림 → 숫자 순서로 같은 문제를 세 번 보여줍니다. 단계를 건너뛰지 않습니다.",
            )
        )

    sfl = _smaller_from_larger(minuend, subtrahend)
    if sfl is not None and child_answer == sfl and sfl != correct:
        candidates.append(
            (
                MathErrorType.REGROUPING_CONCEPT,
                f"각 자리에서 큰 수에서 작은 수를 뺐습니다 "
                f"({minuend % 10}와 {subtrahend % 10} 중 큰 수에서 작은 수). "
                "받아내림이 필요하다는 것을 인식하지 못했습니다.",
                "십의 자리에서 10을 가져와 일의 자리에 합치는 과정을 구체물로 보여줍니다.",
            )
        )
        candidates.append(
            (
                MathErrorType.PROCEDURE_ONLY,
                "세로셈 절차만 외운 상태에서 자리별로 기계적으로 뺀 것으로 보입니다.",
                "절차를 가르치기 전에 '왜 빌려오는가'를 먼저 이해시킵니다.",
            )
        )

    ib = _ignored_borrow(minuend, subtrahend)
    if ib is not None and child_answer == ib:
        candidates.append(
            (
                MathErrorType.REGROUPING_CONCEPT,
                f"일의 자리를 계산하지 못하고 0으로 두었습니다 (답 {child_answer}). "
                "받아내림 자체를 모르는 상태입니다.",
                "10 만들기와 가르기부터 다시 시작합니다.",
            )
        )

    bwr = _borrowed_without_reducing_tens(minuend, subtrahend)
    if bwr is not None and child_answer == bwr and bwr != correct:
        candidates.append(
            (
                MathErrorType.PLACE_VALUE,
                f"일의 자리는 10을 빌려 바르게 계산했지만 십의 자리를 1 줄이지 않았습니다 "
                f"(답 {child_answer}). 빌려온 10이 어디서 왔는지 이해하지 못했습니다.",
                "십의 자리 묶음 하나를 실제로 풀어서 일의 자리로 옮기는 조작을 반복합니다.",
            )
        )

    if abs(child_answer - correct) == 1:
        candidates.append(
            (
                MathErrorType.COUNTING_BACK,
                f"정답과 1 차이입니다 ({child_answer} vs {correct}). "
                "뒤로 세다가 하나를 더 세거나 덜 센 것으로 보입니다.",
                "세지 않고 10을 한 번에 덜어내는 방법으로 넘어가게 합니다.",
            )
        )

    # 절차로 설명되지 않을 때만 '수의 크기 감각' 문제로 본다.
    if child_answer > minuend and not candidates:
        candidates.append(
            (
                MathErrorType.NUMBER_COMPARISON,
                f"답({child_answer})이 처음 수({minuend})보다 큽니다. "
                "빼면 작아진다는 감각이 아직 없습니다.",
                "구체물을 덜어내며 '빼면 줄어든다'를 눈으로 확인시킵니다.",
            )
        )
    elif child_answer > minuend:
        candidates.append(
            (
                MathErrorType.NUMBER_COMPARISON,
                f"답({child_answer})이 처음 수({minuend})보다 큽니다. "
                "빼면 작아진다는 것을 확인하는 단계도 함께 필요합니다.",
                "구체물을 덜어내며 '빼면 줄어든다'를 눈으로 확인시킵니다.",
            )
        )

    if has_signal(obs, BEHAVIOR_SIGNALS["FINGER"]) and not candidates:
        candidates.append(
            (
                MathErrorType.COUNTING_BACK,
                "손가락으로 뒤로 세는 방법에 의존하고 있어 두 자리 수에서 실패합니다.",
                "10 만들기로 한 번에 덜어내는 방법을 연습시킵니다.",
            )
        )

    if not candidates:
        candidates.append(
            (
                MathErrorType.UNKNOWN,
                f"답 {child_answer}가 알려진 오류 패턴과 맞지 않습니다. "
                "아이가 어떻게 풀었는지 직접 물어봐야 합니다.",
                "'어떻게 풀었는지 말해줄래?'라고 묻고 과정을 기록합니다.",
            )
        )

    primary, primary_msg, primary_action = candidates[0]
    finding(str(primary), primary_msg, Severity.CRITICAL, primary_action)
    for code, msg, action in candidates[1:]:
        finding(str(code), msg, Severity.WARN, action)

    if detail["needs_regrouping"]:
        suggestions.append("받아내림이 필요한 문제입니다. 10 만들기·가르기를 먼저 확인하세요.")
    suggestions.append("같은 오류 유형의 문제를 3개 더 주어 패턴이 반복되는지 확인하세요.")
    suggestions.append("구체물 → 그림 → 숫자 순서로 같은 문제를 다시 제시하세요.")

    return ContentDiagnosis(
        classification=str(primary),
        classification_label=MATH_ERROR_LABELS[primary],
        summary=(
            f"{minuend} - {subtrahend} = {correct} 인데 {child_answer}로 답했습니다. "
            f"가장 가능성 높은 원인은 '{MATH_ERROR_LABELS[primary]}'입니다."
            + (f" 후보가 {len(candidates)}개 있어 확인이 필요합니다." if len(candidates) > 1 else "")
        ),
        findings=tuple(findings),
        suggestions=tuple(dict.fromkeys(suggestions)),
        limits=DEFAULT_LIMITS,
        detail=detail,
    )
