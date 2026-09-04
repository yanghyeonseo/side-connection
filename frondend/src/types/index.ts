export type UserMode = 'self' | 'helper'
export type AnswerValue = string | string[]

export type Question = {
  id: string
  title: string
  description?: string
  options?: string[]
  multiple?: boolean
  input?: 'text' | 'number'
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
}
