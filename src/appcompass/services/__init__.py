"""서비스 계층.

UI와 (미래의) REST API가 공통으로 호출하는 진입점.
비즈니스 로직은 여기와 core에만 있고 UI에는 없다 (CLAUDE.md §9).
"""

from .app_service import AppService, ServiceError, PermissionDenied

__all__ = ["AppService", "ServiceError", "PermissionDenied"]
