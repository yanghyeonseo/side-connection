import type { AnswerValue, Benefit, MatchingResponse, UserMode } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const exampleBenefits: Benefit[] = [
  {
    id: 'housing', name: '주거급여', tag: '신청해볼 수 있어요', summary: '집세 부담을 덜어주는 지원이에요.', amount: '매달 집세 일부 지원',
    reason: '소득이 많지 않고 전세·월세에 사신다고 하셔서요.', location: '사시는 곳 동 주민센터', needsCheck: '보증금과 월세를 확인해요.', supplies: ['신분증', '통장 사본', '임대차계약서']
  },
  {
    id: 'basic', name: '기초생활보장 생계급여', tag: '확인이 필요해요', summary: '생활비를 보태주는 지원이에요.', amount: '가구 상황에 따라 달라져요',
    reason: '혼자 사시고 수입이 많지 않다고 하셔서요.', location: '사시는 곳 동 주민센터', needsCheck: '자녀분의 부양 여부를 함께 확인해요.', supplies: ['신분증', '통장 사본']
  },
  {
    id: 'care', name: '노인맞춤돌봄서비스', tag: '신청해볼 수 있어요', summary: '안부 확인과 생활 도움을 받을 수 있어요.', amount: '안부 확인·일상 도움',
    reason: '혼자 생활하는 데 어려움이 있다고 하셔서요.', location: '동 주민센터 또는 노인복지관', supplies: ['신분증']
  }
]

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) throw new Error('요청을 처리하지 못했어요.')
  return response.json() as Promise<T>
}

export async function createSession(mode: UserMode) {
  if (!API_BASE_URL) return { sessionId: crypto.randomUUID() }
  return request<{ sessionId: string }>('/v1/sessions', { method: 'POST', body: JSON.stringify({ mode }) })
}

export async function saveAnswer(sessionId: string, questionId: string, value: AnswerValue) {
  if (!API_BASE_URL) return
  return request<void>(`/v1/sessions/${sessionId}/answers`, { method: 'PUT', body: JSON.stringify({ questionId, value }) })
}

export async function getMatches(sessionId: string, answers: Record<string, AnswerValue>): Promise<MatchingResponse> {
  if (API_BASE_URL) return request<MatchingResponse>(`/v1/sessions/${sessionId}/matches`, { method: 'POST', body: JSON.stringify({ answers }) })
  await delay(700)
  const benefits = [...exampleBenefits]
  if (answers.housing !== '전세·월세예요') benefits.shift()
  return { benefits, needsGuardianInput: answers.children?.toString().includes('끊겼어요') ? ['자녀분과 연락이 끊긴 기간'] : ['정확한 월 소득'] }
}
