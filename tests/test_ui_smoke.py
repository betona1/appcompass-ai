"""UI 스모크 테스트.

화면을 실제로 띄우지 않고(offscreen) 생성·갱신만 수행해
import 오류, 시그널 연결 오류, 빈 상태/결과 상태 렌더링 오류를 잡는다.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from appcompass.core.enums import DimensionCode, DomainCode, EvidenceType  # noqa: E402
from appcompass.ui.context import ScreenContext  # noqa: E402
from appcompass.ui.main_window import MainWindow  # noqa: E402

from conftest import fixture_idea, fixture_raw  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, service):
    win = MainWindow(service)
    yield win
    win.close()


def test_window_starts_with_no_projects(window):
    assert window.header_label.text() == "프로젝트가 없습니다"
    assert window.run_button.isEnabled() is False


def test_all_screens_render_empty_state(window, service):
    ctx = ScreenContext(service=service)
    for key, screen in window.screens.items():
        screen.refresh(ctx)  # 예외 없이 통과해야 한다


def test_full_flow_through_ui(window, service):
    project = service.create_project("스모크", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
        change_reason="스모크 테스트",
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)

    window.reload_projects()
    window.reload_current()

    assert window.ctx.project is not None
    assert window.ctx.run is not None
    assert window.ctx.run.status == "COMPLETED"
    assert "판단 보류" in window.decision_chip.text()

    ctx = window.ctx
    for key, screen in window.screens.items():
        screen.refresh(ctx)

    diagnosis = window.screens["diagnosis"]
    assert diagnosis.score_table.rowCount() == 10
    assert diagnosis.decision_label.text().endswith("판단 보류")

    targets = window.screens["targets"]
    assert targets.cards_layout.count() >= 3

    report = window.screens["report"]
    assert report.preview.toPlainText().strip()


def test_evidence_screen_lists_registered_evidence(window, service):
    project = service.create_project("근거 스모크", domain_code=DomainCode.EXAMATH)
    service.add_evidence(
        project.id,
        EvidenceType.USER_INTERVIEW,
        "학부모 인터뷰",
        sample_size=5,
        supports=[DimensionCode.D01],
    )
    ctx = ScreenContext(service=service, project=service.get_project(project.id))
    screen = window.screens["evidence"]
    screen.refresh(ctx)
    assert screen.table.rowCount() == 1
    assert screen.table.item(0, 1).text() == "학부모 인터뷰"


def test_policy_screen_blocks_invalid_weight_sum(window, service):
    screen = window.screens["policy"]
    screen.refresh(ScreenContext(service=service))
    assert screen.save_button.isEnabled() is True

    screen._weight_spins[DimensionCode.D01].setValue(50)
    assert screen.save_button.isEnabled() is False, (
        "가중치 합계가 100이 아닌데 저장 버튼이 활성화되어 있습니다."
    )

    screen._weight_spins[DimensionCode.D01].setValue(15)
    assert screen.save_button.isEnabled() is True


def test_structure_screen_shows_warnings_live(window, service):
    project = service.create_project("경고 스모크", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/broad_target.json"),
        fixture_idea("vibequest/broad_target.json"),
    )
    ctx = ScreenContext(
        service=service,
        project=service.get_project(project.id),
        version=service.latest_version(project.id),
    )
    screen = window.screens["structure"]
    screen.refresh(ctx)

    from PySide6.QtWidgets import QLabel

    texts = " ".join(
        w.text() for w in screen.warning_list.findChildren(QLabel)
    )
    assert "BROAD_TARGET" in texts
    assert "NO_REAL_TASK_CONTEXT" in texts, "도메인 전용 경고가 표시되지 않았습니다."


def test_versions_screen_requires_two_versions(window, service):
    project = service.create_project("버전 스모크")
    service.create_version(
        project.id,
        fixture_raw("vibequest/broad_target.json"),
        fixture_idea("vibequest/broad_target.json"),
    )
    ctx = ScreenContext(service=service, project=service.get_project(project.id))
    screen = window.screens["versions"]
    screen.refresh(ctx)
    assert screen.empty.isVisible() or not screen.body.isVisible()

    service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
        change_reason="타깃 좁힘",
    )
    ctx.project = service.get_project(project.id)
    screen.refresh(ctx)
    assert screen.table.rowCount() > 0
