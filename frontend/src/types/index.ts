export type UserMode = 'self' | 'helper'
export type AnswerValue = string | string[]

export type Question = {
  id: string
  title: string
  description?: string
  options?: string[]
  multiple?: boolean
  input?: 'text' | 'number'
  control?: 'year' | 'region'
  followUp?: (answer: AnswerValue) => boolean
}

export type Benefit = {
  id: string
  name: string
  tag: string
  summary: string
  amount: string
  reason: string
  location: string
  needsCheck?: string
  supplies: string[]
  contact?: string
  sourceUrl?: string
  eligibilityStatus?: 'LIKELY' | 'NEEDS_CONFIRMATION' | 'NOT_ELIGIBLE'
}

export type MatchingResponse = {
  benefits: Benefit[]
  needsGuardianInput: string[]
  broadened?: boolean
  aiSummary?: string | null
}

export type Session = {
  sessionId: string
  caseCode: string
}

export type AdminCase = {
  caseCode: string
  createdAt: string
  address: string
  household: string
  incomeBand: string
  publicBenefits: string
  familySupport: string
  needs: string
  identityAndAccount: string
  recommendedBenefits: string[]
  note: string
}

export type HelperField = {
  id: string
  label: string
  description?: string
  input?: 'text' | 'number'
  options?: string[]
}

export type HelperCase = {
  caseCode: string
  missingFields: HelperField[]
}
