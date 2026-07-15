import { AppShell } from './components/AppShell'
import { LogsPanel } from './components/LogsPanel'
import { StoreView } from './views/StoreView'

export default function App() {
  return (
    <AppShell>
      <StoreView />
      <LogsPanel />
    </AppShell>
  )
}
