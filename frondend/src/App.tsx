import { useMemo, useState } from 'react'
import { createSession, getMatches, saveAnswer } from './api/client'
import { questions } from './data/questions'
import type { AnswerValue, Benefit, MatchingResponse, UserMode } from './types'

type Screen = 'start' | 'helperType' | 'question' | 'loading' | 'results' | 'detail' | 'brief'

const helperTypes = ['자녀·가족', '요양보호사·활동지원사', '복지사·공무원', '이웃·지인']

function Icon({ name }: { name: 'speaker' | 'arrow' | 'check' | 'copy' | 'close' }) {
  const paths = {
    speaker: <><path d="M4 10v4h3l4 4V6l-4 4H4Z"/><path d="M15 9.5a4 4 0 0 1 0 5M17.8 6.8a8 8 0 0 1 0 10.4"/></>,
    arrow: <path d="m9 18 6-6-6-6"/>, check: <path d="m5 12 4 4L19 6"/>, copy: <><rect x="8" y="8" width="10" height="10" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>, close: <path d="m6 6 12 12M18 6 6 18"/>
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('start')
  const [mode, setMode] = useState<UserMode>('self')
  const [helperType, setHelperType] = useState('')
  const [largeText, setLargeText] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({})
  const [questionIndex, setQuestionIndex] = useState(0)
  const [matches, setMatches] = useState<MatchingResponse | null>(null)
  const [selectedBenefit, setSelectedBenefit] = useState<Benefit | null>(null)
  const [draft, setDraft] = useState<AnswerValue>('')
  const [copied, setCopied] = useState(false)

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
    setSessionId(session.sessionId); setScreen('question')
  }
  const beginHelper = async (type: string) => {
    setHelperType(type)
    const session = await createSession('helper')
    setSessionId(session.sessionId); setScreen('question')
  }
  const readQuestion = () => {
    if ('speechSynthesis' in window && question) window.speechSynthesis.speak(new SpeechSynthesisUtterance(question.title))
  }
  const select = (value: string) => {
    if (!question) return
    if (question.multiple) {
      const previous = Array.isArray(draft) ? draft : []
      setDraft(previous.includes(value) ? previous.filter((item) => item !== value) : [...previous, value])
    } else setDraft(value)
  }
  const next = async (value?: AnswerValue, unknown = false) => {
    if (!question) return
    const finalValue = unknown ? '잘 모르겠어요' : (value ?? draft)
    if (!finalValue || (Array.isArray(finalValue) && finalValue.length === 0)) return
    const updated = { ...answers, [question.id]: finalValue }
    setAnswers(updated)
    void saveAnswer(sessionId, question.id, finalValue)
    if (questionIndex + 1 < activeQuestions.length) {
      setQuestionIndex(questionIndex + 1); setDraft(updated[activeQuestions[questionIndex + 1].id] ?? '')
    } else {
      setScreen('loading')
      try { setMatches(await getMatches(sessionId, updated)) } finally { setScreen('results') }
    }
  }
  const previous = () => {
    if (questionIndex === 0) { setScreen('start'); return }
    const index = questionIndex - 1
    setQuestionIndex(index); setDraft(answers[activeQuestions[index].id] ?? '')
  }
  const brief = () => {
    const child = answers.children === '있는데 아예 끊겼어요' ? '자녀와 연락이 끊긴 상태입니다.' : ''
    return `[곁에 서비스 신청 안내]\n\n안녕하세요. ${answers.area ?? '거주지'}에 사시는 어르신입니다.\n${answers.household ?? ''}\n${child}\n\n다음 지원을 상담받고 싶습니다.\n${matches?.benefits.map((benefit, index) => `${index + 1}. ${benefit.name}`).join('\n') ?? ''}\n\n준비물과 자격을 확인 부탁드립니다.\n정확한 자격은 주민센터에서 확인이 필요합니다.`
  }
  const copyBrief = async () => { await navigator.clipboard?.writeText(brief()); setCopied(true) }

  return <main className={largeText ? 'app large' : 'app'}>
    <header className="topbar">
      <button className="brand" onClick={() => setScreen('start')} aria-label="처음으로">곁에<span>·</span></button>
      <button className="text-toggle" onClick={() => setLargeText(!largeText)}>{largeText ? '보통 글자' : '큰 글자'}</button>
    </header>

    {screen === 'start' && <section className="welcome page">
      <div className="warm-mark">◌</div>
      <p className="eyebrow">복지 지원, 함께 찾아볼까요?</p>
      <h1>내 상황에 맞는<br/>도움을 찾아드려요.</h1>
      <p className="subcopy">질문은 10개쯤이에요.<br/>모르는 건 넘어가도 괜찮아요.</p>
      <div className="choice-stack">
        <button className="mode-card primary" onClick={() => begin('self')}><span>제가 직접 알아볼게요</span><small>내 상황을 천천히 알려드릴게요</small><Icon name="arrow"/></button>
        <button className="mode-card" onClick={() => begin('helper')}><span>어르신을 도와드리려고 해요</span><small>어르신 상황을 대신 입력할게요</small><Icon name="arrow"/></button>
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
      {question.options ? <div className="answer-options">{question.options.map((option) => {
        const selected = Array.isArray(draft) ? draft.includes(option) : draft === option
        return <button className={selected ? 'selected' : ''} key={option} onClick={() => select(option)}>{selected && <Icon name="check"/>}{option}</button>
      })}</div> : <input className="answer-input" autoFocus type={question.input ?? 'text'} inputMode={question.input === 'number' ? 'numeric' : 'text'} placeholder={question.input === 'number' ? '예: 1945' : '예: 서울시 종로구'} value={typeof draft === 'string' ? draft : ''} onChange={(event) => setDraft(event.target.value)} />}
      <div className="question-actions"><button className="unknown" onClick={() => next(undefined, true)}>잘 모르겠어요</button><button className="next" disabled={!draft || (Array.isArray(draft) && draft.length === 0)} onClick={() => next()}>다음 <Icon name="arrow"/></button></div>
    </section>}

    {screen === 'loading' && <section className="loading page"><div className="spinner"/><h1>도움을 찾고 있어요.</h1><p>입력한 상황을 살펴보고 있어요.</p></section>}

    {screen === 'results' && matches && <section className="results page">
      <p className="eyebrow">도움 찾기 결과</p><h1><em>{matches.benefits.length}가지</em> 도움을<br/>찾아봤어요.</h1>
      {matches.needsGuardianInput.length > 0 && <div className="soft-alert"><b>조금 더 정확히 찾으려면</b><span>{matches.needsGuardianInput.join(', ')}을 확인해 주세요.</span></div>}
      <div className="benefit-list">{matches.benefits.map((benefit) => <button className="benefit-card" key={benefit.id} onClick={() => { setSelectedBenefit(benefit); setScreen('detail') }}><span className="pill">{benefit.tag}</span><h2>{benefit.name}</h2><p>{benefit.summary}</p><Icon name="arrow"/></button>)}</div>
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
      <button className="back" onClick={() => setScreen('results')}>‹ 결과로</button><p className="eyebrow">주민센터 전달용</p><h1>이 화면을<br/>보여주세요.</h1><p className="subcopy">말로 설명하기 어려울 때 도움이 돼요.</p>
      <article className="letter">{brief().split('\n').map((line, index) => <p key={index}>{line || ' '}</p>)}</article>
      <button className="copy-button" onClick={copyBrief}><Icon name="copy"/>{copied ? '복사했어요' : '안내문 복사하기'}</button>
      <p className="disclaimer">계좌번호는 화면에 담지 않아요.</p>
    </section>}
  </main>
}
