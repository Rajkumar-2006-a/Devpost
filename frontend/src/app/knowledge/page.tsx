'use client'
import { useState, useEffect, useCallback } from 'react'
import ReactFlow, {
  Node, Edge, Background, Controls, MiniMap,
  useNodesState, useEdgesState, MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { motion } from 'framer-motion'
import { Zap, Search } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || ''

const levelColors: Record<number, string> = {
  0: '#6366f1',  // topic
  1: '#8b5cf6',  // subtopic
  2: '#06b6d4',  // concept
}

const TopicNode = ({ data }: any) => (
  <div className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
    style={{
      background: `${levelColors[data.level]}22`,
      border: `1.5px solid ${levelColors[data.level]}66`,
      color: '#e2e8f0',
      maxWidth: 180,
      textAlign: 'center',
      boxShadow: `0 0 12px ${levelColors[data.level]}22`,
    }}>
    <div className="truncate">{data.label}</div>
    {data.description && <div className="text-xs text-slate-500 truncate mt-0.5">{data.description.slice(0,40)}</div>}
  </div>
)

const nodeTypes = { topicNode: TopicNode }

export default function KnowledgePage() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [studentId, setStudentId] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<any>(null)

  useEffect(() => {
    const sid = localStorage.getItem('student_id') || ''
    setStudentId(sid)
    if (sid) loadGraph(sid)
    else setLoading(false)
  }, [])

  const loadGraph = async (sid: string) => {
    try {
      const res = await fetch(`${API}/api/knowledge/graph?student_id=${sid}`)
      const data = await res.json()

      // Auto-layout: group by level in columns
      const levelGroups: Record<number, any[]> = { 0: [], 1: [], 2: [] }
      for (const node of data.nodes) {
        const level = node.data?.level ?? 0
        levelGroups[level] = levelGroups[level] || []
        levelGroups[level].push(node)
      }

      const positioned: Node[] = []
      const colX = [100, 400, 700]
      for (const [level, group] of Object.entries(levelGroups)) {
        const lvl = parseInt(level)
        group.forEach((n: any, i: number) => {
          positioned.push({
            ...n,
            position: { x: colX[lvl] ?? lvl * 300, y: i * 100 + 60 },
            type: 'topicNode',
          })
        })
      }

      const styledEdges: Edge[] = data.edges.map((e: any) => ({
        ...e,
        animated: true,
        style: { stroke: '#6366f180', strokeDasharray: '4 2' },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f180' },
        label: 'requires',
        labelStyle: { fill: '#64748b', fontSize: 10 },
      }))

      setNodes(positioned)
      setEdges(styledEdges)
    } catch {}
    setLoading(false)
  }

  const filteredNodes = search
    ? nodes.filter(n => (n.data.label as string).toLowerCase().includes(search.toLowerCase()))
    : nodes

  return (
    <div className="h-screen flex flex-col">
      <div className="px-6 py-4 border-b flex items-center gap-4" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}>
        <Zap className="text-indigo-400" size={20} />
        <h1 className="font-bold text-lg gradient-text">Knowledge Map</h1>
        <div className="ml-auto flex items-center gap-2">
          <Search size={14} className="text-slate-500" />
          <input className="input-field w-48 text-sm py-1.5" placeholder="Search topics…"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          {Object.entries({ 'Topic': 0, 'Subtopic': 1, 'Concept': 2 }).map(([label, level]) => (
            <span key={label} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ background: levelColors[level] }} />{label}
            </span>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-slate-500">Loading knowledge graph…</p>
          </div>
        </div>
      ) : nodes.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Zap className="mx-auto mb-4 text-slate-600" size={48} />
            <p className="text-slate-500">No knowledge graph yet.</p>
            <p className="text-slate-600 text-sm mt-1">Upload study materials to auto-generate the topic hierarchy.</p>
          </div>
        </div>
      ) : (
        <div className="flex-1" style={{ background: 'var(--bg-primary)' }}>
          <ReactFlow
            nodes={filteredNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            onNodeClick={(_, node) => setSelectedNode(node)}
            fitView
            attributionPosition="bottom-right">
            <Background color="#6366f120" gap={20} />
            <Controls style={{ background: '#1e293b', border: '1px solid rgba(99,102,241,0.2)' }} />
            <MiniMap style={{ background: '#0f172a', border: '1px solid rgba(99,102,241,0.2)' }}
              nodeColor={(n: any) => levelColors[n.data?.level ?? 0] + '88'} />
          </ReactFlow>
        </div>
      )}

      {/* Selected node detail panel */}
      {selectedNode && (
        <motion.div
          initial={{ y: 100 }} animate={{ y: 0 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 glass p-4 w-80 rounded-2xl"
          style={{ zIndex: 100 }}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{selectedNode.data.label}</p>
              <p className="text-xs text-slate-500 mt-0.5">{['Topic', 'Subtopic', 'Concept'][selectedNode.data.level]}</p>
              {selectedNode.data.description && (
                <p className="text-sm text-slate-400 mt-2">{selectedNode.data.description}</p>
              )}
            </div>
            <button className="text-slate-600 hover:text-slate-300 shrink-0" onClick={() => setSelectedNode(null)}>✕</button>
          </div>
        </motion.div>
      )}
    </div>
  )
}
