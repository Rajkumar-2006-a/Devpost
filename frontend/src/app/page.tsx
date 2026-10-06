'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { BookOpen, Video, FileText, Presentation, Brain, Zap, BarChart3, Upload, ArrowRight, CheckCircle } from 'lucide-react'
import { toast } from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || ''

export default function HomePage() {
  const [studentId, setStudentId] = useState('')
  const [studentName, setStudentName] = useState('')
  const [creating, setCreating] = useState(false)
  const [sources, setSources] = useState<any[]>([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    const sid = localStorage.getItem('student_id')
    if (sid) {
      setStudentId(sid)
      fetchSources(sid)
    }
  }, [])

  const createStudent = async () => {
    if (!studentName.trim()) return toast.error('Enter your name')
    setCreating(true)
    try {
      const res = await fetch(`${API}/api/learner/onboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: studentName }),
      })
      const data = await res.json()
      localStorage.setItem('student_id', data.student_id)
      localStorage.setItem('student_name', studentName)
      setStudentId(data.student_id)
      toast.success(`Welcome, ${studentName}! 🎉`)
    } catch (e) {
      toast.error('Could not create profile')
    } finally {
      setCreating(false)
    }
  }

  const fetchSources = async (sid: string) => {
    try {
      const res = await fetch(`${API}/api/ingest/sources?student_id=${sid}`)
      const data = await res.json()
      setSources(data)
    } catch {}
  }

  const handleUpload = async (file: File) => {
    if (!studentId) return toast.error('Create your profile first')
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('student_id', studentId)
    try {
      const res = await fetch(`${API}/api/ingest/upload`, { method: 'POST', body: formData })
      const data = await res.json()
      toast.success('Ingestion started! Processing in background...')
      // Poll status
      pollStatus(data.source_id)
      setSources(prev => [{ ...data, status: 'processing' }, ...prev])
    } catch (e) {
      toast.error('Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const pollStatus = (sourceId: string) => {
    const es = new EventSource(`${API}/api/ingest/status/${sourceId}`)
    es.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.status === 'done') {
        toast.success(`✓ ${msg.message}`)
        es.close()
        fetchSources(studentId)
      } else if (msg.status === 'error') {
        toast.error(`Ingestion failed: ${msg.message}`)
        es.close()
      }
    }
    es.onerror = () => es.close()
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }

  const statusColor = (s: string) => ({
    ready: 'text-emerald-400',
    processing: 'text-yellow-400 animate-pulse',
    error: 'text-red-400',
    pending: 'text-slate-400',
  }[s] || 'text-slate-400')

  const typeIcon = (t: string) => ({
    pdf: '📄',
    pptx: '📊',
    video: '🎥',
  }[t] || '📁')

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <header className="px-8 pt-16 pb-12 text-center max-w-4xl mx-auto w-full">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-6"
            style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)', color: '#818cf8' }}>
            <Zap size={12} /> Hackathon 2026 · Track D: Personalized Tutoring
          </div>
          <h1 className="text-5xl font-extrabold mb-4 leading-tight">
            <span className="gradient-text">StudyCompanion AI</span>
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto">
            Upload your lectures, textbooks, and slides. Get <strong className="text-slate-200">source-grounded answers</strong>,
            adaptive quizzes, and a personalized learning path — all backed by your own materials.
          </p>
        </motion.div>

        {/* Feature pills */}
        <motion.div className="flex flex-wrap justify-center gap-3 mt-8"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          {[
            { icon: BookOpen, label: 'Grounded Chat', color: '#6366f1' },
            { icon: Brain, label: 'Bayesian Mastery', color: '#8b5cf6' },
            { icon: BarChart3, label: 'Adaptive Assessment', color: '#06b6d4' },
            { icon: Zap, label: 'Spaced Repetition', color: '#10b981' },
          ].map(({ icon: Icon, label, color }) => (
            <div key={label} className="glass-sm px-4 py-2 flex items-center gap-2 text-sm">
              <Icon size={14} style={{ color }} />
              <span className="text-slate-300">{label}</span>
            </div>
          ))}
        </motion.div>
      </header>

      <main className="flex-1 px-8 max-w-5xl mx-auto w-full pb-16">
        {/* Profile creation */}
        {!studentId ? (
          <motion.div className="glass p-8 mb-8 text-center max-w-md mx-auto"
            initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3 }}>
            <Brain className="mx-auto mb-4 text-indigo-400" size={40} />
            <h2 className="text-xl font-bold mb-2">Create Your Learning Profile</h2>
            <p className="text-slate-400 text-sm mb-6">Your mastery state, quiz history, and personalization data will be saved.</p>
            <input
              className="input-field mb-4"
              placeholder="Your name"
              value={studentName}
              onChange={e => setStudentName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && createStudent()}
            />
            <button className="btn-primary w-full" onClick={createStudent} disabled={creating}>
              {creating ? 'Creating...' : 'Get Started →'}
            </button>
          </motion.div>
        ) : (
          <motion.div className="mb-6 flex items-center justify-between glass p-4 rounded-xl"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center text-white font-bold">
                {(localStorage.getItem('student_name') || 'S')[0].toUpperCase()}
              </div>
              <div>
                <div className="font-semibold">{localStorage.getItem('student_name')}</div>
                <div className="text-xs text-slate-500 font-mono">{studentId.slice(0,8)}…</div>
              </div>
            </div>
            <div className="flex gap-2">
              {[
                { href: '/chat', label: 'Tutor Chat', icon: BookOpen },
                { href: '/assessment', label: 'Quiz', icon: Brain },
                { href: '/dashboard', label: 'Dashboard', icon: BarChart3 },
                { href: '/knowledge', label: 'Knowledge Map', icon: Zap },
              ].map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href} className="btn-secondary text-sm flex items-center gap-1.5">
                  <Icon size={13} />{label}
                </Link>
              ))}
            </div>
          </motion.div>
        )}

        {/* Upload zone */}
        {studentId && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <div
              className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-200 cursor-pointer ${
                dragging ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-700 hover:border-indigo-500/50 hover:bg-indigo-500/5'
              }`}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <input id="file-input" type="file" className="hidden" accept=".pdf,.pptx,.ppt,.mp4,.mov"
                onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
              <Upload className="mx-auto mb-4 text-indigo-400" size={40} />
              <p className="text-lg font-semibold text-slate-200 mb-2">
                {uploading ? 'Uploading...' : 'Drop your study materials here'}
              </p>
              <p className="text-sm text-slate-500">PDF textbooks · PPTX slides · MP4 lecture videos</p>
              <div className="flex justify-center gap-3 mt-4">
                {[
                  { label: 'PDF', cls: 'badge-pdf', icon: FileText },
                  { label: 'PPTX', cls: 'badge-pptx', icon: Presentation },
                  { label: 'Video', cls: 'badge-video', icon: Video },
                ].map(({ label, cls, icon: Icon }) => (
                  <span key={label} className={`${cls} px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1`}>
                    <Icon size={11} />{label}
                  </span>
                ))}
              </div>
            </div>

            {/* YouTube ingestion */}
            <YoutubeIngester studentId={studentId} onDone={() => fetchSources(studentId)} />

            {/* Sources list */}
            {sources.length > 0 && (
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Ingested Sources</h3>
                <div className="space-y-2">
                  {sources.map(src => (
                    <div key={src.id} className="glass-sm p-4 flex items-center gap-4">
                      <span className="text-2xl">{typeIcon(src.source_type)}</span>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-slate-200 truncate">{src.title}</div>
                        <div className="text-xs text-slate-500">
                          {src.total_pages ? `${src.total_pages} pages` : ''}
                          {src.duration_sec ? `${Math.round(src.duration_sec / 60)} min` : ''}
                        </div>
                      </div>
                      <span className={`text-xs font-semibold ${statusColor(src.status)}`}>
                        {src.status === 'ready' && <CheckCircle size={12} className="inline mr-1" />}
                        {src.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </main>
    </div>
  )
}

function YoutubeIngester({ studentId, onDone }: { studentId: string; onDone: () => void }) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const API = process.env.NEXT_PUBLIC_API_URL || ''

  const ingest = async () => {
    if (!url.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/ingest/youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, student_id: studentId }),
      })
      const data = await res.json()
      toast.success('YouTube ingestion started!')
      setUrl('')
      onDone()
    } catch {
      toast.error('Failed to start YouTube ingestion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-4 flex gap-2">
      <input
        className="input-field flex-1"
        placeholder="Or paste a YouTube lecture URL..."
        value={url}
        onChange={e => setUrl(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && ingest()}
      />
      <button className="btn-secondary px-6" onClick={ingest} disabled={loading || !url}>
        {loading ? '...' : <><Video size={14} className="inline mr-1" />Ingest</>}
      </button>
    </div>
  )
}
