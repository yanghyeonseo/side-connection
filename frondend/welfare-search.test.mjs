import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  MATCH_STATUS,
  evaluateProgram,
  findProgramMatches,
  getFilterOptions,
  loadWelfareCatalog,
  searchPrograms,
} from "./welfare-search.js";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function localFetch(url) {
  const pathname = decodeURIComponent(new URL(url).pathname).replace(/^\/+/, "");
  try {
    const body = await fs.readFile(path.join(repositoryRoot, pathname), "utf8");
    return { ok: true, status: 200, json: async () => JSON.parse(body) };
  } catch {
    return { ok: false, status: 404, json: async () => ({}) };
  }
}

const catalog = await loadWelfareCatalog("/data/manifest.json", {
  fetchImpl: localFetch,
  baseUrl: "http://local.test/",
});

test("매니페스트에서 12개 파일과 72개 고유 사업을 병렬 로드한다", () => {
  assert.equal(catalog.departments.length, 12);
  assert.equal(catalog.programs.length, 72);
  assert.equal(new Set(catalog.programs.map((program) => program.id)).size, 72);
});

test("키워드·분류·지역·연령·접수상태를 동시에 검색한다", () => {
  const results = searchPrograms(catalog.programs, {
    keyword: "돌봄",
    categories: ["CARE", "MOBILITY"],
    region: "서울특별시",
    minAge: 78,
    maxAge: 78,
    onlyCurrentlyOpen: true,
    onDate: "2026-09-04",
  });

  assert.ok(results.length > 0);
  assert.ok(results.every((program) => program.status === "ACTIVE"));
  assert.ok(results.some((program) => program.id === "seoul-care-sos-2026"));
});

test("명확한 연령 불일치만 탈락시킨다", () => {
  const program = catalog.programs.find((item) => item.id === "national-basic-pension-2026");
  const result = evaluateProgram(program, { age: 50, region: "서울특별시" });
  assert.equal(result.status, MATCH_STATUS.NOT_ELIGIBLE);
  assert.equal(result.conditions.find((item) => item.key === "age").status, "NOT_MATCHED");
});

test("소득정보가 불완전하면 탈락 대신 확인 필요로 남긴다", () => {
  const program = catalog.programs.find((item) => item.id === "national-government-rice-discount-2026");
  const result = evaluateProgram(program, { age: 78, region: "서울특별시", incomeInformationComplete: false });
  assert.equal(result.status, MATCH_STATUS.NEEDS_CONFIRMATION);
});

test("추천 결과와 UI 필터 선택지를 만든다", () => {
  const results = findProgramMatches(
    catalog.programs,
    {
      age: 78,
      region: "서울특별시",
      livingAlone: true,
      basicPensionRecipient: true,
      needs: ["CARE", "MEAL", "MOBILITY"],
      assistanceNeed: ["MEDIUM"],
      tags: ["LIVING_ALONE", "MEAL_PREP_DIFFICULTY"],
    },
    { includeNotEligible: false, limit: 10 },
  );

  assert.equal(results.length, 10);
  assert.ok(results.every((result) => result.status !== MATCH_STATUS.NOT_ELIGIBLE));
  assert.ok(getFilterOptions(catalog.programs).categories.includes("SAFETY"));
});
