import { findProgramMatches, loadWelfareCatalog } from '../../welfare-search.js'
import type { BeneficiaryProfile, ProgramMatch, WelfareCatalog } from '../../welfare-search.js'
import type { AdminCase, AnswerValue, Benefit, HelperCase, MatchingResponse, Session, UserMode } from '../types'

// 백엔드 주소(끝에 /api 포함). 비어 있으면 브라우저 안에서만 동작하는 데모 모드가 된다.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')

// 백엔드에 닿지 못한 채 만든 세션. 답변을 기기 밖으로 보내지 않고 내장 엔진으로 추천한다.
const LOCAL_SESSION_PREFIX = 'local-'

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) throw new Error('요청을 처리하지 못했어요.')
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function isRemoteSession(sessionId: string) {
  return Boolean(API_BASE_URL) && !sessionId.startsWith(LOCAL_SESSION_PREFIX)
}

export async function createSession(mode: UserMode): Promise<Session> {
  if (API_BASE_URL) {
    try {
      return await request<Session>('/v1/sessions', { method: 'POST', body: JSON.stringify({ mode }) })
    } catch {
      // 서버에 닿지 못해도 어르신 흐름은 끊지 않는다. 아래 로컬 세션으로 이어간다.
    }
  }
  // 로컬 세션에는 사례번호가 없다. 상담원이 조회할 수 없는 가짜 번호를 만들지 않는다.
  return { sessionId: `${LOCAL_SESSION_PREFIX}${crypto.randomUUID()}`, caseCode: '' }
}

export async function saveAnswer(sessionId: string, questionId: string, value: AnswerValue) {
  if (!isRemoteSession(sessionId)) return
  try {
    await request<void>(`/v1/sessions/${sessionId}/answers/${encodeURIComponent(questionId)}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    })
  } catch {
    // 추천 요청에 전체 답변을 다시 보내므로, 중간 저장 실패로 흐름을 막지 않는다.
  }
}

export async function getMatches(sessionId: string, answers: Record<string, AnswerValue>): Promise<MatchingResponse> {
  if (isRemoteSession(sessionId)) {
    return request<MatchingResponse>(`/v1/sessions/${sessionId}/matches`, {
      method: 'POST',
      body: JSON.stringify({ answers }),
    })
  }
  return matchLocally(answers)
}

export async function getAdminCase(caseCode: string): Promise<AdminCase> {
  if (!API_BASE_URL) throw new Error('행정 확인 화면은 서버 연결이 필요해요.')
  return request<AdminCase>(`/v1/admin/cases/${caseCode}`, { method: 'GET' })
}

export async function getHelperCase(caseCode: string): Promise<HelperCase> {
  if (!API_BASE_URL) throw new Error('보호자 입력 화면은 서버 연결이 필요해요.')
  return request<HelperCase>(`/v1/helper/cases/${caseCode}`, { method: 'GET' })
}

export async function saveHelperAnswers(caseCode: string, answers: Record<string, string>) {
  if (!API_BASE_URL) throw new Error('보호자 입력 화면은 서버 연결이 필요해요.')
  return request<void>(`/v1/helper/cases/${caseCode}/answers`, { method: 'PUT', body: JSON.stringify({ answers }) })
}

// ── 로컬(데모) 매칭: 백엔드 없이도 정적 데이터로 같은 판정을 수행한다 ──

const needCategories: Record<string, string[]> = {
  '생활비가 부담돼요': ['LIVING'],
  '병원비가 걱정돼요': ['MEDICAL'],
  '식사·혼자 생활': ['MEAL', 'CARE'],
  '외출·이동': ['MOBILITY'],
  '집 문제': ['HOUSING'],
  '혼자 있을 때 안전': ['SAFETY'],
}

const categoryLabels: Record<string, string> = {
  CARE: '일상 돌봄',
  HOUSING: '주거',
  LIVING: '생활비',
  MEAL: '식사',
  MEDICAL: '의료',
  MOBILITY: '이동',
  SAFETY: '안전',
}

let catalogPromise: Promise<WelfareCatalog> | undefined

function getCatalog() {
  catalogPromise ??= loadWelfareCatalog(`${import.meta.env.BASE_URL}manifest.json`)
  return catalogPromise
}

function stringAnswer(answers: Record<string, AnswerValue>, key: string) {
  const value = answers[key]
  return typeof value === 'string' && value !== '잘 모르겠어요' ? value : undefined
}

function listAnswer(answers: Record<string, AnswerValue>, key: string) {
  const value = answers[key]
  return Array.isArray(value) ? value.filter((item) => item !== '잘 모르겠어요') : []
}

function answersToProfile(answers: Record<string, AnswerValue>): BeneficiaryProfile {
  const currentYear = new Date().getFullYear()
  const birthYear = Number(stringAnswer(answers, 'birthYear'))
  const household = stringAnswer(answers, 'household')
  const receiving = listAnswer(answers, 'receiving')
  const needs = listAnswer(answers, 'need')
  const mobility = stringAnswer(answers, 'mobility')
  const housing = stringAnswer(answers, 'housing')
  const visit = stringAnswer(answers, 'visit')
  const children = stringAnswer(answers, 'children')

  const categories = [...new Set(needs.flatMap((need) => needCategories[need] ?? []))]
  const incomeTypes: string[] = []
  const tags: string[] = []

  if (receiving.includes('기초연금')) incomeTypes.push('BASIC_PENSION_RECIPIENT')
  if (receiving.includes('생계비 지원')) incomeTypes.push('BASIC_LIVELIHOOD_ANY')
  if (receiving.includes('병원비 지원')) incomeTypes.push('MEDICAL_AID_RECIPIENT')
  if (receiving.includes('집세 지원')) incomeTypes.push('BASIC_LIVELIHOOD_ANY')

  if (household === '혼자 살아요') tags.push('LIVING_ALONE', 'SOCIAL_ISOLATION')
  if (children?.includes('끊겼어요') || children?.includes('없어요')) tags.push('FAMILY_SUPPORT_ABSENT')
  if (needs.includes('식사·혼자 생활')) tags.push('MEAL_PREP_DIFFICULTY', 'DAILY_LIVING_DIFFICULTY')
  if (needs.includes('외출·이동') || visit === '못 가요') tags.push('MOBILITY_DIFFICULTY')
  if (needs.includes('병원비가 걱정돼요')) tags.push('MEDICAL_EXPENSE_BURDEN')
  if (needs.includes('혼자 있을 때 안전')) tags.push('EMERGENCY_SAFETY_RISK')
  if (housing === '제 집이에요') tags.push('HOME_OWNER')
  if (housing === '전세·월세예요') tags.push('RENT_BURDEN')
  if (housing === '자녀·친척 집이에요') tags.push('HOUSING_INSTABILITY')

  const assistanceNeed = mobility === '못 해요'
    ? ['HIGH']
    : mobility === '힘들지만 해요'
      ? ['MEDIUM']
      : ['LOW']

  return {
    age: Number.isInteger(birthYear) && birthYear > 1900 && birthYear <= currentYear
      ? currentYear - birthYear
      : undefined,
    region: stringAnswer(answers, 'area'),
    livingAlone: household ? household === '혼자 살아요' : undefined,
    basicLivelihoodRecipient: receiving.includes('생계비 지원'),
    medicalAidRecipient: receiving.includes('병원비 지원'),
    basicPensionRecipient: receiving.includes('기초연금'),
    incomeInformationComplete: false,
    incomeTypes,
    needs: categories,
    assistanceNeed,
    tags,
  }
}

function matchReason(match: ProgramMatch) {
  const needs = match.matchedNeeds.map((item) => categoryLabels[item] ?? item)
  if (needs.length > 0) return `말씀하신 ${needs.join('·')} 도움이 이 사업의 지원내용과 맞을 수 있어요.`
  const matched = match.conditions.find((item) => item.status === 'MATCHED' && item.key !== 'region')
  return matched?.detail ?? '입력하신 상황에서 신청 가능성을 확인해 볼 만한 사업이에요.'
}

function toBenefit(match: ProgramMatch): Benefit {
  const unknown = match.conditions.filter((item) => item.status === 'UNKNOWN')
  const needsCheck = [
    ...unknown.map((item) => item.detail),
    ...match.confirmationItems.slice(0, 2),
  ].filter(Boolean)

  return {
    id: match.program.id,
    name: match.program.name,
    tag: match.status === 'LIKELY' ? '신청해볼 수 있어요' : '확인이 필요해요',
    summary: match.program.summary,
    amount: match.program.benefits.join(' · '),
    reason: matchReason(match),
    location: `${match.program.application.organization} · ${match.program.application.method}`,
    needsCheck: needsCheck.length > 0 ? needsCheck.join(' / ') : undefined,
    supplies: match.program.requiredDocuments,
    contact: match.program.application.contact,
    sourceUrl: match.program.source.url,
    eligibilityStatus: match.status,
  }
}

async function matchLocally(answers: Record<string, AnswerValue>): Promise<MatchingResponse> {
  const [catalog] = await Promise.all([getCatalog(), delay(500)])
  const profile = answersToProfile(answers)
  let matches = findProgramMatches(catalog.programs, profile, {
    filters: { onlyCurrentlyOpen: true },
    includeNotEligible: false,
    limit: 12,
  })
  let broadened = false

  // 정확한 자격을 아직 판단할 수 없다고 해서 결과를 0건으로 끝내지 않는다.
  // 연령·지역·소득은 주민센터에서 최종 확인하도록 남기고, 현재 접수 가능한 일반 후보를 제시한다.
  if (matches.length === 0) {
    broadened = true
    matches = findProgramMatches(catalog.programs, {
      ...profile,
      age: undefined,
      region: undefined,
      livingAlone: undefined,
      needs: [],
      tags: [],
    }, {
      filters: { onlyCurrentlyOpen: true },
      includeNotEligible: false,
      limit: 12,
    })
  }

  const needsGuardianInput = [...new Set(
    matches
      .flatMap((match) => match.conditions)
      .filter((item) => item.status === 'UNKNOWN')
      .map((item) => item.label),
  )].slice(0, 3)

  return {
    benefits: matches.map(toBenefit),
    needsGuardianInput,
    broadened,
  }
}
