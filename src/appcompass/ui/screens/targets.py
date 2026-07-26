"""화면 D: 타깃 후보.

주목적 하나 — 후보를 비교해 다음에 검증할 타깃 하나를 고르는 것.
근거가 부족하면 추천하지 않고 비교만 제공한다 (TECHSPEC F-060).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..context import ScreenContext
from ..widgets import (
    Banner,
    BulletList,
    EmptyState,
    clear_layout,
    h1,
    h2,
    hint,
    scrollable,
)
from ..workers import LlmDraftWorker
from .base import ScreenBase


class TargetsScreen(ScreenBase):
    title = "D. 타깃 후보"
    purpose = "후보를 비교하고, 이번 주에 실제로 만날 수 있는 타깃 하나를 고릅니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._worker: LlmDraftWorker | None = None

        self.empty = EmptyState(
            "분석 결과가 없습니다",
            "분석을 실행하면 타깃 후보가 생성됩니다.",
        )

        self.inner = QWidget()
        self.layout_ = QVBoxLayout(self.inner)
        self.layout_.setContentsMargins(18, 16, 18, 16)
        self.layout_.addWidget(h1(self.title))
        self.layout_.addWidget(hint(self.purpose))
        self.banner = Banner("", "info")
        self.layout_.addWidget(self.banner)
        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.cards_host)

        # --- AI가 제안하는 추가 후보 ---
        # 규칙 엔진 후보를 대체하지 않는다. 아래에 따로 쌓아 '초안'임을 분명히 한다.
        self.layout_.addWidget(h2("AI가 제안하는 다른 후보"))
        row = QHBoxLayout()
        self.draft_button = QPushButton("다른 후보 제안받기")
        self.draft_button.clicked.connect(self._request_draft)
        row.addWidget(self.draft_button)
        self.draft_hint = QLabel("")
        self.draft_hint.setObjectName("Hint")
        self.draft_hint.setWordWrap(True)
        row.addWidget(self.draft_hint, 1)
        self.layout_.addLayout(row)

        self.llm_host = QWidget()
        self.llm_layout = QVBoxLayout(self.llm_host)
        self.llm_layout.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.llm_host)
        self.layout_.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scrollable(self.inner)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll)

    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        result = ctx.result
        self.empty.setVisible(result is None)
        self.scroll.setVisible(result is not None)
        if result is None:
            return

        self._refresh_draft_controls()

        targets = result["targets"]
        recommended = targets["recommended_candidate_index"]
        self.banner.set_text(
            targets["recommendation_reason"],
            "ok" if recommended is not None else "info",
        )

        clear_layout(self.cards_layout)

        if not targets["candidates"]:
            self.cards_layout.addWidget(
                hint("후보가 없습니다. 구조화 화면에서 타깃을 먼저 다시 정의하세요.")
            )
            return

        for i, c in enumerate(targets["candidates"]):
            self.cards_layout.addWidget(
                _CandidateCard(i + 1, c, is_recommended=(recommended == i))
            )

    # -- AI 초안 ----------------------------------------------------------
    def _refresh_draft_controls(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.version is None:
            self.draft_button.setEnabled(False)
            return

        status = ctx.service.llm_status()
        running = self._worker is not None and self._worker.isRunning()
        self.draft_button.setEnabled(status.available and not running)
        if running:
            self.draft_hint.setText("후보를 만드는 중입니다…")
        elif not status.available:
            self.draft_hint.setText(
                f"AI 초안이 꺼져 있습니다 — {status.message} "
                "'AI 도우미' 화면에서 설정할 수 있습니다."
            )
        else:
            self.draft_hint.setText(
                "위 후보는 규칙 엔진이 만든 것입니다. AI에게 다른 각도의 후보를 물어봅니다. "
                "여기 나오는 후보는 저장되지 않으며, 쓸 만하면 'B. 구조화 검토'에 직접 옮겨 적으세요."
            )

    def _request_draft(self) -> None:
        ctx = self._ctx
        if ctx is None or ctx.version is None:
            return
        version_id = ctx.version.id
        service = ctx.service

        self._worker = LlmDraftWorker(lambda: service.draft_targets(version_id), self)
        self._worker.finished_ok.connect(self._show_draft)
        self._worker.failed.connect(self._draft_failed)
        self._worker.finished.connect(self._refresh_draft_controls)
        self._worker.start()
        self._refresh_draft_controls()
        self.status_message.emit("AI 후보를 만드는 중입니다…")

    def _draft_failed(self, message: str, next_action: str) -> None:
        clear_layout(self.llm_layout)
        text = message + (f"\n다음에 할 것: {next_action}" if next_action else "")
        banner = Banner(text, "critical")
        self.llm_layout.addWidget(banner)
        self.status_message.emit("AI 후보 생성 실패")

    def _show_draft(self, draft) -> None:
        clear_layout(self.llm_layout)
        if not draft.candidates:
            self.llm_layout.addWidget(hint("AI가 제안한 후보가 없습니다."))
            return

        self.llm_layout.addWidget(
            Banner(
                f"{draft.assist.model} 이(가) 제안한 초안 {len(draft.candidates)}건입니다. "
                "저장되지 않았고, 순위도 매기지 않았습니다. "
                "각 후보의 '검증 질문'을 실제 사용자에게 물어본 뒤에야 근거가 됩니다.",
                "info",
            )
        )
        for i, candidate in enumerate(draft.candidates):
            data = candidate.to_dict()
            data["name"] = f"[AI 초안] {data['name']}"
            self.llm_layout.addWidget(_CandidateCard(i + 1, data, is_recommended=False))


class _CandidateCard(QGroupBox):
    def __init__(self, number: int, data: dict, is_recommended: bool) -> None:
        mark = "  ★ 추천" if is_recommended else ""
        super().__init__(f"{number}. {data['name']}{mark}")
        layout = QVBoxLayout(self)

        roles = QLabel(
            f"<b>사용자</b> {data['user']}<br>"
            f"<b>구매자</b> {data.get('payer') or '-'}　　"
            f"<b>영향자</b> {data.get('influencer') or '-'}"
        )
        roles.setWordWrap(True)
        layout.addWidget(roles)

        situation = QLabel(
            f"<b>발생 상황</b> {data.get('trigger_situation') or '-'}<br>"
            f"<b>문제</b> {data.get('problem') or '-'}<br>"
            f"<b>현재 대안</b> {data.get('current_alternative') or '-'}"
        )
        situation.setWordWrap(True)
        layout.addWidget(situation)

        columns = QHBoxLayout()
        for title, key, empty in (
            ("유망한 이유", "why_promising", "근거 없음"),
            ("위험", "risks", "확인된 위험 없음"),
            ("검증 질문", "validation_questions", "질문 없음"),
        ):
            col = QWidget()
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.addWidget(h2(title))
            col_layout.addWidget(BulletList(data.get(key) or [], empty))
            col_layout.addStretch(1)
            columns.addWidget(col, 1)
        layout.addLayout(columns)

        exp = QLabel(f"<b>추천 실험</b>　{data.get('recommended_experiment') or '-'}")
        exp.setWordWrap(True)
        layout.addWidget(exp)
