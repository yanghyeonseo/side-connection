/**
 * 곁이음 정적 복지 데이터 로더·검색·추천 모듈.
 * 서버, DB, 외부 패키지 없이 브라우저의 fetch와 ES module만 사용한다.
 */

export const MATCH_STATUS = Object.freeze({
  LIKELY: "LIKELY",
  NEEDS_CONFIRMATION: "NEEDS_CONFIRMATION",
  NOT_ELIGIBLE: "NOT_ELIGIBLE",
});

export const CONDITION_STATUS = Object.freeze({
  MATCHED: "MATCHED",
  UNKNOWN: "UNKNOWN",
  NOT_MATCHED: "NOT_MATCHED",
  NOT_APPLICABLE: "NOT_APPLICABLE",
});

const ARRAY_MODE = Object.freeze({ ANY: "ANY", ALL: "ALL" });
const NATIONWIDE = new Set(["전국"]);
const UNCERTAIN_NATIONWIDE = new Set(["전국-지자체별상이", "전국-공고별상이"]);

function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("ko-KR")
    .replace(/[\s\p{P}\p{S}]+/gu, "");
}

function asArray(value) {
  if (value == null || value === "") return [];
  return Array.isArray(value) ? value.filter((item) => item != null && item !== "") : [value];
}

function includesByMode(values, selected, mode = ARRAY_MODE.ANY) {
  const wanted = asArray(selected);
  if (wanted.length === 0) return true;
  const source = new Set(asArray(values));
  return mode === ARRAY_MODE.ALL
    ? wanted.every((item) => source.has(item))
    : wanted.some((item) => source.has(item));
}

function textContainsAny(haystack, keywords) {
  const text = normalizeText(haystack);
  return asArray(keywords).every((keyword) => text.includes(normalizeText(keyword)));
}

function getSearchText(program) {
  return [
    program.name,
    program.summary,
    program.managingOrganization,
    program.managingDepartment,
    ...(program.coverage ?? []),
    program.category,
    ...(program.relatedCategories ?? []),
    ...(program.serviceTypes ?? []),
    ...(program.eligibility?.conditions ?? []),
    ...(program.benefits ?? []),
    ...(program.matchTags ?? []),
  ].join(" ");
}

function regionsCompatible(coverage, region) {
  const wanted = normalizeText(region);
  if (!wanted) return null;
  if (coverage.some((item) => NATIONWIDE.has(item))) return true;
  if (coverage.some((item) => UNCERTAIN_NATIONWIDE.has(item))) return null;

  const normalizedCoverage = coverage.map(normalizeText);
  return normalizedCoverage.some(
    (item) => item === wanted || item.startsWith(wanted) || wanted.startsWith(item),
  );
}

function ageRangesOverlap(program, minAge, maxAge) {
  if (minAge == null && maxAge == null) return true;
  const programMin = program.eligibility?.minAge ?? -Infinity;
  const programMax = program.eligibility?.maxAge ?? Infinity;
  const queryMin = minAge ?? -Infinity;
  const queryMax = maxAge ?? Infinity;
  return programMin <= queryMax && queryMin <= programMax;
}

function dateOnly(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function isApplicationOpen(program, onDate = new Date()) {
  if (program.status === "CLOSED") return false;
  const deadline = dateOnly(program.application?.deadline);
  const target = dateOnly(onDate instanceof Date ? onDate.toISOString().slice(0, 10) : onDate);
  if (deadline && target && deadline < target) return false;
  return program.status === "ACTIVE";
}

function validateDocument(document, expectedDepartment) {
  if (!document || !Array.isArray(document.programs) || !document.department?.id) {
    throw new TypeError(`잘못된 부서 데이터: ${expectedDepartment?.file ?? "unknown"}`);
  }
  if (expectedDepartment && document.department.id !== expectedDepartment.id) {
    throw new TypeError(
      `매니페스트 부서 ID(${expectedDepartment.id})와 JSON 부서 ID(${document.department.id})가 다릅니다.`,
    );
  }
}

async function fetchJson(url, fetchImpl) {
  const response = await fetchImpl(url);
  if (!response.ok) throw new Error(`데이터 요청 실패 (${response.status}): ${url}`);
  return response.json();
}

/**
 * manifest와 모든 부서 JSON을 병렬로 읽는다.
 * @returns {Promise<{manifest: object, departments: object[], programs: object[]}>}
 */
export async function loadWelfareCatalog(
  manifestUrl = "/data/manifest.json",
  { fetchImpl = globalThis.fetch, baseUrl = globalThis.location?.href ?? "http://localhost/" } = {},
) {
  if (typeof fetchImpl !== "function") throw new TypeError("fetch 구현이 필요합니다.");

  const absoluteManifestUrl = new URL(manifestUrl, baseUrl);
  const manifest = await fetchJson(absoluteManifestUrl.href, fetchImpl);
  if (!Array.isArray(manifest.departments)) throw new TypeError("manifest.departments가 배열이 아닙니다.");

  const manifestDirectory = new URL("./", absoluteManifestUrl);
  const documents = await Promise.all(
    manifest.departments.map(async (entry) => {
      const document = await fetchJson(new URL(entry.file, manifestDirectory).href, fetchImpl);
      validateDocument(document, entry);
      return document;
    }),
  );

  const programs = documents.flatMap((document) =>
    document.programs.map((program) => ({
      ...program,
      departmentId: document.department.id,
      departmentName: document.department.name,
    })),
  );

  const ids = new Set(programs.map((program) => program.id));
  if (ids.size !== programs.length) throw new TypeError("중복된 복지사업 ID가 있습니다.");
  if (manifest.dataset?.recordCount != null && manifest.dataset.recordCount !== programs.length) {
    throw new TypeError(
      `매니페스트 건수(${manifest.dataset.recordCount})와 실제 건수(${programs.length})가 다릅니다.`,
    );
  }

  return { manifest, departments: documents, programs };
}

/**
 * 다중 조건 정적 검색. 조건 종류 간에는 AND, 배열 내부는 arrayMode(기본 ANY)를 적용한다.
 */
export function searchPrograms(programs, filters = {}) {
  const mode = filters.arrayMode === ARRAY_MODE.ALL ? ARRAY_MODE.ALL : ARRAY_MODE.ANY;
  const queryKeywords = String(filters.keyword ?? "").trim().split(/\s+/).filter(Boolean);

  return programs.filter((program) => {
    const allCategories = [program.category, ...(program.relatedCategories ?? [])];
    const allIncomeTypes = program.eligibility?.incomeTypes ?? [];

    if (queryKeywords.length && !textContainsAny(getSearchText(program), queryKeywords)) return false;
    if (!includesByMode(allCategories, filters.categories, mode)) return false;
    if (!includesByMode(program.relatedCategories, filters.relatedCategories, mode)) return false;
    if (!includesByMode([program.departmentId], filters.departmentIds, mode)) return false;
    if (!includesByMode([program.status], filters.statuses, mode)) return false;
    if (!includesByMode(program.serviceTypes, filters.serviceTypes, mode)) return false;
    if (!includesByMode(program.matchTags, filters.matchTags, mode)) return false;
    if (!includesByMode(allIncomeTypes, filters.incomeTypes, mode)) return false;
    if (!includesByMode([program.application?.periodType], filters.periodTypes, mode)) return false;
    if (!includesByMode(program.coverage, filters.coverage, mode)) return false;
    if (!ageRangesOverlap(program, filters.minAge, filters.maxAge)) return false;

    if (filters.region) {
      const compatible = regionsCompatible(program.coverage ?? [], filters.region);
      if (compatible === false) return false;
    }
    if (filters.livingAloneOnly && program.eligibility?.livingAlone !== true) return false;
    if (filters.managingOrganization) {
      if (!textContainsAny(program.managingOrganization, filters.managingOrganization)) return false;
    }
    if (filters.onlyCurrentlyOpen && !isApplicationOpen(program, filters.onDate ?? new Date())) return false;
    return true;
  });
}

function condition(key, label, status, detail, hard = false) {
  return { key, label, status, detail, hard };
}

function evaluateAge(program, profile) {
  const min = program.eligibility?.minAge;
  const max = program.eligibility?.maxAge;
  if (min == null && max == null) return condition("age", "연령", CONDITION_STATUS.NOT_APPLICABLE, "연령 제한 없음");
  if (profile.age == null) return condition("age", "연령", CONDITION_STATUS.UNKNOWN, `연령 확인 필요 (${min ?? 0}~${max ?? "제한 없음"}세)`, true);
  const matched = (min == null || profile.age >= min) && (max == null || profile.age <= max);
  return condition("age", "연령", matched ? CONDITION_STATUS.MATCHED : CONDITION_STATUS.NOT_MATCHED, matched ? `만 ${profile.age}세로 연령 범위 충족` : `만 ${profile.age}세는 사업 연령 범위 밖`, true);
}

function evaluateRegion(program, profile) {
  const coverage = program.coverage ?? [];
  if (coverage.some((item) => NATIONWIDE.has(item))) return condition("region", "지역", CONDITION_STATUS.MATCHED, "전국 사업", true);
  if (!profile.region) return condition("region", "지역", CONDITION_STATUS.UNKNOWN, `거주지 확인 필요 (${coverage.join(", ")})`, true);
  const matched = regionsCompatible(coverage, profile.region);
  if (matched == null) return condition("region", "지역", CONDITION_STATUS.UNKNOWN, "전국 틀 안에서 지자체·공고별 시행 여부 확인", true);
  return condition("region", "지역", matched ? CONDITION_STATUS.MATCHED : CONDITION_STATUS.NOT_MATCHED, matched ? `${profile.region} 대상 가능` : `${profile.region}은 지원 지역과 불일치`, true);
}

function evaluateLivingAlone(program, profile) {
  if (program.eligibility?.livingAlone !== true) return condition("livingAlone", "독거 여부", CONDITION_STATUS.NOT_APPLICABLE, "독거 필수 아님");
  if (profile.livingAlone == null) return condition("livingAlone", "독거 여부", CONDITION_STATUS.UNKNOWN, "독거 여부 확인 필요", true);
  return condition("livingAlone", "독거 여부", profile.livingAlone ? CONDITION_STATUS.MATCHED : CONDITION_STATUS.NOT_MATCHED, profile.livingAlone ? "독거 조건 충족" : "독거 필수 사업", true);
}

function deriveIncomeTypes(profile) {
  const values = new Set(asArray(profile.incomeTypes));
  if (profile.basicLivelihoodRecipient === true) values.add("BASIC_LIVELIHOOD_ANY");
  if (profile.medicalAidRecipient === true) {
    values.add("MEDICAL_AID_RECIPIENT");
    values.add("BASIC_LIVELIHOOD_MEDICAL");
  }
  if (profile.nearPovertyStatus === true) values.add("NEAR_POVERTY");
  if (profile.basicPensionRecipient === true) values.add("BASIC_PENSION_RECIPIENT");
  if (profile.registeredDisabled === true) values.add("REGISTERED_DISABLED");
  return values;
}

function incomeCodeMatches(required, known) {
  if (required === "ANY") return true;
  if (known.has(required)) return true;
  if (required.startsWith("BASIC_LIVELIHOOD_") && known.has("BASIC_LIVELIHOOD_ANY")) return true;
  if (required === "BASIC_LIVELIHOOD_ANY" && [...known].some((item) => item.startsWith("BASIC_LIVELIHOOD_"))) return true;
  if (required.startsWith("NEAR_POVERTY") && known.has("NEAR_POVERTY")) return true;
  return false;
}

function evaluateIncome(program, profile) {
  const required = program.eligibility?.incomeTypes ?? [];
  if (required.length === 0 || required.includes("ANY")) return condition("income", "소득·자격", CONDITION_STATUS.NOT_APPLICABLE, "소득 제한 없음 또는 다른 자격과 병행 가능");
  const known = deriveIncomeTypes(profile);
  if (known.size === 0) return condition("income", "소득·자격", CONDITION_STATUS.UNKNOWN, `다음 중 해당 여부 확인: ${required.join(", ")}`, true);
  if (required.some((item) => incomeCodeMatches(item, known))) return condition("income", "소득·자격", CONDITION_STATUS.MATCHED, "입력한 수급·소득자격과 후보 조건이 일치", true);
  if (profile.incomeInformationComplete === true) return condition("income", "소득·자격", CONDITION_STATUS.NOT_MATCHED, `필요 자격과 불일치: ${required.join(", ")}`, true);
  return condition("income", "소득·자격", CONDITION_STATUS.UNKNOWN, `현재 입력으로 확인 불가: ${required.join(", ")}`, true);
}

function scoreRelevance(program, profile) {
  let score = 0;
  const needs = new Set(asArray(profile.needs));
  const programCategories = new Set([program.category, ...(program.relatedCategories ?? [])]);
  const matchedNeeds = [...needs].filter((item) => programCategories.has(item));
  score += matchedNeeds.length * 18;

  const tags = new Set(asArray(profile.tags));
  const matchedTags = (program.matchTags ?? []).filter((item) => tags.has(item));
  score += matchedTags.length * 7;

  const assistance = asArray(profile.assistanceNeed);
  if (assistance.some((item) => program.eligibility?.assistanceNeed?.includes(item))) score += 10;
  return { score, matchedNeeds, matchedTags };
}

/** 프로필 하나에 대해 사업 하나의 추천상태·점수·판정근거를 계산한다. */
export function evaluateProgram(program, profile = {}) {
  const conditions = [
    evaluateAge(program, profile),
    evaluateRegion(program, profile),
    evaluateLivingAlone(program, profile),
    evaluateIncome(program, profile),
  ];
  const relevance = scoreRelevance(program, profile);

  let score = relevance.score;
  for (const item of conditions) {
    if (item.status === CONDITION_STATUS.MATCHED) score += 12;
    if (item.status === CONDITION_STATUS.UNKNOWN) score -= 3;
    if (item.status === CONDITION_STATUS.NOT_MATCHED) score -= 50;
  }
  score = Math.max(0, Math.min(100, score));

  const hasHardMismatch = conditions.some((item) => item.hard && item.status === CONDITION_STATUS.NOT_MATCHED);
  const hasHardUnknown = conditions.some((item) => item.hard && item.status === CONDITION_STATUS.UNKNOWN);
  const status = hasHardMismatch
    ? MATCH_STATUS.NOT_ELIGIBLE
    : hasHardUnknown
      ? MATCH_STATUS.NEEDS_CONFIRMATION
      : MATCH_STATUS.LIKELY;

  return {
    program,
    status,
    score,
    conditions,
    matchedNeeds: relevance.matchedNeeds,
    matchedTags: relevance.matchedTags,
    confirmationItems: program.eligibility?.conditions ?? [],
  };
}

/** 검색 조건을 먼저 적용한 뒤 프로필 추천순으로 정렬한다. */
export function findProgramMatches(programs, profile = {}, options = {}) {
  const filtered = searchPrograms(programs, options.filters ?? {});
  const statusRank = { [MATCH_STATUS.LIKELY]: 0, [MATCH_STATUS.NEEDS_CONFIRMATION]: 1, [MATCH_STATUS.NOT_ELIGIBLE]: 2 };
  const results = filtered
    .map((program) => evaluateProgram(program, profile))
    .filter((result) => options.includeNotEligible || result.status !== MATCH_STATUS.NOT_ELIGIBLE)
    .sort((a, b) => statusRank[a.status] - statusRank[b.status] || b.score - a.score || a.program.name.localeCompare(b.program.name, "ko"));
  const offset = Math.max(0, options.offset ?? 0);
  const limit = options.limit == null ? results.length : Math.max(0, options.limit);
  return results.slice(offset, offset + limit);
}

/** 로드부터 검색·추천까지 한 번에 수행하는 편의 함수. */
export async function queryWelfare({ manifestUrl, loaderOptions, filters, profile, includeNotEligible, limit, offset } = {}) {
  const catalog = await loadWelfareCatalog(manifestUrl, loaderOptions);
  const results = findProgramMatches(catalog.programs, profile, { filters, includeNotEligible, limit, offset });
  return { ...catalog, results };
}

/** 체크박스·셀렉트 UI 구성에 쓸 수 있는 실제 데이터 옵션을 반환한다. */
export function getFilterOptions(programs) {
  const unique = (items) => [...new Set(items.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "ko"));
  return {
    categories: unique(programs.flatMap((p) => [p.category, ...(p.relatedCategories ?? [])])),
    departments: unique(programs.map((p) => p.departmentId)),
    organizations: unique(programs.map((p) => p.managingOrganization)),
    coverage: unique(programs.flatMap((p) => p.coverage ?? [])),
    serviceTypes: unique(programs.flatMap((p) => p.serviceTypes ?? [])),
    incomeTypes: unique(programs.flatMap((p) => p.eligibility?.incomeTypes ?? [])),
    periodTypes: unique(programs.map((p) => p.application?.periodType)),
    matchTags: unique(programs.flatMap((p) => p.matchTags ?? [])),
  };
}

export function getProgramById(programs, id) {
  return programs.find((program) => program.id === id) ?? null;
}

export function groupProgramsByDepartment(programs) {
  return programs.reduce((groups, program) => {
    (groups[program.departmentId] ??= []).push(program);
    return groups;
  }, {});
}
