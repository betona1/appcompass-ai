from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = ROOT / "fixtures"

from appcompass.core.models import IdeaStructure, RawIdeaInput  # noqa: E402
from appcompass.storage.db import Database  # noqa: E402
from appcompass.services.app_service import AppService  # noqa: E402


def load_fixture(relative: str) -> dict:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


def fixture_idea(relative: str) -> IdeaStructure:
    return IdeaStructure.from_dict(load_fixture(relative)["structured_idea"])


def fixture_raw(relative: str) -> RawIdeaInput:
    return RawIdeaInput.from_dict(load_fixture(relative)["raw_input"])


@pytest.fixture
def service(tmp_path) -> AppService:
    db = Database(url=f"sqlite:///{tmp_path / 'test.sqlite3'}")
    svc = AppService(db)
    yield svc
    db.dispose()
