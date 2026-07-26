# AppCompass AI

앱 아이디어를 구조화하고 진단해 **유지·수정·피벗**을 판단하는 기획 의사결정 시스템.

현재 단계: **Phase 0 + Phase 1 (PySide6 데스크톱, 규칙 엔진 전용)**

> **AI가 정답을 결정하지 않습니다.**
> 이 도구는 문제를 구조화하고, 부족한 근거를 찾고, 검증할 실험을 제안합니다.
> 최종 결정은 사람이 승인합니다.

📖 **[사용 설명서 (MANUAL.md)](docs/MANUAL.md)** — 처음 쓰신다면 여기부터

---

## 실행

### 실행파일 (Python 설치 불필요)

[Releases](../../releases) 에서 `AppCompass-AI-x.y.z-win64.zip` 을 받아 압축을 풀고
`AppCompass.exe` 를 실행합니다. Windows 10 이상 64비트.

> SmartScreen 경고가 뜨면 `추가 정보` → `실행`. 코드 서명이 되어 있지 않아서입니다.

### 소스에서 실행

```bash
pip install -r requirements.txt   # 또는 pip install -e .
python run_app.py
```

Python 3.11 이상이 필요합니다. 데이터는 `%APPDATA%\AppCompass\appcompass.sqlite3`에 저장됩니다.
다른 위치를 쓰려면 환경변수 `APPCOMPASS_DB_URL`을 지정하세요.

```bash
# 예: 프로젝트 폴더에 DB 두기
set APPCOMPASS_DB_URL=sqlite:///./appcompass.sqlite3
python run_app.py
```

### 실행파일 직접 빌드

```bash
pip install pyinstaller
python tools/build_exe.py
# dist/AppCompass/AppCompass.exe 생성
```

## 테스트

```bash
pytest -q                # 88개
```

UI 스모크 테스트는 offscreen 모드로 돌아가므로 창이 뜨지 않습니다.

## 화면 확인용 스크린샷

```bash
python tools/screenshot.py tools/shots
```

데모 데이터를 만들고 모든 화면을 PNG로 저장합니다. 창은 뜨지 않습니다.

---

## 아키텍처

```text
appcompass/
├─ core/        Qt·DB에 의존하지 않는 순수 엔진 (판정의 전부가 여기 있다)
│  ├─ enums.py         모든 상태값
│  ├─ models.py        값 객체 (dataclass)
│  ├─ policy.py        가중치·신뢰도·임계치  ← 운영자가 바꾸는 유일한 지점
│  ├─ textsignals.py   결정론적 텍스트 신호 사전
│  ├─ rules.py         경고 규칙 (BROAD_TARGET 등)
│  ├─ scoring.py       10개 항목 채점 (순수 함수)
│  ├─ confidence.py    근거 기반 신뢰도
│  ├─ pivot.py         피벗 판정 (HOLD 우선)
│  ├─ planner.py       타깃 후보 / MVP 초안
│  ├─ pipeline.py      오케스트레이터
│  ├─ report.py        Markdown / HTML
│  ├─ schema.py        JSON Schema 검증
│  ├─ ports.py         LLM 연결 지점 (지금은 비어 있음)
│  └─ domains/         VibeQuest / examath 도메인 모듈
├─ storage/     SQLAlchemy 2.0 ORM + 리포지토리
├─ services/    AppService — UI와 (미래의) REST API 공통 진입점
└─ ui/          PySide6 화면
```

**의존 방향은 한쪽입니다.** `ui → services → storage → core`.
`core`는 위 어느 것도 import하지 않습니다. 웹으로 옮길 때 `ui`만 버리고
같은 `AppService`를 Django/FastAPI 뷰 뒤에 두면 됩니다.

---

## 화면 흐름

| 탭 | 목적 | 완료 조건 |
|---|---|---|
| A. 아이디어 입력 | 원문을 그대로 받아 보존 | 새 버전 생성 |
| B. 구조화 검토 | 구조화 필드를 채우고 경고 해소 후 승인 | 승인해야 분석 가능 |
| 근거 | 인터뷰·프로토타입·행동 데이터 등록 | 신뢰도 상승 |
| C. 자동 진단 | 판단 → 다음 행동 → 위험 → 점수 | — |
| D. 타깃 후보 | 후보 비교 후 하나 선택 | — |
| E. MVP | P0 / P1 / 제외 기능 확정 | — |
| G. 피벗 보고서 | Markdown·HTML 미리보기와 내보내기 | — |
| H. 버전 비교 | 무엇이 왜 바뀌었고 점수·판단이 어떻게 달라졌는지 | — |
| 정책 | 가중치·임계치 수정 (운영자) | 합계 100 강제 |

---

## 이 버전에서 지켜지는 규칙

- **점수·신뢰도·피벗은 전부 결정론적 규칙 엔진**이 계산합니다. 동일 입력 + 동일 정책 버전이면 항상 같은 결과가 나옵니다.
- **근거가 없으면 항목 신뢰도는 0.20을 넘지 못하고**, 전체 신뢰도가 임계치 미만이면 판단은 `HOLD`입니다.
  다만 "근거가 충분했다면 무엇이었을지"(`would_be_decision`)를 함께 보여줍니다.
- **AI는 근거를 만들지 않습니다.** 근거는 사람이 등록한 것만 존재합니다.
- 모든 분석 결과는 저장 전에 **JSON Schema 검증**을 통과해야 합니다 (`schemas/`).
  실패하면 상태가 `FAILED_SCHEMA`가 되고 그 결과로는 점수도 피벗도 만들지 않습니다.
- 모든 결과와 보고서에 **엔진·정책·스키마 버전**이 기록됩니다.
- 생성·수정·삭제·분석·정책 변경은 **감사 로그**에 남습니다.
- 파괴적 작업(프로젝트 삭제)은 **이름을 직접 입력**해야 실행됩니다.
- 심각도와 판정은 **색만으로 구분하지 않고** 기호 + 한글 라벨을 함께 씁니다.

## 아직 없는 것

Phase 2 이후로 미룬 항목입니다.

- 가설·실험 설계와 결과 입력 (화면 F)
- 피벗 승인/거절 워크플로
- PDF 내보내기
- 앱 이벤트 수집 SDK, 퍼널 대시보드
- LLM 연동 (`core/ports.py`에 인터페이스만 열려 있음)
- 다중 사용자·조직 권한 (구조는 이미 있으나 데스크톱에서는 로컬 사용자 1명)

---

## 도메인 모듈 추가하기

`core/domains/`에 모듈을 만들고 `registry.py`에 등록하면 끝입니다.
`core` 엔진은 건드리지 않습니다.

```python
class MyDomain:
    code = DomainCode.MY_DOMAIN
    label = "표시 이름"

    def validate_input(self, idea) -> list[DiagnosisWarning]: ...
    def enrich_unknowns(self, idea) -> list[str]: ...
    def score_adjustments(self, idea, warnings) -> list[ScoreAdjustment]: ...
    def seed_target_candidates(self, idea) -> list[TargetCandidate]: ...
    def constrain_mvp(self, plan, idea) -> MvpPlan: ...
    def domain_metrics(self) -> list[MetricDefinition]: ...
    def domain_pivot_rules(self) -> list[PivotRule]: ...
```

---

## 문서

| 문서 | 내용 |
|---|---|
| [docs/MANUAL.md](docs/MANUAL.md) | **사용 설명서** — 10분 따라하기, 화면별 사용법, FAQ |
| [CLAUDE.md](CLAUDE.md) | 제품 원칙과 도메인 정의 (최상위 지침) |
| [TECHSPEC.md](TECHSPEC.md) | 기술 명세. 부록 A에 1차 구현 현황 |
| [docs/decisions/](docs/decisions/) | ADR — 왜 데스크톱인지, 왜 LLM을 안 쓰는지 |

---

## 참고 서적

이 프로젝트의 제품 원칙(`CLAUDE.md`)은 다음 네 권의 공통 구조를 기반으로 정리한 것입니다.
각 판정 규칙이 어디에서 왔는지 밝히기 위해 명시합니다.

| 서적 | 이 프로젝트에 반영된 부분 |
|---|---|
| **기획의 정석** — 박신영, 세종서적 | 문제 정의, Why·Whom, 핵심 메시지 한 문장, 논리 흐름 → `rules.py`의 문제 정의 검증, D01·D05 채점 |
| **10년차 IT 기획자의 노트** — 정재현, 로드북 | 요구사항·스펙 작성, 협업 문서, 백로그, 예외 상황 우선, 회고 → 화면 B의 12개 구조화 필드, 실패·빈 상태 요구사항 |
| **앱 기획편** (기획자·디자이너를 위한) | UX/UI, 정보구조(IA), 사용자 흐름, 와이어프레임, 출시 절차 → `planner.py`의 핵심 사용자 흐름, 첫 성공 경험(D06) |
| **모바일 앱 마케팅** | 유입·전환·참여, 딥링크, 측정과 개선 → D09 유입 가능성, 측정 이벤트 필수 규칙(§2.6) |

> **저작권 안내**
> 위 서적들의 내용을 정리한 요약본(`앱기획_4권_통합요약본.html`)은 로컬 참고용으로만 사용하며,
> 이 공개 저장소에는 포함하지 않았습니다. 원 저작물의 권리는 각 저자와 출판사에 있습니다.
> 이 저장소에 있는 것은 위 원칙을 **코드로 구현한 결과물**이며, 서적 본문이 아닙니다.
> 각 개념을 제대로 이해하려면 원서를 직접 읽어보시길 권합니다.

---

## 라이선스

[MIT License](LICENSE) — 이 저장소의 소스 코드에 한합니다.
위 참고 서적의 내용은 각 저작권자에게 권리가 있으며 이 라이선스의 적용을 받지 않습니다.
