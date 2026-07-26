"""메인 윈도우.

왼쪽에 프로젝트 목록, 오른쪽에 흐름 순서대로 배치한 화면 탭.
분석 실행은 워커 스레드에서 돌리고 UI는 로딩 상태를 보여준다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.domains.registry import available_domains
from ..core.enums import DomainCode, ProjectStage
from ..services.app_service import AppService, ServiceError
from ..services.dto import ProjectDTO
from .context import ScreenContext
from .screens.base import ScreenBase
from .screens.diagnosis import DiagnosisScreen
from .screens.evidence import EvidenceScreen
from .screens.idea_input import IdeaInputScreen
from .screens.mvp import MvpScreen
from .screens.policy import PolicyScreen
from .screens.report import ReportScreen
from .screens.structure_review import StructureReviewScreen
from .screens.targets import TargetsScreen
from .screens.versions import VersionsScreen
from .theme import decision_label
from .widgets import h2, hint
from .workers import AnalysisWorker

STAGE_LABELS: dict[ProjectStage, str] = {
    ProjectStage.IDEA: "아이디어",
    ProjectStage.RESEARCH: "리서치",
    ProjectStage.PROTOTYPE: "프로토타입",
    ProjectStage.MVP: "MVP",
    ProjectStage.LIVE: "운영 중",
    ProjectStage.PAUSED: "중단",
    ProjectStage.ARCHIVED: "보관",
}


class MainWindow(QMainWindow):
    def __init__(self, service: AppService) -> None:
        super().__init__()
        self.service = service
        self.ctx = ScreenContext(service=service)
        self._worker: AnalysisWorker | None = None

        self.setWindowTitle("AppCompass AI — 앱 기획 의사결정 시스템")
        self.resize(1480, 940)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_main_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([310, 1170])
        self.setCentralWidget(splitter)

        self._build_menu()
        self.statusBar().showMessage("준비됨")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

        self.reload_projects()

    # ==================================================================
    # 레이아웃
    # ==================================================================
    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 8, 12)

        layout.addWidget(h2("프로젝트"))
        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_project_selected)
        layout.addWidget(self.project_list, 1)

        self.project_detail = QLabel("-")
        self.project_detail.setObjectName("Hint")
        self.project_detail.setWordWrap(True)
        layout.addWidget(self.project_detail)

        button_row = QVBoxLayout()
        new_button = QPushButton("새 프로젝트")
        new_button.setObjectName("Primary")
        new_button.clicked.connect(self.create_project_dialog)
        edit_button = QPushButton("프로젝트 설정 수정")
        edit_button.clicked.connect(self.edit_project_dialog)
        archive_button = QPushButton("보관")
        archive_button.clicked.connect(self.archive_project)
        delete_button = QPushButton("삭제")
        delete_button.setObjectName("Danger")
        delete_button.clicked.connect(self.delete_project)
        for b in (new_button, edit_button, archive_button, delete_button):
            button_row.addWidget(b)
        layout.addLayout(button_row)

        self.show_archived = QPushButton("보관함 표시")
        self.show_archived.setCheckable(True)
        self.show_archived.toggled.connect(lambda _: self.reload_projects())
        layout.addWidget(self.show_archived)
        return panel

    def _build_main_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 12, 12, 12)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 0, 6, 0)
        self.header_label = QLabel("프로젝트를 선택하세요")
        self.header_label.setObjectName("H1")
        header_layout.addWidget(self.header_label, 1)

        self.decision_chip = QLabel("")
        self.decision_chip.setObjectName("H2")
        header_layout.addWidget(self.decision_chip)

        self.run_button = QPushButton("분석 실행")
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self.run_analysis)
        header_layout.addWidget(self.run_button)
        layout.addWidget(header)

        self.header_hint = QLabel("")
        self.header_hint.setObjectName("Hint")
        self.header_hint.setWordWrap(True)
        layout.addWidget(self.header_hint)

        self.tabs = QTabWidget()
        self.screens: dict[str, ScreenBase] = {
            "idea": IdeaInputScreen(),
            "structure": StructureReviewScreen(),
            "evidence": EvidenceScreen(),
            "diagnosis": DiagnosisScreen(),
            "targets": TargetsScreen(),
            "mvp": MvpScreen(),
            "report": ReportScreen(),
            "versions": VersionsScreen(),
            "policy": PolicyScreen(),
        }
        for key, screen in self.screens.items():
            screen.data_changed.connect(self.reload_current)
            screen.status_message.connect(self.statusBar().showMessage)
            screen.request_screen.connect(self._handle_screen_request)
            self.tabs.addTab(screen, screen.title)
        self.tabs.currentChanged.connect(lambda _: self.refresh_screens())
        layout.addWidget(self.tabs, 1)
        return panel

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("파일")
        new_action = QAction("새 프로젝트", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.create_project_dialog)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        quit_action = QAction("종료", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        run_menu = self.menuBar().addMenu("분석")
        run_action = QAction("분석 실행", self)
        run_action.setShortcut("Ctrl+R")
        run_action.triggered.connect(self.run_analysis)
        run_menu.addAction(run_action)

        tools_menu = self.menuBar().addMenu("도구")
        audit_action = QAction("감사 로그 보기", self)
        audit_action.triggered.connect(self.show_audit_log)
        tools_menu.addAction(audit_action)
        events_action = QAction("분석 이벤트 보기", self)
        events_action.triggered.connect(self.show_events)
        tools_menu.addAction(events_action)

        help_menu = self.menuBar().addMenu("도움말")
        about_action = QAction("AppCompass 정보", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    # ==================================================================
    # 데이터 로딩
    # ==================================================================
    def reload_projects(self) -> None:
        current_id = self.ctx.project.id if self.ctx.project else None
        self.project_list.blockSignals(True)
        self.project_list.clear()
        projects = self.service.list_projects(
            include_archived=self.show_archived.isChecked()
        )
        for p in projects:
            decision = f" · {p.latest_decision}" if p.latest_decision else ""
            item = QListWidgetItem(
                f"{p.name}\n  {p.domain_code} · v{p.latest_version_no or 0}{decision}"
            )
            item.setData(Qt.UserRole, p.id)
            self.project_list.addItem(item)
        self.project_list.blockSignals(False)

        if not projects:
            self.ctx.project = None
            self.ctx.version = None
            self.ctx.run = None
            self.header_label.setText("프로젝트가 없습니다")
            self.header_hint.setText(
                "왼쪽 아래 '새 프로젝트'로 시작하세요. VibeQuest·examath 도메인을 고르면 "
                "해당 도메인의 경고와 MVP 제외 규칙이 자동 적용됩니다."
            )
            self.decision_chip.setText("")
            self.run_button.setEnabled(False)
            self.run_button.setToolTip("먼저 프로젝트를 만드세요.")
            self.refresh_screens()
            return

        target_row = 0
        if current_id:
            for i in range(self.project_list.count()):
                if self.project_list.item(i).data(Qt.UserRole) == current_id:
                    target_row = i
                    break
        self.project_list.setCurrentRow(target_row)

    def reload_current(self) -> None:
        """현재 프로젝트의 버전·분석 결과를 다시 읽는다."""
        if self.ctx.project is None:
            self.refresh_screens()
            return
        try:
            self.ctx.project = self.service.get_project(self.ctx.project.id)
            self.ctx.version = self.service.latest_version(self.ctx.project.id)
            self.ctx.run = self.service.latest_run(self.ctx.project.id)
        except ServiceError as exc:
            QMessageBox.warning(self, "불러오기 실패", str(exc))
            return
        self._update_header()
        self.refresh_screens()

    def refresh_screens(self) -> None:
        current = self.tabs.currentWidget()
        if isinstance(current, ScreenBase):
            current.refresh(self.ctx)
        # 사이드바 요약은 항상 최신으로
        self._update_sidebar_detail()

    def _update_header(self) -> None:
        p = self.ctx.project
        if p is None:
            return
        self.header_label.setText(p.name)

        if self.ctx.version is None:
            state = "아직 버전이 없습니다. 'A. 아이디어 입력'에서 시작하세요."
        elif not self.ctx.version.structure_approved:
            state = (
                f"v{self.ctx.version.version_no} 미승인 — "
                "'B. 구조화 검토'에서 승인해야 분석할 수 있습니다."
            )
        elif self.ctx.run is None:
            state = f"v{self.ctx.version.version_no} 승인됨 — 분석을 실행하세요."
        else:
            state = (
                f"v{self.ctx.version.version_no} · 최근 분석 v{self.ctx.run.version_no} "
                f"({self.ctx.run.status})"
            )
        self.header_hint.setText(
            f"{p.domain_code} · {STAGE_LABELS.get(p.stage, p.stage)} · "
            f"버전 {p.version_count}개 · 근거 {p.evidence_count}건 — {state}"
        )

        run = self.ctx.run
        if run and run.status == "COMPLETED" and run.result:
            decision = run.result["pivot"]["decision"]
            conf = run.result["pivot"]["confidence"]
            self.decision_chip.setText(f"{decision_label(decision)}  ·  신뢰도 {conf:.2f}")
        elif run and run.status.startswith("FAILED"):
            self.decision_chip.setText(f"■ 분석 실패 ({run.error_code})")
        else:
            self.decision_chip.setText("")

        can_run = self.ctx.version is not None and self.ctx.version.structure_approved
        self.run_button.setEnabled(can_run and self._worker is None)
        self.run_button.setToolTip(
            "" if can_run else "구조화 결과를 승인해야 분석을 실행할 수 있습니다."
        )

    def _update_sidebar_detail(self) -> None:
        p = self.ctx.project
        if p is None:
            self.project_detail.setText("-")
            return
        self.project_detail.setText(
            f"앱 이름: {p.app_name or '-'}\n"
            f"도메인: {p.domain_code}\n"
            f"단계: {STAGE_LABELS.get(p.stage, p.stage)}\n"
            f"버전: {p.version_count} · 근거: {p.evidence_count}\n"
            f"최근 판단: {p.latest_decision or '분석 없음'}"
        )

    # ==================================================================
    # 이벤트 핸들러
    # ==================================================================
    def _on_project_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        project_id = current.data(Qt.UserRole)
        try:
            self.ctx.project = self.service.get_project(project_id)
            self.ctx.version = self.service.latest_version(project_id)
            self.ctx.run = self.service.latest_run(project_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "불러오기 실패", str(exc))
            return
        self._update_header()
        self.refresh_screens()

    def _handle_screen_request(self, key: str) -> None:
        if key == "run_analysis":
            self.reload_current()
            self.run_analysis()
            return
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is self.screens.get(key):
                self.tabs.setCurrentIndex(i)
                return

    # ==================================================================
    # 분석 실행
    # ==================================================================
    def run_analysis(self) -> None:
        if self.ctx.version is None:
            QMessageBox.information(
                self, "분석 불가", "먼저 아이디어를 저장하고 구조화를 승인하세요."
            )
            return
        if not self.ctx.version.structure_approved:
            QMessageBox.information(
                self,
                "분석 불가",
                "구조화 결과를 승인해야 분석을 실행할 수 있습니다. (B. 구조화 검토)",
            )
            return
        if self._worker is not None:
            return

        self.progress.setVisible(True)
        self.run_button.setEnabled(False)
        self.statusBar().showMessage("분석 중… 규칙 엔진이 점수와 판정을 계산합니다.")

        worker = AnalysisWorker(self.service, self.ctx.version.id, self)
        worker.finished_ok.connect(self._on_analysis_done)
        worker.failed.connect(self._on_analysis_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_analysis_done(self, run) -> None:
        self.ctx.run = run
        if run.status.startswith("FAILED"):
            self.statusBar().showMessage(f"분석 실패: {run.error_code}")
            QMessageBox.warning(
                self,
                "분석 실패",
                f"상태: {run.status}\n\n{run.error_detail or '원인 정보 없음'}\n\n"
                "이 결과로는 점수나 피벗 판정을 만들지 않습니다.",
            )
        else:
            decision = run.result["pivot"]["decision"]
            self.statusBar().showMessage(f"분석 완료 — 판단: {decision}")
            self.tabs.setCurrentIndex(
                list(self.screens.keys()).index("diagnosis")
            )
        self.reload_current()
        self.reload_projects()

    def _on_analysis_failed(self, message: str) -> None:
        self.statusBar().showMessage("분석 실패")
        QMessageBox.warning(self, "분석 실패", message)

    def _on_worker_finished(self) -> None:
        self.progress.setVisible(False)
        self._worker = None
        self._update_header()

    # ==================================================================
    # 프로젝트 관리
    # ==================================================================
    def create_project_dialog(self) -> None:
        dialog = ProjectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        try:
            project = self.service.create_project(**values)
        except ServiceError as exc:
            QMessageBox.warning(self, "생성 실패", str(exc))
            return
        self.ctx.project = project
        self.reload_projects()
        self.tabs.setCurrentIndex(0)
        self.statusBar().showMessage(f"'{project.name}' 프로젝트를 만들었습니다.")

    def edit_project_dialog(self) -> None:
        if self.ctx.project is None:
            return
        dialog = ProjectDialog(self, self.ctx.project)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_project(self.ctx.project.id, **dialog.values())
        except ServiceError as exc:
            QMessageBox.warning(self, "수정 실패", str(exc))
            return
        self.reload_projects()
        self.reload_current()

    def archive_project(self) -> None:
        if self.ctx.project is None:
            return
        answer = QMessageBox.question(
            self,
            "프로젝트 보관",
            f"'{self.ctx.project.name}'을(를) 보관할까요?\n"
            "데이터는 지워지지 않고 목록에서만 숨겨집니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.service.archive_project(self.ctx.project.id)
        self.ctx.project = None
        self.reload_projects()

    def delete_project(self) -> None:
        """파괴적 작업. 이름을 직접 입력해야 삭제된다."""
        if self.ctx.project is None:
            return
        name = self.ctx.project.name
        confirm = QDialog(self)
        confirm.setWindowTitle("프로젝트 삭제")
        layout = QVBoxLayout(confirm)
        layout.addWidget(
            QLabel(
                f"'{name}'의 모든 버전, 분석, 근거, 보고서가 영구 삭제됩니다.\n"
                "되돌릴 수 없습니다."
            )
        )
        layout.addWidget(hint("계속하려면 아래에 프로젝트 이름을 그대로 입력하세요."))
        edit = QLineEdit()
        layout.addWidget(edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("영구 삭제")
        ok_button.setEnabled(False)
        edit.textChanged.connect(lambda t: ok_button.setEnabled(t.strip() == name))
        buttons.accepted.connect(confirm.accept)
        buttons.rejected.connect(confirm.reject)
        layout.addWidget(buttons)

        if confirm.exec() != QDialog.Accepted:
            return
        self.service.delete_project(self.ctx.project.id)
        self.ctx.project = None
        self.ctx.version = None
        self.ctx.run = None
        self.reload_projects()
        self.statusBar().showMessage(f"'{name}'을(를) 삭제했습니다.")

    # ==================================================================
    # 도구
    # ==================================================================
    def show_audit_log(self) -> None:
        logs = self.service.list_audit_logs()
        text = "\n".join(
            f"{a.created_at:%Y-%m-%d %H:%M:%S}  {a.action:22}  {a.object_type}  {a.object_id or ''}"
            for a in logs
        )
        _show_text_dialog(
            self, "감사 로그", text or "기록이 없습니다.",
            "모든 생성·수정·삭제·분석·정책 변경이 여기에 남습니다."
        )

    def show_events(self) -> None:
        events = self.service.list_events()
        text = "\n".join(
            f"{when:%Y-%m-%d %H:%M:%S}  {name:24}  {project_id or ''}"
            for name, project_id, when in events
        )
        _show_text_dialog(
            self, "분석 이벤트", text or "기록이 없습니다.",
            "TECHSPEC §12 이벤트입니다. 데스크톱에서는 로컬 DB에만 저장됩니다."
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "AppCompass AI",
            "<h3>AppCompass AI 0.1.0</h3>"
            "<p>앱 아이디어를 구조화하고 진단해 유지·수정·피벗을 판단하는 시스템입니다.</p>"
            "<p><b>현재 단계: Phase 0+1 (규칙 엔진 전용)</b><br>"
            "점수·신뢰도·피벗 판정은 전부 결정론적 규칙 엔진이 계산합니다. "
            "LLM은 사용하지 않으며, 붙이더라도 판정은 위임하지 않습니다.</p>"
            "<p>AI가 정답을 결정하지 않습니다. "
            "시스템은 문제를 구조화하고, 부족한 근거를 찾고, 검증할 실험을 제안합니다. "
            "최종 결정은 사람이 승인합니다.</p>",
        )


def _show_text_dialog(parent, title: str, text: str, note: str) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(880, 560)
    layout = QVBoxLayout(dialog)
    layout.addWidget(hint(note))
    view = QPlainTextEdit(text)
    view.setReadOnly(True)
    view.setLineWrapMode(QPlainTextEdit.NoWrap)
    layout.addWidget(view)
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


class ProjectDialog(QDialog):
    def __init__(self, parent, project: ProjectDTO | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("프로젝트 설정" if project else "새 프로젝트")
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(project.name if project else "")
        self.app_name_edit = QLineEdit(project.app_name if project else "")
        self.description_edit = QPlainTextEdit(project.description if project else "")
        self.description_edit.setFixedHeight(80)

        self.domain_combo = QComboBox()
        for code, label in available_domains():
            self.domain_combo.addItem(label, code)
        if project:
            index = self.domain_combo.findData(project.domain_code)
            if index >= 0:
                self.domain_combo.setCurrentIndex(index)

        self.stage_combo = QComboBox()
        for stage, label in STAGE_LABELS.items():
            self.stage_combo.addItem(label, stage)
        if project:
            index = self.stage_combo.findData(project.stage)
            if index >= 0:
                self.stage_combo.setCurrentIndex(index)

        form.addRow("프로젝트 이름", self.name_edit)
        form.addRow("앱 이름", self.app_name_edit)
        form.addRow("설명", self.description_edit)
        form.addRow("도메인", self.domain_combo)
        form.addRow("단계", self.stage_combo)
        layout.addLayout(form)
        layout.addWidget(
            hint(
                "도메인을 고르면 해당 도메인의 필수 경고, 언노운, MVP 제외 규칙, "
                "측정 이벤트가 분석에 자동 적용됩니다."
            )
        )

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "name": self.name_edit.text(),
            "app_name": self.app_name_edit.text(),
            "description": self.description_edit.toPlainText(),
            "domain_code": DomainCode(self.domain_combo.currentData()),
            "stage": ProjectStage(self.stage_combo.currentData()),
        }
