"""가장 작은 마이그레이션.

`create_all()`은 **없는 테이블만** 만든다. 이미 있는 테이블에 컬럼을 더해도
기존 사용자의 DB에는 반영되지 않고, 그 컬럼을 읽는 순간 OperationalError가 난다.

정식 마이그레이션 도구(Alembic)를 넣지 않는 이유는, 지금 필요한 변경이
"nullable 컬럼 추가" 하나뿐이고 그건 SQLite와 PostgreSQL 모두에서
`ALTER TABLE ... ADD COLUMN` 한 줄로 끝나기 때문이다.

여기에 넣어도 되는 것: nullable 컬럼 추가.
여기에 넣으면 안 되는 것: 컬럼 삭제·이름 변경·타입 변경·데이터 백필.
그런 변경이 필요해지는 순간이 Alembic을 도입할 때다 (TECHSPEC 마이그레이션 절 참고).
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

#: (테이블, 컬럼, DDL 타입). 이미 있으면 건너뛴다.
ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("project_versions", "llm_assist", "JSON"),
)


def apply_additive_migrations(engine: Engine) -> list[str]:
    """빠진 컬럼을 더한다. 무엇을 더했는지 목록으로 돌려준다.

    여러 번 실행해도 안전하다(멱등). 앱이 뜰 때마다 호출된다.
    """
    inspector = inspect(engine)
    applied: list[str] = []

    for table, column, ddl_type in ADDITIVE_COLUMNS:
        if not inspector.has_table(table):
            continue  # create_all이 새로 만들 테이블 — 이미 컬럼을 갖고 태어난다
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column in existing:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
        applied.append(f"{table}.{column}")

    return applied
