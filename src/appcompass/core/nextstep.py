"""다음 할 일 판정.

이 도구는 화면이 9개고 개념도 많다. 처음 쓰는 사람은 "그래서 지금 뭘 해야 하지"에서 막힌다.
그 막막함을 없애는 것이 이 모듈의 목적이다.

원칙은 하나다. **한 번에 하나만 시킨다.**
할 일을 다섯 개 늘어놓으면 결국 아무것도 안 하게 된다.
지금 가장 중요한 것 하나만 고르고, 나머지는 그것이 끝난 뒤에 보여준다.

판정은 규칙이다. LLM을 쓰지 않는다. 같은 상태면 항상 같은 안내가 나온다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import (
    DimensionCode,
    DomainCode,
    PivotDecision,
    ProjectStage,
    Severity,
    WarningCode,
)
from .policy import EvaluationPolicy

#: 기획을 마무리하기까지의 여정. 진행률 표시에 쓴다.
JOURNEY: tuple[tuple[str, str], ...] = (
    ("PROJECT", "프로젝트 만들기"),
    ("IDEA", "아이디어 적기"),
    ("STRUCTURE", "구조화 채우기"),
    ("ANALYZE", "승인하고 분석"),
    ("FIX_CRITICAL", "치명 문제 해소"),
    ("EVIDENCE", "근거 등록"),
    ("DECIDE", "판단 확정"),
    ("FINISH", "기획 마무리"),
)
_JOURNEY_INDEX = {code: i for i, (code, _label) in enumerate(JOURNEY)}


@dataclass(frozen=True, slots=True)
class ProjectState:
    """다음 할 일을 정하는 데 필요한 현재 상태."""

    has_project: bool = False
    project_name: str = ""
    domain_code: DomainCode = DomainCode.GENERIC
    stage: ProjectStage = ProjectStage.IDEA
    has_version: bool = False
    version_no: int | None = None
    missing_required: tuple[tuple[str, str, str], ...] = ()
    structure_approved: bool = False
    has_analysis: bool = False
    analysis_failed: bool = False
    analysis_error: str | None = None
    result: dict[str, Any] | None = None
    evidence_count: int = 0
    feature_total: int = 0
    feature_built: int = 0
    pivot_pending: bool = False
    pivot_decision_id: str | None = None


@dataclass(frozen=True, slots=True)
class NextStep:
    """지금 할 일 하나."""

    step_id: str
    stage_code: str
    title: str
    why: str
    how: tuple[str, ...] = ()
    screen: str = ""
    button_text: str = ""
    is_blocking: bool = True
    is_done: bool = False

    @property
    def stage_index(self) -> int:
        return _JOURNEY_INDEX.get(self.stage_code, 0)

    @property
    def stage_label(self) -> str:
        for code, label in JOURNEY:
            if code == self.stage_code:
                return label
        return ""


def decide_next_step(
    state: ProjectState, policy: EvaluationPolicy | None = None
) -> NextStep:
    """지금 가장 중요한 할 일 하나를 고른다. 위에서부터 먼저 걸리는 것이 답이다."""

    policy = policy or EvaluationPolicy()

    # 1. 프로젝트 --------------------------------------------------------
    if not state.has_project:
        return NextStep(
            step_id="CREATE_PROJECT",
            stage_code="PROJECT",
            title="프로젝트를 만드세요",
            why="아이디어를 담을 곳이 있어야 시작할 수 있습니다.",
            how=(
                "왼쪽 아래 '새 프로젝트'를 누릅니다.",
                "이름은 가칭이어도 됩니다. 나중에 바꿀 수 있습니다.",
                "도메인을 고르면 그 분야의 경고와 금지 기능이 자동으로 적용됩니다.",
            ),
            screen="",
            button_text="",
        )

    # 2. 아이디어 원문 ----------------------------------------------------
    if not state.has_version:
        return NextStep(
            step_id="WRITE_IDEA",
            stage_code="IDEA",
            title="아이디어를 그대로 적으세요",
            why=(
                "다듬지 않아도 됩니다. 여기 적은 원문은 이후 어떤 경우에도 수정되지 않습니다. "
                "정리는 다음 단계에서 합니다."
            ),
            how=(
                "'A. 아이디어 입력' 화면으로 갑니다.",
                "떠오르는 대로 적습니다. 예상 사용자에 '모든 사람'이라고 써도 괜찮습니다.",
                "다 적었으면 '새 버전으로 저장하고 구조화로 이동'을 누릅니다.",
            ),
            screen="idea",
            button_text="A. 아이디어 입력으로 가기",
        )

    # 3. 구조화 필수 항목 --------------------------------------------------
    if state.missing_required:
        first = state.missing_required[0]
        others = len(state.missing_required) - 1
        return NextStep(
            step_id="FILL_REQUIRED",
            stage_code="STRUCTURE",
            title=f"'{first[1]}' 칸을 채우세요"
            + (f" (그 외 {others}개 더)" if others else ""),
            why=first[2],
            how=(
                "'B. 구조화 검토' 화면으로 갑니다.",
                f"빨간 별표(*)가 붙은 칸을 채웁니다. 지금 비어 있는 것: "
                + ", ".join(label for _k, label, _w in state.missing_required),
                "오른쪽 경고를 보면서 고치면 경고가 줄어듭니다.",
            ),
            screen="structure",
            button_text="B. 구조화 검토로 가기",
        )

    # 4. 승인과 분석 ------------------------------------------------------
    if not state.structure_approved:
        return NextStep(
            step_id="APPROVE",
            stage_code="ANALYZE",
            title="구조화 결과를 승인하고 분석을 실행하세요",
            why=(
                "필수 항목이 다 찼습니다. 승인하면 이 버전이 잠기고 기록으로 남습니다. "
                "이후 수정은 새 버전으로 만들어집니다."
            ),
            how=(
                "'B. 구조화 검토' 화면 아래 '승인하고 분석 실행'을 누릅니다.",
                "치명 경고가 남아 있어도 승인할 수 있습니다. 확인 창이 한 번 뜹니다.",
            ),
            screen="structure",
            button_text="B. 구조화 검토로 가기",
        )

    if state.analysis_failed:
        return NextStep(
            step_id="ANALYSIS_FAILED",
            stage_code="ANALYZE",
            title="분석이 실패했습니다",
            why=f"원인: {state.analysis_error or '알 수 없음'}",
            how=(
                "'분석 실행'을 다시 눌러 봅니다.",
                "계속 실패하면 프로그램 결함일 수 있습니다. 오류 내용과 함께 알려주세요.",
            ),
            screen="diagnosis",
            button_text="C. 자동 진단으로 가기",
        )

    if not state.has_analysis or state.result is None:
        return NextStep(
            step_id="RUN_ANALYSIS",
            stage_code="ANALYZE",
            title="분석을 실행하세요",
            why="승인은 끝났습니다. 이제 규칙 엔진이 점수와 판단을 계산합니다.",
            how=("오른쪽 위 '분석 실행' 버튼을 누릅니다. 몇 초면 끝납니다.",),
            screen="",
            button_text="",
        )

    result = state.result
    diag = result["diagnosis"]
    pivot = result["pivot"]

    # 5. 치명 경고 --------------------------------------------------------
    criticals = [w for w in diag["warnings"] if w["severity"] == str(Severity.CRITICAL)]
    # 근거 부족은 6단계에서 따로 다룬다. 여기서 겹쳐 보여주면 혼란스럽다.
    criticals = [w for w in criticals if w["code"] != str(WarningCode.LOW_EVIDENCE)]
    if criticals:
        w = criticals[0]
        others = len(criticals) - 1
        return NextStep(
            step_id="FIX_CRITICAL",
            stage_code="FIX_CRITICAL",
            title=f"치명 문제를 고치세요: {w['message'].split('.')[0]}"
            + (f" (그 외 {others}개 더)" if others else ""),
            why=(
                "치명으로 표시된 것은 이걸 두고 다음으로 가면 나머지 판단이 전부 흔들리는 문제입니다. "
                f"{w['message']}"
            ),
            how=(
                f"→ {w['recommended_action']}",
                "'B. 구조화 검토'에서 '새 버전 만들어 수정하기'로 고칩니다.",
                "고친 뒤 다시 승인하고 분석하면 경고가 사라집니다.",
            ),
            screen="structure",
            button_text="B. 구조화 검토로 가기",
        )

    # 6. 근거 ------------------------------------------------------------
    confidence = diag["overall_confidence"]
    if state.evidence_count == 0:
        return NextStep(
            step_id="ADD_EVIDENCE",
            stage_code="EVIDENCE",
            title="실제로 물어본 것을 근거로 등록하세요",
            why=(
                "지금 판단은 '판단 보류(HOLD)'입니다. 기획서를 잘 쓴 것과 검증된 것은 다릅니다. "
                "등록된 근거가 없으면 신뢰도가 0.20을 넘지 못하고 판단을 확정할 수 없습니다."
            ),
            how=(
                "'F. 실험' 화면에 검증되지 않은 가설별로 구체적인 실험이 제안돼 있습니다.",
                "가장 위 실험(대개 인터뷰 5명, 30분)을 '이 실험 시작하기'로 시작합니다.",
                "실제로 물어본 뒤 결과를 적고 '근거로 등록하고 재분석'을 누릅니다.",
                "직접 등록하려면 '근거' 화면에서 '예시로 양식 채우기'로 형식을 확인하세요.",
            ),
            screen="experiments",
            button_text="F. 실험으로 가기",
        )

    if confidence < policy.hold_threshold:
        weak = sorted(
            (d for d in diag["dimensions"] if d.get("missing_evidence")),
            key=lambda d: (d["raw_score"], -d["weight"]),
        )
        target = weak[0] if weak else None
        return NextStep(
            step_id="MORE_EVIDENCE",
            stage_code="EVIDENCE",
            title="근거가 조금 더 필요합니다",
            why=(
                f"근거 {state.evidence_count}건이 등록됐지만 전체 신뢰도가 "
                f"{confidence:.2f}로 기준 {policy.hold_threshold:.2f}에 못 미칩니다."
            ),
            how=(
                (
                    f"가장 비어 있는 항목: {target['label']} — "
                    f"{', '.join(target['missing_evidence'])}"
                    if target
                    else "비어 있는 평가 항목에 근거를 붙입니다."
                ),
                "'F. 실험'에서 아직 검증되지 않은 가설의 실험을 하나 더 진행하세요.",
                "실험 결과를 '근거로 등록하고 재분석'하면 신뢰도가 올라갑니다.",
            ),
            screen="experiments",
            button_text="F. 실험으로 가기",
        )

    # 7. 판단 반영 --------------------------------------------------------
    decision = pivot["decision"]
    pivot_guides: dict[str, tuple[str, str, tuple[str, ...]]] = {
        str(PivotDecision.PROBLEM_PIVOT): (
            "문제 정의를 다시 쓰세요",
            "해결책이 아니라 문제가 약합니다. 이대로 만들면 아무도 안 씁니다.",
            (
                "대상 5명에게 '최근 한 달에 몇 번 겪었는지' 직접 묻습니다.",
                "'B. 구조화 검토'에서 문제 상황을 다시 씁니다.",
            ),
        ),
        str(PivotDecision.TARGET_PIVOT): (
            "타깃을 하나로 좁히세요",
            "문제는 살아 있는데 타깃이 넓어 검증 대상을 특정할 수 없습니다.",
            (
                "'D. 타깃 후보'에서 후보를 비교합니다.",
                "이번 주에 실제로 만날 수 있는 후보 하나를 고릅니다.",
                "'B. 구조화 검토'에서 그 타깃으로 다시 씁니다.",
            ),
        ),
        str(PivotDecision.SOLUTION_PIVOT): (
            "핵심 행동을 다시 설계하세요",
            "관심은 있는데 핵심 행동이 끝까지 완료되지 않는 구조입니다.",
            (
                "첫 성공 경험을 3분 이내로 줄입니다.",
                "'B. 구조화 검토'에서 핵심 행동과 첫 성공 경험을 다시 씁니다.",
            ),
        ),
        str(PivotDecision.RETENTION_REDESIGN): (
            "다시 돌아올 이유를 만드세요",
            "핵심 행동은 되는데 재방문 이유가 약합니다.",
            ("'B. 구조화 검토'에서 재방문 이유를 제품 안의 장치로 다시 씁니다.",),
        ),
        str(PivotDecision.CHANNEL_PIVOT): (
            "첫 100명을 만날 채널을 정하세요",
            "제품 조건은 갖췄는데 사람을 데려올 경로가 약합니다.",
            ("채널 한 곳을 정해 소규모로 테스트합니다.",),
        ),
        str(PivotDecision.REVENUE_PIVOT): (
            "왜 돈을 낼지 정리하세요",
            "쓰기는 하는데 대체재 대비 차별점이 약해 지불 근거가 부족합니다.",
            ("현재 대체재가 실패하는 지점을 근거와 함께 정리합니다.",),
        ),
    }
    if decision in pivot_guides:
        title, why, how = pivot_guides[decision]
        return NextStep(
            step_id=f"PIVOT_{decision}",
            stage_code="DECIDE",
            title=title,
            why=f"현재 판단은 {decision}입니다. {why}",
            how=how + ("고친 뒤 '분석 실행'을 다시 눌러 점수가 올랐는지 확인합니다.",),
            screen="targets" if decision == str(PivotDecision.TARGET_PIVOT) else "structure",
            button_text=(
                "D. 타깃 후보로 가기"
                if decision == str(PivotDecision.TARGET_PIVOT)
                else "B. 구조화 검토로 가기"
            ),
        )

    # 8. 사람의 승인 ------------------------------------------------------
    # 시스템은 판단을 제안할 뿐이다. 사람이 확인해야 다음으로 넘어간다.
    if state.pivot_pending:
        return NextStep(
            step_id="APPROVE_PIVOT",
            stage_code="DECIDE",
            title=f"판단을 검토하고 승인하거나 거절하세요: {decision}",
            why=(
                "근거가 판단을 뒷받침하는 상태입니다. 시스템은 제안만 하고 적용하지 않습니다. "
                "사람이 확인해야 기록이 남습니다."
            ),
            how=(
                "'G. 피벗 보고서' 화면의 '사람의 결정'에서 내용을 확인합니다.",
                "동의하면 '승인'을, 다르게 판단했다면 사유를 적고 '거절'을 누릅니다.",
                "거절 사유는 나중에 그 판단이 옳았는지 되짚는 근거가 됩니다.",
            ),
            screen="report",
            button_text="G. 피벗 보고서로 가기",
        )

    # 9. 마무리 ----------------------------------------------------------
    weakest = min(diag["dimensions"], key=lambda d: (d["raw_score"], -d["weight"]))
    if decision == str(PivotDecision.REFINE) and weakest["raw_score"] <= 3:
        return NextStep(
            step_id="REFINE_WEAKEST",
            stage_code="DECIDE",
            title=f"가장 약한 항목을 보완하세요: {weakest['label']}",
            why=(
                f"큰 방향은 맞습니다. 다만 {weakest['label']}이(가) "
                f"{weakest['raw_score']}/5로 낮습니다."
            ),
            how=(
                f"→ {weakest['recommended_action']}",
                "'B. 구조화 검토'에서 새 버전을 만들어 고칩니다.",
            ),
            screen="structure",
            button_text="B. 구조화 검토로 가기",
            is_blocking=False,
        )

    # 이미 만든 MVP가 있으면 개선으로, 아니면 구현 착수로 안내한다.
    if state.stage in (ProjectStage.MVP, ProjectStage.LIVE):
        if state.feature_total and state.feature_built == 0:
            return NextStep(
                step_id="MARK_BUILT",
                stage_code="FINISH",
                title="이미 만든 기능을 표시하세요",
                why=(
                    "프로젝트 단계가 MVP 이상인데 구현된 기능이 표시되지 않았습니다. "
                    "무엇을 만들었는지 알아야 무엇을 고칠지 알려드릴 수 있습니다."
                ),
                how=(
                    "'E. MVP' 화면 '기능별 구현 상태'에서 만든 기능을 '구현됨'으로 바꿉니다.",
                    "실제로 겪은 문제가 있으면 '관찰된 문제' 칸에 적습니다.",
                    "'구현 상태 저장'을 누릅니다.",
                ),
                screen="mvp",
                button_text="E. MVP로 가기",
                is_blocking=False,
            )
        return NextStep(
            step_id="EXPORT_IMPROVEMENT",
            stage_code="FINISH",
            title="개선 명세를 내보내 다음 버전을 시작하세요",
            why=(
                "판단이 확정됐고 구현 현황도 있습니다. "
                "이제 무엇을 유지하고 무엇을 고칠지 문서로 뽑을 수 있습니다."
            ),
            how=(
                "'G. 피벗 보고서'에서 형식을 '개선 명세'로 고릅니다.",
                "'파일로 내보내기'를 누릅니다.",
                "문서의 [결정 필요] 칸을 채운 뒤 개발에 넘깁니다.",
            ),
            screen="report",
            button_text="G. 피벗 보고서로 가기",
            is_blocking=False,
            is_done=True,
        )

    return NextStep(
        step_id="EXPORT_TECHSPEC",
        stage_code="FINISH",
        title="기획이 마무리됐습니다. 기술 명세를 내보내세요",
        why=(
            f"판단은 {decision}, 총점 {diag['total_score']:.1f}점, "
            f"신뢰도 {confidence:.2f}입니다. 근거가 판단을 뒷받침하고 있습니다."
        ),
        how=(
            "'G. 피벗 보고서'에서 형식을 '기술 명세 TECHSPEC'으로 고릅니다.",
            "'파일로 내보내기'를 누릅니다.",
            "문서에 남은 [결정 필요] 칸을 채운 뒤 개발을 시작합니다.",
            "만든 뒤에는 'E. MVP'에서 구현 상태를 표시하면 개선 명세를 받을 수 있습니다.",
        ),
        screen="report",
        button_text="G. 피벗 보고서로 가기",
        is_blocking=False,
        is_done=True,
    )
