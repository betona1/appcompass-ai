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
from appcompass.core.models import IdeaStructure  # noqa: E402
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


def test_edited_raw_input_reaches_structured_idea(window, service):
    """A화면에서 고친 원문은 반드시 구조화 결과에 반영되어야 한다.

    반영되지 않으면 아이디어를 바꿔도 분석 결과가 그대로여서
    사용자에게는 '수정이 저장되지 않는' 것으로 보인다.
    """
    project = service.create_project("수정 반영", domain_code=DomainCode.VIBEQUEST)
    window.ctx.project = project
    window.ctx.version = None
    screen = window.screens["idea"]
    screen.refresh(window.ctx)

    screen.raw_idea.setPlainText("원래 아이디어")
    screen.target_raw.setPlainText("모든 사람")
    screen.problem_raw.setPlainText("원래 문제 상황")
    screen.solution_raw.setPlainText("원래 해결 방법")
    screen._save()

    window.ctx.version = service.latest_version(project.id)
    v1 = window.ctx.version
    assert v1.structured_idea["target_user"] == "모든 사람"

    # B화면에서만 채우는 값 — 원문을 안 고쳤다면 다음 버전에도 살아남아야 한다.
    service.update_version(
        v1.id,
        idea=IdeaStructure.from_dict({**v1.structured_idea, "payer": "회사 교육 담당자"}),
    )
    window.ctx.version = service.latest_version(project.id)

    # A화면에서 타깃과 문제만 고친다.
    screen.refresh(window.ctx)
    screen.target_raw.setPlainText("AI 코딩 도구로 처음 앱을 만들다 용어에 막히는 비개발자")
    screen.problem_raw.setPlainText("오류 메시지 용어를 몰라 작업이 중단된다")
    screen._save()

    v2 = service.latest_version(project.id)
    assert v2.version_no == 2

    # 고친 것은 반영된다
    assert v2.structured_idea["target_user"].startswith("AI 코딩 도구로 처음")
    assert v2.structured_idea["problem_situation"] == "오류 메시지 용어를 몰라 작업이 중단된다"
    # 안 고친 원문에서 온 값은 유지된다
    assert v2.structured_idea["core_action"] == "원래 해결 방법"
    # B화면에서 다듬은 값도 유지된다
    assert v2.structured_idea["payer"] == "회사 교육 담당자"


def test_unchanged_raw_input_preserves_refined_structure(window, service):
    """원문을 안 고쳤으면 B화면에서 다듬은 구조화 값을 덮어쓰지 않는다."""
    from appcompass.ui.screens.idea_input import _seed_structure
    from appcompass.core.models import RawIdeaInput

    raw = RawIdeaInput(
        app_name="앱", raw_idea="아이디어", target_user_raw="모든 사람",
        problem_raw="문제", solution_raw="해결",
    )
    refined = IdeaStructure(
        app_name="앱",
        target_user="상황까지 적어 다듬은 타깃",   # B화면에서 고친 값
        problem_situation="문제",
        core_action="해결",
        payer="부모",
    )
    seed, labels = _seed_structure(raw, refined, raw.to_dict())
    assert labels == []
    assert seed.target_user == "상황까지 적어 다듬은 타깃"
    assert seed.payer == "부모"


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
