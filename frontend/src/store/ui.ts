import { create } from 'zustand'

export type View = 'single' | 'batch' | 'archive'
type Theme = 'dark' | 'light'

const THEME_KEY = 'tofes-theme'

function readTheme(): Theme {
  try {
    return (localStorage.getItem(THEME_KEY) as Theme | null) ?? 'dark'
  } catch {
    return 'dark'
  }
}

function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

/** Apply the persisted theme on boot (called from main.tsx before render). */
export function initTheme(): void {
  applyTheme(readTheme())
}

interface UIState {
  view: View
  theme: Theme
  setView: (v: View) => void
  toggleTheme: () => void
}

export const useUI = create<UIState>((set, get) => ({
  view: 'single',
  theme: readTheme(),
  setView: (v) => set({ view: v }),
  toggleTheme: () => {
    const theme: Theme = get().theme === 'dark' ? 'light' : 'dark'
    applyTheme(theme)
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      /* storage unavailable — keep in-memory only */
    }
    set({ theme })
  },
}))
