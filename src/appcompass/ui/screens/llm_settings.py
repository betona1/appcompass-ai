"""화면: AI 도우미 설정.

두 가지만 한다.
    1. API 키를 설정한다.
    2. AI가 무엇을 하고 무엇을 하지 않는지 분명히 알린다.

두 번째가 첫 번째만큼 중요하다. 이 앱의 핵심 주장은 "AI가 정답을 정하지 않는다"인데,
설정 화면에 'AI 켜기' 토글만 있으면 사용자는 켜는 순간 AI가 판정한다고 믿는다.
그래서 경계를 화면에 못 박아 둔다 (CLAUDE.md §10, ADR-0002).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...llm.config import (
    DEFAULT_MODEL,
    ENV_API_KEY,
    clear_api_key,
    env_file_path,
    load_config,
    save_api_key,
)
from ...llm.errors import LLMError
from ..context import ScreenContext
from ..widgets import Banner, BulletList, h1, h2, hint, scrollable
from .base import ScreenBase

_MODELS = (
    ("claude-opus-5", "가장 정확 — 기본값"),
    ("claude-sonnet-5", "빠르고 저렴"),
    ("claude-haiku-4-5", "가장 저렴 (초안 품질은 떨어집니다)"),
)

_DOES = [
    "원문을 읽고 구조화 12칸의 초안을 제안합니다",
    "확인이 필요한 것(언노운)을 뽑아냅니다",
    "다른 타깃 후보를 제안합니다",
]

_DOES_NOT = [
    "점수를 계산하지 않습니다 — 규칙 엔진이 계산합니다",
    "근거 신뢰도를 계산하지 않습니다 — 등록된 근거의 종류로 결정됩니다",
    "유지·수정·피벗을 판단하지 않습니다 — 규칙 엔진이 판정합니다",
    "근거를 만들지 않습니다 — 근거는 사람이 등록한 것만 존재합니다",
    "승인 없이 아무 칸도 덮어쓰지 않습니다 — 칸마다 직접 고릅니다",
]


class LlmSettingsScreen(ScreenBase):
    title = "AI 도우미"
    purpose = "AI는 초안만 만듭니다. 판단은 규칙 엔진과 사람이 합니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        self.status_banner = Banner("", "info")
        layout.addWidget(self.status_banner)

        # --- 경계 먼저 ---
        boundary = QGroupBox("AI의 역할 범위")
        b_layout = QHBoxLayout(boundary)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(h2("합니다"))
        left_layout.addWidget(BulletList(_DOES, ""))
        left_layout.addStretch(1)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(h2("하지 않습니다"))
        right_layout.addWidget(BulletList(_DOES_NOT, ""))
        right_layout.addStretch(1)
        b_layout.addWidget(left, 1)
        b_layout.addWidget(right, 1)
        layout.addWidget(boundary)

        layout.addWidget(
            hint(
                "AI 초안을 쓰지 않아도 이 앱의 모든 기능은 그대로 동작합니다. "
                "초안은 12칸을 처음부터 채우는 부담을 줄이기 위한 보조일 뿐입니다."
            )
        )

        # --- 키 설정 ---
        key_box = QGroupBox("API 키")
        form = QFormLayout(key_box)

        self.key_state = QLabel("-")
        self.key_state.setWordWrap(True)
        form.addRow("현재 상태", self.key_state)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-ant-... (붙여넣으면 화면에 보이지 않습니다)")
        form.addRow("새 키", self.key_input)

        self.model_box = QComboBox()
        for value, note in _MODELS:
            self.model_box.addItem(f"{value} — {note}", value)
        form.addRow("모델", self.model_box)

        layout.addWidget(key_box)

        row = QHBoxLayout()
        row.addStretch(1)
        self.clear_button = QPushButton("저장된 키 지우기")
        self.clear_button.clicked.connect(self._clear)
        self.save_button = QPushButton("저장")
        self.save_button.setObjectName("Primary")
        self.save_button.clicked.connect(self._save)
        row.addWidget(self.clear_button)
        row.addWidget(self.save_button)
        layout.addLayout(row)

        layout.addWidget(
            hint(
                f"키는 <code>{env_file_path()}</code> 에 <b>평문으로</b> 저장됩니다. "
                "이 PC를 다른 사람과 함께 쓴다면 파일에 저장하지 말고, "
                f"환경변수 <code>{ENV_API_KEY}</code> 로 넣으세요. "
                "환경변수가 항상 파일보다 우선합니다.<br>"
                "키는 프로젝트 데이터베이스에 저장되지 않으므로, "
                "기획서를 내보내거나 백업해도 함께 나가지 않습니다."
            )
        )

        cost = QGroupBox("비용과 보내지는 내용")
        cost_layout = QVBoxLayout(cost)
        cost_layout.addWidget(
            BulletList(
                [
                    "초안 버튼을 누를 때만 호출됩니다. 화면을 열어 두는 것만으로는 호출되지 않습니다.",
                    "보내지는 것: 해당 버전의 원문 또는 구조화 결과, 도메인 이름.",
                    "보내지 않는 것: 등록한 근거, 실험 기록, 점수, 다른 프로젝트의 내용.",
                    "요금은 Anthropic 계정으로 청구됩니다. 이 앱은 결제에 관여하지 않습니다.",
                ],
                "",
            )
        )
        layout.addWidget(cost)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(body))

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        status = ctx.service.llm_status()

        if status.available:
            self.status_banner.set_text(
                f"사용 가능합니다 — 모델 {status.model}, 사고 강도 {status.effort}", "ok"
            )
        elif not status.sdk_installed:
            self.status_banner.set_text(
                "anthropic 패키지가 설치되어 있지 않아 AI 초안을 쓸 수 없습니다.\n"
                "터미널에서 pip install anthropic 을 실행한 뒤 앱을 다시 시작하세요.",
                "critical",
            )
        else:
            self.status_banner.set_text(
                "API 키가 없어 AI 초안이 꺼져 있습니다. 아래에서 키를 넣으면 켜집니다. "
                "키가 없어도 나머지 기능은 모두 정상 동작합니다.",
                "info",
            )

        if status.key_configured:
            self.key_state.setText(
                f"설정됨 — {status.masked_key}　(출처: {status.key_source})"
            )
        else:
            self.key_state.setText("설정되지 않음")

        index = self.model_box.findData(status.model)
        self.model_box.setCurrentIndex(index if index >= 0 else 0)
        self.key_input.clear()

    # -- 동작 -------------------------------------------------------------
    def _save(self) -> None:
        key = self.key_input.text().strip()
        model = self.model_box.currentData() or DEFAULT_MODEL

        if not key:
            # 키 없이 모델만 바꾸는 경우. 이미 저장된 키가 있어야 의미가 있다.
            if not load_config().is_configured:
                self.status_banner.set_text("API 키를 입력하세요.", "critical")
                return
            key = load_config().api_key

        try:
            path = save_api_key(key, model)
        except LLMError as exc:
            self.status_banner.set_text(str(exc), "critical")
            return
        except OSError as exc:
            self.status_banner.set_text(f"파일을 저장하지 못했습니다: {exc}", "critical")
            return

        self.key_input.clear()
        self.status_message.emit(f"AI 설정을 저장했습니다 ({path.name})")
        self.data_changed.emit()
        if self._ctx is not None:
            self.refresh(self._ctx)

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "저장된 키 지우기",
            f"{env_file_path()} 에서 API 키를 지웁니다.\n"
            "AI 초안 기능이 꺼지고, 나머지 기능은 그대로 동작합니다. 계속할까요?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            removed = clear_api_key()
        except OSError as exc:
            self.status_banner.set_text(f"파일을 고치지 못했습니다: {exc}", "critical")
            return

        if removed is None:
            self.status_banner.set_text(
                "이 파일에 저장된 키가 없습니다. 환경변수로 넣은 키는 여기서 지울 수 없습니다.",
                "info",
            )
        else:
            self.status_message.emit("저장된 API 키를 지웠습니다.")
        self.data_changed.emit()
        if self._ctx is not None:
            self.refresh(self._ctx)
