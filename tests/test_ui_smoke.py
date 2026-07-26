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


def test_approved_version_offers_a_way_to_keep_editing(window, service, monkeypatch):
    """승인된 버전에서도 구조화 결과를 고칠 경로가 있어야 한다.

    구매자·첫 성공 경험·재방문 이유는 B화면에만 있는 항목이라
    이 경로가 없으면 승인 후 영영 고칠 수 없다.
    """
    from PySide6.QtWidgets import QInputDialog

    project = service.create_project("승인 후 수정", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
    )
    service.approve_structure(version.id)

    window.ctx.project = service.get_project(project.id)
    window.ctx.version = service.latest_version(project.id)
    screen = window.screens["structure"]
    screen.refresh(window.ctx)

    # 승인 상태: 잠겨 있고, 새 버전 버튼이 나와야 한다
    assert screen._editors["first_success"].isReadOnly() is True
    assert screen.new_version_button.isVisible() or not screen.save_button.isVisible()

    # 새 버전 만들기
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("첫 성공 경험 보완", True))
    screen._editors["first_success"].setPlainText("가입 없이 첫 3분 미션 하나를 끝낸다")
    screen._create_new_version()

    window.ctx.version = service.latest_version(project.id)
    v2 = window.ctx.version
    assert v2.version_no == 2
    assert v2.structure_approved is False
    assert v2.structured_idea["first_success"] == "가입 없이 첫 3분 미션 하나를 끝낸다"
    assert v2.change_reason == "첫 성공 경험 보완"
    # 원문은 그대로 물려받는다
    assert v2.raw_input == service.list_versions(project.id)[1].raw_input

    # 새 버전은 다시 편집 가능해야 한다
    screen.refresh(window.ctx)
    assert screen._editors["first_success"].isReadOnly() is False


def test_unapproved_version_saves_structure_only_fields(window, service):
    """B화면에만 있는 항목이 임시 저장으로 실제 반영되는지."""
    project = service.create_project("임시저장", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
    )
    window.ctx.project = service.get_project(project.id)
    window.ctx.version = service.latest_version(project.id)
    screen = window.screens["structure"]
    screen.refresh(window.ctx)

    for key, value in (
        ("first_success", "첫 3분 미션 완료"),
        ("payer", "회사 교육 담당자"),
        ("retention_reason", "매일 새 용어 지도가 열린다"),
    ):
        screen._editors[key].setPlainText(value)
    screen._save()

    saved = service.latest_version(project.id).structured_idea
    assert saved["first_success"] == "첫 3분 미션 완료"
    assert saved["payer"] == "회사 교육 담당자"
    assert saved["retention_reason"] == "매일 새 용어 지도가 열린다"


def test_required_fields_block_approval(window, service):
    """필수 항목이 비면 승인 버튼이 잠긴다."""
    from appcompass.core.models import RawIdeaInput

    project = service.create_project("필수", domain_code=DomainCode.VIBEQUEST)
    service.create_version(
        project.id,
        RawIdeaInput(app_name="앱", raw_idea="아이디어만 적었다"),
        IdeaStructure(app_name="앱"),
    )
    window.ctx.project = service.get_project(project.id)
    window.ctx.version = service.latest_version(project.id)
    screen = window.screens["structure"]
    screen.refresh(window.ctx)

    assert screen.approve_button.isEnabled() is False
    assert "필수" in screen.approve_button.toolTip()

    for key, value in (
        ("target_user", "AI 코딩 도구로 처음 앱을 만들다 용어에 막히는 비개발자"),
        ("problem_situation", "오류 메시지 용어를 몰라 작업이 자주 중단된다"),
        ("core_action", "막힌 단계의 3분 미션 하나를 완료한다"),
        ("expected_result", "작업 재개율이 50% 이상이 된다"),
    ):
        screen._editors[key].setPlainText(value)
    screen._validate()

    assert screen.approve_button.isEnabled() is True


def test_examath_additionally_requires_payer(window, service):
    """어린이 도메인은 구매자가 필수다 (아이가 쓰고 부모가 결제)."""
    project = service.create_project("어린이", domain_code=DomainCode.EXAMATH)
    idea = IdeaStructure.from_dict(
        {**fixture_idea("examath/refined_target.json").to_dict(), "payer": None}
    )
    service.create_version(project.id, fixture_raw("examath/refined_target.json"), idea)
    window.ctx.project = service.get_project(project.id)
    window.ctx.version = service.latest_version(project.id)
    screen = window.screens["structure"]
    screen.refresh(window.ctx)

    assert screen.approve_button.isEnabled() is False, "구매자가 비었는데 승인이 가능합니다."

    screen._editors["payer"].setPlainText("부모")
    screen._validate()
    assert screen.approve_button.isEnabled() is True


def test_vibequest_does_not_require_payer(window, service):
    """도메인마다 필수 항목이 다르다. VibeQuest는 구매자를 강제하지 않는다."""
    project = service.create_project("바이브", domain_code=DomainCode.VIBEQUEST)
    idea = IdeaStructure.from_dict(
        {**fixture_idea("vibequest/refined_target.json").to_dict(), "payer": None}
    )
    service.create_version(project.id, fixture_raw("vibequest/refined_target.json"), idea)
    window.ctx.project = service.get_project(project.id)
    window.ctx.version = service.latest_version(project.id)
    screen = window.screens["structure"]
    screen.refresh(window.ctx)
    assert screen.approve_button.isEnabled() is True


def test_hold_shows_cause_and_path_to_resolve(window, service):
    """HOLD일 때 원인과 해결 경로가 화면에 나와야 한다."""
    project = service.create_project("HOLD 안내", domain_code=DomainCode.VIBEQUEST)
    version = service.create_version(
        project.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
    )
    service.approve_structure(version.id)
    service.run_analysis(version.id)
    window.ctx.project = service.get_project(project.id)
    window.ctx.run = service.latest_run(project.id)

    screen = window.screens["diagnosis"]
    screen.refresh(window.ctx)

    assert window.ctx.run.result["pivot"]["decision"] == "HOLD"
    text = screen.hold_help._label.text()
    assert "오류가 아닙니다" in text
    assert "근거" in text


def test_evidence_example_fills_form_without_registering(window, service):
    """예시는 양식만 채운다. 근거로 등록되면 안 된다."""
    project = service.create_project("예시", domain_code=DomainCode.EXAMATH)
    ctx = ScreenContext(service=service, project=service.get_project(project.id))
    screen = window.screens["evidence"]
    screen.refresh(ctx)

    assert screen.example_menu.actions(), "예시 메뉴가 비어 있습니다."

    before = len(service.list_evidence(project.id))
    screen.example_menu.actions()[0].trigger()

    # 양식이 채워졌는가
    assert screen.title_edit.text()
    assert screen.summary_edit.toPlainText()
    assert any(b.isChecked() for b in screen._support_boxes.values())

    # 등록되지는 않았는가
    assert len(service.list_evidence(project.id)) == before

    # 예시라는 사실을 경고하는가
    assert "근거가 아니라" in screen.banner._label.text()


def test_evidence_examples_are_domain_specific(window, service):
    """도메인마다 다른 예시가 나와야 한다."""
    em = service.create_project("수학", domain_code=DomainCode.EXAMATH)
    vq = service.create_project("바이브", domain_code=DomainCode.VIBEQUEST)
    screen = window.screens["evidence"]

    screen.refresh(ScreenContext(service=service, project=service.get_project(em.id)))
    screen.example_menu.actions()[0].trigger()
    examath_text = screen.summary_edit.toPlainText()

    screen.refresh(ScreenContext(service=service, project=service.get_project(vq.id)))
    screen.example_menu.actions()[0].trigger()
    vibequest_text = screen.summary_edit.toPlainText()

    assert examath_text != vibequest_text
    assert "받아내림" in examath_text
    assert "용어" in vibequest_text


def test_filled_example_is_actually_registrable(window, service):
    """예시를 채운 뒤 등록 버튼이 실제로 동작해야 한다 (필수 항목 충족)."""
    project = service.create_project("등록", domain_code=DomainCode.EXAMATH)
    ctx = ScreenContext(service=service, project=service.get_project(project.id))
    screen = window.screens["evidence"]
    screen.refresh(ctx)
    screen.example_menu.actions()[0].trigger()
    screen._add()

    items = service.list_evidence(project.id)
    assert len(items) == 1
    assert items[0].supports, "지지 항목이 저장되지 않았습니다."


def test_first_example_lifts_hold(service):
    """① 예시가 실제로 HOLD를 푸는지 (안내가 사실인지) 확인."""
    from appcompass.core.confidence import compute_confidence
    from appcompass.core.domains.registry import get_domain
    from appcompass.core.models import EvidenceItem
    from appcompass.core.policy import EvaluationPolicy

    policy = EvaluationPolicy()
    for domain in (DomainCode.EXAMATH, DomainCode.VIBEQUEST, DomainCode.GENERIC):
        ex = get_domain(domain).evidence_examples()[0]
        item = EvidenceItem(
            id="e1",
            evidence_type=ex.evidence_type,
            title=ex.title,
            sample_size=ex.sample_size,
            supports=ex.supports,
            contradicts=ex.contradicts,
        )
        result = compute_confidence([item], policy)
        assert result.overall >= policy.hold_threshold, (
            f"{domain} ① 예시로 HOLD가 안 풀립니다 ({result.overall:.3f}). "
            "안내 문구가 사실과 다릅니다."
        )


def test_clear_form_resets_everything(window, service):
    project = service.create_project("비우기", domain_code=DomainCode.EXAMATH)
    ctx = ScreenContext(service=service, project=service.get_project(project.id))
    screen = window.screens["evidence"]
    screen.refresh(ctx)
    screen.example_menu.actions()[0].trigger()
    screen._clear_form()

    assert screen.title_edit.text() == ""
    assert screen.summary_edit.toPlainText() == ""
    assert not any(b.isChecked() for b in screen._support_boxes.values())
    assert not any(b.isChecked() for b in screen._contradict_boxes.values())


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
