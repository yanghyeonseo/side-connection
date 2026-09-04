import { useEffect, useMemo, useState } from 'react'
import { createSession, getAdminCase, getHelperCase, getMatches, saveAnswer, saveHelperAnswers } from './api/client'
import { questions } from './data/questions'
import type { AdminCase, AnswerValue, Benefit, HelperCase, MatchingResponse, UserMode } from './types'

type Screen = 'start' | 'helperType' | 'question' | 'loading' | 'results' | 'detail' | 'brief' | 'helperInvite'

const helperTypes = ['자녀·가족', '요양보호사·활동지원사', '복지사·공무원', '이웃·지인']
const regions: Record<string, string[]> = {
  '서울특별시': ['종로구', '중구', '용산구', '성동구', '광진구', '마포구', '강남구', '송파구'],
  '부산광역시': ['중구', '서구', '동구', '부산진구', '해운대구', '사하구'],
  '대구광역시': ['중구', '동구', '서구', '남구', '수성구', '달서구'],
  '인천광역시': ['중구', '동구', '미추홀구', '연수구', '부평구', '서구'],
  '광주광역시': ['동구', '서구', '남구', '북구', '광산구'],
  '대전광역시': ['동구', '중구', '서구', '유성구', '대덕구'],
  '울산광역시': ['중구', '남구', '동구', '북구', '울주군'],
  '세종특별자치시': ['세종시'], '경기도': ['수원시', '성남시', '고양시', '용인시', '부천시', '화성시'],
  '강원특별자치도': ['춘천시', '원주시', '강릉시'], '충청북도': ['청주시', '충주시', '제천시'],
  '충청남도': ['천안시', '공주시', '아산시'], '전북특별자치도': ['전주시', '군산시', '익산시'],
  '전라남도': ['목포시', '여수시', '순천시'], '경상북도': ['포항시', '경주시', '구미시'],
  '경상남도': ['창원시', '진주시', '김해시'], '제주특별자치도': ['제주시', '서귀포시']
}
const birthYears = Array.from({ length: 107 }, (_, index) => String(2026 - index))

function Icon({ name }: { name: 'speaker' | 'arrow' | 'check' | 'copy' | 'close' }) {
  const paths = {
    speaker: <><path d="M4 10v4h3l4 4V6l-4 4H4Z"/><path d="M15 9.5a4 4 0 0 1 0 5M17.8 6.8a8 8 0 0 1 0 10.4"/></>,
    arrow: <path d="m9 18 6-6-6-6"/>, check: <path d="m5 12 4 4L19 6"/>, copy: <><rect x="8" y="8" width="10" height="10" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>, close: <path d="m6 6 12 12M18 6 6 18"/>
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

export default function App() {
  const appBasePath = import.meta.env.BASE_URL.replace(/\/$/, '')
  const appPath = window.location.pathname.startsWith(appBasePath) ? window.location.pathname.slice(appBasePath.length) : window.location.pathname
  const adminCode = appPath.match(/^\/admin\/cases\/(\d{6,12})\/?$/)?.[1]
  const helperCode = appPath.match(/^\/helper\/cases\/(\d{6,12})\/?$/)?.[1]
  const [screen, setScreen] = useState<Screen>('start')
  const [mode, setMode] = useState<UserMode>('self')
  const [helperType, setHelperType] = useState('')
  const [largeText, setLargeText] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [caseCode, setCaseCode] = useState('')
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({})
  const [questionIndex, setQuestionIndex] = useState(0)
  const [matches, setMatches] = useState<MatchingResponse | null>(null)
  const [matchError, setMatchError] = useState(false)
  const [selectedBenefit, setSelectedBenefit] = useState<Benefit | null>(null)
  const [draft, setDraft] = useState<AnswerValue>('')
  const [regionCity, setRegionCity] = useState('')
  const [regionDistrict, setRegionDistrict] = useState('')
  const [regionDetail, setRegionDetail] = useState('')
  const [linkCopied, setLinkCopied] = useState(false)

  const activeQuestions = useMemo(() => questions.filter((question) => {
    if (question.id === 'lastContact') return typeof answers.children === 'string' && answers.children !== '없어요' && answers.children !== '네, 연락도 잘 돼요'
    if (question.id === 'mobility') return Array.isArray(answers.need) && answers.need.includes('식사·혼자 생활')
    return true
  }), [answers.children, answers.need])
  const question = activeQuestions[questionIndex]

  const begin = async (nextMode: UserMode) => {
    setMode(nextMode)
    if (nextMode === 'helper') { setScreen('helperType'); return }
    const session = await createSession(nextMode)
    setSessionId(session.sessionId); setCaseCode(session.caseCode); setScreen('question')
  }
  const beginHelper = async (type: string) => {
    setHelperType(type)
    const session = await createSession('helper')
    setSessionId(session.sessionId); setCaseCode(session.caseCode); setScreen('question')
  }
  const readQuestion = () => {
    if (!('speechSynthesis' in window) || !question) return
    const speak = () => {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(`${question.title}. ${question.description ?? ''}`)
      utterance.lang = 'ko-KR'
      utterance.rate = 0.82
      utterance.pitch = 1
      const koreanVoice = window.speechSynthesis.getVoices().find((voice) => voice.lang.toLowerCase().startsWith('ko'))
      if (koreanVoice) utterance.voice = koreanVoice
      window.speechSynthesis.speak(utterance)
    }
    if (window.speechSynthesis.getVoices().some((voice) => voice.lang.toLowerCase().startsWith('ko'))) speak()
    else window.speechSynthesis.onvoiceschanged = speak
  }
  const select = (value: string) => {
    if (!question) return
    if (question.multiple) {
      const previous = Array.isArray(draft) ? draft : []
      setDraft(previous.includes(value) ? previous.filter((item) => item !== value) : [...previous, value])
    } else setDraft(value)
  }
  const findMatches = async (nextAnswers: Record<string, AnswerValue>) => {
    setScreen('loading')
    setMatchError(false)
    try {
      setMatches(await getMatches(sessionId, nextAnswers))
    } catch {
      setMatches({ benefits: [], needsGuardianInput: [] })
      setMatchError(true)
    } finally {
      setScreen('results')
    }
  }
  const next = async (value?: AnswerValue, unknown = false) => {
    if (!question) return
    const finalValue = unknown ? '잘 모르겠어요' : (value ?? draft)
    if (!finalValue || (Array.isArray(finalValue) && finalValue.length === 0)) return
    const answer = question.id === 'area' ? `${regionCity} ${regionDistrict}` : finalValue
    const updated: Record<string, AnswerValue> = { ...answers, [question.id]: answer, ...(question.id === 'area' && regionDetail ? { areaDetail: regionDetail } : {}) }
    setAnswers(updated)
    void saveAnswer(sessionId, question.id, answer)
    if (question.id === 'area' && regionDetail) void saveAnswer(sessionId, 'areaDetail', regionDetail)
    if (questionIndex + 1 < activeQuestions.length) {
      setQuestionIndex(questionIndex + 1); setDraft(updated[activeQuestions[questionIndex + 1].id] ?? '')
    } else {
      void findMatches(updated)
    }
  }
  const previous = () => {
    if (questionIndex === 0) { setScreen('start'); return }
    const index = questionIndex - 1
    setQuestionIndex(index); setDraft(answers[activeQuestions[index].id] ?? '')
  }
  const caseUrl = `${window.location.origin}${import.meta.env.BASE_URL}admin/cases/${caseCode}`
  const helperUrl = `${window.location.origin}${import.meta.env.BASE_URL}helper/cases/${caseCode}`
  const callNumber = (import.meta.env.VITE_WELFARE_CENTER_PHONE ?? '129').replace(/[^0-9]/g, '')
  const smsNumber = (import.meta.env.VITE_WELFARE_CENTER_SMS_NUMBER ?? '').replace(/[^0-9]/g, '')
  const smsBody = `복지 지원 상담 요청입니다.\n사례번호: ${caseCode}\n행정 확인 화면: ${caseUrl}`
  const smsHref = `sms:${smsNumber}?body=${encodeURIComponent(smsBody)}`

  const missingCount = Object.values(answers).filter((answer) => answer === '잘 모르겠어요').length
  const shareHelperLink = async () => {
    const shareData = { title: '곁이음 보호자 보완', text: '어르신이 답하지 못한 항목을 채워 주세요.', url: helperUrl }
    if (navigator.share) await navigator.share(shareData)
    else { await navigator.clipboard?.writeText(helperUrl); setLinkCopied(true) }
  }

  if (adminCode) return <AdministrativeCase caseCode={adminCode} />
  if (helperCode) return <HelperCompletion caseCode={helperCode} />

  return <main className={largeText ? 'app large' : 'app'}>
    <header className="topbar">
      <button className="brand" onClick={() => setScreen('start')} aria-label="처음으로">곁이음<span>·</span></button>
      <button className="text-toggle" onClick={() => setLargeText(!largeText)}>{largeText ? '보통 글자' : '큰 글자'}</button>
    </header>

    {screen === 'start' && <section className="welcome page">
      <div className="warm-mark">◌</div>
      <p className="eyebrow">복지 지원, 함께 찾아볼까요?</p>
      <h1>내 상황에 맞는<br/>도움을 찾아드려요.</h1>
      <p className="subcopy">질문은 10개쯤이에요.<br/>모르는 건 넘어가도 괜찮아요.</p>
      <div className="choice-stack">
        <button className="mode-card primary" onClick={() => begin('self')}><span>어르신 본인이에요</span><Icon name="arrow"/></button>
        <button className="mode-card" onClick={() => begin('helper')}><span>어르신 보호자예요</span><Icon name="arrow"/></button>
      </div>
      <p className="notice">로그인 없이 이용할 수 있어요.</p>
    </section>}

    {screen === 'helperType' && <section className="page selection-page">
      <button className="back" onClick={() => setScreen('start')}>‹ 이전</button>
      <p className="eyebrow">도와주시는 분</p><h1>어르신과 어떤<br/>관계이신가요?</h1>
      <div className="option-list">{helperTypes.map((type) => <button key={type} onClick={() => beginHelper(type)}>{type}<Icon name="arrow"/></button>)}</div>
    </section>}

    {screen === 'question' && question && <section className="question-page page">
      <div className="progress-label"><button className="back" onClick={previous}>‹ 이전</button><span>{questionIndex + 1} / {activeQuestions.length}</span></div>
      <div className="progress"><i style={{ width: `${((questionIndex + 1) / activeQuestions.length) * 100}%` }} /></div>
      <div className="question-head"><p className="eyebrow">상황 알아보기</p><h1>{question.title}</h1>{question.description && <p>{question.description}</p>}<button className="listen" onClick={readQuestion}><Icon name="speaker"/> 읽어드릴게요</button></div>
      {question.control === 'year' ? <div className="year-dial"><label htmlFor="birthYear">출생 연도</label><select id="birthYear" value={typeof draft === 'string' ? draft : ''} onChange={(event) => setDraft(event.target.value)}><option value="">연도를 선택해 주세요</option>{birthYears.map((year) => <option value={year} key={year}>{year}년</option>)}</select><p>휴대폰에서는 다이얼을 돌리듯 고를 수 있어요.</p></div> : question.control === 'region' ? <div className="region-picker"><div><label>시·도</label><div className="region-chips">{Object.keys(regions).map((city) => <button className={regionCity === city ? 'selected' : ''} key={city} onClick={() => { setRegionCity(city); setRegionDistrict(''); setDraft('') }}>{city.replace(/특별자치|특별|광역/g, '')}</button>)}</div></div>{regionCity && <div><label>시·군·구</label><div className="region-chips">{regions[regionCity].map((district) => <button className={regionDistrict === district ? 'selected' : ''} key={district} onClick={() => { setRegionDistrict(district); setDraft(`${regionCity} ${district}`) }}>{district}</button>)}</div></div>}{regionDistrict && <label className="detail-address">상세 주소 <small>선택</small><input placeholder="예: ○○동, ○○아파트" value={regionDetail} onChange={(event) => setRegionDetail(event.target.value)} /></label>}</div> : question.options ? <div className="answer-options">{question.options.map((option) => {
        const selected = Array.isArray(draft) ? draft.includes(option) : draft === option
        return <button className={selected ? 'selected' : ''} key={option} onClick={() => select(option)}>{selected && <Icon name="check"/>}{option}</button>
      })}</div> : <input className="answer-input" autoFocus type={question.input ?? 'text'} inputMode={question.input === 'number' ? 'numeric' : 'text'} placeholder={question.input === 'number' ? '예: 1945' : '예: 서울시 종로구'} value={typeof draft === 'string' ? draft : ''} onChange={(event) => setDraft(event.target.value)} />}
      <div className="question-actions"><button className="unknown" onClick={() => next(undefined, true)}>잘 모르겠어요</button><button className="next" disabled={!draft || (Array.isArray(draft) && draft.length === 0)} onClick={() => next()}>다음 <Icon name="arrow"/></button></div>
    </section>}

    {screen === 'loading' && <section className="loading page"><div className="spinner"/><h1>도움을 찾고 있어요.</h1><p>입력한 상황을 살펴보고 있어요.</p></section>}

    {screen === 'results' && matches && <section className="results page">
      <p className="eyebrow">도움 찾기 결과</p><h1><em>{matches.benefits.length}가지</em> 도움을<br/>찾아봤어요.</h1>
      {matchError && <div className="result-state"><b>결과를 불러오지 못했어요.</b><span>인터넷 연결을 확인한 뒤 다시 시도해 주세요.</span><button onClick={() => void findMatches(answers)}>다시 찾기</button></div>}
      {matches.aiSummary && <p className="ai-summary">{matches.aiSummary}</p>}
      {matches.broadened && <div className="soft-alert"><b>넓게 찾아본 결과예요</b><span>정확한 자격은 주민센터에서 한 번 더 확인해 주세요.</span></div>}
      {matches.needsGuardianInput.length > 0 && <div className="soft-alert"><b>조금 더 정확히 찾으려면</b><span>{matches.needsGuardianInput.join(', ')}을 확인해 주세요.</span></div>}
      {!matchError && matches.benefits.length === 0 && <div className="result-state"><b>지금은 딱 맞는 도움을 찾기 어려워요.</b><span>주민센터에서 현재 상황을 한 번 더 확인해 주세요.</span></div>}
      <div className="benefit-list">{matches.benefits.map((benefit) => <button className="benefit-card" key={benefit.id} onClick={() => { setSelectedBenefit(benefit); setScreen('detail') }}><span className="pill">{benefit.tag}</span><h2>{benefit.name}</h2><p>{benefit.summary}</p><Icon name="arrow"/></button>)}</div>
      {missingCount > 0 && <button className="helper-button" onClick={() => setScreen('helperInvite')}>보호자에게 빈칸 채워달라고 하기 <Icon name="arrow"/></button>}
      <button className="brief-button" onClick={() => setScreen('brief')}>주민센터에 보여줄 안내문 만들기 <Icon name="arrow"/></button>
      <p className="disclaimer">정확한 자격은 주민센터에서 확인해요.</p>
    </section>}

    {screen === 'detail' && selectedBenefit && <section className="detail page">
      <button className="back" onClick={() => setScreen('results')}>‹ 결과로</button><span className="pill">{selectedBenefit.tag}</span><h1>{selectedBenefit.name}</h1><p className="detail-summary">{selectedBenefit.summary}</p>
      <dl><div><dt>어떤 도움인가요?</dt><dd>{selectedBenefit.amount}</dd></div><div><dt>왜 해당할 수 있나요?</dt><dd>{selectedBenefit.reason}</dd></div><div><dt>어디로 가면 되나요?</dt><dd>{selectedBenefit.location}</dd></div>{selectedBenefit.contact && <div><dt>문의</dt><dd>{selectedBenefit.contact}</dd></div>}</dl>
      <div className="supplies"><h2>가져갈 것</h2>{selectedBenefit.supplies.map((supply) => <p key={supply}><span>✓</span>{supply}</p>)}</div>
      {selectedBenefit.needsCheck && <div className="soft-alert"><b>주민센터에서 확인해요</b><span>{selectedBenefit.needsCheck}</span></div>}
      {selectedBenefit.sourceUrl && <a className="source-link" href={selectedBenefit.sourceUrl} target="_blank" rel="noreferrer">공식 안내 확인하기 ↗</a>}
    </section>}

    {screen === 'brief' && <section className="brief page">
      <button className="back" onClick={() => setScreen('results')}>‹ 결과로</button><p className="eyebrow">주민센터 연결</p><h1>담당자에게<br/>바로 알려주세요.</h1><p className="subcopy">사례번호와 안전한 확인 링크가 함께 전달돼요.</p>
      <div className="case-code"><span>상담 사례번호</span><strong>{caseCode}</strong><small>전화할 때 이 번호를 말씀해 주세요.</small></div>
      <div className="contact-actions"><a className="contact-button call" href={`tel:${callNumber}`}>주민센터에 전화하기 <Icon name="arrow"/></a>{smsNumber && <a className="contact-button message" href={smsHref}>담당자에게 메시지 보내기 <Icon name="arrow"/></a>}</div>
      <div className="send-note"><b>행정 확인용 정보가 링크에 담겨요</b><span>주소, 가구·소득 구간, 수급 여부와 추천 근거를 전문 용어로 확인할 수 있어요.</span></div>
      <p className="disclaimer">계좌번호는 전송하지 않아요. 실제 수신 번호는 환경설정으로 연결할 수 있어요.</p>
    </section>}

    {screen === 'helperInvite' && <section className="brief page">
      <button className="back" onClick={() => setScreen('results')}>‹ 결과로</button><p className="eyebrow">보호자에게 부탁하기</p><h1>모르는 항목만<br/>채워주세요.</h1><p className="subcopy">보호자에게 이 링크를 보내면 돼요.</p>
      <div className="case-code"><span>보호자 보완 사례번호</span><strong>{caseCode}</strong><small>보호자는 비어 있는 항목만 볼 수 있어요.</small></div>
      <button className="share-button" onClick={shareHelperLink}>{linkCopied ? '링크를 복사했어요' : '보호자에게 링크 보내기'} <Icon name="arrow"/></button>
      <div className="send-note"><b>보호자가 채우면 결과가 더 정확해져요</b><span>소득, 집 계약, 현재 받는 지원처럼 어르신이 알기 어려운 정보만 요청해요.</span></div>
    </section>}
  </main>
}

function AdministrativeCase({ caseCode }: { caseCode: string }) {
  const [caseInfo, setCaseInfo] = useState<AdminCase | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { getAdminCase(caseCode).then(setCaseInfo).catch(() => setError(true)) }, [caseCode])
  if (error) return <main className="admin-page"><h1>사례를 찾을 수 없어요.</h1><p>사례번호를 다시 확인해 주세요.</p></main>
  if (!caseInfo) return <main className="admin-page"><div className="spinner"/><p>사례 정보를 불러오는 중이에요.</p></main>
  const fields = [['거주지', caseInfo.address], ['가구 구성', caseInfo.household], ['소득 구간', caseInfo.incomeBand], ['공적 급여 수급', caseInfo.publicBenefits], ['부양·가족 관계', caseInfo.familySupport], ['주요 욕구', caseInfo.needs], ['신청 준비 상태', caseInfo.identityAndAccount]]
  return <main className="admin-page"><header><span>곁이음 · 행정 확인용</span><b>사례 {caseInfo.caseCode}</b></header><section><p className="eyebrow">사전상담 정보</p><h1>복지 지원 상담 사례</h1><p className="admin-time">등록 시각 {caseInfo.createdAt}</p><dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><div className="admin-benefits"><b>추천 검토 사업</b>{caseInfo.recommendedBenefits.map((benefit) => <span key={benefit}>{benefit}</span>)}</div><div className="admin-note"><b>판정 유의사항</b><p>{caseInfo.note}</p></div></section></main>
}

function HelperCompletion({ caseCode }: { caseCode: string }) {
  const [helperCase, setHelperCase] = useState<HelperCase | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState(false)
  useEffect(() => { getHelperCase(caseCode).then(setHelperCase).catch(() => setError(true)) }, [caseCode])
  if (error) return <main className="admin-page"><h1>사례를 찾을 수 없어요.</h1><p>링크가 만료됐을 수 있어요. 어르신께 새 링크를 부탁해 주세요.</p></main>
  if (!helperCase) return <main className="admin-page"><div className="spinner"/><p>보완할 항목을 불러오는 중이에요.</p></main>
  if (helperCase.missingFields.length === 0 && !complete) return <main className="admin-page"><h1>채울 항목이 없어요.</h1><p>어르신이 모든 질문에 답하셨어요. 고마워요!</p></main>
  const ready = helperCase.missingFields.every((field) => values[field.id]?.trim())
  const submit = async () => {
    try { await saveHelperAnswers(caseCode, values); setComplete(true) } catch { setError(true) }
  }
  return <main className="helper-page"><header><span>곁이음</span><b>보호자 입력</b></header>{complete ? <section className="helper-done"><div className="warm-mark">✓</div><h1>잘 받았어요.</h1><p>입력한 내용이 어르신 결과에 반영됐어요.</p></section> : <section><p className="eyebrow">어르신 대신 입력하기</p><h1>아는 내용만<br/>채워주세요.</h1><p className="subcopy">정확하지 않아도 괜찮아요. 최종 확인은 주민센터에서 해요.</p><div className="helper-fields">{helperCase.missingFields.map((field) => <label key={field.id}><b>{field.label}</b>{field.description && <small>{field.description}</small>}{field.options ? <div className="helper-options">{field.options.map((option) => <button className={values[field.id] === option ? 'selected' : ''} key={option} onClick={() => setValues({ ...values, [field.id]: option })}>{option}</button>)}</div> : <input type={field.input ?? 'text'} value={values[field.id] ?? ''} onChange={(event) => setValues({ ...values, [field.id]: event.target.value })} />}</label>)}</div><button className="share-button" disabled={!ready} onClick={submit}>입력 완료 <Icon name="arrow"/></button></section>}</main>
}
