# 곁이음 프론트엔드 데이터 검색

`welfare-search.js`는 백엔드 없이 정적 매니페스트와 부서별 JSON을 브라우저에서 병렬로 읽는 ES module입니다. 이 프로젝트는 Vite의 `publicDir`를 저장소의 `../data`로 지정하므로 배포 후 `/manifest.json`과 `/departments/*.json`으로 제공됩니다.

## 빠른 사용

```js
import {
  loadWelfareCatalog,
  searchPrograms,
  findProgramMatches,
  getFilterOptions,
} from "./welfare-search.js";

const catalog = await loadWelfareCatalog("/manifest.json");

// 조건 종류 간 AND, 같은 배열 안에서는 기본 ANY
const searched = searchPrograms(catalog.programs, {
  keyword: "병원 동행",
  categories: ["CARE", "MOBILITY"],
  region: "서울특별시",
  minAge: 75,
  maxAge: 85,
  incomeTypes: ["BASIC_LIVELIHOOD_ANY", "NEAR_POVERTY"],
  periodTypes: ["ALWAYS_OPEN", "ANNOUNCEMENT_BASED"],
  onlyCurrentlyOpen: true,
});

const recommendations = findProgramMatches(catalog.programs, {
  age: 78,
  region: "서울특별시",
  livingAlone: true,
  basicLivelihoodRecipient: true,
  nearPovertyStatus: false,
  basicPensionRecipient: true,
  // 알고 있는 코드가 있으면 직접 추가
  incomeTypes: ["BASIC_LIVELIHOOD_LIVING_OR_MEDICAL"],
  // false인 자격까지 모두 확인했다면 true. 아니면 미확인을 탈락시키지 않음
  incomeInformationComplete: false,
  needs: ["CARE", "MEAL", "MOBILITY"],
  assistanceNeed: ["MEDIUM"],
  tags: ["LIVING_ALONE", "MEAL_PREP_DIFFICULTY", "HOSPITAL_VISIT_SUPPORT"],
}, {
  filters: { onlyCurrentlyOpen: true },
  includeNotEligible: false,
  limit: 20,
});

// 실제 데이터에서 체크박스/셀렉트 선택지를 생성
const filterOptions = getFilterOptions(catalog.programs);
```

## 지원 검색 조건

- `keyword`: 사업명, 설명, 기관, 조건, 혜택, 태그 전체에서 공백 단위 AND 검색
- `categories`, `relatedCategories`, `departmentIds`, `statuses`
- `serviceTypes`, `matchTags`, `incomeTypes`, `periodTypes`, `coverage`
- `region`, `minAge`, `maxAge`, `livingAloneOnly`
- `managingOrganization`, `onlyCurrentlyOpen`, `onDate`
- `arrayMode`: 배열 내부 조건을 `ANY`(기본) 또는 `ALL`로 처리

조건 종류끼리는 모두 AND입니다. 예를 들어 `region + categories + incomeTypes`를 동시에 주면 세 조건을 모두 통과한 결과만 반환합니다.

## 맞춤 추천 판정

`findProgramMatches` 결과에는 다음이 들어갑니다.

- `status`: `LIKELY`, `NEEDS_CONFIRMATION`, `NOT_ELIGIBLE`
- `score`: 필요분류·상황태그·조건 일치도를 합친 0~100 점수
- `conditions`: 연령·지역·독거·소득자격의 조건별 판정과 설명
- `confirmationItems`: 담당기관에 최종 확인할 원문 세부조건

지역이 `전국-지자체별상이`이거나 소득정보가 불완전하면 `NOT_ELIGIBLE`로 버리지 않고 `NEEDS_CONFIRMATION`으로 남깁니다. 신청 자격의 최종 확정은 반드시 담당기관이 해야 합니다.

## 현재 React 앱 연결

- `src/api/client.ts`가 질문 답변을 연령·지역·독거·필요분류·상황태그로 변환합니다.
- 결과는 72건을 대상으로 브라우저 안에서 계산되며 답변을 외부 서버로 보내지 않습니다.
- 상세 화면에서 신청처, 문의번호와 공식 원문을 확인할 수 있습니다.

`file://`로 HTML을 직접 열면 브라우저 CORS 정책 때문에 `fetch`가 실패할 수 있습니다. Vite 개발 서버나 간단한 정적 파일 서버에서 실행하세요.

데이터 로드·복합 검색·보수적 판정 테스트는 저장소 루트에서 다음처럼 실행합니다.

```bash
node --test frondend/welfare-search.test.mjs
```

---

# 곁에 — 프론트엔드

취약계층 공공지원사업 안내 서비스의 모바일 웹 UI입니다.

```bash
npm install
npm run dev
```

## GitHub Pages 배포

`.github/workflows/deploy-pages.yml`이 `main`에 푸시될 때 자동으로 배포합니다.

1. GitHub 저장소의 `Settings → Pages`에서 Source를 `GitHub Actions`로 선택합니다.
2. `main`에 푸시하거나 Actions의 `Deploy GitHub Pages`를 수동 실행합니다.
3. 배포 주소는 `https://yanghyeonseo.github.io/side-connection/`입니다.

Pages 빌드는 `/side-connection/` base path를 사용하며 정적 복지 데이터도 빌드 결과에 함께 포함합니다.

## 백엔드 연결

- `POST /v1/sessions` — `{ mode }` → `{ sessionId, caseCode }` (`caseCode`는 숫자로만 구성)
- `PUT /v1/sessions/:sessionId/answers` — `{ questionId, value }`
- `POST /v1/sessions/:sessionId/matches` — `{ answers }` → `{ benefits, needsGuardianInput }`
- `GET /v1/admin/cases/:caseCode` — 행정직원용 사례 정보(주소, 가구·소득, 수급 상태, 추천 근거)를 반환

`benefits`의 항목은 `id`, `name`, `tag`, `summary`, `amount`, `reason`, `location`, `needsCheck?`, `supplies`를 반환하면 됩니다.

전화·문자 수신처는 `VITE_WELFARE_CENTER_PHONE`, `VITE_WELFARE_CENTER_SMS_NUMBER`로 설정합니다. 메시지는 `/admin/cases/:caseCode` 링크를 열며, 사례번호는 유추하기 어려운 숫자로 발급하고 서버에서 만료·접근 통제를 적용해야 합니다.
