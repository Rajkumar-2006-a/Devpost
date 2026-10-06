'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BookOpen, Brain, BarChart3, Upload, Zap } from 'lucide-react'

const NAV_ITEMS = [
  { href: '/', label: 'Upload', icon: Upload },
  { href: '/chat', label: 'Tutor', icon: BookOpen },
  { href: '/knowledge', label: 'Knowledge Map', icon: Zap },
  { href: '/assessment', label: 'Quiz', icon: Brain },
  { href: '/dashboard', label: 'Dashboard', icon: BarChart3 },
]

export function Navbar() {
  const pathname = usePathname()
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b px-6 py-3 flex items-center gap-6"
      style={{ background: 'rgba(2,6,23,0.85)', backdropFilter: 'blur(12px)', borderColor: 'rgba(99,102,241,0.15)' }}>
      <Link href="/" className="flex items-center gap-2 mr-4">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center">
          <BookOpen size={14} className="text-white" />
        </div>
        <span className="font-bold text-sm gradient-text hidden sm:block">StudyCompanion AI</span>
      </Link>
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href
        return (
          <Link key={href} href={href}
            className={`flex items-center gap-1.5 text-sm transition-colors px-3 py-1.5 rounded-lg ${
              active ? 'text-indigo-300 bg-indigo-500/10' : 'text-slate-500 hover:text-slate-200'
            }`}>
            <Icon size={14} />{label}
          </Link>
        )
      })}
    </nav>
  )
}
