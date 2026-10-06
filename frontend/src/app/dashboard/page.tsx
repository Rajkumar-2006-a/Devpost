'use client'
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, Target, Clock, TrendingUp, BookOpen, Zap } from 'lucide-react'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts'

const API = process.env.NEXT_PUBLIC_API_URL || ''

export default function DashboardPage() {
  const [studentId, setStudentId] = useState('')
  const [model, setModel] = useState<any>(null)
  const [summary, setSummary] = useState<any>(null)
  const [schedule, setSchedule] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const sid = localStorage.getItem('student_id') || ''
    setStudentId(sid)
    if (sid) loadData(sid)
  }, [])

  const loadData = async (sid: string) => {
    try {
      const [modelRes, summaryRes, scheduleRes, histRes] = await Promise.all([
        fetch(`${API}/api/learner/${sid}/model`),
        fetch(`${API}/api/learner/${sid}/summary`),
        fetch(`${API}/api/learner/${sid}/schedule`),
        fetch(`${API}/api/assessment/history?student_id=${sid}`),
      ])
      setModel(await modelRes.json())
      setSummary(await summaryRes.json())
      setSchedule(await scheduleRes.json())
      setHistory(await histRes.json())
    } catch {}
    setLoading(false)
  }

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-500">Loading dashboard…</p>
      </div>
    </div>
  )

  const concepts = model?.concepts || []
  const avgMastery = summary?.average_mastery || 0

  // Prepare chart data
  const masteryData = concepts.slice(0, 12).map((c: any) => ({
    name: c.concept_id.slice(0, 12),
    mastery: Math.round(c.mastery_prob * 100),
    retention: Math.round(c.retention * 100),
  }))

  const radarData = concepts.slice(0, 8).map((c: any) => ({
    concept: c.concept_id.slice(0, 10),
    mastery: Math.round(c.mastery_prob * 100),
  }))

  const statsCards = [
    { label: 'Avg Mastery', value: `${Math.round(avgMastery * 100)}%`, icon: Target, color: '#6366f1' },
    { label: 'Concepts Tracked', value: concepts.length, icon: BookOpen, color: '#8b5cf6' },
    { label: 'Due for Review', value: schedule?.due_now?.length || 0, icon: Clock, color: '#f59e0b' },
    { label: 'Assessments', value: history.length, icon: BarChart3, color: '#10b981' },
  ]

  return (
    <div className="min-h-screen px-6 py-10 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <BarChart3 className="text-indigo-400" size={24} />
        <h1 className="text-2xl font-bold gradient-text">Learning Dashboard</h1>
      </div>
      {summary && <p className="text-slate-500 mb-8">Welcome back, <span className="text-slate-200">{summary.name}</span></p>}

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statsCards.map(({ label, value, icon: Icon, color }) => (
          <motion.div key={label} className="glass p-5"
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
              <Icon size={16} style={{ color }} />
            </div>
            <div className="text-3xl font-extrabold" style={{ color }}>{value}</div>
          </motion.div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Mastery Bar Chart */}
        <div className="glass p-6">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-wider flex items-center gap-2">
            <TrendingUp size={14} /> Concept Mastery
          </h2>
          {masteryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={masteryData} margin={{ top: 0, right: 0, bottom: 20, left: -20 }}>
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} angle={-30} textAnchor="end" />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, color: '#f1f5f9' }}
                  formatter={(v: number) => [`${v}%`, 'Mastery']}
                />
                <Bar dataKey="mastery" radius={[4, 4, 0, 0]}>
                  {masteryData.map((_: any, i: number) => (
                    <Cell key={i} fill={`hsl(${240 + i * 10}, 70%, ${45 + masteryData[i].mastery * 0.3}%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-slate-600">No mastery data yet. Take a quiz!</div>
          )}
        </div>

        {/* Radar Chart */}
        <div className="glass p-6">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-wider flex items-center gap-2">
            <Zap size={14} /> Knowledge Radar
          </h2>
          {radarData.length > 2 ? (
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(99,102,241,0.2)" />
                <PolarAngleAxis dataKey="concept" tick={{ fill: '#64748b', fontSize: 10 }} />
                <Radar name="Mastery" dataKey="mastery" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-slate-600">Need ≥3 concepts for radar. Complete assessments!</div>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Review schedule */}
        <div className="glass p-6">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-wider flex items-center gap-2">
            <Clock size={14} /> Review Schedule
          </h2>
          {schedule?.due_now?.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-amber-400 font-semibold mb-2">⏰ Due Now ({schedule.due_now.length})</p>
              {schedule.due_now.slice(0, 5).map((item: any) => (
                <div key={item.concept_id} className="flex items-center justify-between py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                  <span className="text-sm text-slate-300 font-mono">{item.concept_id.slice(0, 20)}</span>
                  <span className="text-xs text-amber-400">{Math.round(item.mastery * 100)}% mastery</span>
                </div>
              ))}
            </div>
          )}
          {schedule?.upcoming?.length > 0 ? (
            schedule.upcoming.slice(0, 5).map((item: any) => (
              <div key={item.concept_id} className="flex items-center justify-between py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                <span className="text-sm text-slate-300 font-mono">{item.concept_id.slice(0, 20)}</span>
                <span className="text-xs text-slate-500">in {item.days_until}d</span>
              </div>
            ))
          ) : <p className="text-slate-600 text-sm">Complete quizzes to build a review schedule.</p>}
        </div>

        {/* Assessment history */}
        <div className="glass p-6">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-wider flex items-center gap-2">
            <BarChart3 size={14} /> Recent Assessments
          </h2>
          {history.length > 0 ? history.slice(0, 6).map((a: any) => (
            <div key={a.id} className="flex items-center justify-between py-2 border-b" style={{ borderColor: 'var(--border)' }}>
              <div>
                <p className="text-sm text-slate-300">{a.title}</p>
                <p className="text-xs text-slate-600">{new Date(a.created_at).toLocaleDateString()}</p>
              </div>
              {a.score != null && (
                <span className={`text-sm font-bold ${a.score >= 0.7 ? 'text-emerald-400' : a.score >= 0.5 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {Math.round(a.score * 100)}%
                </span>
              )}
            </div>
          )) : <p className="text-slate-600 text-sm">No assessments yet.</p>}
        </div>
      </div>
    </div>
  )
}
