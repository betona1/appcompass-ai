"""저장 계층.

SQLite로 시작하지만 SQLAlchemy 2.0 선언형 모델을 쓰기 때문에
PostgreSQL로 옮길 때 연결 문자열과 일부 타입만 바꾸면 된다.
core는 이 패키지를 import하지 않는다.
"""

from .db import Database, default_db_path
from .repository import Repository

__all__ = ["Database", "Repository", "default_db_path"]
