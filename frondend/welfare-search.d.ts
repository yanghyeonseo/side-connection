export type MatchStatus = 'LIKELY' | 'NEEDS_CONFIRMATION' | 'NOT_ELIGIBLE'
export type ConditionStatus = 'MATCHED' | 'UNKNOWN' | 'NOT_MATCHED' | 'NOT_APPLICABLE'

export type WelfareProgram = {
  id: string
  name: string
  summary: string
  managingOrganization: string
  managingDepartment: string
  departmentId: string
  departmentName: string
  status: string
  coverage: string[]
  category: string
  relatedCategories: string[]
  serviceTypes: string[]
  eligibility: {
    minAge: number | null
    maxAge: number | null
    livingAlone: boolean | null
    assistanceNeed: string[]
    incomeTypes: string[]
    conditions: string[]
  }
  benefits: string[]
  requiredDocuments: string[]
  application: {
    periodType: string
    deadline: string | null
    method: string
    organization: string
    contact: string
  }
  source: {
    name: string
    url: string
    basisYear: number
    verifiedAt: string
  }
  matchTags: string[]
}

export type BeneficiaryProfile = {
  age?: number
  region?: string
  livingAlone?: boolean
  basicLivelihoodRecipient?: boolean
  medicalAidRecipient?: boolean
  nearPovertyStatus?: boolean
  basicPensionRecipient?: boolean
  registeredDisabled?: boolean
  incomeInformationComplete?: boolean
  incomeTypes?: string[]
  needs?: string[]
  assistanceNeed?: string[]
  tags?: string[]
}

export type MatchCondition = {
  key: string
  label: string
  status: ConditionStatus
  detail: string
  hard: boolean
}

export type ProgramMatch = {
  program: WelfareProgram
  status: MatchStatus
  score: number
  conditions: MatchCondition[]
  matchedNeeds: string[]
  matchedTags: string[]
  confirmationItems: string[]
}

export type WelfareCatalog = {
  manifest: { dataset?: { recordCount?: number }; departments: unknown[] }
  departments: unknown[]
  programs: WelfareProgram[]
}

export function loadWelfareCatalog(
  manifestUrl?: string,
  options?: { fetchImpl?: typeof fetch; baseUrl?: string },
): Promise<WelfareCatalog>

export function findProgramMatches(
  programs: WelfareProgram[],
  profile?: BeneficiaryProfile,
  options?: {
    filters?: Record<string, unknown>
    includeNotEligible?: boolean
    limit?: number
    offset?: number
  },
): ProgramMatch[]
