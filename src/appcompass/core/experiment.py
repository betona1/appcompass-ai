"""실험 설계와 결과 (TECHSPEC F-080).

이 모듈이 순환을 닫는다.

    가설 → 실험 설계 → 실행 → 결과 입력 → 근거로 등록 → 재분석 → 판단 갱신

지금까지는 "근거를 등록하세요"까지만 말할 수 있었다. 그런데 사용자 입장에서
막막한 건 '무엇을' 검증할지가 아니라 '어떻게' 검증할지다.
그래서 검증되지 않은 가설마다 **구체적인 실험을 제안**하고,
결과를 넣으면 **근거로 바로 변환**한다.

제안은 규칙이다. 도메인과 가설 종류에 따라 정해진 실험이 나온다.
LLM을 쓰지 않으므로 같은 상태면 항상 같은 제안이 나온다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Sequence

from .enums import DimensionCode, DomainCode, EvidenceType, HypothesisStatus
from .models import HypothesisVerdict


class ExperimentType(StrEnum):
    """TECHSPEC F-080 실험 유형."""

    INTERVIEW = "INTERVIEW"
    LANDING_PAGE = "LANDING_PAGE"
    CLICK_DUMMY = "CLICK_DUMMY"
    PROTOTYPE = "PROTOTYPE"
    CONCIERGE = "CONCIERGE"
    MVP_RELEASE = "MVP_RELEASE"
    PRICING_TEST = "PRICING_TEST"
    RETENTION_TEST = "RETENTION_TEST"


EXPERIMENT_TYPE_LABELS: dict[ExperimentType, str] = {
    ExperimentType.INTERVIEW: "인터뷰",
    ExperimentType.LANDING_PAGE: "랜딩 페이지",
    ExperimentType.CLICK_DUMMY: "클릭더미",
    ExperimentType.PROTOTYPE: "프로토타입 테스트",
    ExperimentType.CONCIERGE: "컨시어지 (수동 제공)",
    ExperimentType.MVP_RELEASE: "MVP 출시",
    ExperimentType.PRICING_TEST: "가격 테스트",
    ExperimentType.RETENTION_TEST: "재방문 테스트",
}

#: 실험 유형이 만들어내는 근거의 종류.
#: 인터뷰는 진술이고 프로토타입·출시는 행동이다. 신뢰도가 다르다.
EXPERIMENT_EVIDENCE_TYPE: dict[ExperimentType, EvidenceType] = {
    ExperimentType.INTERVIEW: EvidenceType.USER_INTERVIEW,
    ExperimentType.LANDING_PAGE: EvidenceType.BEHAVIOR_DATA,
    ExperimentType.CLICK_DUMMY: EvidenceType.PROTOTYPE_TEST,
    ExperimentType.PROTOTYPE: EvidenceType.PROTOTYPE_TEST,
    ExperimentType.CONCIERGE: EvidenceType.PROTOTYPE_TEST,
    ExperimentType.MVP_RELEASE: EvidenceType.BEHAVIOR_DATA,
    ExperimentType.PRICING_TEST: EvidenceType.BEHAVIOR_DATA,
    ExperimentType.RETENTION_TEST: EvidenceType.BEHAVIOR_DATA,
}


class ExperimentStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


EXPERIMENT_STATUS_LABELS: dict[ExperimentStatus, str] = {
    ExperimentStatus.DRAFT: "초안",
    ExperimentStatus.READY: "준비됨",
    ExperimentStatus.RUNNING: "진행 중",
    ExperimentStatus.COMPLETED: "완료",
    ExperimentStatus.CANCELLED: "취소",
}


class ExperimentConclusion(StrEnum):
    """실험이 가설에 대해 무엇을 말했는가."""

    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    INCONCLUSIVE = "INCONCLUSIVE"


CONCLUSION_LABELS: dict[ExperimentConclusion, str] = {
    ExperimentConclusion.SUPPORTS: "가설을 지지함",
    ExperimentConclusion.REFUTES: "가설을 반박함",
    ExperimentConclusion.INCONCLUSIVE: "판단 불가 (표본·설계 부족)",
}


@dataclass(frozen=True, slots=True)
class Experiment:
    """실험 하나. 설계와 결과를 함께 담는다."""

    id: str
    project_id: str
    title: str
    hypothesis_id: str
    experiment_type: ExperimentType
    target_segment: str = ""
    procedure: tuple[str, ...] = ()
    success_metric: str = ""
    target_value: str = ""
    sample_goal: int | None = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    started_at: datetime | None = None
    ended_at: datetime | None = None
    # --- 결과 ---
    actual_sample: int | None = None
    quantitative_result: str = ""
    qualitative_summary: str = ""
    conclusion: ExperimentConclusion | None = None
    next_experiment: str = ""
    evidence_id: str | None = None  # 근거로 등록했다면 그 id

    @property
    def is_completed(self) -> bool:
        return self.status == ExperimentStatus.COMPLETED

    @property
    def can_become_evidence(self) -> bool:
        """결론이 나온 완료 실험만 근거가 될 수 있다."""
        return (
            self.is_completed
            and self.conclusion is not None
            and self.conclusion != ExperimentConclusion.INCONCLUSIVE
            and self.evidence_id is None
        )


@dataclass(frozen=True, slots=True)
class ExperimentSuggestion:
    """검증되지 않은 가설에 대한 실험 제안."""

    hypothesis_id: str
    hypothesis_label: str
    title: str
    experiment_type: ExperimentType
    why_now: str
    procedure: tuple[str, ...]
    success_metric: str
    target_value: str
    sample_goal: int
    dimensions: tuple[DimensionCode, ...]
    cost_hint: str = ""


# ---------------------------------------------------------------------------
# 제안 규칙
# ---------------------------------------------------------------------------

#: 가설 종류별 기본 실험. 싼 것부터 제안한다.
#: 인터뷰 5건이 프로토타입 개발보다 항상 먼저다.
_BASE_SUGGESTIONS: dict[str, dict] = {
    "H-PROBLEM": {
        "type": ExperimentType.INTERVIEW,
        "title": "문제 발생 빈도·강도 인터뷰",
        "procedure": (
            "타깃에 해당하는 5명을 찾는다 (스크리닝 질문 3개로 거른다).",
            "'최근 한 달에 이 상황을 몇 번 겪었는지' 횟수를 묻는다.",
            "가장 최근 사례를 처음부터 끝까지 이야기하게 한다.",
            "그때 실제로 무엇을 했는지 행동을 확인한다. 의견은 묻지 않는다.",
            "해결하지 못한 채 넘어간 적이 있는지 확인한다.",
        ),
        "success_metric": "5명 중 문제를 월 2회 이상 겪었다고 답한 사람 수",
        "target_value": "5명 중 3명 이상",
        "sample_goal": 5,
        "cost_hint": "30분 × 5명. 개발 없음.",
    },
    "H-BEHAVIOR": {
        "type": ExperimentType.CLICK_DUMMY,
        "title": "핵심 행동 완료율 클릭더미 테스트",
        "procedure": (
            "핵심 행동 한 줄기만 담은 클릭더미를 만든다 (종이도 된다).",
            "타깃 6~8명에게 아무 설명 없이 건네고 끝까지 해보게 한다.",
            "어디서 멈추는지 관찰한다. 도와주지 않는다.",
            "완료까지 걸린 시간을 잰다.",
        ),
        "success_metric": "첫 시도에 핵심 행동을 끝까지 완료한 비율",
        "target_value": "70% 이상, 3분 이내",
        "sample_goal": 6,
        "cost_hint": "종이 프로토타입이면 반나절. 개발 불필요.",
    },
    "H-VALUE": {
        "type": ExperimentType.PROTOTYPE,
        "title": "핵심 행동 후 실제 변화 측정",
        "procedure": (
            "핵심 행동을 완료한 사용자에게 기대 결과가 실제로 생겼는지 측정한다.",
            "가능하면 행동으로 확인한다 (설문 대신 재시도·완료 여부).",
            "완료하지 못한 사용자와 비교한다.",
        ),
        "success_metric": "기대 결과가 실제로 발생한 비율",
        "target_value": "40% 이상",
        "sample_goal": 10,
        "cost_hint": "프로토타입 필요. 며칠~1주.",
    },
    "H-RETENTION": {
        "type": ExperimentType.RETENTION_TEST,
        "title": "다음 날 재방문 코호트 테스트",
        "procedure": (
            "첫 세션을 완료한 사용자 집단을 만든다.",
            "알림 없이 다음 날 스스로 돌아오는지 관찰한다.",
            "돌아온 사람에게 왜 돌아왔는지 묻는다.",
            "돌아오지 않은 사람에게도 이유를 묻는다. 이쪽이 더 중요하다.",
        ),
        "success_metric": "1일 재방문율 (알림 없이)",
        "target_value": "20% 이상",
        "sample_goal": 20,
        "cost_hint": "최소 2일 필요. 사용자 확보가 선행돼야 함.",
    },
    "H-REVENUE": {
        "type": ExperimentType.PRICING_TEST,
        "title": "지불 의사 확인",
        "procedure": (
            "구매 결정자에게 가격을 제시하고 반응을 본다.",
            "'살 것 같다'는 답은 근거로 치지 않는다. 실제 결제 시도나 사전예약을 받는다.",
            "거절 이유를 반드시 기록한다.",
        ),
        "success_metric": "가격 제시 후 결제 시도(또는 사전예약)한 비율",
        "target_value": "10% 이상",
        "sample_goal": 20,
        "cost_hint": "랜딩 페이지 + 결제 버튼이면 하루.",
    },
}

#: 도메인별로 실험 절차를 구체화한다. 일반론만 주면 실행되지 않는다.
_DOMAIN_OVERRIDES: dict[tuple[DomainCode, str], dict] = {
    (DomainCode.EXAMATH, "H-PROBLEM"): {
        "title": "받아내림 회피 실태 학부모 인터뷰",
        "procedure": (
            "초등 2학년 학부모 5명을 찾는다.",
            "'받아내림 문제에서 아이가 멈춘 적이 있는지' 최근 사례를 묻는다.",
            "최근 한 달에 몇 번 있었는지 횟수를 확인한다.",
            "그때 부모가 실제로 무엇을 했는지 행동을 확인한다.",
            "아이가 스스로 다시 시도한 적이 있는지 묻는다.",
        ),
        "success_metric": "5명 중 '월 2회 이상 겪었다'고 답한 학부모 수",
        "target_value": "5명 중 3명 이상",
    },
    (DomainCode.EXAMATH, "H-BEHAVIOR"): {
        "title": "구체물 조작 종이 프로토타입 테스트",
        "procedure": (
            "블록이나 종이 조각으로 10 만들기 미션을 만든다.",
            "초2 6명에게 설명 없이 건네고 스스로 해보게 한다.",
            "어디서 멈추는지 관찰한다. 도와주지 않는다.",
            "성공한 아이에게 같은 유형의 숫자 문제를 준다 (전이 확인).",
        ),
        "success_metric": "구체물 문제 자력 해결 비율 / 숫자 문제 전이 비율",
        "target_value": "구체물 70% 이상, 전이 40% 이상",
    },
    (DomainCode.EXAMATH, "H-REVENUE"): {
        "title": "학부모 지불 의사 확인",
        "procedure": (
            "주간 요약 리포트 목업을 학부모에게 보여준다.",
            "월 구독 가격을 제시하고 반응을 본다.",
            "'살 것 같다'는 답은 치지 않는다. 사전예약 신청을 받는다.",
            "아이 화면에 결제 요소가 없다는 점을 명시한다.",
        ),
        "success_metric": "가격 제시 후 사전예약한 학부모 비율",
        "target_value": "10% 이상",
    },
    (DomainCode.VIBEQUEST, "H-PROBLEM"): {
        "title": "용어로 막힌 경험 인터뷰",
        "procedure": (
            "AI 코딩 도구를 쓰는 비개발자 5명을 찾는다.",
            "'최근 일주일에 용어 때문에 멈춘 적이 몇 번인지' 묻는다.",
            "가장 최근 사례에서 어떤 용어였는지 확인한다.",
            "그때 실제로 무엇을 했는지 (검색/되묻기/포기) 확인한다.",
            "그날 작업을 끝냈는지 확인한다.",
        ),
        "success_metric": "5명 중 '주 2회 이상 멈췄다'고 답한 사람 수",
        "target_value": "5명 중 3명 이상",
    },
    (DomainCode.VIBEQUEST, "H-VALUE"): {
        "title": "학습 후 작업 재개율 측정",
        "procedure": (
            "실제로 막혔던 용어 3개를 상황형 미션으로 만든다.",
            "막혀 있는 사용자 8명에게 제공한다.",
            "24시간 내에 막혔던 작업을 재개했는지 확인한다.",
            "재개하지 못한 사람의 이유를 기록한다.",
        ),
        "success_metric": "학습 후 24시간 내 작업 재개율",
        "target_value": "50% 이상",
    },
}


def suggest_experiments(
    verdicts: Sequence[HypothesisVerdict],
    domain_code: DomainCode = DomainCode.GENERIC,
    limit: int = 3,
) -> list[ExperimentSuggestion]:
    """검증되지 않은 가설에 대해 실험을 제안한다.

    싼 것부터, 그리고 판정 우선순위가 높은 것부터 제안한다.
    문제 가설이 안 풀렸는데 가격 테스트를 하는 건 순서가 틀렸다.
    """

    # 검증 우선순위. 위쪽이 안 풀리면 아래는 의미가 없다.
    order = ["H-PROBLEM", "H-BEHAVIOR", "H-VALUE", "H-RETENTION", "H-REVENUE"]
    by_id = {v.id: v for v in verdicts}

    suggestions: list[ExperimentSuggestion] = []
    for hid in order:
        verdict = by_id.get(hid)
        if verdict is None:
            continue
        if verdict.status == HypothesisStatus.SUPPORTED:
            continue  # 이미 검증됨

        base = _BASE_SUGGESTIONS.get(hid)
        if base is None:
            continue
        spec = dict(base)
        spec.update(_DOMAIN_OVERRIDES.get((DomainCode(domain_code), hid), {}))

        if verdict.status == HypothesisStatus.REFUTED:
            why = (
                f"{verdict.label}이(가) 반박됐습니다. 기능을 고치기 전에 "
                "무엇이 틀렸는지 좁히는 실험이 먼저입니다."
            )
        elif verdict.status == HypothesisStatus.CONFLICTED:
            why = (
                f"{verdict.label}에 지지와 반박이 함께 있습니다. "
                "어느 쪽이 맞는지 가리는 실험이 필요합니다."
            )
        else:
            why = f"{verdict.label}이(가) 아직 검증되지 않았습니다. {verdict.reason}"

        suggestions.append(
            ExperimentSuggestion(
                hypothesis_id=hid,
                hypothesis_label=verdict.label,
                title=spec["title"],
                experiment_type=spec["type"],
                why_now=why,
                procedure=tuple(spec["procedure"]),
                success_metric=spec["success_metric"],
                target_value=spec["target_value"],
                sample_goal=spec["sample_goal"],
                dimensions=verdict.dimensions,
                cost_hint=spec.get("cost_hint", ""),
            )
        )
        if len(suggestions) >= limit:
            break
    return suggestions


def evidence_from_experiment(
    experiment: Experiment, verdict_dimensions: Sequence[DimensionCode]
) -> dict:
    """완료된 실험을 근거 등록용 값으로 바꾼다.

    실험 유형이 근거 유형을 결정한다. 사용자가 임의로 고르게 하면
    인터뷰를 '행동 데이터'로 등록해 신뢰도를 부풀릴 수 있다.
    """
    if not experiment.can_become_evidence:
        raise ValueError(
            "완료되고 결론이 난 실험만 근거가 될 수 있습니다. "
            "'판단 불가'는 근거로 등록하지 않습니다."
        )

    supports: tuple[DimensionCode, ...] = ()
    contradicts: tuple[DimensionCode, ...] = ()
    if experiment.conclusion == ExperimentConclusion.SUPPORTS:
        supports = tuple(verdict_dimensions)
    else:
        contradicts = tuple(verdict_dimensions)

    summary_parts = []
    if experiment.quantitative_result:
        summary_parts.append(f"정량: {experiment.quantitative_result}")
    if experiment.qualitative_summary:
        summary_parts.append(f"정성: {experiment.qualitative_summary}")
    summary_parts.append(
        f"성공 기준: {experiment.success_metric} / 목표 {experiment.target_value}"
    )

    return {
        "evidence_type": EXPERIMENT_EVIDENCE_TYPE[experiment.experiment_type],
        "title": f"[실험] {experiment.title}",
        "summary": "\n".join(summary_parts),
        "source_reference": f"experiment:{experiment.id}",
        "sample_size": experiment.actual_sample,
        "observed_at": experiment.ended_at,
        "supports": supports,
        "contradicts": contradicts,
    }
