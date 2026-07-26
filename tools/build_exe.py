"""Windows 실행파일 빌드.

    pip install pyinstaller
    python tools/build_exe.py

결과: dist/AppCompass/AppCompass.exe  (+ release/AppCompass-AI-<버전>-win64.zip)

onefile 대신 onedir을 쓴다.
- 첫 실행이 빠르다 (onefile은 매번 임시폴더에 압축 해제)
- 백신 오탐이 상대적으로 적다
- schemas/ 를 실행파일 옆에 그대로 둘 수 있어 문제 추적이 쉽다
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release"
APP_NAME = "AppCompass"

sys.path.insert(0, str(SRC))
from appcompass import __version__  # noqa: E402


def run_pyinstaller() -> None:
    sep = ";" if sys.platform == "win32" else ":"
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--windowed",  # 콘솔 창 없이 GUI만
        "--paths",
        str(SRC),
        # 스키마는 반드시 동봉해야 한다. 없으면 모든 분석이 FAILED_SCHEMA가 된다.
        "--add-data",
        f"{ROOT / 'schemas'}{sep}schemas",
        # 문서도 함께 넣어 실행파일만 받은 사용자가 매뉴얼을 볼 수 있게 한다.
        "--add-data",
        f"{ROOT / 'docs' / 'MANUAL.md'}{sep}docs",
        "--add-data",
        f"{ROOT / 'LICENSE'}{sep}.",
        # PySide6에서 쓰지 않는 무거운 모듈을 제외해 용량을 줄인다.
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pytest",
        str(ROOT / "run_app.py"),
    ]
    print(">", " ".join(args[2:]))
    subprocess.run(args, check=True, cwd=ROOT)


def stage_extras(app_dir: Path) -> None:
    """실행파일 옆에 사람이 읽을 파일을 둔다."""
    shutil.copy2(ROOT / "docs" / "MANUAL.md", app_dir / "사용설명서.md")
    shutil.copy2(ROOT / "README.md", app_dir / "README.md")
    shutil.copy2(ROOT / "LICENSE", app_dir / "LICENSE")
    # schemas는 --add-data로 _internal에 들어가지만, 진단·수정이 쉽도록 옆에도 둔다.
    target = app_dir / "schemas"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / "schemas", target)


def make_zip(app_dir: Path) -> Path:
    RELEASE.mkdir(exist_ok=True)
    zip_path = RELEASE / f"AppCompass-AI-{__version__}-win64.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                zf.write(path, Path(APP_NAME) / path.relative_to(app_dir))
    return zip_path


def main() -> int:
    for directory in (DIST, BUILD):
        if directory.exists():
            shutil.rmtree(directory)

    run_pyinstaller()

    app_dir = DIST / APP_NAME
    exe = app_dir / f"{APP_NAME}.exe"
    if not exe.exists():
        print(f"빌드 실패: {exe} 가 없습니다.", file=sys.stderr)
        return 1

    stage_extras(app_dir)
    zip_path = make_zip(app_dir)

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print()
    print(f"실행파일 : {exe}")
    print(f"배포 zip : {zip_path}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
