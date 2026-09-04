# 곁에 — 백엔드 API

취약계층 공공지원사업 안내 서비스의 FastAPI 백엔드입니다. 프론트엔드(`frontend/src/api/client.ts`)가 브라우저 안에서 처리하던 세션 생성 → 답변 저장 → 사업 매칭 → 안내문 생성 흐름을 HTTP API로 제공합니다.

- 데이터는 큐레이션 정적 데이터(`data/`)에 공공데이터포털 실시간 수집분(정부24 공공서비스·복지로 복지서비스)을 합쳐 메모리에 올립니다. 수집분은 `data/cache/`에 캐시되고 24시간마다 백그라운드 갱신됩니다.
- 로그인·본인인증 없이 세션 코드만으로 동작하고, 답변은 TTL이 지나면 삭제됩니다.
- 추천 결과는 후보 검색용이며 "확실히 받을 수 있다"는 표현을 쓰지 않습니다. 자격의 최종 확정은 담당기관이 합니다.

## 실행

```bash
cd backend
uv sync                      # 또는 pip install -r requirements.txt
uv run uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- 설정은 `.env.example`을 `.env`로 복사해 바꿉니다. 모든 값은 `GYEOTE_` 접두사를 씁니다.

## 엔드포인트

| 메서드 | 경로 | 설명 | 프론트엔드 대응 |
|---|---|---|---|
| GET | `/health` | 서버 상태, 데이터셋 기준일·건수 | |
| GET | `/api/v1/departments` | 담당 영역(부처·기관) 목록 | |
| GET | `/api/v1/programs` | 복지사업 검색. `keyword`, `categories`, `region`, `minAge`, `onlyCurrentlyOpen` 등 | `searchPrograms` |
| GET | `/api/v1/programs/filter-options` | 실제 데이터에 존재하는 필터 선택지 | `getFilterOptions` |
| GET | `/api/v1/programs/{id}` | 사업 상세 | `getProgramById` |
| POST | `/api/v1/matches` | 프로필 기반 추천. 조건별 판정과 근거 포함 | `findProgramMatches` |
| GET | `/api/v1/questions` | 상황 입력 질문 전체 | `questions.ts` |
| POST | `/api/v1/sessions` | 세션 생성 (`mode`: self / helper) | `createSession` |
| GET | `/api/v1/sessions/{id}` | 세션 조회. 보호자 보완 목록 포함 | |
| GET | `/api/v1/sessions/{id}/questions` | 답변 기준 활성 질문 (후속 질문 분기 적용) | `activeQuestions` |
| PUT | `/api/v1/sessions/{id}/answers/{questionId}` | 답변 저장 | `saveAnswer` |
| POST | `/api/v1/sessions/{id}/matches` | 답변 → 프로필 변환 → 추천 카드 | `getMatches` |
| GET | `/api/v1/sessions/{id}/brief` | 주민센터 전달용 안내문 | `brief()` |
| DELETE | `/api/v1/sessions/{id}` | 세션 삭제 | |
| GET | `/api/v1/admin/cases/{caseCode}` | 행정 확인 화면: 진술 요약, 추천 검토 사업, AI 상담원 메모 | `getAdminCase` |
| GET | `/api/v1/helper/cases/{caseCode}` | 보호자가 대신 채울 빈 항목 목록 | `getHelperCase` |
| PUT | `/api/v1/helper/cases/{caseCode}/answers` | 보호자 답변 저장 (세션 답변에 병합) | `saveHelperAnswers` |

응답 JSON은 프론트엔드 타입(`Benefit`, `MatchingResponse`, `WelfareProgram`)과 같은 camelCase 키를 씁니다.

## 흐름 예시

```bash
# 1. 세션 생성
curl -X POST localhost:8000/api/v1/sessions -H 'content-type: application/json' \
  -d '{"mode":"helper","helperType":"자녀·가족"}'

# 2. 답변 저장
curl -X PUT localhost:8000/api/v1/sessions/$SID/answers/birthYear -H 'content-type: application/json' -d '{"value":"1948"}'
curl -X PUT localhost:8000/api/v1/sessions/$SID/answers/area      -H 'content-type: application/json' -d '{"value":"서울특별시"}'
curl -X PUT localhost:8000/api/v1/sessions/$SID/answers/need      -H 'content-type: application/json' -d '{"value":["식사·혼자 생활","외출·이동"]}'

# 3. 추천 카드
curl -X POST localhost:8000/api/v1/sessions/$SID/matches

# 4. 주민센터 안내문
curl localhost:8000/api/v1/sessions/$SID/brief
```

## 구조

```
app/
├── main.py            앱 팩토리, CORS, 라우터 등록, 기동 시 데이터 적재
├── config.py          환경변수 설정 (GYEOTE_*)
├── dependencies.py    카탈로그·세션 저장소·세션 조회 의존성
├── schemas/           Pydantic 모델. data/ JSON과 프론트엔드 타입에 맞춘 camelCase
├── services/
│   ├── catalog.py     manifest + departments 로드·검증
│   ├── search.py      다중 조건 검색 (welfare-search.js searchPrograms 포팅)
│   ├── matching.py    연령·지역·독거·소득 판정과 점수 (evaluateProgram 포팅)
│   ├── profile.py     질문 답변 → 프로필 변환 (client.ts answersToProfile 포팅)
│   ├── presenter.py   판정 결과 → 결과 카드(Benefit)
│   ├── brief.py       주민센터 전달 안내문
│   ├── questions.py   질문 목록과 후속 질문 분기
│   └── sessions.py    메모리 세션 저장소 (TTL)
└── routers/           health, departments, programs, matches, questions, sessions
```

## 판정 원칙

- 연령·지역이 **명확히** 불일치할 때만 `NOT_ELIGIBLE`로 제외합니다.
- 정보가 없거나 `전국-지자체별상이`처럼 지자체마다 다른 조건은 `NEEDS_CONFIRMATION`으로 남깁니다.
- 소득 정보가 불완전하면(`incomeInformationComplete=false`) 불일치를 탈락이 아니라 확인 필요로 처리합니다.
- `eligibility.conditions`의 개별심사·중복 제한은 결과 카드의 확인사항으로 그대로 보여줍니다.

## 운영 시 바꿀 것

- 세션 저장소를 메모리에서 Redis 등으로 교체 (`services/sessions.py` 인터페이스 유지)
- 정적 JSON 대신 복지로·보조금24 공공데이터 API 어댑터 연결
- 자유 답변 구조화, 쉬운 말 변환 등 LLM 오케스트레이션 단계 추가
