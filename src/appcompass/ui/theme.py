"""시각 스타일과 상태 표기.

CLAUDE.md §9: "색만으로 상태를 구분하지 않는다."
따라서 심각도·판정은 항상 [글머리 기호 + 한글 라벨 + 코드] 를 함께 쓴다.
"""

from __future__ import annotations

from ..core.enums import PivotDecision, Severity

SEVERITY_MARK: dict[Severity, str] = {
    Severity.CRITICAL: "■ 치명",
    Severity.WARN: "▲ 주의",
    Severity.INFO: "· 참고",
}

SEVERITY_COLOR: dict[Severity, str] = {
    Severity.CRITICAL: "#b3261e",
    Severity.WARN: "#8a6100",
    Severity.INFO: "#41474d",
}

DECISION_MARK: dict[str, str] = {
    str(PivotDecision.KEEP): "● 유지",
    str(PivotDecision.REFINE): "● 보완",
    str(PivotDecision.TARGET_PIVOT): "◆ 타깃 피벗",
    str(PivotDecision.PROBLEM_PIVOT): "◆ 문제 피벗",
    str(PivotDecision.SOLUTION_PIVOT): "◆ 해결책 피벗",
    str(PivotDecision.CHANNEL_PIVOT): "◆ 채널 피벗",
    str(PivotDecision.REVENUE_PIVOT): "◆ 수익 피벗",
    str(PivotDecision.RETENTION_REDESIGN): "◆ 재방문 재설계",
    str(PivotDecision.HOLD): "■ 판단 보류",
}

DECISION_COLOR: dict[str, str] = {
    str(PivotDecision.KEEP): "#1b5e20",
    str(PivotDecision.REFINE): "#33691e",
    str(PivotDecision.HOLD): "#b3261e",
}
DEFAULT_DECISION_COLOR = "#8a4b00"


def decision_label(decision: str) -> str:
    return DECISION_MARK.get(decision, decision)


def decision_color(decision: str) -> str:
    return DECISION_COLOR.get(decision, DEFAULT_DECISION_COLOR)


def score_bar(raw_score: int, maximum: int = 5) -> str:
    """색 없이 점수를 읽게 하는 텍스트 게이지."""
    filled = max(0, min(maximum, raw_score))
    return "█" * filled + "░" * (maximum - filled)


STYLESHEET = """
QWidget { font-family: "Malgun Gothic", "Segoe UI", sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: #f6f7f9; }

QLabel#H1 { font-size: 20px; font-weight: 700; color: #16181d; }
QLabel#H2 { font-size: 15px; font-weight: 700; color: #16181d; padding-top: 6px; }
QLabel#Hint { color: #5a6068; font-size: 12px; }
QLabel#Big { font-size: 26px; font-weight: 700; }

QGroupBox {
    border: 1px solid #d9dde2; border-radius: 8px; margin-top: 14px;
    background: #ffffff; padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 5px;
    font-weight: 700; color: #2f3437;
}

QPushButton {
    background: #ffffff; border: 1px solid #c6ccd3; border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { background: #eef2f7; }
QPushButton:disabled { color: #a4abb3; background: #f2f3f5; }
QPushButton#Primary {
    background: #2f6fed; color: #ffffff; border: 1px solid #2559c4; font-weight: 700;
}
QPushButton#Primary:hover { background: #2559c4; }
QPushButton#Primary:disabled { background: #9db7ea; border-color: #9db7ea; }
QPushButton#Danger { color: #b3261e; border-color: #e0b4b1; }
QPushButton#Danger:hover { background: #fdeceb; }

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    border: 1px solid #c6ccd3; border-radius: 6px; padding: 5px 7px; background: #ffffff;
}
QPlainTextEdit:focus, QLineEdit:focus { border-color: #2f6fed; }
/* 읽기 전용은 겉모습이 달라야 한다. 같으면 입력이 고장 난 것으로 오해한다. */
QPlainTextEdit[readOnly="true"], QLineEdit[readOnly="true"] {
    background: #f1f2f4; color: #5a6068; border-style: dashed;
}

QTableWidget, QTreeWidget, QListWidget {
    border: 1px solid #d9dde2; border-radius: 8px; background: #ffffff;
}
QHeaderView::section {
    background: #eef1f5; border: none; border-right: 1px solid #d9dde2;
    border-bottom: 1px solid #d9dde2; padding: 6px; font-weight: 700;
}
QTabWidget::pane { border: 1px solid #d9dde2; border-radius: 8px; background: #ffffff; }
QTabBar::tab {
    background: #e9edf2; border: 1px solid #d9dde2; border-bottom: none;
    padding: 7px 14px; margin-right: 2px;
    border-top-left-radius: 7px; border-top-right-radius: 7px;
}
QTabBar::tab:selected { background: #ffffff; font-weight: 700; color: #2f6fed; }

QFrame#Card {
    background: #ffffff; border: 1px solid #d9dde2; border-radius: 8px;
}
QFrame#Banner {
    background: #fff8e6; border: 1px solid #f0d99b; border-radius: 8px;
}
QFrame#BannerCritical {
    background: #fdeceb; border: 1px solid #efb9b5; border-radius: 8px;
}
QFrame#BannerOk {
    background: #edf7ee; border: 1px solid #b7ddb9; border-radius: 8px;
}
"""
