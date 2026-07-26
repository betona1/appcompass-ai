"""분석 결과 JSON Schema 검증 (CLAUDE.md §10.3 출력 계약).

Phase 1은 규칙 엔진만 쓰므로 스키마 실패가 나면 그것은 우리 코드의 버그다.
그래도 검증을 강제하는 이유는, 나중에 LLM 결과가 같은 경로로 들어올 때
'검증 없이 저장'하는 경로가 애초에 존재하지 않게 만들기 위해서다.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ANALYSIS_RESULT_SCHEMA = "analysis_result-0.1.0.json"
IDEA_STRUCTURE_DRAFT_SCHEMA = "idea_structure_draft-0.1.0.json"
TARGET_CANDIDATES_DRAFT_SCHEMA = "target_candidates_draft-0.1.0.json"

_HERE = Path(__file__).resolve()


def _search_paths() -> tuple[Path, ...]:
    """스키마 파일 후보 경로.

    소스 실행(repo/schemas), 패키지 동봉(appcompass/schemas),
    PyInstaller 번들(sys._MEIPASS/schemas)을 모두 지원한다.
    실행파일에서 스키마를 못 찾으면 모든 분석이 FAILED_SCHEMA가 되므로
    번들 경로를 반드시 포함해야 한다.
    """
    paths: list[Path] = []
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        paths.append(Path(bundle_dir) / "schemas")
    paths.append(_HERE.parents[3] / "schemas")
    paths.append(_HERE.parents[1] / "schemas")
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).resolve().parent / "schemas")
    return tuple(paths)


SCHEMA_SEARCH_PATHS: tuple[Path, ...] = _search_paths()


def _schema_path(schema_name: str) -> Path:
    for base in SCHEMA_SEARCH_PATHS:
        candidate = base / schema_name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"스키마 파일을 찾을 수 없습니다: {schema_name} "
        f"(검색 경로: {[str(p) for p in SCHEMA_SEARCH_PATHS]})"
    )


class SchemaValidationError(ValueError):
    """스키마 검증 실패. 이 예외가 나면 분석 상태는 FAILED_SCHEMA가 된다."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        super().__init__(
            f"{schema_name} 스키마 검증 실패 ({len(errors)}건):\n"
            + "\n".join(f"  - {e}" for e in errors[:20])
        )


@lru_cache(maxsize=8)
def _validator(schema_name: str) -> Draft202012Validator:
    schema = json.loads(_schema_path(schema_name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_payload(schema_name: str, payload: Any) -> None:
    """임의의 스키마로 payload를 검증한다. 실패 시 SchemaValidationError.

    LLM 응답도 반드시 이 함수를 통과해야 한다 (CLAUDE.md §10.3).
    '검증 없이 저장'하는 경로를 코드에 만들지 않기 위해, 저장 직전이 아니라
    어댑터가 값을 만들어 내는 지점에서 검증한다.
    """
    validator = _validator(schema_name)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        raise SchemaValidationError(
            schema_name,
            [
                f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                for e in errors
            ],
        )


def load_schema(schema_name: str) -> dict[str, Any]:
    """스키마 원문을 돌려준다.

    LLM에게 구조화 출력(output_config.format)을 요구할 때 같은 파일을 그대로 넘긴다.
    프롬프트에 스키마를 다시 적으면 검증용 스키마와 요청용 스키마가 어긋난다.
    """
    return json.loads(_schema_path(schema_name).read_text(encoding="utf-8"))


def validate_analysis_result(payload: dict[str, Any]) -> None:
    """실패 시 SchemaValidationError를 던진다. 성공 시 조용히 반환한다."""
    validate_payload(ANALYSIS_RESULT_SCHEMA, payload)
