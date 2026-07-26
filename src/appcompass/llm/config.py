"""LLM 설정 로드/저장.

키는 코드·DB·로그 어디에도 남기지 않는다 (CLAUDE.md §9 '로그에 민감정보 금지').
읽는 곳은 두 군데뿐이다.

    1. 환경변수 ANTHROPIC_API_KEY
    2. .env 파일 — 현재 작업 폴더, 그리고 앱 데이터 폴더

환경변수가 항상 이긴다. CI나 관리형 환경에서 파일을 심지 않고도 주입할 수 있어야 한다.
DB에 넣지 않는 이유는 분명하다. 프로젝트 데이터를 내보내거나 백업할 때
키가 함께 딸려 나가는 사고를 구조적으로 막기 위해서다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import LLMError

ENV_API_KEY = "ANTHROPIC_API_KEY"
ENV_MODEL = "APPCOMPASS_LLM_MODEL"
ENV_EFFORT = "APPCOMPASS_LLM_EFFORT"

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")

# 초안 하나가 이보다 오래 걸리면 사용자는 앱이 멈춘 줄 안다.
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_TOKENS = 8000


class LLMSettingsError(LLMError):
    next_action = "입력한 값을 확인하고 다시 저장하세요."


def app_data_dir() -> Path:
    """DB와 같은 곳. 앱을 지우지 않는 한 유지된다."""
    base = Path(os.environ.get("APPDATA") or Path.home())
    directory = base / "AppCompass"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def env_file_path() -> Path:
    """설정 화면에서 저장할 때 쓰는 파일."""
    return app_data_dir() / ".env"


def _candidate_env_files() -> tuple[Path, ...]:
    """앞의 것이 이긴다. 개발 중에는 저장소 .env가 앱 데이터보다 우선한다."""
    return (Path.cwd() / ".env", env_file_path())


def _read_env_file(path: Path) -> dict[str, str]:
    """아주 작은 .env 파서.

    python-dotenv를 쓰지 않는다. 의존성 하나를 더 얹을 만한 일이 아니고,
    여기서 필요한 문법은 KEY=VALUE 한 줄이 전부다.
    """
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _lookup(name: str) -> str:
    """환경변수 → .env 순서로 찾는다. 없으면 빈 문자열."""
    from_env = os.environ.get(name)
    if from_env:
        return from_env.strip()
    for path in _candidate_env_files():
        value = _read_env_file(path).get(name, "").strip()
        if value:
            return value
    return ""


def mask_key(key: str) -> str:
    """화면·로그에 쓰는 표시용. 원본은 어떤 경우에도 출력하지 않는다."""
    if not key:
        return "(없음)"
    if len(key) <= 12:
        return "*" * len(key)
    return f"{key[:7]}…{key[-4:]}"


@dataclass(frozen=True, slots=True)
class LLMConfig:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    #: 키를 어디서 찾았는지. 사용자가 "어느 파일을 고쳐야 하나"를 알 수 있어야 한다.
    source: str = "없음"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def masked_key(self) -> str:
        return mask_key(self.api_key)

    def redacted(self) -> dict[str, object]:
        """로그·감사 기록용. 키 원본이 들어갈 자리가 아예 없다."""
        return {
            "model": self.model,
            "effort": self.effort,
            "max_tokens": self.max_tokens,
            "key_source": self.source,
            "key": self.masked_key,
        }

    def with_key(self, api_key: str) -> LLMConfig:
        return replace(self, api_key=api_key.strip(), source="직접 지정")


def load_config() -> LLMConfig:
    """호출할 때마다 다시 읽는다.

    설정 화면에서 키를 저장한 직후 곧바로 쓸 수 있어야 하므로 캐시하지 않는다.
    파일 읽기 비용은 LLM 호출 한 번에 비하면 무시할 수 있다.
    """
    key = ""
    source = "없음"
    if os.environ.get(ENV_API_KEY, "").strip():
        key = os.environ[ENV_API_KEY].strip()
        source = f"환경변수 {ENV_API_KEY}"
    else:
        for path in _candidate_env_files():
            value = _read_env_file(path).get(ENV_API_KEY, "").strip()
            if value:
                key = value
                source = str(path)
                break

    model = _lookup(ENV_MODEL) or DEFAULT_MODEL
    effort = (_lookup(ENV_EFFORT) or DEFAULT_EFFORT).lower()
    if effort not in VALID_EFFORTS:
        effort = DEFAULT_EFFORT

    return LLMConfig(api_key=key, model=model, effort=effort, source=source)


def save_api_key(api_key: str, model: str = "") -> Path:
    """앱 데이터 폴더의 .env에 키를 쓴다.

    평문으로 저장된다. OS 키체인을 쓰지 않는 이유는, 지금 이 앱이 1인 로컬 도구이고
    같은 계정으로 로그인한 사람은 어차피 DB 파일 전체를 읽을 수 있기 때문이다.
    설정 화면은 이 사실을 사용자에게 그대로 알린다.

    기존 파일의 다른 키(예: 저장소 토큰)는 건드리지 않는다.
    """
    api_key = (api_key or "").strip()
    if not api_key:
        raise LLMSettingsError("API 키가 비어 있습니다.")
    if any(c.isspace() for c in api_key):
        raise LLMSettingsError("API 키에 공백이 들어 있습니다. 복사할 때 잘렸는지 확인하세요.")

    path = env_file_path()
    values = _read_env_file(path)
    values[ENV_API_KEY] = api_key
    if model.strip():
        values[ENV_MODEL] = model.strip()

    lines = [
        "# AppCompass AI — LLM 설정",
        "# 이 파일에는 평문 API 키가 들어 있습니다. 공유하거나 커밋하지 마세요.",
        "",
    ]
    lines.extend(f"{k}={v}" for k, v in sorted(values.items()))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)  # POSIX에서만 의미가 있다. Windows에서는 조용히 무시된다.
    except OSError:
        pass
    return path


def clear_api_key() -> Path | None:
    """앱 데이터 .env에서 키만 지운다. 다른 키는 남긴다."""
    path = env_file_path()
    values = _read_env_file(path)
    if ENV_API_KEY not in values:
        return None
    values.pop(ENV_API_KEY)
    lines = ["# AppCompass AI — LLM 설정", ""]
    lines.extend(f"{k}={v}" for k, v in sorted(values.items()))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
