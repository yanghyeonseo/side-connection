# 곁에 — 프론트엔드

취약계층 공공지원사업 안내 서비스의 모바일 웹 UI입니다.

```bash
npm install
npm run dev
```

## 백엔드 연결

`VITE_API_BASE_URL`에 백엔드 주소를 지정하면 아래 API를 호출합니다. 값이 없으면 데모용 목업 결과를 보여줍니다.

- `POST /v1/sessions` — `{ mode }` → `{ sessionId }`
- `PUT /v1/sessions/:sessionId/answers` — `{ questionId, value }`
- `POST /v1/sessions/:sessionId/matches` — `{ answers }` → `{ benefits, needsGuardianInput }`

`benefits`의 항목은 `id`, `name`, `tag`, `summary`, `amount`, `reason`, `location`, `needsCheck?`, `supplies`를 반환하면 됩니다.
