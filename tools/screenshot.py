"""개발용 스크린샷 도구.

실제 창을 띄우지 않고(offscreen) 화면을 렌더링해 PNG로 저장한다.
UI 변경 후 눈으로 확인할 때 쓴다.

    python tools/screenshot.py out_dir
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from appcompass.core.enums import DimensionCode, DomainCode, EvidenceType  # noqa: E402
from appcompass.services.app_service import AppService  # noqa: E402
from appcompass.storage.db import Database  # noqa: E402
from appcompass.ui.main_window import MainWindow  # noqa: E402
from appcompass.ui.theme import STYLESHEET  # noqa: E402

from conftest import fixture_idea, fixture_raw  # noqa: E402


def build_demo(service: AppService) -> None:
    vq = service.create_project(
        "VibeQuest", app_name="VibeQuest", domain_code=DomainCode.VIBEQUEST
    )
    v1 = service.create_version(
        vq.id,
        fixture_raw("vibequest/broad_target.json"),
        fixture_idea("vibequest/broad_target.json"),
        change_reason="최초 아이디어",
    )
    service.approve_structure(v1.id)
    service.run_analysis(v1.id)

    v2 = service.create_version(
        vq.id,
        fixture_raw("vibequest/refined_target.json"),
        fixture_idea("vibequest/refined_target.json"),
        change_reason="타깃을 상황 기반으로 좁히고 첫 성공·재방문 정의 추가",
    )
    service.approve_structure(v2.id)
    service.add_evidence(
        vq.id,
        EvidenceType.USER_INTERVIEW,
        "비개발자 8명 인터뷰 (2026-01)",
        summary="8명 중 7명이 최근 일주일에 2회 이상 용어 때문에 작업을 중단했다고 진술",
        source_reference="interviews/2026-01-vibecoding.md",
        sample_size=8,
        supports=[DimensionCode.D01, DimensionCode.D02, DimensionCode.D03],
    )
    service.add_evidence(
        vq.id,
        EvidenceType.PROTOTYPE_TEST,
        "3분 미션 클릭더미 테스트",
        summary="12명 중 9명이 첫 미션을 완료. 3명은 난이도가 높다고 응답",
        sample_size=12,
        supports=[DimensionCode.D05, DimensionCode.D06, DimensionCode.D10],
        contradicts=[DimensionCode.D08],
    )
    service.run_analysis(v2.id)

    em = service.create_project(
        "examath", app_name="examath", domain_code=DomainCode.EXAMATH
    )
    ev = service.create_version(
        em.id,
        fixture_raw("examath/broad_child.json"),
        fixture_idea("examath/broad_child.json"),
        change_reason="최초 아이디어",
    )
    service.approve_structure(ev.id)
    service.run_analysis(ev.id)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools" / "shots")
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    app.setStyleSheet(STYLESHEET)

    db_path = out / "_demo.sqlite3"
    if db_path.exists():
        db_path.unlink()
    db = Database(url=f"sqlite:///{db_path}")
    service = AppService(db)
    build_demo(service)

    window = MainWindow(service)
    window.resize(1600, 1000)
    # show()하지 않는다. grab()은 오프스크린 렌더링이라 사용자 화면에 창을 띄우지 않는다.
    window.ensurePolished()
    window.layout().activate()
    app.processEvents()
    window.reload_projects()
    app.processEvents()

    for index in range(window.tabs.count()):
        window.tabs.setCurrentIndex(index)
        app.processEvents()
        name = list(window.screens.keys())[index]
        path = out / f"{index}_{name}.png"
        window.grab().save(str(path))
        print(f"saved {path}")

    db.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
