import '@fontsource/heebo/300.css'
import '@fontsource/heebo/400.css'
import '@fontsource/heebo/600.css'
import '@fontsource/heebo/800.css'
import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './App'
import { initTheme } from './store/ui'

initTheme()

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
})

const root = document.getElementById('root')
if (root) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  )
}
