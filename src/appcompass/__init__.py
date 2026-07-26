"""AppCompass AI - 앱 기획 의사결정 시스템.

계층 구조:
    core     : Qt/DB에 의존하지 않는 순수 도메인 엔진 (규칙·점수·신뢰도·피벗·보고서)
    llm      : LLM 어댑터 (core의 Port 구현. 초안만 만들고 판정하지 않는다)
    storage  : SQLAlchemy ORM 및 리포지토리
    services : UI/API가 공통으로 호출하는 파사드
    ui       : PySide6 데스크톱 화면

core는 어떤 상황에서도 storage/services/ui/llm을 import하지 않는다.
이 규칙이 유지되어야 이후 웹 서비스로 이전할 때 core를 그대로 재사용할 수 있고,
LLM을 통째로 들어내도 분석 엔진이 그대로 동작한다.
"""

__version__ = "0.7.0"
