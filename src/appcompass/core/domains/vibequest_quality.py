"""VibeQuest 문항 품질 분류기 (CLAUDE.md §4.6~4.7).

이 도메인의 가장 큰 위험은 **일반적인 용어 퀴즈 앱으로 보이는 것**이다.
그건 문항 하나하나에서 결정된다. 기획서에 "실제 상황형 문제"라고 써 두어도
실제 문항이 "API란 무엇인가?"면 아무 소용이 없다.

그래서 만든 문항을 넣으면 어떤 유형인지 분류하고, 정의 암기형이면 경고한다.

CLAUDE.md §4.6 권장 문제 유형:
    정의-실제 상황 연결 / 올바른 도구 선택 / 잘못된 AI 답변 찾기 /
    코드·화면·오류와 용어 연결 / 유사 개념 차이 구분 / 작업 순서 배열 /
    시나리오형 4지선다 / 짧은 주관식 후 키워드 채점
"""

from __future__ import annotations

from enum import StrEnum

from ..content import DEFAULT_LIMITS, ContentDiagnosis, ContentFinding
from ..enums import Severity
from ..textsignals import has_signal, normalize


class QuestionType(StrEnum):
    """CLAUDE.md §4.6 권장 문제 유형 + 피해야 할 유형."""

    DEFINITION_TO_SITUATION = "DEFINITION_TO_SITUATION"
    TOOL_CHOICE = "TOOL_CHOICE"
    SPOT_WRONG_AI_ANSWER = "SPOT_WRONG_AI_ANSWER"
    ARTIFACT_TO_TERM = "ARTIFACT_TO_TERM"
    DISTINGUISH_SIMILAR = "DISTINGUISH_SIMILAR"
    ORDER_STEPS = "ORDER_STEPS"
    SCENARIO_MCQ = "SCENARIO_MCQ"
    SHORT_ANSWER_KEYWORD = "SHORT_ANSWER_KEYWORD"
    # 피해야 할 유형
    ROTE_DEFINITION = "ROTE_DEFINITION"
    UNCLASSIFIED = "UNCLASSIFIED"


QUESTION_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.DEFINITION_TO_SITUATION: "정의와 실제 상황 연결",
    QuestionType.TOOL_CHOICE: "올바른 도구 선택",
    QuestionType.SPOT_WRONG_AI_ANSWER: "잘못된 AI 답변 찾기",
    QuestionType.ARTIFACT_TO_TERM: "코드·화면·오류와 용어 연결",
    QuestionType.DISTINGUISH_SIMILAR: "유사 개념 차이 구분",
    QuestionType.ORDER_STEPS: "작업 순서 배열",
    QuestionType.SCENARIO_MCQ: "시나리오형 4지선다",
    QuestionType.SHORT_ANSWER_KEYWORD: "짧은 주관식 (키워드 채점)",
    QuestionType.ROTE_DEFINITION: "단순 정의 암기형 (권장하지 않음)",
    QuestionType.UNCLASSIFIED: "분류 불가",
}

RECOMMENDED_TYPES = frozenset(
    t for t in QuestionType
    if t not in (QuestionType.ROTE_DEFINITION, QuestionType.UNCLASSIFIED)
)

# --- 신호 사전 --------------------------------------------------------
_ROTE = ("무엇인가", "무엇입니까", "뜻은", "의미는", "정의는", "무엇을 뜻", "란?", "이란")
_SITUATION = (
    "상황에서", "하려고", "하다가", "만들던 중", "작업 중", "때 어떻게",
    "하려는데", "막혔", "진행 중", "다음에 무엇", "이럴 때",
)
_ARTIFACT = (
    "오류 메시지", "에러", "traceback", "로그", "코드", "화면", "터미널",
    "스크린샷", "아래 코드", "다음 코드", "이 메시지",
)
_AI_ANSWER = ("ai가", "챗봇이", "gpt가", "assistant", "답변 중", "이 답변", "틀린 부분")
_TOOL = ("어느 것을 써야", "무엇을 사용", "어떤 도구", "어떤 방법을 골라", "가장 알맞은 도구")
_COMPARE = ("차이", "다른 점", "구분", "vs", "와(과)의 차이", "어느 쪽이")
# '먼저'는 "가장 먼저 확인할 것은?"처럼 순서 문제가 아닌 곳에도 흔히 쓰인다.
# 배열을 요구하는 표현만 남긴다.
_ORDER = ("순서대로", "차례대로", "단계를 배열", "순서를 맞추", "순서로 나열", "올바른 순서")
_STAGE = (
    "설치", "환경 설정", "환경변수", "배포", "커밋", "git", "api 키", "db",
    "데이터베이스", "인증", "토큰", "프롬프트", "에이전트", "빌드", "테스트",
)


def diagnose_question(
    stem: str,
    choices: str = "",
    explanation: str = "",
    project_stage: str = "",
    source: str = "",
) -> ContentDiagnosis:
    """문항 하나의 유형을 분류하고 품질 문제를 찾는다."""

    s = normalize(stem)
    all_text = normalize(f"{stem} {choices} {explanation}")
    findings: list[ContentFinding] = []
    suggestions: list[str] = []

    def finding(code, message, severity=Severity.WARN, action=""):
        findings.append(
            ContentFinding(code=code, message=message, severity=severity, recommended_action=action)
        )

    has_situation = has_signal(s, _SITUATION)
    has_artifact = has_signal(all_text, _ARTIFACT)
    choice_lines = [c for c in (choices or "").splitlines() if c.strip()]

    # --- 유형 분류 (구체적인 것부터) -------------------------------------
    if has_signal(all_text, _AI_ANSWER) and has_signal(all_text, ("틀린", "잘못", "오류가 있")):
        qtype = QuestionType.SPOT_WRONG_AI_ANSWER
    elif has_signal(s, _ORDER):
        qtype = QuestionType.ORDER_STEPS
    elif has_signal(s, _COMPARE):
        qtype = QuestionType.DISTINGUISH_SIMILAR
    elif has_signal(s, _TOOL):
        qtype = QuestionType.TOOL_CHOICE
    elif has_artifact:
        qtype = QuestionType.ARTIFACT_TO_TERM
    elif has_situation and len(choice_lines) >= 3:
        qtype = QuestionType.SCENARIO_MCQ
    elif has_situation:
        qtype = QuestionType.DEFINITION_TO_SITUATION
    elif has_signal(s, _ROTE):
        qtype = QuestionType.ROTE_DEFINITION
    elif not choice_lines and stem.strip():
        qtype = QuestionType.SHORT_ANSWER_KEYWORD
    else:
        qtype = QuestionType.UNCLASSIFIED

    # --- 품질 점검 ------------------------------------------------------
    if qtype == QuestionType.ROTE_DEFINITION:
        finding(
            "ROTE_DEFINITION",
            "용어의 뜻을 그대로 묻는 문항입니다. 외우면 맞지만 실제 작업에 전이되지 않습니다. "
            "이런 문항이 쌓이면 일반 용어 퀴즈 앱과 구분되지 않습니다.",
            Severity.CRITICAL,
            "'~란 무엇인가' 대신 '이 상황에서 무엇을 해야 하는가'로 바꿉니다.",
        )
        suggestions.append(
            "예: 'API란 무엇인가?' → 'AI가 API 키를 넣으라고 했는데 어디서 발급받아야 하는가?'"
        )
    elif not has_situation and not has_artifact:
        finding(
            "NO_REAL_TASK_CONTEXT",
            "실제 작업 상황이나 코드·오류 메시지가 문항에 없습니다. "
            "용어 지식은 묻지만 '언제 쓰는지'는 묻지 않습니다.",
            Severity.WARN,
            "문항 앞에 '~을 만들다가 ~한 상황에서' 같은 맥락을 붙입니다.",
        )

    if not has_signal(all_text, _STAGE):
        finding(
            "NO_PROJECT_STAGE",
            "어떤 프로젝트 단계의 문항인지 드러나지 않습니다. "
            "단계가 없으면 '지금 내가 막힌 것'과 연결되지 않습니다.",
            Severity.WARN,
            "설치·환경설정·배포·인증 등 구체적 단계를 문항에 넣습니다.",
        )

    if not project_stage.strip():
        finding(
            "NO_DIFFICULTY_SPLIT",
            "대상 단계·난이도가 지정되지 않았습니다. "
            "초보자와 현업 개발자에게 같은 문항이 나가면 양쪽 다 이탈합니다.",
            Severity.WARN,
            "이 문항이 어느 수준을 위한 것인지 표시합니다.",
        )

    if choice_lines and len(choice_lines) < 3:
        finding(
            "TOO_FEW_CHOICES",
            f"보기가 {len(choice_lines)}개뿐입니다. 찍어서 맞을 확률이 높습니다.",
            Severity.WARN,
            "보기를 4개로 늘리고 오답도 그럴듯하게 만듭니다.",
        )

    if not explanation.strip():
        finding(
            "NO_EXPLANATION",
            "정답 해설이 없습니다. 틀렸을 때 무엇을 배우는지가 없습니다.",
            Severity.CRITICAL,
            "왜 그 답인지, 틀린 답은 왜 틀렸는지 한 줄씩 적습니다.",
        )

    if not source.strip():
        finding(
            "NO_SOURCE",
            "출처가 없습니다. AI가 만든 부정확한 문항이 섞여도 확인할 방법이 없습니다.",
            Severity.WARN,
            "공식 문서 링크나 실제 겪은 사례를 출처로 남깁니다.",
        )

    if qtype in RECOMMENDED_TYPES and not findings:
        summary = (
            f"권장 유형 '{QUESTION_TYPE_LABELS[qtype]}'에 해당하며 품질 문제가 발견되지 않았습니다."
        )
    elif qtype == QuestionType.ROTE_DEFINITION:
        summary = (
            "정의 암기형입니다. 이 유형이 많아지면 제품의 존재 이유가 사라집니다. "
            "실제 작업 상황형으로 바꾸세요."
        )
    elif qtype == QuestionType.UNCLASSIFIED:
        summary = (
            "권장 유형 중 어디에도 분류되지 않았습니다. 문항이 너무 짧거나 형식이 불명확합니다."
        )
    else:
        summary = (
            f"'{QUESTION_TYPE_LABELS[qtype]}' 유형이지만 보완할 점이 "
            f"{len(findings)}건 있습니다."
        )

    if qtype in RECOMMENDED_TYPES:
        suggestions.append(
            "이 문항으로 '학습 후 막혔던 작업을 재개했는가'를 측정할 수 있는지 확인하세요."
        )

    return ContentDiagnosis(
        classification=str(qtype),
        classification_label=QUESTION_TYPE_LABELS[qtype],
        summary=summary,
        findings=tuple(findings),
        suggestions=tuple(dict.fromkeys(suggestions)),
        limits=(
            DEFAULT_LIMITS
            + " 문항의 사실관계(정답이 실제로 맞는지)는 검사하지 않습니다."
        ),
        detail={
            "type": str(qtype),
            "has_situation": has_situation,
            "has_artifact": has_artifact,
            "choice_count": len(choice_lines),
        },
    )
