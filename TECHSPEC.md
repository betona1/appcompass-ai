# TECHSPEC.md

> 프로젝트: **AppCompass AI**
>
> 문서 버전: 0.1
>
> 상태: MVP 기술 명세
>
> 주요 대상: 기획자, 개발자, AI 에이전트, 운영자

---

# 1. 문서 목적

본 문서는 AppCompass AI의 제품 요구사항을 구현 가능한 기술 단위로 분류한다.

AppCompass AI는 다음을 수행한다.

1. 자유 형식 앱 아이디어 입력
2. 구조화된 문제·타깃·가치 제안 생성
3. 규칙 엔진과 AI를 결합한 자동 진단
4. 타깃 후보 및 해결책 제안
5. MVP 및 검증 실험 설계
6. 실제 근거와 행동 데이터 저장
7. 유지·수정·피벗 판단
8. Markdown, HTML, PDF 보고서 생성
9. VibeQuest와 examath 도메인 전용 분석

---

# 2. 범위

## 2.1 MVP 포함 범위

- 사용자 계정
- 프로젝트 생성 및 버전 관리
- 아이디어 구조화
- 문제·타깃 자동 진단
- 10개 평가 항목 점수
- 근거 등록
- 신뢰도 계산
- 핵심 언노운 생성
- 타깃 후보 3개 생성
- MVP 기능 제안
- 실험 계획 생성
- 피벗 상태 판정
- Markdown/HTML 보고서
- VibeQuest 도메인 모듈
- examath 도메인 모듈
- 감사 로그
- 관리자 정책 설정

## 2.2 MVP 제외 범위

- 실제 광고 플랫폼 자동 집행
- 앱스토어 계정 자동 등록
- 실시간 협업 편집
- 완전 자동 투자 판단
- 자동 법률 검토
- 자유로운 외부 코드 실행
- 어린이 대상 공개 커뮤니티
- 실시간 다국어 번역
- 사용자 승인 없는 자동 피벗 적용
- 실시간 전체 앱 분석 SDK

---

# 3. 권장 기술 스택

## 3.1 Backend

- Python
- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- OpenAPI Schema
- pytest

## 3.2 Frontend

- React + TypeScript
- 반응형 Web UI
- Query cache 라이브러리
- Form schema validation
- E2E 테스트 도구

## 3.3 AI

- LLM Provider Adapter
- JSON Schema 기반 구조 출력
- Prompt Registry
- Prompt Versioning
- 규칙 기반 Scoring Engine
- 규칙 기반 Pivot Engine

## 3.4 배포

- Docker
- Nginx
- Gunicorn 또는 ASGI Server
- PostgreSQL 백업
- Redis 분리
- Object Storage
- CI/CD

---

# 4. 논리 아키텍처

```text
[Web Client]
     │
     ▼
[REST API]
     │
     ├─ Account Service
     ├─ Project Service
     ├─ Evidence Service
     ├─ Experiment Service
     ├─ Report Service
     │
     ▼
[Analysis Orchestrator]
     ├─ Idea Structure LLM
     ├─ Rule Validator
     ├─ Scoring Engine
     ├─ Target Candidate LLM
     ├─ MVP Planner LLM
     ├─ Pivot Engine
     └─ Report Generator
     │
     ├─ Domain Module: VibeQuest
     └─ Domain Module: examath
     │
     ▼
[PostgreSQL / Redis / Object Storage]
```

---

# 5. 기능 분류

## 5.1 F-001 계정 및 권한

### 목적

사용자별 프로젝트와 분석 결과를 보호한다.

### 기능

- 이메일 로그인 또는 소셜 로그인
- 사용자 프로필
- 조직 확장 가능 구조
- 프로젝트 소유자
- 프로젝트 편집자
- 프로젝트 조회자
- 관리자

### 권한

```text
OWNER
EDITOR
VIEWER
ADMIN
```

### 완료 기준

- 권한 없는 프로젝트 조회 차단
- 역할별 API 테스트
- 프로젝트 삭제는 OWNER만 가능
- 감사 로그 기록

---

## 5.2 F-010 프로젝트 관리

### 데이터

- 프로젝트 이름
- 앱 이름
- 설명
- 도메인
- 현재 단계
- 상태
- 생성자
- 최신 버전
- 보관 여부

### 프로젝트 단계

```text
IDEA
RESEARCH
PROTOTYPE
MVP
LIVE
PAUSED
ARCHIVED
```

### 기능

- 생성
- 수정
- 복제
- 보관
- 버전 생성
- 버전 비교
- 최신 보고서 보기

---

## 5.3 F-020 아이디어 입력 및 구조화

### 입력 필드

```json
{
  "app_name": "string",
  "raw_idea": "string",
  "target_user_raw": "string",
  "problem_raw": "string",
  "solution_raw": "string",
  "revenue_model_raw": "string",
  "distribution_channel_raw": "string",
  "current_stage": "IDEA"
}
```

### 구조화 결과

```json
{
  "app_name": "string",
  "target_user": "string",
  "payer": "string|null",
  "influencer": "string|null",
  "problem_situation": "string",
  "current_solution": "string|null",
  "current_solution_problem": "string|null",
  "core_action": "string",
  "expected_result": "string",
  "first_success": "string|null",
  "retention_reason": "string|null",
  "revenue_model": "string|null",
  "distribution_channel": "string|null",
  "unknowns": ["string"],
  "warnings": ["string"]
}
```

### 규칙

- 원문 보존
- AI 구조화 결과 별도 저장
- 사용자 승인 전 원문 덮어쓰기 금지
- 넓은 타깃 표현 자동 경고
- 사용자·구매자·영향자 누락 경고

---

## 5.4 F-030 자동 진단

### 평가 항목

| 코드 | 항목 | 가중치 |
|---|---|---:|
| D01 | 문제 구체성 | 15 |
| D02 | 문제 강도·빈도 | 10 |
| D03 | 타깃 명확성 | 10 |
| D04 | 사용자·구매자 구분 | 5 |
| D05 | 가치 제안 | 10 |
| D06 | 첫 성공 경험 | 10 |
| D07 | 반복 사용 이유 | 10 |
| D08 | 차별성 | 10 |
| D09 | 유입 가능성 | 10 |
| D10 | 구현 가능성 | 10 |

가중치 합계는 100이어야 한다.

### 점수

각 항목은 0~5점이다.

```text
0 = 정보 없음
1 = 매우 약함
2 = 약함
3 = 보통
4 = 강함
5 = 매우 강함
```

### 정규화 점수

```text
normalized_score =
Σ((dimension_score / 5) × dimension_weight)
```

결과 범위는 0~100이다.

### 결과 필드

```json
{
  "total_score": 0,
  "dimensions": [
    {
      "code": "D01",
      "score": 0,
      "weight": 15,
      "reason": "string",
      "missing_evidence": ["string"],
      "recommended_action": "string"
    }
  ],
  "critical_risks": ["string"],
  "unknowns": ["string"]
}
```

---

## 5.5 F-040 근거 관리

### 근거 유형

```text
FOUNDER_ASSUMPTION
DESK_RESEARCH
USER_INTERVIEW
PROTOTYPE_TEST
BEHAVIOR_DATA
EXPERT_REVIEW
```

### 초기 신뢰도

| 근거 유형 | 기본값 |
|---|---:|
| FOUNDER_ASSUMPTION | 0.20 |
| DESK_RESEARCH | 0.35 |
| USER_INTERVIEW | 0.50 |
| PROTOTYPE_TEST | 0.70 |
| BEHAVIOR_DATA | 1.00 |
| EXPERT_REVIEW | 관리자 설정 |

### Evidence 필드

```json
{
  "type": "USER_INTERVIEW",
  "title": "string",
  "summary": "string",
  "source_reference": "string|null",
  "sample_size": 0,
  "observed_at": "datetime|null",
  "confidence_override": null,
  "supports": ["hypothesis-id"],
  "contradicts": ["hypothesis-id"],
  "attachment_id": null
}
```

### 규칙

- AI가 근거를 임의 생성하지 않음
- 원본 출처 또는 사용자 입력 추적
- 근거는 가설을 지지하거나 반박할 수 있음
- 근거 삭제도 감사 로그 기록
- 행동 데이터는 이벤트 정의와 연결

---

## 5.6 F-050 신뢰도 계산

### 목적

같은 점수라도 근거 수준에 따라 판단 강도를 다르게 한다.

### 계산 원칙

```text
dimension_confidence =
weighted_average(evidence_confidence)
```

근거가 없는 항목은 0.20을 초과할 수 없다.

### 전체 신뢰도

```text
overall_confidence =
Σ(dimension_confidence × dimension_weight) / 100
```

### 규칙

- `overall_confidence < policy.hold_threshold`이면 `HOLD`
- 관리자 정책값으로 임계치 변경 가능
- 근거가 상충하면 신뢰도와 경고를 함께 낮춤
- 표본 수만으로 자동 확정하지 않음

---

## 5.7 F-060 타깃 후보 생성

### 출력 개수

기본 3개.

### 후보 구조

```json
{
  "candidates": [
    {
      "name": "string",
      "user": "string",
      "payer": "string|null",
      "influencer": "string|null",
      "trigger_situation": "string",
      "problem": "string",
      "current_alternative": "string|null",
      "why_promising": ["string"],
      "risks": ["string"],
      "validation_questions": ["string"],
      "recommended_experiment": "string"
    }
  ],
  "recommended_candidate_index": 0,
  "recommendation_reason": "string"
}
```

### 규칙

- 단순 인구통계만 다른 후보 금지
- 문제 상황과 행동이 서로 달라야 함
- 사용자·구매자·영향자 구분
- 추천 이유에 근거 연결
- 근거 부족 시 추천 대신 비교만 제공

---

## 5.8 F-070 MVP 계획

### 출력

```json
{
  "core_hypothesis": "string",
  "problem_hypothesis": "string",
  "behavior_hypothesis": "string",
  "value_hypothesis": "string",
  "retention_hypothesis": "string",
  "revenue_hypothesis": "string|null",
  "p0_features": ["string"],
  "p1_features": ["string"],
  "excluded_features": ["string"],
  "first_success_experience": "string",
  "core_user_flow": ["string"],
  "metrics": ["string"],
  "risks": ["string"]
}
```

### 규칙

- 기능별로 검증할 가설 연결
- 측정 이벤트 없는 기능 경고
- MVP 제외 기능을 명시
- P2/P3 기능은 기본 숨김
- 도메인 모듈 제약 적용

---

## 5.9 F-080 실험 설계

### 실험 유형

```text
INTERVIEW
LANDING_PAGE
CLICK_DUMMY
PROTOTYPE
CONCIERGE
MVP_RELEASE
PRICING_TEST
RETENTION_TEST
```

### Experiment 필드

```json
{
  "title": "string",
  "hypothesis_id": "uuid",
  "type": "PROTOTYPE",
  "target_segment": "string",
  "procedure": ["string"],
  "success_metric": "string",
  "target_value": "number|null",
  "sample_goal": "number|null",
  "start_at": "datetime|null",
  "end_at": "datetime|null",
  "status": "DRAFT"
}
```

### 상태

```text
DRAFT
READY
RUNNING
COMPLETED
CANCELLED
```

### 결과

- 정량 결과
- 정성 요약
- 지지
- 반박
- 불충분
- 다음 실험

---

## 5.10 F-090 피벗 엔진

### Pivot 상태

```text
KEEP
REFINE
TARGET_PIVOT
PROBLEM_PIVOT
SOLUTION_PIVOT
CHANNEL_PIVOT
REVENUE_PIVOT
RETENTION_REDESIGN
HOLD
```

### 우선 규칙

```text
1. 신뢰도 부족 → HOLD
2. 문제 강도 부족 → PROBLEM_PIVOT
3. 타깃 불명확 → TARGET_PIVOT
4. 관심은 있으나 핵심 행동 실패 → SOLUTION_PIVOT
5. 핵심 행동 성공, 재방문 실패 → RETENTION_REDESIGN
6. 유지율 양호, 유입 실패 → CHANNEL_PIVOT
7. 사용 양호, 지불 실패 → REVENUE_PIVOT
8. 큰 문제 없음 → KEEP 또는 REFINE
```

### 주의

임계치는 전역 상수가 아니라 `EvaluationPolicy`에서 관리한다.

### 결과

```json
{
  "decision": "TARGET_PIVOT",
  "confidence": 0.0,
  "reason_codes": ["BROAD_TARGET"],
  "evidence_ids": ["uuid"],
  "keep": ["string"],
  "change": ["string"],
  "remove": ["string"],
  "next_experiments": ["uuid"],
  "requires_human_approval": true
}
```

---

## 5.11 F-100 보고서

### 형식

- Markdown
- HTML
- PDF

### 섹션

1. 프로젝트 개요
2. 원본 아이디어
3. 구조화된 문제 정의
4. 타깃 분석
5. 점수 및 이유
6. 핵심 위험
7. 언노운
8. 추천 타깃
9. MVP
10. 실험
11. 피벗 판단
12. 근거와 신뢰도
13. 다음 행동
14. 버전 변경 요약

### 규칙

- 분석 버전 고정
- 프롬프트 버전 기록
- 사용한 근거 표시
- 오래된 보고서는 수정하지 않고 새 버전 생성
- 결과 문구와 원시 JSON 함께 저장

---

# 6. 도메인 모듈

## 6.1 DomainModule 인터페이스

```python
class DomainModule(Protocol):
    code: str

    def validate_input(self, idea: IdeaStructure) -> list[DomainWarning]:
        ...

    def enrich_unknowns(self, idea: IdeaStructure) -> list[str]:
        ...

    def score_adjustments(self, context: AnalysisContext) -> list[ScoreAdjustment]:
        ...

    def constrain_mvp(self, plan: MvpPlan) -> MvpPlan:
        ...

    def domain_metrics(self) -> list[MetricDefinition]:
        ...

    def domain_pivot_rules(self) -> list[PivotRule]:
        ...
```

---

## 6.2 VibeQuest 모듈

### 코드

```text
VIBEQUEST
```

### 필수 경고

- “모든 사람”
- AI 관심자 전체
- 용어 정의 문제만 존재
- 실제 작업 상황 없음
- 난이도 구분 없음
- 출처 검증 없는 AI 생성 문제
- 학습 전이 측정 없음

### 필수 언노운

- 사용자가 실제로 막히는 용어
- 막히는 프로젝트 단계
- 초보자의 선행지식
- 학습 후 실제 작업 재개 여부
- 재방문 이유
- 유료 전환 이유

### 도메인 지표

```text
diagnostic_complete
first_mission_complete
scenario_question_complete
wrong_concept_review_complete
project_stage_selected
concept_to_task_transfer
daily_mission_return
```

### 도메인 피벗 예

- 일반 용어 정답률은 높지만 실제 상황 문제 실패  
  → `SOLUTION_PIVOT`
- AI 용어보다 개발 기본 용어 오답이 압도적  
  → 범위를 바이브코딩 기초로 확장 또는 재정의
- 비개발자 완료율이 낮음  
  → 타깃 또는 난이도 피벗
- 기업 교육 문의가 반복됨  
  → B2B 후보 생성

---

## 6.3 examath 모듈

### 코드

```text
EXAMATH
```

### 필수 경고

- “수학을 배우는 아이 전체”
- 학년과 난관이 없음
- 어린이 사용자와 부모 구매자 미분리
- 정답률만 평가
- 과도한 경쟁
- 광고 또는 가챠
- 실패를 부정적으로 표현
- 어린이 데이터 과수집

### 오류 분류 Enum

```text
SUBTRACTION_MEANING
COUNTING_BACK
NUMBER_COMPARISON
MAKE_TEN
PLACE_VALUE
REGROUPING_CONCEPT
PROCEDURE_ONLY
MATH_ANXIETY_AVOIDANCE
CONCRETE_TO_SYMBOL_TRANSFER
UNKNOWN
```

### 도메인 지표

```text
child_session_start
diagnostic_complete
manipulative_action_complete
make_ten_complete
concrete_problem_complete
pictorial_problem_complete
symbol_problem_complete
hint_used
retry_after_error
error_type_detected
parent_weekly_summary_view
```

### 도메인 피벗 예

- 구체물 성공, 숫자 실패  
  → 표현 전환 단계 강화
- 부모 설치, 아이 첫 세션 실패  
  → 첫 경험과 난이도 변경
- 아이 사용, 부모 유지 의사 낮음  
  → 부모 가치 제안 변경
- 특정 오류가 대부분  
  → 해당 오류 중심으로 범위 축소
- 교사 사용 비중 증가  
  → 교실 보조 도구 후보 생성

### 어린이 보호 원칙

- 최소 정보만 수집
- 공개 프로필 없음
- 공개 채팅 없음
- 행동 데이터는 익명 또는 가명 처리
- 부모용 결과에 낙인 표현 금지
- 법률·스토어 정책은 출시 전 별도 검토

---

# 7. 데이터 모델

## 7.1 Project

| 필드 | 형식 |
|---|---|
| id | UUID |
| owner_id | FK |
| name | string |
| app_name | string |
| domain_code | enum |
| stage | enum |
| status | enum |
| latest_version_id | FK nullable |
| created_at | datetime |
| updated_at | datetime |

## 7.2 ProjectVersion

| 필드 | 형식 |
|---|---|
| id | UUID |
| project_id | FK |
| version_no | integer |
| raw_input | JSON |
| structured_idea | JSON |
| created_by | FK |
| created_at | datetime |

## 7.3 AnalysisRun

| 필드 | 형식 |
|---|---|
| id | UUID |
| project_version_id | FK |
| status | enum |
| prompt_version | string |
| model_name | string |
| policy_version | string |
| started_at | datetime |
| completed_at | datetime nullable |
| error_code | string nullable |

### 상태

```text
QUEUED
RUNNING
COMPLETED
FAILED_SCHEMA
FAILED_PROVIDER
FAILED_INTERNAL
CANCELLED
```

## 7.4 EvaluationScore

| 필드 | 형식 |
|---|---|
| id | UUID |
| analysis_run_id | FK |
| dimension_code | string |
| raw_score | decimal |
| weight | decimal |
| normalized_score | decimal |
| reason | text |
| confidence | decimal |

## 7.5 Evidence

| 필드 | 형식 |
|---|---|
| id | UUID |
| project_id | FK |
| evidence_type | enum |
| title | string |
| summary | text |
| sample_size | integer nullable |
| source_reference | text nullable |
| observed_at | datetime nullable |
| confidence | decimal |
| created_by | FK |

## 7.6 Hypothesis

```text
PROBLEM
TARGET
BEHAVIOR
VALUE
RETENTION
REVENUE
CHANNEL
```

## 7.7 Experiment

- hypothesis
- experiment_type
- target_segment
- procedure
- success_metric
- target_value
- status
- result
- conclusion

## 7.8 PivotDecision

- decision
- confidence
- reason_codes
- keep
- change
- remove
- approval_status
- approved_by
- approved_at

## 7.9 Report

- analysis_run
- format
- storage_path
- checksum
- created_at

## 7.10 AuditLog

- actor
- action
- object_type
- object_id
- before
- after
- created_at

---

# 8. API 명세

## 8.1 프로젝트

```http
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/versions
GET    /api/v1/projects/{project_id}/versions
```

## 8.2 분석

```http
POST /api/v1/projects/{project_id}/analysis-runs
GET  /api/v1/analysis-runs/{run_id}
POST /api/v1/analysis-runs/{run_id}/cancel
POST /api/v1/analysis-runs/{run_id}/retry
```

### 분석 생성 응답

```json
{
  "run_id": "uuid",
  "status": "QUEUED"
}
```

## 8.3 근거

```http
POST   /api/v1/projects/{project_id}/evidence
GET    /api/v1/projects/{project_id}/evidence
PATCH  /api/v1/evidence/{evidence_id}
DELETE /api/v1/evidence/{evidence_id}
```

## 8.4 가설·실험

```http
POST  /api/v1/projects/{project_id}/hypotheses
GET   /api/v1/projects/{project_id}/hypotheses
POST  /api/v1/projects/{project_id}/experiments
GET   /api/v1/projects/{project_id}/experiments
PATCH /api/v1/experiments/{experiment_id}
POST  /api/v1/experiments/{experiment_id}/results
```

## 8.5 피벗

```http
GET  /api/v1/projects/{project_id}/pivot-decisions/latest
POST /api/v1/pivot-decisions/{decision_id}/approve
POST /api/v1/pivot-decisions/{decision_id}/reject
```

## 8.6 보고서

```http
GET  /api/v1/projects/{project_id}/reports
POST /api/v1/analysis-runs/{run_id}/reports
GET  /api/v1/reports/{report_id}/download
```

## 8.7 이벤트 수집

```http
POST /api/v1/events/batch
```

### 이벤트 형식

```json
{
  "events": [
    {
      "event_name": "core_action_complete",
      "anonymous_user_id": "string",
      "project_id": "uuid",
      "occurred_at": "datetime",
      "properties": {}
    }
  ]
}
```

---

# 9. LLM 파이프라인

## 9.1 단계

```text
RAW_INPUT
→ IDEA_STRUCTURE
→ VALIDATION
→ DIAGNOSIS_NARRATIVE
→ TARGET_CANDIDATES
→ MVP_PLAN
→ RULE_SCORING
→ PIVOT_DECISION
→ REPORT
```

## 9.2 책임 분리

| 작업 | LLM | 규칙 엔진 |
|---|---:|---:|
| 자유 입력 구조화 | O | 검증 |
| 타깃 후보 생성 | O | 제약 |
| 이유 설명 | O | 사실성 검사 |
| 점수 계산 | X | O |
| 신뢰도 계산 | X | O |
| 피벗 상태 결정 | 보조 | O |
| 보고서 문장 | O | 값 검증 |

## 9.3 프롬프트 버전

모든 호출은 다음을 기록한다.

- prompt_key
- prompt_version
- model_provider
- model_name
- schema_version
- input_hash
- output_hash
- latency
- token usage
- status

---

# 10. 규칙 엔진

## 10.1 넓은 타깃 감지

초기 키워드:

```text
모든 사람
누구나
전 국민
전체 사용자
관심 있는 사람
학생 모두
아이들 전체
```

문자열 규칙만 사용하지 않고 LLM 구조화 결과의 구체성도 검사한다.

## 10.2 필수 누락

- problem_situation 없음
- current_solution 없음
- core_action 없음
- expected_result 없음
- payer 없음이지만 교육·어린이 도메인
- first_success 없음
- retention_reason 없음

## 10.3 경고 코드

```text
BROAD_TARGET
NO_TRIGGER_SITUATION
NO_CURRENT_ALTERNATIVE
NO_PAYER_DEFINED
NO_FIRST_SUCCESS
NO_RETENTION_REASON
NO_MEASURABLE_RESULT
FEATURE_FIRST_IDEA
UNSUPPORTED_CLAIM
LOW_EVIDENCE
CONFLICTING_EVIDENCE
CHILD_DATA_RISK
```

---

# 11. UI 분류

## 11.1 화면 A: 프로젝트 입력

- 앱 이름
- 아이디어
- 예상 사용자
- 문제 상황
- 현재 대체 수단
- 해결 방법
- 수익 모델
- 유입 경로
- 도메인 선택

## 11.2 화면 B: 구조화 검토

- 원문
- AI 구조화 결과
- 수정
- 승인
- 경고
- 누락 필드

## 11.3 화면 C: 자동 진단

- 총점
- 항목별 점수
- 점수 이유
- 부족한 근거
- 핵심 위험
- 신뢰도

점수보다 이유와 다음 행동을 더 크게 표시한다.

## 11.4 화면 D: 타깃 후보

- 후보 3개
- 사용자
- 구매자
- 영향자
- 문제 상황
- 위험
- 검증 질문
- 선택

## 11.5 화면 E: MVP

- 핵심 가설
- P0
- P1
- 제외 기능
- 첫 성공
- 사용자 흐름
- 이벤트

## 11.6 화면 F: 실험

- 언노운
- 연결된 가설
- 추천 실험
- 성공 기준
- 결과 입력
- 결론

## 11.7 화면 G: 피벗 보고서

- 판단
- 신뢰도
- 근거
- 유지
- 변경
- 삭제
- 다음 실험
- 승인 또는 거절

## 11.8 화면 H: 버전 비교

- 이전 문제 정의
- 현재 문제 정의
- 이전 타깃
- 현재 타깃
- 기능 변경
- 점수 변화
- 변경 이유

---

# 12. 분석 이벤트

## 12.1 AppCompass 이벤트

```text
project_created
idea_input_started
idea_input_completed
structure_reviewed
analysis_requested
analysis_completed
analysis_failed
target_candidate_selected
mvp_plan_viewed
evidence_added
experiment_created
experiment_completed
pivot_report_viewed
pivot_approved
pivot_rejected
report_exported
```

## 12.2 공통 속성

- project_id
- project_version
- domain_code
- user_role
- analysis_run_id
- policy_version
- prompt_version

---

# 13. 보안 및 개인정보

## 13.1 기본

- 전송 구간 암호화
- 민감정보 로그 금지
- 파일 업로드 확장자와 크기 제한
- 객체 접근 권한 확인
- 프롬프트에 비밀키 삽입 금지
- API 키는 환경변수 또는 Secret Manager 사용
- 분석 입력에 포함된 토큰·키 패턴 마스킹
- 감사 로그 변조 방지

## 13.2 AI 보안

- 사용자 입력을 시스템 명령으로 취급하지 않음
- 업로드 문서의 지시문은 데이터로만 취급
- 출력 JSON Schema 강제
- HTML 보고서 출력 시 escaping
- 링크와 첨부파일 별도 검증
- 외부 코드 실행 금지

## 13.3 어린이 도메인

- 최소 수집
- 익명 또는 가명 ID
- 공개 프로필 없음
- 공개 채팅 없음
- 개인별 부정적 낙인 문구 금지
- 출시 국가의 관련 법령 및 스토어 정책 별도 검토

---

# 14. 비기능 요구사항

## 성능

- 일반 API p95 목표는 프로젝트 정책으로 관리
- 분석 생성은 비동기
- 상태 폴링 또는 SSE 지원 가능
- 보고서 재생성은 캐시 가능
- 동일 입력 중복 분석 방지

## 안정성

- LLM Provider 장애 시 재시도
- Celery 작업 idempotency
- 부분 실패 상태 저장
- 분석 단계별 재개
- DB 백업
- 보고서 checksum

## 관측성

- 구조화 로그
- 분석 단계별 latency
- LLM 실패율
- 스키마 실패율
- 피벗 승인율
- 도메인별 경고 빈도
- 비용 추적

---

# 15. 테스트 전략

## 15.1 단위 테스트

- 점수 정규화
- 가중치 합계
- 신뢰도 계산
- HOLD 우선
- 경고 코드
- 도메인 제약
- 피벗 규칙

## 15.2 계약 테스트

- IdeaStructure Schema
- Diagnosis Schema
- TargetCandidates Schema
- MvpPlan Schema
- PivotDecision Schema

## 15.3 고정 시나리오

### VibeQuest 입력

```text
AI 용어 문제풀이 앱
타깃: 바이브코딩에 관심 있는 모든 사람
```

필수 기대 결과:

- `BROAD_TARGET`
- `TARGET_PIVOT` 또는 신뢰도 부족 시 `HOLD`
- 초보 프로젝트 제작자 후보 포함
- 일반 용어 퀴즈 차별성 위험
- 실제 상황형 문제 제안

### examath 입력

```text
수학을 처음 배우는 꼬맹이들이
뺄셈의 난관에서 수학을 멀리하지 않게 하는 앱
```

필수 기대 결과:

- 사용자·구매자 분리 경고
- 초등 2학년 받아내림 후보
- 오류 유형 진단 제안
- 구체물→그림→숫자 전환
- 광고·가챠·실시간 랭킹 제외

## 15.4 E2E

- 프로젝트 생성
- 구조화 승인
- 분석 실행
- 근거 추가
- 재분석
- 피벗 결과 변화
- 보고서 다운로드

---

# 16. 완료 기준

MVP 완료 조건:

- 프로젝트와 버전 관리 가능
- 두 고정 시나리오 분석 성공
- 10개 평가 점수 재현 가능
- 근거와 신뢰도 반영
- HOLD 규칙 작동
- 타깃 후보 3개 생성
- MVP 계획 생성
- 피벗 보고서 생성
- Markdown/HTML 내보내기
- 권한 테스트 통과
- 감사 로그 작동
- 도메인 모듈 분리
- 운영자가 가중치와 임계치 수정 가능

---

# 17. 구현 단계

## Phase 0: 기반

- 저장소
- 인증
- 프로젝트
- 버전
- 정책 모델
- 감사 로그

## Phase 1: 분석 MVP

- 아이디어 구조화
- 넓은 타깃 감지
- 점수 엔진
- 타깃 후보
- MVP
- HTML/Markdown 보고서

## Phase 2: 근거와 실험

- 근거
- 가설
- 실험
- 신뢰도
- 재분석

## Phase 3: 피벗

- 피벗 규칙
- 승인
- 버전 비교
- 변경 이력

## Phase 4: 도메인 강화

- VibeQuest 문제 품질 모듈
- examath 오류 진단 모듈
- 도메인 이벤트
- 도메인 보고서

## Phase 5: 외부 데이터

- 앱 이벤트 수집
- 대시보드
- 퍼널
- 실제 데이터 기반 자동 재평가

---

# 18. 향후 확장

- TECHSPEC 자동 생성
- 사용자 인터뷰 질문 자동 생성
- 경쟁 앱 리뷰 입력
- 앱 이벤트 SDK
- 다중 프로젝트 포트폴리오
- 팀 협업
- 평가 정책 템플릿
- 도메인 플러그인 마켓
- 언어별 기획 보고서
- 실험 결과 자동 요약

---

# 19. 결정 기록

중요한 기술·제품 결정은 `docs/decisions/ADR-xxxx.md`에 저장한다.

ADR 필수 항목:

```text
제목
상태
날짜
문제
결정
대안
장점
단점
영향
재검토 조건
```

---

# 20. 최종 설계 원칙

```text
LLM은 문장을 만들고,
규칙 엔진은 판정을 재현하며,
근거 시스템은 신뢰도를 결정하고,
사람은 최종 결정을 승인한다.
```

---

# 부록 A. 1차 구현 현황 (Phase 0 + Phase 1)

> 갱신: 2026-07-26 · 대상 커밋: 초기 구현
>
> 본문 §3의 권장 스택(Django + React)과 다르게 1차는 **PySide6 데스크톱**으로 구현했다.
> 사유와 재검토 조건은 `docs/decisions/ADR-0001-desktop-first-pyside6.md` 참고.
> LLM을 쓰지 않는 사유는 `docs/decisions/ADR-0002-rule-engine-before-llm.md` 참고.

## A.1 실제 구현 스택

| 계층 | 본문 §3 권장 | 1차 구현 | 웹 이전 시 |
|---|---|---|---|
| 프레젠테이션 | React + TypeScript | PySide6 | 교체 |
| API | Django REST Framework | `services.AppService` (파사드) | 뷰가 그대로 호출 |
| 도메인 로직 | services/ | `core/` (Qt·DB 무의존) | **그대로 재사용** |
| 저장소 | PostgreSQL | SQLite + SQLAlchemy 2.0 | 연결 문자열 교체 |
| 비동기 | Celery + Redis | QThread 워커 | Celery로 교체 |
| 스키마 검증 | JSON Schema | `jsonschema` + `schemas/` | **그대로 재사용** |
| 테스트 | pytest | pytest (88개) | 확장 |

의존 방향은 `ui → services → storage → core` 한 방향이다. `core`는 나머지를 import하지 않는다.

## A.2 기능 구현 상태

| 코드 | 기능 | 상태 | 비고 |
|---|---|---|---|
| F-001 | 계정 및 권한 | 부분 | 로컬 사용자 1명. 소유자 검사와 `PermissionDenied`는 구현·테스트됨 |
| F-010 | 프로젝트 관리 | 완료 | 생성·수정·보관·삭제·버전 생성·버전 비교 |
| F-020 | 아이디어 입력 및 구조화 | 완료 | 구조화는 사람이 입력. 원문 불변 보장 |
| F-030 | 자동 진단 | 완료 | 10개 항목, 가중치 합계 100 강제 |
| F-040 | 근거 관리 | 완료 | 6개 유형, 지지·반박 항목 연결, 삭제 감사 로그 |
| F-050 | 신뢰도 계산 | 완료 | 무근거 상한 0.20, 상충 감쇠, 표본 보정 |
| F-060 | 타깃 후보 생성 | 완료(규칙) | 도메인 시드 + 현재 입력 파생. 근거 부족 시 추천 없이 비교만 |
| F-070 | MVP 계획 | 완료(규칙) | 도메인 `constrain_mvp` 적용 |
| F-080 | 실험 설계 | **미구현** | Phase 2 |
| F-090 | 피벗 엔진 | 완료 | 8단계 우선순위 + HOLD 우선 + `would_be_decision` |
| F-100 | 보고서 | 부분 | Markdown·HTML 완료. PDF 미구현 |

## A.3 데이터 모델 대비

본문 §7의 테이블 중 다음이 구현되었다.

```text
users / projects / project_versions / evaluation_policies
analysis_runs / evaluation_scores / evidence / reports
audit_logs / analytics_events
```

미구현: `Hypothesis`, `Experiment`, `PivotDecision`(승인 워크플로용 별도 테이블).
현재 피벗 결과는 `analysis_runs.result` JSON 안에 포함되고 승인 상태는 저장하지 않는다.

## A.4 API 대신 서비스 메서드

본문 §8의 엔드포인트에 대응하는 `AppService` 메서드는 다음과 같다.
웹 전환 시 뷰가 이 메서드를 호출하면 된다.

| 엔드포인트 | AppService 메서드 |
|---|---|
| `POST /api/v1/projects` | `create_project` |
| `GET /api/v1/projects` | `list_projects` |
| `PATCH /api/v1/projects/{id}` | `update_project` |
| `DELETE /api/v1/projects/{id}` | `delete_project` |
| `POST .../versions` | `create_version` |
| `GET .../versions` | `list_versions` |
| `POST .../analysis-runs` | `run_analysis` |
| `GET /analysis-runs/{id}` | `get_run` |
| `POST .../evidence` | `add_evidence` |
| `DELETE /evidence/{id}` | `delete_evidence` |
| `GET .../reports` | `get_reports` |
| `GET /reports/{id}/download` | `export_report` |

`run_analysis`는 (버전 내용 + 정책 + 근거)의 SHA-256을 idempotency key로 써서
동일 입력의 중복 분석을 만들지 않는다. 본문 §14의 "동일 입력 중복 분석 방지"에 해당한다.

데스크톱에서는 분석이 동기적으로 끝나므로 작업 ID 폴링 대신 QThread 워커를 쓴다.
`AnalysisRun` 상태 머신(`QUEUED/RUNNING/COMPLETED/FAILED_*`)은 그대로 유지해
웹 전환 시 Celery 작업으로 바꾸기만 하면 되게 했다.

## A.5 정책값 위치

본문 §5.10의 "임계치는 전역 상수가 아니라 `EvaluationPolicy`에서 관리한다"를 따라
모든 임계치는 `core/policy.py`의 `EvaluationPolicy`에 있고, 엔진 함수는 정책을 인자로 받는다.
운영자는 '정책' 화면에서 수정할 수 있으며, 가중치 합계가 100이 아니면 저장 버튼이 비활성화된다.

정책 버전은 `analysis_runs.policy_version`과 모든 보고서에 기록된다.
정책을 바꿔도 기존 분석 결과는 수정되지 않고, 다시 실행해야 새 정책이 적용된다.

## A.6 테스트 현황 (88개)

| 파일 | 대상 |
|---|---|
| `test_policy.py` | 가중치 합계 100, 신뢰도 범위, 직렬화 왕복, CLAUDE.md §11 기본값 일치 |
| `test_rules.py` | 넓은 타깃 감지, 사용자·구매자·영향자 분리, 필수 누락, 심각도 중복 제거 |
| `test_scoring_confidence.py` | 정규화 공식, 결정론, 무근거 상한, 상충 감쇠, 표본 보정 한계 |
| `test_pivot.py` | HOLD 우선, `would_be_decision`, 각 피벗 분기, 정책 임계치 반영 |
| `test_pipeline_scenarios.py` | 본문 §15.3 두 고정 시나리오, JSON Schema, 동일 입력 동일 출력 |
| `test_report.py` | 섹션 존재, 버전 기록, 판단이 점수보다 앞, HTML escaping |
| `test_service.py` | 승인 강제, idempotency, 권한, 감사 로그, 이벤트, 버전 비교, 정책 반영 |
| `test_ui_smoke.py` | 전 화면 빈 상태·결과 상태 렌더링, 가중치 합계 검증 UI |

본문 §12 "최소 필수 테스트" 항목 중 미구현은 다음 뿐이다.
- 보고서 버전 추적: 부분(체크섬·정책 버전은 검증, 별도 버전 번호 체계는 없음)

## A.7 다음 단계

Phase 2에서 `Hypothesis` / `Experiment` 테이블과 화면 F(실험)를 추가한다.
Phase 3에서 `PivotDecision` 승인 워크플로를 추가한다.
LLM은 `core/ports.py`의 Protocol 구현체로 붙이며, 붙이더라도
점수·신뢰도·피벗 판정은 규칙 엔진이 계속 담당한다.
