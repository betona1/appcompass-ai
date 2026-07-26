"""화면: 평가 정책 (운영자용).

CLAUDE.md §11 / TECHSPEC §16: "운영자가 가중치와 임계치를 수정 가능"해야 한다.
가중치 합계 100은 저장 시 강제되며, 위반하면 저장이 거부된다.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.enums import DIMENSION_LABELS, DimensionCode, EvidenceType
from ...core.policy import EvaluationPolicy, PolicyError
from ..context import ScreenContext
from ..widgets import Banner, h1, hint, scrollable
from .base import ScreenBase

EVIDENCE_LABELS: dict[EvidenceType, str] = {
    EvidenceType.FOUNDER_ASSUMPTION: "창업자 가정",
    EvidenceType.DESK_RESEARCH: "데스크 리서치",
    EvidenceType.USER_INTERVIEW: "사용자 인터뷰",
    EvidenceType.PROTOTYPE_TEST: "프로토타입 테스트",
    EvidenceType.BEHAVIOR_DATA: "실제 행동 데이터",
    EvidenceType.EXPERT_REVIEW: "전문가 검토",
}

THRESHOLDS: tuple[tuple[str, str, str], ...] = (
    ("hold_threshold", "HOLD 임계치", "전체 신뢰도가 이 값 미만이면 판단을 확정하지 않습니다 (0~1)."),
    ("no_evidence_confidence_cap", "무근거 신뢰도 상한", "근거가 없는 항목의 신뢰도 상한 (0~1)."),
    ("conflict_penalty", "상충 감쇠 계수", "지지·반박 근거가 함께 있을 때 신뢰도를 깎는 정도 (0~1)."),
    ("problem_pivot_threshold", "문제 피벗 임계치", "D01·D02 평균이 이 값 미만이면 PROBLEM_PIVOT (0~5)."),
    ("target_pivot_threshold", "타깃 피벗 임계치", "D03이 이 값 미만이면 TARGET_PIVOT (0~5)."),
    ("solution_pivot_threshold", "해결책 피벗 임계치", "D05·D06 평균 기준 (0~5)."),
    ("retention_pivot_threshold", "재방문 재설계 임계치", "D07 기준 (0~5)."),
    ("channel_pivot_threshold", "채널 피벗 임계치", "D09 기준 (0~5)."),
    ("revenue_pivot_threshold", "수익 피벗 임계치", "D08 기준 (0~5)."),
    ("keep_score_threshold", "KEEP 총점 기준", "총점이 이 값 이상이고 위험이 없으면 KEEP (0~100)."),
)


class PolicyScreen(ScreenBase):
    title = "정책"
    purpose = "가중치와 임계치를 바꾸면 이후 분석의 판정이 달라집니다. 변경은 감사 로그에 남습니다."

    def __init__(self) -> None:
        super().__init__()
        self._ctx: ScreenContext | None = None
        self._weight_spins: dict[DimensionCode, QSpinBox] = {}
        self._evidence_spins: dict[EvidenceType, QDoubleSpinBox] = {}
        self._threshold_spins: dict[str, QDoubleSpinBox] = {}

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(h1(self.title))
        layout.addWidget(hint(self.purpose))

        self.banner = Banner("", "info")
        layout.addWidget(self.banner)

        version_box = QGroupBox("정책 버전")
        v_layout = QVBoxLayout(version_box)
        v_layout.addWidget(
            hint("모든 분석 결과와 보고서에 이 버전 문자열이 기록됩니다. 바꾸면 새 정책으로 저장됩니다.")
        )
        self.version_edit = QLineEdit()
        v_layout.addWidget(self.version_edit)
        layout.addWidget(version_box)

        weight_box = QGroupBox("평가 항목 가중치 (합계 100)")
        w_form = QFormLayout(weight_box)
        for code in DimensionCode:
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.valueChanged.connect(self._update_weight_total)
            self._weight_spins[code] = spin
            w_form.addRow(f"{code} {DIMENSION_LABELS[code]}", spin)
        self.weight_total = QLabel("-")
        self.weight_total.setObjectName("H2")
        w_form.addRow("합계", self.weight_total)
        layout.addWidget(weight_box)

        ev_box = QGroupBox("근거 유형별 기본 신뢰도")
        ev_form = QFormLayout(ev_box)
        for etype, label in EVIDENCE_LABELS.items():
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            self._evidence_spins[etype] = spin
            ev_form.addRow(label, spin)
        layout.addWidget(ev_box)

        th_box = QGroupBox("판정 임계치")
        th_form = QFormLayout(th_box)
        for key, label, tip in THRESHOLDS:
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            if key == "keep_score_threshold":
                spin.setRange(0.0, 100.0)
                spin.setSingleStep(1.0)
            elif key.endswith("pivot_threshold"):
                spin.setRange(0.0, 5.0)
            else:
                spin.setRange(0.0, 1.0)
            spin.setToolTip(tip)
            self._threshold_spins[key] = spin
            th_form.addRow(label, spin)
            th_form.addRow("", hint(tip))
        layout.addWidget(th_box)

        row = QHBoxLayout()
        row.addStretch(1)
        self.reset_button = QPushButton("기본값으로 되돌리기")
        self.reset_button.clicked.connect(self._reset)
        self.save_button = QPushButton("정책 저장")
        self.save_button.setObjectName("Primary")
        self.save_button.clicked.connect(self._save)
        row.addWidget(self.reset_button)
        row.addWidget(self.save_button)
        layout.addLayout(row)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(inner))

    # -- 상태 반영 --------------------------------------------------------
    def refresh(self, ctx: ScreenContext) -> None:
        self._ctx = ctx
        self._load(ctx.service.get_policy())

    def _load(self, policy: EvaluationPolicy) -> None:
        self.version_edit.setText(policy.version)
        for code, spin in self._weight_spins.items():
            spin.blockSignals(True)
            spin.setValue(policy.weights[code])
            spin.blockSignals(False)
        for etype, spin in self._evidence_spins.items():
            spin.setValue(policy.evidence_confidence.get(etype, 0.0))
        for key, spin in self._threshold_spins.items():
            spin.setValue(getattr(policy, key))
        self._update_weight_total()
        self.banner.set_text(
            f"현재 활성 정책: {policy.version}. 저장하면 이후 실행되는 분석부터 적용됩니다.",
            "info",
        )

    def _update_weight_total(self) -> None:
        total = sum(spin.value() for spin in self._weight_spins.values())
        ok = total == 100
        self.weight_total.setText(f"{total} / 100    {'✔ 정상' if ok else '✖ 100이 아님'}")
        self.weight_total.setStyleSheet(f"color: {'#1b5e20' if ok else '#b3261e'};")
        self.save_button.setEnabled(ok)

    # -- 동작 -------------------------------------------------------------
    def _reset(self) -> None:
        self._load(EvaluationPolicy())

    def _save(self) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        try:
            policy = EvaluationPolicy(
                version=self.version_edit.text().strip() or "policy-custom",
                weights={c: s.value() for c, s in self._weight_spins.items()},
                evidence_confidence={
                    e: s.value() for e, s in self._evidence_spins.items()
                },
                **{k: s.value() for k, s in self._threshold_spins.items()},
            )
            ctx.service.save_policy(policy)
        except PolicyError as exc:
            self.banner.set_text(f"정책 저장 거부: {exc}", "critical")
            return
        except Exception as exc:  # noqa: BLE001
            self.banner.set_text(f"저장 실패: {exc}", "critical")
            return

        self.banner.set_text(
            f"정책 '{policy.version}'을(를) 저장했습니다. "
            "기존 분석 결과는 그대로 남고, 다시 실행하면 새 정책이 적용됩니다.",
            "ok",
        )
        self.status_message.emit("정책을 저장했습니다.")
        self.data_changed.emit()
