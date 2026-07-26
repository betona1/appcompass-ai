"""데이터베이스 연결.

기본은 로컬 SQLite. 환경변수 APPCOMPASS_DB_URL을 주면 그쪽을 쓴다.
PostgreSQL로 옮길 때 이 파일 외에는 바뀔 것이 거의 없다.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .orm import Base

ENV_DB_URL = "APPCOMPASS_DB_URL"


def default_db_path() -> Path:
    """사용자 홈 아래 앱 데이터 폴더."""
    base = Path(os.environ.get("APPDATA") or Path.home())
    directory = base / "AppCompass"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "appcompass.sqlite3"


class Database:
    def __init__(self, url: str | None = None, echo: bool = False) -> None:
        self.url = url or os.environ.get(ENV_DB_URL) or f"sqlite:///{default_db_path()}"
        self.engine: Engine = create_engine(self.url, echo=echo, future=True)
        if self.engine.dialect.name == "sqlite":
            _enable_sqlite_foreign_keys(self.engine)
        self._session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, future=True
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """데이터 변경 작업은 항상 이 컨텍스트 안에서 한다 (CLAUDE.md §9)."""
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite는 기본적으로 FK를 강제하지 않는다. ondelete='CASCADE'가 동작하려면 필요하다."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
