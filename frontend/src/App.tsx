import { useEffect, useRef } from 'react'
import { Header } from './components/layout/Header'
import { StepIndicator } from './components/layout/StepIndicator'
import { Sidebar } from './components/layout/Sidebar'
import { SearchPanel } from './components/search/SearchPanel'
import { StatsBar } from './components/stats/StatsBar'
import { PaperList } from './components/papers/PaperList'
import { PdfViewer } from './components/papers/PdfViewer'
import { ProjectWorkspace } from './components/projects/ProjectWorkspace'
import { ExportPanel } from './components/export/ExportPanel'
import { useAutosave } from './hooks/useAutosave'
import { useAppStore } from './store/useAppStore'

function Toast() {
  const msg = useAppStore((s) => s.toastMessage)
  if (!msg) return null
  return <div className="toast-notification">{msg}</div>
}

function App() {
  const papers = useAppStore((s) => s.papers)
  const isSearching = useAppStore((s) => s.isSearching)
  const searchMode = useAppStore((s) => s.searchMode)
  const viewerPaperIdx = useAppStore((s) => s.viewerPaperIdx)
  const activeView = useAppStore((s) => s.activeView)
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    useAppStore.getState().loadSettings()
    useAppStore.getState().loadSessions()
    useAppStore.getState().loadProjects()
    useAppStore.getState().loadCurrentWorkspace()
  }, [])

  useAutosave()

  return (
    <>
      {isSearching && (
        <div className="search-overlay">
          <div className="overlay-spinner" />
          <div className="overlay-text">
            {searchMode === 'ai' ? 'AI가 연구 주제를 분석하고 검색 중입니다...' : '논문을 검색하고 있습니다...'}
          </div>
          <div className="overlay-sub">선택된 데이터베이스에서 병렬로 검색 중</div>
        </div>
      )}
      <Header />
      <StepIndicator />
      <div className="app-layout">
        <Sidebar />
        {activeView === 'project' ? (
          <ProjectWorkspace />
        ) : (
          <>
            <main className={`main-content ${viewerPaperIdx !== null ? 'with-viewer' : ''}`}>
              <SearchPanel />
              {papers.length > 0 && (
                <>
                  <StatsBar />
                  <PaperList />
                  <ExportPanel />
                </>
              )}
            </main>
            <PdfViewer />
          </>
        )}
      </div>
      <Toast />
    </>
  )
}

export default App
