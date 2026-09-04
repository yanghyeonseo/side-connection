import { findProgramMatches, loadWelfareCatalog } from '../../welfare-search.js'
import type { BeneficiaryProfile, ProgramMatch, WelfareCatalog } from '../../welfare-search.js'
import type { AdminCase, AnswerValue, Benefit, MatchingResponse, Session, UserMode } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) throw new Error('요청을 처리하지 못했어요.')
  return response.json() as Promise<T>
}

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

export async function createSession(mode: UserMode): Promise<Session> {
  if (API_BASE_URL) return request<Session>('/v1/sessions', { method: 'POST', body: JSON.stringify({ mode }) })
  return { sessionId: crypto.randomUUID(), caseCode: `${Date.now().toString().slice(-6)}${Math.floor(Math.random() * 90 + 10)}` }
}

export async function saveAnswer(sessionId: string, questionId: string, value: AnswerValue) {
  if (API_BASE_URL) return request<void>(`/v1/sessions/${sessionId}/answers`, { method: 'PUT', body: JSON.stringify({ questionId, value }) })
  // 답변은 브라우저 메모리에만 유지하고 외부로 전송하지 않습니다.
}

export async function getMatches(sessionId: string, answers: Record<string, AnswerValue>): Promise<MatchingResponse> {
  if (API_BASE_URL) return request<MatchingResponse>(`/v1/sessions/${sessionId}/matches`, { method: 'POST', body: JSON.stringify({ answers }) })
  const [catalog] = await Promise.all([getCatalog(), delay(500)])
  const profile = answersToProfile(answers)
  const matches = findProgramMatches(catalog.programs, profile, {
    filters: { onlyCurrentlyOpen: true },
    includeNotEligible: false,
    limit: 12,
  })

  const needsGuardianInput = [...new Set(
    matches
      .flatMap((match) => match.conditions)
      .filter((item) => item.status === 'UNKNOWN')
      .map((item) => item.label),
  )].slice(0, 3)

  return {
    benefits: matches.map(toBenefit),
    needsGuardianInput,
  }
}

export async function getAdminCase(caseCode: string): Promise<AdminCase> {
  if (API_BASE_URL) return request<AdminCase>(`/v1/admin/cases/${caseCode}`, { method: 'GET' })
  return {
    caseCode, createdAt: new Date().toLocaleString('ko-KR'), address: '서울특별시 종로구 (상세 주소는 본인 확인 후 열람)',
    household: '1인 가구(독거)', incomeBand: '월 소득 추정 30~60만 원', publicBenefits: '기초연금 수급(본인 진술)',
    familySupport: '자녀와 연락 단절 가능성 있음', needs: '생계·주거·돌봄 지원 필요도 확인', identityAndAccount: '신분증·본인 명의 계좌 보유 여부 확인 필요',
    recommendedBenefits: ['주거급여', '기초생활보장 생계급여', '노인맞춤돌봄서비스'], note: '본 정보는 본인 또는 보호자 진술 기반의 사전상담 자료입니다. 소득·재산·부양의무자 기준은 공적 시스템으로 확인이 필요합니다.'
  }
}
