import { AppShell } from './components/AppShell'
import { LogsPanel } from './components/LogsPanel'
import { useUI } from './store/ui'
import { ArchiveView } from './views/ArchiveView'
import { BatchView } from './views/BatchView'
import { SingleView } from './views/SingleView'

export default function App() {
  const view = useUI((s) => s.view)
  return (
    <AppShell>
      {view === 'single' && <SingleView />}
      {view === 'batch' && <BatchView />}
      {view === 'archive' && <ArchiveView />}
      <LogsPanel />
    </AppShell>
  )
}
