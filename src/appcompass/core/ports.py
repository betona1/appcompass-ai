"""외부 추론기(LLM) 연결 지점.

CLAUDE.md §7.3 "LLM 호출과 규칙 엔진을 분리".
core는 이 프로토콜만 알고, 구현체는 `appcompass.llm` 패키지에 있다.
core가 llm을 import하지 않으므로 LLM을 통째로 제거해도 분석 엔진은 그대로 돈다.

구현체가 지켜야 할 것 (llm/service.py에서 강제된다):
- 사용자 입력을 시스템 명령으로 취급하지 않는다 → llm/prompts.py의 데이터 태그
- 결과는 반드시 JSON Schema 검증을 통과한다 → schemas/*_draft-*.json, 1회 복구 후 폐기
- 점수·신뢰도·피벗 판정은 절대 LLM에 위임하지 않는다 → 반환 타입에 그 필드가 없다
- 모델·프롬프트 버전을 AnalysisMeta에 기록한다 → core.models.LlmAssist
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from .models import (
    DiagnosisResult,
    IdeaStructure,
    MvpPlan,
    RawIdeaInput,
    TargetCandidate,
)


@runtime_checkable
class StructurerPort(Protocol):
    """자유 입력 → 구조화 초안.

    반환값은 '초안'이다. 사용자 승인 전에는 원문을 덮어쓰지 않는다 (TECHSPEC F-020).
    """

    name: str
    version: str

    def propose_structure(self, raw: RawIdeaInput) -> IdeaStructure: ...


@runtime_checkable
class TargetCandidatePort(Protocol):
    """타깃 후보 생성기. 규칙 엔진이 제약을 검사한 뒤에만 채택한다."""

    name: str
    version: str

    def propose_candidates(
        self, idea: IdeaStructure, diagnosis: DiagnosisResult
    ) -> Sequence[TargetCandidate]: ...


@runtime_checkable
class MvpPlannerPort(Protocol):
    """MVP 초안 생성기. 도메인 모듈의 constrain_mvp를 반드시 거친다."""

    name: str
    version: str

    def propose_plan(
        self, idea: IdeaStructure, diagnosis: DiagnosisResult
    ) -> MvpPlan: ...


class ManualStructurer:
    """Phase 1 기본 구현: 사람이 채운 구조화 결과를 그대로 사용한다.

    자유 입력을 자동으로 해석하지 않는다. 잘못된 초안이 사용자의 판단을
    오염시키는 것보다, 사용자가 직접 채우게 하는 편이 안전하다.
    """

    name = "manual"
    version = "1.0.0"

    def propose_structure(self, raw: RawIdeaInput) -> IdeaStructure:
        return IdeaStructure(
            app_name=raw.app_name,
            target_user=raw.target_user_raw,
            problem_situation=raw.problem_raw,
            core_action=raw.solution_raw,
            revenue_model=raw.revenue_model_raw or None,
            distribution_channel=raw.distribution_channel_raw or None,
        )
