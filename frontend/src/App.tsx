import { AppShell } from './components/AppShell'
import { LogsPanel } from './components/LogsPanel'
import { useUI } from './store/ui'
import { ArchiveView } from './views/ArchiveView'
import { BatchView } from './views/BatchView'
import { SingleView } from './views/SingleView'

export default function App() {
  const view = useUI((s) => s.view)
  // Keep every view MOUNTED and just toggle visibility, so switching to the archive
  // mid-run doesn't unmount SingleView and lose its session (doc, live job, render
  // queue keep going in the background). The server-side workspace + job persist too.
  return (
    <AppShell>
      <div className={view === 'single' ? '' : 'hidden'}>
        <SingleView />
      </div>
      <div className={view === 'batch' ? '' : 'hidden'}>
        <BatchView />
      </div>
      <div className={view === 'archive' ? '' : 'hidden'}>
        <ArchiveView />
      </div>
      <LogsPanel />
    </AppShell>
  )
}
