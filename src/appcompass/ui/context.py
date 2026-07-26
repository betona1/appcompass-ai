"""화면들이 공유하는 현재 상태."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..services.app_service import AppService
from ..services.dto import ProjectDTO, RunDTO, VersionDTO


@dataclass(slots=True)
class ScreenContext:
    service: AppService
    project: ProjectDTO | None = None
    version: VersionDTO | None = None
    run: RunDTO | None = None

    @property
    def has_project(self) -> bool:
        return self.project is not None

    @property
    def has_version(self) -> bool:
        return self.version is not None

    @property
    def result(self) -> dict[str, Any] | None:
        if self.run is None or self.run.status != "COMPLETED":
            return None
        return self.run.result
