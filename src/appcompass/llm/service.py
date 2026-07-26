"""초안 생성기 — core의 Port를 실제로 구현하는 곳.

여기가 CLAUDE.md §10.3 '출력 계약'이 강제되는 지점이다.

    1차 호출 → 스키마 검증 실패 → 1회 자동 복구 프롬프트 → 재실패 → LLMSchemaFailed

재실패하면 초안을 **버린다**. 형식이 깨진 응답에서 쓸 만한 칸만 골라 쓰는 경로는
만들지 않는다. 그런 경로가 있으면 결국 검증되지 않은 값이 화면에 올라온다.

반환값은 언제나 '초안'이다. 이 모듈은 DB를 모르고, 무엇도 저장하지 않는다.
사용자가 화면에서 칸별로 채택해야만 값이 된다 (TECHSPEC F-020).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Sequence

from ..core.models import (
    DiagnosisResult,
    IdeaStructure,
    LlmAssist,
    RawIdeaInput,
    TargetCandidate,
)
from ..core.schema import (
    IDEA_STRUCTURE_DRAFT_SCHEMA,
    TARGET_CANDIDATES_DRAFT_SCHEMA,
    SchemaValidationError,
    load_schema,
    validate_payload,
)
from . import prompts
from .client import AnthropicTransport, Transport
from .config import LLMConfig, load_config
from .errors import LLMNotConfigured, LLMSchemaFailed

TASK_IDEA_STRUCTURE = "IDEA_STRUCTURE"
TASK_TARGET_CANDIDATES = "TARGET_CANDIDATES"

#: 초안이 채울 수 있는 칸. IdeaStructure의 부분집합이며 app_name은 제외한다
#: (앱 이름은 사용자가 정하는 것이지 추론할 대상이 아니다).
DRAFTABLE_FIELDS: tuple[str, ...] = (
    "target_user",
    "payer",
    "influencer",
    "problem_situation",
    "current_solution",
    "current_solution_problem",
    "core_action",
    "expected_result",
    "first_success",
    "retention_reason",
    "revenue_model",
    "distribution_channel",
)

BASIS_LABELS = {
    "FROM_RAW_TEXT": "원문에 있음",
    "INFERRED": "AI 추측 — 확인 필요",
    "MISSING": "원문에 없음",
}


@dataclass(frozen=True, slots=True)
class DraftNote:
    """칸 하나가 어디서 왔는지. 추측을 사실처럼 보이지 않게 하는 장치다."""

    field: str
    basis: str
    reason: str = ""

    @property
    def basis_label(self) -> str:
        return BASIS_LABELS.get(self.basis, self.basis)

    @property
    def needs_review(self) -> bool:
        return self.basis == "INFERRED"


@dataclass(frozen=True, slots=True)
class StructureDraft:
    """구조화 초안. 저장되지 않은 제안이다."""

    fields: dict[str, str]
    unknowns: tuple[str, ...]
    notes: tuple[DraftNote, ...]
    assist: LlmAssist

    def note_for(self, field: str) -> DraftNote | None:
        for note in self.notes:
            if note.field == field:
                return note
        return None

    def filled_fields(self) -> tuple[str, ...]:
        return tuple(k for k in DRAFTABLE_FIELDS if (self.fields.get(k) or "").strip())

    def apply_to(
        self, base: IdeaStructure, accepted: Sequence[str]
    ) -> tuple[IdeaStructure, LlmAssist]:
        """사용자가 고른 칸만 반영한 새 IdeaStructure와, 그 사실의 기록을 함께 준다.

        고르지 않은 칸은 손대지 않는다. 초안을 열었다는 이유만으로
        사용자가 이미 쓴 내용이 사라지면 안 된다.
        """
        accepted_keys = tuple(k for k in accepted if k in DRAFTABLE_FIELDS)
        changes: dict[str, Any] = {}
        for key in accepted_keys:
            value = (self.fields.get(key) or "").strip()
            # payer/influencer 등 Optional 칸은 빈 값을 None으로 둔다.
            nullable = key not in (
                "target_user",
                "problem_situation",
                "core_action",
                "expected_result",
            )
            changes[key] = (value or None) if nullable else value

        merged_unknowns = tuple(
            dict.fromkeys(tuple(base.unknowns) + tuple(self.unknowns))
        )
        idea = replace(base, unknowns=merged_unknowns, **changes)
        return idea, replace(self.assist, accepted_fields=accepted_keys)


@dataclass(frozen=True, slots=True)
class TargetDraft:
    """타깃 후보 초안. 저장되지 않으며 규칙 엔진 후보를 대체하지 않는다."""

    candidates: tuple[TargetCandidate, ...]
    assist: LlmAssist


class DraftAssistant:
    """StructurerPort / TargetCandidatePort 구현체."""

    name = "anthropic"
    version = "0.1.0"

    def __init__(self, transport: Transport, config: LLMConfig | None = None) -> None:
        self._transport = transport
        self._config = config
        self.prompt_version = prompts.PROMPT_VERSION

    # -- 구조화 -----------------------------------------------------------
    def draft_structure(
        self, raw: RawIdeaInput, domain_label: str = "일반"
    ) -> StructureDraft:
        payload = self._call(
            system=prompts.structure_system_prompt(),
            user_message=prompts.structure_user_message(raw, domain_label),
            schema_name=IDEA_STRUCTURE_DRAFT_SCHEMA,
            schema_title="idea_structure_draft",
        )

        fields = {
            key: str(payload["fields"].get(key) or "").strip()
            for key in DRAFTABLE_FIELDS
        }
        notes = tuple(
            DraftNote(
                field=n["field"],
                basis=n["basis"],
                reason=str(n.get("reason") or "").strip(),
            )
            for n in payload.get("notes", [])
            if n.get("field") in DRAFTABLE_FIELDS
        )
        unknowns = tuple(
            u.strip() for u in payload.get("unknowns", []) if str(u).strip()
        )
        return StructureDraft(
            fields=fields,
            unknowns=unknowns,
            notes=notes,
            assist=self._assist(TASK_IDEA_STRUCTURE),
        )

    def propose_structure(self, raw: RawIdeaInput) -> IdeaStructure:
        """StructurerPort 구현.

        초안을 그대로 IdeaStructure로 만든다. 사용자 승인을 거치지 않는 경로이므로
        UI는 이것을 쓰지 않고 draft_structure를 쓴다. 배치 처리나 향후 API 서버가
        Port 계약대로 호출할 때를 위해 남겨 둔다.
        """
        draft = self.draft_structure(raw)
        idea, _ = draft.apply_to(
            IdeaStructure(app_name=raw.app_name), draft.filled_fields()
        )
        return idea

    # -- 타깃 후보 --------------------------------------------------------
    def draft_targets(
        self,
        idea: IdeaStructure,
        diagnosis: DiagnosisResult | None = None,
        domain_label: str = "일반",
    ) -> TargetDraft:
        warnings = (
            [f"[{w.severity}] {w.message}" for w in diagnosis.warnings]
            if diagnosis
            else []
        )
        payload = self._call(
            system=prompts.target_system_prompt(),
            user_message=prompts.target_user_message(idea, domain_label, warnings),
            schema_name=TARGET_CANDIDATES_DRAFT_SCHEMA,
            schema_title="target_candidates_draft",
        )

        candidates = tuple(
            TargetCandidate(
                name=str(c.get("name") or "").strip() or "이름 없는 후보",
                user=str(c.get("user") or "").strip(),
                payer=(str(c.get("payer") or "").strip() or None),
                influencer=(str(c.get("influencer") or "").strip() or None),
                trigger_situation=str(c.get("trigger_situation") or "").strip(),
                problem=str(c.get("problem") or "").strip(),
                current_alternative=(
                    str(c.get("current_alternative") or "").strip() or None
                ),
                why_promising=tuple(
                    s.strip() for s in c.get("why_promising", []) if str(s).strip()
                ),
                risks=tuple(s.strip() for s in c.get("risks", []) if str(s).strip()),
                validation_questions=tuple(
                    s.strip()
                    for s in c.get("validation_questions", [])
                    if str(s).strip()
                ),
                # 실험은 규칙 엔진(core.experiment)이 정한다. LLM에게 맡기지 않는다.
                recommended_experiment="",
            )
            for c in payload.get("candidates", [])
        )
        return TargetDraft(
            candidates=candidates, assist=self._assist(TASK_TARGET_CANDIDATES)
        )

    def propose_candidates(
        self, idea: IdeaStructure, diagnosis: DiagnosisResult
    ) -> Sequence[TargetCandidate]:
        """TargetCandidatePort 구현."""
        return self.draft_targets(idea, diagnosis).candidates

    # -- 공통 -------------------------------------------------------------
    def _assist(self, task: str) -> LlmAssist:
        return LlmAssist(
            provider=self._transport.provider,
            model=self._transport.model,
            prompt_version=prompts.PROMPT_VERSION,
            task=task,
            accepted_fields=(),
            created_at=datetime.now(timezone.utc),
        )

    def _call(
        self,
        *,
        system: str,
        user_message: str,
        schema_name: str,
        schema_title: str,
    ) -> dict[str, Any]:
        """1차 호출 → 검증 → (실패 시) 1회 복구 → 재검증 (CLAUDE.md §10.3)."""
        schema = load_schema(schema_name)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        raw = self._transport.complete_json(
            system=system,
            messages=messages,
            schema=schema,
            schema_title=schema_title,
        )
        try:
            validate_payload(schema_name, raw)
            return raw
        except SchemaValidationError as first:
            errors = list(first.errors)

        # 복구 프롬프트는 직전 응답을 assistant 턴으로 되돌려 준 뒤,
        # 무엇이 틀렸는지만 알려 준다. 새 내용을 요구하지 않는다.
        import json as _json

        messages.extend(
            [
                {"role": "assistant", "content": _json.dumps(raw, ensure_ascii=False)},
                {"role": "user", "content": prompts.repair_prompt(errors)},
            ]
        )
        repaired = self._transport.complete_json(
            system=system,
            messages=messages,
            schema=schema,
            schema_title=schema_title,
        )
        try:
            validate_payload(schema_name, repaired)
        except SchemaValidationError as second:
            raise LLMSchemaFailed(
                "AI 응답이 형식 검증을 두 번 통과하지 못해 초안을 버렸습니다. "
                "검증되지 않은 값으로는 어떤 칸도 채우지 않습니다.",
                errors=list(second.errors),
            ) from second
        return repaired


def build_assistant(config: LLMConfig | None = None) -> DraftAssistant:
    """설정에서 어시스턴트를 만든다. 키가 없으면 LLMNotConfigured."""
    cfg = config or load_config()
    if not cfg.is_configured:
        raise LLMNotConfigured("API 키가 설정되지 않았습니다.")
    return DraftAssistant(AnthropicTransport(cfg), cfg)
