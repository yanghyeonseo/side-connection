# 곁이음 프론트엔드 데이터 검색

`welfare-search.js`는 백엔드 없이 `/data/manifest.json`과 부서별 JSON을 브라우저에서 병렬로 읽는 ES module입니다. 데이터 폴더를 프론트 앱의 정적 공개 경로에 두면 됩니다.

## 빠른 사용

```js
import {
  loadWelfareCatalog,
  searchPrograms,
  findProgramMatches,
  getFilterOptions,
} from "./welfare-search.js";

const catalog = await loadWelfareCatalog("/data/manifest.json");

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

## 프레임워크 연결

- Vite/React: `public/data/`에 데이터 폴더를 복사하고 모듈을 `src/lib/`에서 import
- Next.js: `public/data/`에 데이터 폴더를 두고 클라이언트 컴포넌트에서 호출
- 정적 HTML: `<script type="module">`에서 import

`file://`로 HTML을 직접 열면 브라우저 CORS 정책 때문에 `fetch`가 실패할 수 있습니다. Vite 개발 서버나 간단한 정적 파일 서버에서 실행하세요.

데이터 로드·복합 검색·보수적 판정 테스트는 저장소 루트에서 다음처럼 실행합니다.

```bash
node --test frondend/welfare-search.test.mjs
```
