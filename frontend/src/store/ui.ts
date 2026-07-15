import { create } from 'zustand'

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
  theme: Theme
  toggleTheme: () => void
  // sourceId -> the workspace doc_id currently open for it, so leaving a source and
  // coming back reuses the same run (its data + renders) instead of re-opening.
  openDocs: Record<number, string>
  setOpenDoc: (sourceId: number, docId: string) => void
}

export const useUI = create<UIState>((set, get) => ({
  theme: readTheme(),
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
  openDocs: {},
  setOpenDoc: (sourceId, docId) =>
    set((s) => ({ openDocs: { ...s.openDocs, [sourceId]: docId } })),
}))
