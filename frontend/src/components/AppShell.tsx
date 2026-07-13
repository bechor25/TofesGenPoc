import type { ReactNode } from 'react'

import { useUI, type View } from '../store/ui'

const NAV: { key: View; label: string; icon: string }[] = [
  { key: 'single', label: 'מסמך יחיד', icon: '📄' },
  { key: 'batch', label: 'אצווה', icon: '🗂️' },
  { key: 'archive', label: 'מאגר', icon: '🗄️' },
]

function NavButtons({ orientation }: { orientation: 'row' | 'col' }) {
  const { view, setView } = useUI()
  return (
    <>
      {NAV.map((n) => {
        const active = view === n.key
        return (
          <button
            key={n.key}
            onClick={() => setView(n.key)}
            className={
              'flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition ' +
              (orientation === 'col' ? 'w-full ' : '') +
              (active
                ? 'bg-accent/15 text-accent-700 dark:bg-accent/25 dark:text-white'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/5')
            }
          >
            <span aria-hidden>{n.icon}</span>
            {n.label}
          </button>
        )
      })}
    </>
  )
}

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
        </div>
        <button className="btn-ghost" onClick={toggleTheme}>
          {theme === 'dark' ? '☀️ בהיר' : '🌙 כהה'}
        </button>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-6">
        <nav className="mb-4 flex gap-1 sm:hidden">
          <NavButtons orientation="row" />
        </nav>
        <div className="flex gap-6">
          <nav className="sticky top-20 hidden h-fit w-48 shrink-0 flex-col gap-1 sm:flex">
            <NavButtons orientation="col" />
          </nav>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </div>
  )
}
