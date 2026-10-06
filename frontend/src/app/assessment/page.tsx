'use client'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Play, CheckCircle, XCircle, ArrowRight, BarChart2, RefreshCw } from 'lucide-react'
import { toast } from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || ''

type QuizState = 'setup' | 'running' | 'submitted'

interface Question {
  id: string
  stem: string
  qtype: string
  difficulty: number
  choices?: { id: string; text: string }[]
  source_location?: string
}

interface GradedAnswer {
  question_id: string
  correct: boolean
  correct_answer: string
  explanation: string
  feedback: string
  citation_url?: string
}

export default function AssessmentPage() {
  const [state, setState] = useState<QuizState>('setup')
  const [studentId, setStudentId] = useState('')
  const [nQuestions, setNQuestions] = useState(5)
  const [qtype, setQtype] = useState('mcq')
  const [adaptive, setAdaptive] = useState(true)
  const [questions, setQuestions] = useState<Question[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [assessmentId, setAssessmentId] = useState('')
  const [graded, setGraded] = useState<GradedAnswer[]>([])
  const [report, setReport] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [currentQ, setCurrentQ] = useState(0)

  useEffect(() => {
    setStudentId(localStorage.getItem('student_id') || '')
  }, [])

  const generate = async () => {
    if (!studentId) return toast.error('Create your profile first')
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/assessment/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: studentId, n_questions: nQuestions, qtype, adaptive }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setAssessmentId(data.assessment_id)
      setQuestions(data.questions)
      setAnswers({})
      setCurrentQ(0)
      setState('running')
    } catch (e: any) {
      toast.error(e.message || 'Generation failed')
    } finally {
      setLoading(false)
    }
  }

  const submit = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/assessment/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assessment_id: assessmentId,
          answers: Object.entries(answers).map(([question_id, student_answer]) => ({ question_id, student_answer })),
        }),
      })
      const data = await res.json()
      setGraded(data.graded)
      setReport(data.report)
      setState('submitted')
    } catch {
      toast.error('Submission failed')
    } finally {
      setLoading(false)
    }
  }

  const difficultyLabel = (d: number) => ['', 'Very Easy', 'Easy', 'Medium', 'Hard', 'Expert'][d] || 'Medium'
  const difficultyColor = (d: number) => ['', 'text-emerald-400', 'text-green-400', 'text-yellow-400', 'text-orange-400', 'text-red-400'][d] || 'text-slate-400'

  return (
    <div className="min-h-screen px-6 py-10 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Brain className="text-indigo-400" size={24} />
        <h1 className="text-2xl font-bold gradient-text">Adaptive Assessment</h1>
      </div>

      <AnimatePresence mode="wait">
        {/* SETUP */}
        {state === 'setup' && (
          <motion.div key="setup" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="glass p-8 space-y-6">
              <h2 className="text-lg font-semibold">Configure Your Quiz</h2>

              <div>
                <label className="block text-sm text-slate-400 mb-2">Number of questions</label>
                <div className="flex gap-2">
                  {[5, 10, 15, 20].map(n => (
                    <button key={n}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${nQuestions === n ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setNQuestions(n)}>{n}</button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-2">Question type</label>
                <div className="flex gap-2 flex-wrap">
                  {[['mcq', 'Multiple Choice'], ['short', 'Short Answer'], ['numerical', 'Numerical'], ['mixed', 'Mixed']].map(([v, l]) => (
                    <button key={v}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${qtype === v ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setQtype(v)}>{l}</button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-6 rounded-full transition-colors cursor-pointer relative ${adaptive ? 'bg-indigo-500' : 'bg-slate-700'}`}
                  onClick={() => setAdaptive(!adaptive)}>
                  <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${adaptive ? 'left-5' : 'left-1'}`} />
                </div>
                <div>
                  <p className="text-sm font-medium">Adaptive mode</p>
                  <p className="text-xs text-slate-500">Targets your weak areas using Bayesian Knowledge Tracing</p>
                </div>
              </div>

              <button className="btn-primary w-full flex items-center justify-center gap-2 py-3" onClick={generate} disabled={loading}>
                {loading ? <><RefreshCw size={14} className="animate-spin" />Generating…</> : <><Play size={14} />Start Quiz</>}
              </button>
            </div>
          </motion.div>
        )}

        {/* RUNNING */}
        {state === 'running' && questions.length > 0 && (
          <motion.div key="running" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            {/* Progress */}
            <div className="mb-6">
              <div className="flex justify-between text-sm text-slate-500 mb-2">
                <span>Question {currentQ + 1} of {questions.length}</span>
                <span>{Object.keys(answers).length} answered</span>
              </div>
              <div className="mastery-bar">
                <div className="mastery-fill bg-gradient-to-r from-indigo-500 to-violet-500"
                  style={{ width: `${((currentQ + 1) / questions.length) * 100}%` }} />
              </div>
            </div>

            <AnimatePresence mode="wait">
              {questions[currentQ] && (
                <motion.div key={currentQ} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                  <QuestionCard
                    question={questions[currentQ]}
                    answer={answers[questions[currentQ].id] || ''}
                    onAnswer={ans => setAnswers(prev => ({ ...prev, [questions[currentQ].id]: ans }))}
                    difficultyLabel={difficultyLabel}
                    difficultyColor={difficultyColor}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <div className="flex justify-between mt-6">
              <button className="btn-secondary" onClick={() => setCurrentQ(q => Math.max(0, q - 1))} disabled={currentQ === 0}>← Prev</button>
              {currentQ < questions.length - 1 ? (
                <button className="btn-primary flex items-center gap-2" onClick={() => setCurrentQ(q => q + 1)}>
                  Next <ArrowRight size={14} />
                </button>
              ) : (
                <button className="btn-primary flex items-center gap-2" onClick={submit} disabled={loading}>
                  {loading ? 'Submitting…' : 'Submit Quiz ✓'}
                </button>
              )}
            </div>

            {/* Question dots */}
            <div className="flex gap-1.5 justify-center mt-6 flex-wrap">
              {questions.map((q, i) => (
                <button key={q.id} className={`w-8 h-8 rounded-lg text-xs font-bold transition-all ${
                  i === currentQ ? 'bg-indigo-500 text-white' :
                  answers[q.id] ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
                  'bg-slate-800 text-slate-500'
                }`} onClick={() => setCurrentQ(i)}>{i + 1}</button>
              ))}
            </div>
          </motion.div>
        )}

        {/* SUBMITTED */}
        {state === 'submitted' && (
          <motion.div key="submitted" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            {report && (
              <div className="glass p-6 mb-6">
                <div className="text-center mb-6">
                  <div className="text-6xl font-extrabold gradient-text mb-2">
                    {Math.round(report.score * 100)}%
                  </div>
                  <p className="text-slate-400">{report.correct}/{report.total} correct</p>
                </div>
                {report.recommendations?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-400 mb-2">Recommendations</h3>
                    <ul className="space-y-1">
                      {report.recommendations.map((r: string, i: number) => (
                        <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                          <ArrowRight size={12} className="text-indigo-400 mt-1 shrink-0" />{r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-4">
              {graded.map((g, i) => {
                const q = questions.find(qq => qq.id === g.question_id)
                return (
                  <div key={g.question_id} className={`glass-sm p-4 rounded-xl border-l-2 ${g.correct ? 'border-emerald-500' : 'border-red-500'}`}>
                    <div className="flex items-start gap-3">
                      {g.correct ? <CheckCircle size={16} className="text-emerald-400 mt-0.5 shrink-0" /> : <XCircle size={16} className="text-red-400 mt-0.5 shrink-0" />}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium mb-1">{q?.stem}</p>
                        <p className="text-xs text-slate-500 mb-2">Your answer: <span className="text-slate-300">{answers[g.question_id] || '—'}</span></p>
                        {!g.correct && <p className="text-xs text-emerald-400 mb-2">Correct: {g.correct_answer}</p>}
                        <p className="text-xs text-slate-400">{g.explanation}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <button className="btn-secondary mt-6 w-full" onClick={() => setState('setup')}>
              <RefreshCw size={14} className="inline mr-2" />Take Another Quiz
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function QuestionCard({ question, answer, onAnswer, difficultyLabel, difficultyColor }: {
  question: Question
  answer: string
  onAnswer: (a: string) => void
  difficultyLabel: (d: number) => string
  difficultyColor: (d: number) => string
}) {
  return (
    <div className="glass p-6 rounded-2xl">
      <div className="flex items-center gap-2 mb-4">
        <span className={`text-xs font-semibold ${difficultyColor(question.difficulty)}`}>{difficultyLabel(question.difficulty)}</span>
        <span className="text-xs text-slate-600">·</span>
        <span className="text-xs text-slate-500 capitalize">{question.qtype}</span>
        {question.source_location && <span className="text-xs text-slate-600 ml-auto">📍 {question.source_location}</span>}
      </div>

      <p className="text-base font-medium mb-6 leading-relaxed">{question.stem}</p>

      {question.qtype === 'mcq' && question.choices && (
        <div className="space-y-2">
          {question.choices.map(c => (
            <button key={c.id}
              className={`w-full text-left px-4 py-3 rounded-xl text-sm transition-all ${
                answer === c.id
                  ? 'border-indigo-500 bg-indigo-500/10 text-indigo-200'
                  : 'border-slate-700 hover:border-indigo-500/50 hover:bg-indigo-500/5 text-slate-300'
              }`}
              style={{ border: `1px solid ${answer === c.id ? '#6366f1' : 'rgba(100,116,139,0.3)'}` }}
              onClick={() => onAnswer(c.id)}>
              <span className="font-bold mr-3 text-slate-400">{c.id}.</span>{c.text}
            </button>
          ))}
        </div>
      )}

      {(question.qtype === 'short' || question.qtype === 'numerical') && (
        <textarea
          className="input-field w-full resize-none"
          rows={4}
          placeholder={question.qtype === 'numerical' ? 'Enter your numeric answer with units…' : 'Write your answer…'}
          value={answer}
          onChange={e => onAnswer(e.target.value)}
        />
      )}
    </div>
  )
}
