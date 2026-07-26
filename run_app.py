"""저장소 루트에서 바로 실행하는 런처.

    python run_app.py

pip install 없이도 src/ 를 import 경로에 넣어 준다.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from appcompass.ui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
