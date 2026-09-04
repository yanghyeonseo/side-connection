# 곁이음 (side-connection)

취약계층 어르신에게 맞는 공공지원사업을 찾아주는 서비스입니다. 로그인 없이 쉬운 질문 10여 개에 답하면, 실시간 공공데이터에서 후보 사업을 찾고 AI가 어르신 눈높이 문구로 안내합니다.

## 구성

| 디렉터리 | 내용 |
|---|---|
| `frontend/` | React + Vite. 문진, 추천 결과, 보호자 보완, 행정 확인 화면 |
| `backend/` | FastAPI. 세션·매칭·사례번호·AI 큐레이션·공공데이터 수집 |
| `data/` | 큐레이션된 복지사업 72건 (검증된 핵심 데이터) |
| `docs/` | 기획서·질문서 |

핵심 흐름:

1. **문진** — 어르신 또는 보호자가 상황을 입력. 모르는 항목은 "잘 모르겠어요"로 넘어감
2. **추천** — 결정적 매칭 엔진이 큐레이션 72건 + 공공데이터포털 실시간 수집 약 1,350건에서 후보를 찾음. AI(OpenAI)는 문구만 다듬고 자격 판정은 하지 않음
3. **보호자 보완** — 사례번호 링크로 보호자가 빈칸만 대신 입력
4. **연결** — 전화(129)·문자로 상담 연결, 상담원은 `admin/cases/{사례번호}` 화면에서 진술 요약과 AI 메모 확인

## 실행

```bash
# 백엔드 (localhost:8000, /docs 에 Swagger)
cd backend && uv sync && uv run uvicorn app.main:app --reload

# 프론트엔드 (localhost:5173)
cd frontend && npm ci && npm run dev

# 테스트
cd backend && uv run pytest
cd frontend && node welfare-search.test.mjs
```

## 환경변수 (git 미추적)

서버 비밀키는 저장소 루트 `.env`(예시: `.env.example`), 프론트 빌드 변수는 `frontend/.env`(예시: `frontend/.env.example`)로 분리되어 있습니다. 빌드는 루트 `.env`를 읽지 않으므로 비밀키가 번들에 섞일 수 없습니다.

| 키 (루트 `.env`) | 설명 |
|---|---|
| `OPENAI_KEY`, `OPENAI_MODEL` | AI 큐레이션·상담원 메모. 없으면 규칙 기반 문구로 동작 |
| `GOV24_SERVICE_KEY` | [행정안전부] 대한민국 공공서비스(혜택) 정보 인증키 |
| `WELFARE_INFO_SERVICE_KEY` | [한국사회보장정보원] 복지서비스정보 인증키 |
| `WELFARE_CENTER_PHONE` / `WELFARE_CENTER_SMS_NUMBER` | 상담 전화·문자 번호 (기본 129) |
| `GYEOTIEUM_OPEN_DATA_AUTO_REFRESH` | `false`면 주기 갱신 없이 기동 시 캐시가 낡았을 때만 1회 수집 |

| 키 (`frontend/.env`) | 설명 |
|---|---|
| `VITE_API_BASE_URL` | 프론트가 부를 백엔드 주소 (`…/api`까지). 비우면 브라우저 내 데모 모드 |

공공데이터는 `data/cache/`에 캐시되며, 기본값은 24시간마다 백그라운드 갱신입니다. 포털 장애 시 캐시 → 큐레이션 데이터 순으로 동작이 유지됩니다.

## 배포

- **프론트엔드**: `https://gyeotieum.hs-yang.com` — GitHub Pages 커스텀 도메인으로 `main` 푸시 시 자동 배포됩니다. 백엔드에 닿지 못하면 브라우저 내 데모 모드로 폴백하므로 화면은 항상 동작합니다.
- **백엔드**: `https://gyeotieum-api.hs-yang.com` — 소유자의 홈서버에서 systemd 서비스로 상시 실행되며, Cloudflare Tunnel로 공개됩니다. 빌드된 프론트도 함께 서빙하므로 풀스택 미러 역할도 합니다.
