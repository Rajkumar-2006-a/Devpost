'use client'
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, BookOpen, AlertTriangle, ExternalLink, ChevronRight, RefreshCw, X } from 'lucide-react'
import { toast } from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || ''

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  refused?: boolean
  outsideKnowledge?: string
}

interface Citation {
  index: number
  unit_id: string
  source_id: string
  source_type: string
  location: string
  title: string
  snippet: string
  url: string
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const [studentId, setStudentId] = useState('')
  const messagesEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const sid = localStorage.getItem('student_id') || ''
    setStudentId(sid)
    if (!sid) toast.error('No profile found — go to Home to create one')
  }, [])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading || !studentId) return
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          message: input,
          session_id: sessionId,
        }),
      })
      const data = await res.json()
      setSessionId(data.session_id)

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.answer,
        citations: data.citations,
        refused: data.refused,
        outsideKnowledge: data.outside_knowledge,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (e) {
      toast.error('Chat error — check backend connection')
    } finally {
      setLoading(false)
    }
  }

  const requestOutsideKnowledge = async (originalQuery: string) => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          message: originalQuery,
          session_id: sessionId,
          request_outside_knowledge: true,
        }),
      })
      const data = await res.json()
      setMessages(prev => prev.map(m =>
        m.id === prev[prev.length - 1].id
          ? { ...m, outsideKnowledge: data.outside_knowledge }
          : m
      ))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex overflow-hidden">
      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="border-b px-6 py-4 flex items-center gap-3" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}>
          <BookOpen className="text-indigo-400" size={20} />
          <h1 className="font-bold text-lg gradient-text">Tutor Chat</h1>
          {sessionId && <span className="text-xs text-slate-500 font-mono ml-2">{sessionId.slice(0,8)}…</span>}
          <button className="ml-auto btn-secondary text-xs flex items-center gap-1"
            onClick={() => { setMessages([]); setSessionId(null) }}>
            <RefreshCw size={11} /> New session
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center mt-20">
              <BookOpen className="mx-auto mb-4 text-indigo-400/40" size={48} />
              <p className="text-slate-500">Ask anything about your study materials.</p>
              <p className="text-slate-600 text-sm mt-1">Answers will cite exact pages, slides, or timestamps.</p>
              <div className="flex flex-wrap justify-center gap-2 mt-6">
                {[
                  'Explain the main concept in simple terms',
                  'What are the key formulas covered?',
                  'Summarize the most important topics',
                ].map(s => (
                  <button key={s} className="btn-secondary text-xs" onClick={() => setInput(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          <AnimatePresence>
            {messages.map(msg => (
              <motion.div key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-tr-sm text-sm"
                    style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: 'white' }}>
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[85%] space-y-2">
                    {msg.refused && (
                      <div className="refusal-card p-3 flex items-start gap-2 text-sm">
                        <AlertTriangle size={14} className="text-red-400 mt-0.5 shrink-0" />
                        <span className="text-slate-300">This question isn't covered in your materials.</span>
                      </div>
                    )}

                    {!msg.refused && (
                      <div className="glass p-4 rounded-2xl rounded-tl-sm">
                        <div className="prose-dark text-sm">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}
                            components={{
                              // Intercept citation markers [N]
                              text: ({ children }) => {
                                const text = String(children)
                                const parts = text.split(/(\[\d+\])/)
                                return <>
                                  {parts.map((p, i) => {
                                    const match = p.match(/^\[(\d+)\]$/)
                                    if (match) {
                                      const idx = parseInt(match[1])
                                      const cit = msg.citations?.find(c => c.index === idx)
                                      return cit ? (
                                        <button key={i} className="citation-badge mx-0.5"
                                          onClick={() => setActiveCitation(cit)}>
                                          {idx}
                                        </button>
                                      ) : <span key={i}>{p}</span>
                                    }
                                    return <span key={i}>{p}</span>
                                  })}
                                </>
                              }
                            }}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>

                        {/* Citations list */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                            <p className="text-xs text-slate-500 mb-2">Sources:</p>
                            <div className="space-y-1">
                              {msg.citations.map(c => (
                                <button key={c.unit_id} className="flex items-center gap-2 text-xs text-slate-400 hover:text-indigo-300 transition-colors w-full text-left"
                                  onClick={() => setActiveCitation(c)}>
                                  <span className="citation-badge shrink-0">{c.index}</span>
                                  <span className="truncate">{c.title} — {c.snippet.slice(0,60)}…</span>
                                  <ExternalLink size={10} className="shrink-0 ml-auto" />
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Outside knowledge section */}
                    {msg.outsideKnowledge && (
                      <div className="glass-sm p-3 rounded-xl border-l-2" style={{ borderLeftColor: '#f59e0b' }}>
                        <p className="text-xs font-semibold text-amber-400 mb-1">⚠️ Outside Your Materials</p>
                        <div className="prose-dark text-xs">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.outsideKnowledge}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <div className="flex justify-start">
              <div className="glass px-4 py-3 rounded-2xl rounded-tl-sm">
                <div className="flex gap-1">
                  {[0,1,2].map(i => (
                    <span key={i} className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
                      style={{ animationDelay: `${i*0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}>
          <div className="flex gap-2">
            <textarea
              className="input-field flex-1 resize-none"
              rows={2}
              placeholder="Ask about your study materials..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
            />
            <button className="btn-primary px-5 self-end" onClick={sendMessage} disabled={loading || !input.trim()}>
              <Send size={16} />
            </button>
          </div>
          <p className="text-xs text-slate-600 mt-1.5">Enter to send · Shift+Enter for new line</p>
        </div>
      </div>

      {/* Citation side panel */}
      <AnimatePresence>
        {activeCitation && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 380, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="border-l flex flex-col overflow-hidden"
            style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}>
            <div className="p-4 flex items-center justify-between border-b" style={{ borderColor: 'var(--border)' }}>
              <div>
                <p className="font-semibold text-sm">Source [{activeCitation.index}]</p>
                <p className="text-xs text-slate-500">{activeCitation.title}</p>
              </div>
              <button className="text-slate-500 hover:text-white" onClick={() => setActiveCitation(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 p-4 overflow-y-auto">
              <div className="glass-sm p-3 rounded-lg mb-4">
                <p className="text-xs text-slate-500 mb-2">Excerpt</p>
                <p className="text-sm text-slate-300">{activeCitation.snippet}</p>
              </div>
              <a
                href={activeCitation.url}
                className="btn-primary w-full text-center flex items-center justify-center gap-2 text-sm"
                target="_blank">
                <ExternalLink size={13} />
                Open in Viewer
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
