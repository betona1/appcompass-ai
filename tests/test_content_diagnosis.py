"""도메인 콘텐츠 진단 테스트 (Phase 4).

examath는 수학적으로 검증 가능하다. 아이가 쓴 답에서 어떤 절차를 밟았는지
역추적할 수 있으므로, 분류가 맞는지 계산으로 확인한다.

VibeQuest는 문항이 '정의 암기형'인지 '실제 상황형'인지를 가린다.
이 도메인의 가장 큰 위험이 일반 용어 퀴즈로 보이는 것이라, 문항 단위 판정이 중요하다.
"""

from __future__ import annotations

import pytest

from appcompass.core.domains.examath import MathErrorType
from appcompass.core.domains.examath_errors import diagnose_subtraction
from appcompass.core.domains.registry import get_domain
from appcompass.core.domains.vibequest_quality import (
    RECOMMENDED_TYPES,
    QuestionType,
    diagnose_question,
)
from appcompass.core.enums import DomainCode, Severity


# ==========================================================================
# examath — 오답 역추적
# ==========================================================================


@pytest.mark.parametrize(
    "minuend,subtrahend,answer,expected",
    [
        # 각 자리에서 큰 수 - 작은 수 (43-7 → 7-3=4, 십의자리 4 → 44)
        (43, 7, 44, MathErrorType.REGROUPING_CONCEPT),
        # 일의 자리를 계산 못 하고 0으로 둠
        (43, 7, 40, MathErrorType.REGROUPING_CONCEPT),
        # 10을 빌렸지만 십의 자리를 안 줄임 (43-7 → 13-7=6, 십의자리 4 → 46)
        (43, 7, 46, MathErrorType.PLACE_VALUE),
        # 하나 더/덜 셈
        (52, 8, 45, MathErrorType.COUNTING_BACK),
    ],
)
def test_subtraction_error_is_traced_from_the_answer(
    minuend, subtrahend, answer, expected
):
    d = diagnose_subtraction(minuend, subtrahend, answer)
    assert d.classification == str(expected), (
        f"{minuend}-{subtrahend}={answer} → {d.classification_label}"
    )


def test_correct_answer_is_not_an_error():
    d = diagnose_subtraction(43, 7, 36)
    assert d.classification == "CORRECT"
    assert d.critical_count == 0


def test_correct_but_finger_counting_is_flagged():
    """정답이어도 손가락 세기에 머물면 다음 단계가 남아 있다."""
    d = diagnose_subtraction(43, 7, 36, "손가락으로 하나씩 뒤로 셈")
    assert d.classification == str(MathErrorType.COUNTING_BACK)
    assert d.critical_count == 0  # 정답이므로 치명은 아니다


def test_no_answer_is_avoidance_not_a_calculation_error():
    """답이 없는데 오답 유형을 따지는 건 순서가 틀렸다."""
    d = diagnose_subtraction(43, 7, None)
    assert d.classification == str(MathErrorType.MATH_ANXIETY_AVOIDANCE)
    assert d.critical_count == 1


def test_avoidance_behavior_overrides_everything():
    d = diagnose_subtraction(43, 7, 44, "문제를 보고 연필을 놓고 시도하지 않음")
    assert d.classification == str(MathErrorType.MATH_ANXIETY_AVOIDANCE)


def test_concrete_success_points_to_transfer_gap():
    d = diagnose_subtraction(34, 6, 38, "블록으로는 잘 함")
    assert d.classification == str(MathErrorType.CONCRETE_TO_SYMBOL_TRANSFER)


def test_procedural_explanation_beats_magnitude_explanation():
    """43-7=44는 '답이 크다'보다 '자리별로 큰수-작은수'가 더 구체적인 진단이다."""
    d = diagnose_subtraction(43, 7, 44)
    assert d.classification == str(MathErrorType.REGROUPING_CONCEPT)
    # 크기 문제도 후보로는 남아야 한다
    codes = {f.code for f in d.findings}
    assert str(MathErrorType.NUMBER_COMPARISON) in codes


def test_unknown_pattern_asks_to_observe():
    d = diagnose_subtraction(43, 7, 21)
    assert d.classification == str(MathErrorType.UNKNOWN)
    # 패턴이 안 잡히면 지어내지 말고 아이에게 직접 물으라고 해야 한다
    actions = " ".join(f.recommended_action for f in d.findings)
    assert "묻" in actions or "물어" in actions


def test_diagnosis_always_states_its_limits():
    """분류가 확정처럼 보이면 사용자가 관찰을 멈춘다."""
    for answer in (44, 36, None, 21):
        d = diagnose_subtraction(43, 7, answer)
        assert d.limits
        assert "관찰" in d.limits or "확인" in d.limits


def test_diagnosis_is_deterministic():
    a = diagnose_subtraction(43, 7, 44, "세로로 계산")
    b = diagnose_subtraction(43, 7, 44, "세로로 계산")
    assert a.to_dict() == b.to_dict()


def test_domain_rejects_invalid_input():
    domain = get_domain(DomainCode.EXAMATH)
    with pytest.raises(ValueError):
        domain.diagnose_content({"minuend": "", "subtrahend": "7"})
    with pytest.raises(ValueError, match="빼어지는 수가 더 작습니다"):
        domain.diagnose_content({"minuend": "7", "subtrahend": "43"})


# ==========================================================================
# VibeQuest — 문항 품질
# ==========================================================================


def test_rote_definition_is_critical():
    """이 도메인의 존재 이유를 무너뜨리는 유형이라 치명으로 잡는다."""
    d = diagnose_question("API란 무엇인가?")
    assert d.classification == str(QuestionType.ROTE_DEFINITION)
    assert d.critical_count >= 1
    assert any(f.code == "ROTE_DEFINITION" for f in d.findings)


def test_situation_question_is_recommended_type():
    d = diagnose_question(
        "AI 코딩 도구로 배포하려는데 'API key not found' 오류가 났습니다. "
        "가장 먼저 확인해야 할 것은?",
        choices="환경변수 확인\n들여쓰기 확인\n캐시 삭제\n인터넷 확인",
        explanation="키가 전달되지 않았다는 뜻입니다.",
        project_stage="첫 배포 / 비개발자",
        source="커뮤니티 사례",
    )
    assert QuestionType(d.classification) in RECOMMENDED_TYPES
    assert d.critical_count == 0


def test_order_signal_does_not_match_plain_meonjeo():
    """'가장 먼저 확인할 것은?'은 순서 배열 문제가 아니다."""
    d = diagnose_question(
        "배포하다가 오류가 났습니다. 가장 먼저 확인해야 할 것은?",
        choices="a\nb\nc\nd",
    )
    assert d.classification != str(QuestionType.ORDER_STEPS)

    ordered = diagnose_question("배포 과정을 순서대로 나열하세요.")
    assert ordered.classification == str(QuestionType.ORDER_STEPS)


def test_missing_explanation_is_critical():
    d = diagnose_question(
        "배포 중 오류 메시지를 보고 원인을 고르세요.",
        choices="a\nb\nc\nd",
        explanation="",
    )
    assert any(
        f.code == "NO_EXPLANATION" and f.severity == Severity.CRITICAL
        for f in d.findings
    )


def test_too_few_choices_is_flagged():
    d = diagnose_question(
        "배포 중 오류가 났습니다. 원인은?", choices="a\nb", explanation="설명"
    )
    assert any(f.code == "TOO_FEW_CHOICES" for f in d.findings)


def test_missing_source_is_flagged():
    """AI가 만든 부정확한 문항을 걸러낼 방법이 없어진다."""
    d = diagnose_question("배포 중 오류가 났습니다. 원인은?", explanation="설명")
    assert any(f.code == "NO_SOURCE" for f in d.findings)


def test_artifact_question_is_classified():
    d = diagnose_question(
        "다음 오류 메시지를 보고 어떤 개념과 관련 있는지 고르세요.\n"
        "ModuleNotFoundError: No module named 'requests'",
        choices="패키지 설치\n환경변수\n포트\n권한",
        explanation="설치되지 않은 패키지입니다.",
    )
    assert d.classification == str(QuestionType.ARTIFACT_TO_TERM)


def test_wrong_ai_answer_type_is_classified():
    d = diagnose_question(
        "AI가 아래와 같이 답했습니다. 틀린 부분은?",
        choices="a\nb\nc\nd",
        explanation="설명",
    )
    assert d.classification == str(QuestionType.SPOT_WRONG_AI_ANSWER)


def test_question_diagnosis_is_deterministic():
    a = diagnose_question("API란 무엇인가?")
    b = diagnose_question("API란 무엇인가?")
    assert a.to_dict() == b.to_dict()


def test_quality_check_admits_it_cannot_verify_facts():
    d = diagnose_question("배포 오류의 원인은?", choices="a\nb\nc\nd", explanation="설명")
    assert "사실관계" in d.limits


# ==========================================================================
# 도메인 계약
# ==========================================================================


def test_generic_domain_has_no_content_diagnosis():
    """억지로 만들면 의미 없는 양식이 된다. 없으면 없다고 한다."""
    assert get_domain(DomainCode.GENERIC).content_spec() is None


@pytest.mark.parametrize("domain", [DomainCode.EXAMATH, DomainCode.VIBEQUEST])
def test_content_spec_is_complete(domain):
    spec = get_domain(domain).content_spec()
    assert spec is not None
    assert spec.title and spec.description and spec.fields
    assert spec.example, "예시가 없으면 무엇을 넣어야 할지 알 수 없습니다."
    # 예시는 필수 칸을 전부 채워야 바로 진단이 돌아간다
    required = {f.key for f in spec.fields if f.required}
    assert required <= set(spec.example)


@pytest.mark.parametrize("domain", [DomainCode.EXAMATH, DomainCode.VIBEQUEST])
def test_example_actually_runs(domain):
    module = get_domain(domain)
    spec = module.content_spec()
    result = module.diagnose_content(dict(spec.example))
    assert result.classification
    assert result.summary
