"""텍스트 신호 사전과 판정 헬퍼.

여기 있는 함수는 모두 결정론적이다. 같은 문자열이면 항상 같은 결과를 낸다.
"AI가 대충 판단한다"는 인상을 주지 않도록, 어떤 신호가 걸렸는지를
호출자가 그대로 이유 문구에 넣을 수 있게 매칭된 키워드를 반환한다.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 넓은 타깃 표현 (CLAUDE.md §2.2, TECHSPEC §10.1)
# ---------------------------------------------------------------------------

BROAD_TARGET_PHRASES: tuple[str, ...] = (
    "모든 사람",
    "모든사람",
    "누구나",
    "누구든",
    "전 국민",
    "전국민",
    "전체 사용자",
    "모든 사용자",
    "관심 있는 사람",
    "관심있는 사람",
    "관심 있는 모든",
    "학생 모두",
    "학생 전체",
    "모든 학생",
    "아이들 전체",
    "모든 아이",
    "전 연령",
    "남녀노소",
    "일반인",
    "대중",
    "모두를 위한",
    "누구를 위한",
)

# 대상 명사: "학생 전체", "모든 아이" 처럼 집단 전체를 가리키는 표현을 잡는 데 쓴다.
_GROUP_NOUNS = r"(?:사람|분|이들|누구|사용자|유저|학생|아이|아동|어린이|초등학생|개발자|직장인|고객)"

BROAD_TARGET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "~를 배우고 싶은 사람" 처럼 상황이 없는 관심 기반 정의
    re.compile(rf"(?:배우고|알고|하고|쓰고|만들고)\s*싶은\s*(?:모든\s*)?{_GROUP_NOUNS}"),
    re.compile(rf"에\s*관심\s*(?:이\s*)?있는\s*(?:모든\s*)?{_GROUP_NOUNS}"),
    # "아이 전체", "학생들 모두" 등 집단 + 전체 수식어
    re.compile(rf"{_GROUP_NOUNS}들?\s*(?:전체|전부|모두)"),
    # "모든 아이", "온 국민" 등 전체 수식어 + 집단
    re.compile(rf"(?:모든|전체|모든\s*연령의|온)\s*{_GROUP_NOUNS}"),
)

# ---------------------------------------------------------------------------
# 신호 사전
# ---------------------------------------------------------------------------

PAIN_SIGNALS: tuple[str, ...] = (
    "중단", "막힘", "막혀", "막힌", "포기", "실패", "회피", "피하",
    "불안", "좌절", "짜증", "헤매", "시간이 오래", "복잡", "비용",
    "어려", "모르겠", "헷갈", "이해 못", "틀리", "귀찮",
)

FREQUENCY_SIGNALS: tuple[str, ...] = (
    "매일", "하루", "자주", "반복", "항상", "매번", "주 ", "주간",
    "수시로", "계속", "번씩", "번에 한", "회씩",
)

MEASURABLE_SIGNALS: tuple[str, ...] = (
    "%", "퍼센트", "분 이내", "초 이내", "분 안에", "회 이상", "명 이상",
    "완료율", "정답률", "재방문", "전환율", "감소", "증가", "단축",
    "이상", "이하", "배 ", "점 ",
)

RETENTION_SIGNALS: tuple[str, ...] = (
    "매일", "주간", "진도", "복습", "성장", "기록", "누적", "연속",
    "알림", "리포트", "요약", "도감", "레벨", "습관",
)

CHANNEL_SIGNALS: tuple[str, ...] = (
    "커뮤니티", "카페", "오픈채팅", "유튜브", "블로그", "검색",
    "aso", "seo", "앱스토어", "플레이스토어", "인스타", "쓰레드",
    "트위터", "디스코드", "학원", "학교", "교사", "학부모", "추천", "제휴",
    "광고", "인플루언서", "뉴스레터", "레딧", "슬랙", "링크드인",
)

FEATURE_FIRST_SIGNALS: tuple[str, ...] = (
    "기능", "화면", "버튼", "챗봇", "ai로", "gpt", "블록체인", "메타버스",
    "대시보드", "랭킹", "게시판",
)

# 어린이/교육 도메인에서 결제자가 사용자와 다를 가능성이 높은 신호
CHILD_SIGNALS: tuple[str, ...] = (
    "어린이", "아이", "아동", "초등", "유치", "학생", "꼬맹", "자녀", "미취학",
)


def normalize(text: str | None) -> str:
    """비교용 정규화: 소문자화 + 연속 공백 축약."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def has_text(text: str | None, min_len: int = 1) -> bool:
    return bool(text) and len(text.strip()) >= min_len


def matched_signals(text: str | None, signals: tuple[str, ...]) -> list[str]:
    """텍스트에서 발견된 신호 키워드를 원래 순서대로 반환한다."""
    norm = normalize(text)
    if not norm:
        return []
    return [s for s in signals if s.strip() and s.lower() in norm]


def has_signal(text: str | None, signals: tuple[str, ...]) -> bool:
    return bool(matched_signals(text, signals))


def broad_target_hits(text: str | None) -> list[str]:
    """넓은 타깃 표현을 찾아 매칭된 근거 문자열을 반환한다.

    문자열 규칙만 쓰지 않는다 (TECHSPEC §10.1).
    구체성 신호가 하나도 없는 짧은 타깃 문장도 넓은 타깃으로 본다.
    """
    norm = normalize(text)
    if not norm:
        return []
    hits = [p for p in BROAD_TARGET_PHRASES if p.lower() in norm]
    for pattern in BROAD_TARGET_PATTERNS:
        m = pattern.search(norm)
        if m:
            hits.append(m.group(0).strip())
    return list(dict.fromkeys(hits))


def target_specificity_score(target_user: str | None) -> int:
    """타깃 문장이 담고 있는 구체성 신호 개수 (0~4).

    상황, 현재 행동, 중단 원인, 구체적 대상 4가지를 본다.
    """
    norm = normalize(target_user)
    if not norm:
        return 0
    score = 0
    if len(norm) >= 20:
        score += 1
    if has_signal(norm, ("상황", "때", "중", "하다가", "하면서", "과정", "단계")):
        score += 1
    if has_signal(norm, PAIN_SIGNALS):
        score += 1
    if has_signal(
        norm,
        ("사용", "쓰고", "쓰는", "이용", "만들", "배우", "풀", "하고 있", "진행"),
    ):
        score += 1
    return score
