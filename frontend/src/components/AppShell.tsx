import type { ReactNode } from 'react'

import { useUI } from '../store/ui'

export function AppShell({ children }: { children: ReactNode }) {
  const { theme, toggleTheme } = useUI()
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200/60 bg-white/60 px-6 py-3 backdrop-blur dark:border-white/10 dark:bg-black/20">
        <div className="flex items-center gap-2">
          <span className="text-xl" aria-hidden>
            🪄
          </span>
          <h1 className="text-lg font-extrabold tracking-tight">מחולל טפסים</h1>
          <span className="field-label hidden sm:inline">· חנות מסמכים</span>
        </div>
        <button className="btn-ghost" onClick={toggleTheme}>
          {theme === 'dark' ? '☀️ בהיר' : '🌙 כהה'}
        </button>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-6">{children}</div>
    </div>
  )
}
