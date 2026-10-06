import type { Metadata } from 'next'
import './globals.css'
import { Toaster } from 'react-hot-toast'
import { Navbar } from '@/components/Navbar'

export const metadata: Metadata = {
  title: 'StudyCompanion AI — Personalized AI Tutor',
  description: 'Upload your lecture videos, PDFs, and slides. Get source-grounded answers, adaptive quizzes, and personalized study plans.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {/* Animated background blobs */}
        <div className="gradient-blob w-96 h-96 bg-indigo-600" style={{ top: '-5rem', left: '-5rem' }} />
        <div className="gradient-blob w-80 h-80 bg-violet-600" style={{ bottom: '10%', right: '-3rem', animationDelay: '-3s' }} />
        <div className="gradient-blob w-64 h-64 bg-cyan-600" style={{ top: '50%', left: '50%', animationDelay: '-6s' }} />
        <Navbar />
        <div style={{ paddingTop: '56px' }}>
          {children}
        </div>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#1e293b',
              color: '#f1f5f9',
              border: '1px solid rgba(99,102,241,0.25)',
              borderRadius: '10px',
            },
          }}
        />
      </body>
    </html>
  )
}
