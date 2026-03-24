import { useState, type RefObject } from 'react'
import type { Paper } from '../../types'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  index: number
  paper: Paper
  fileInputRef: RefObject<HTMLInputElement | null>
  onAbstractToggle: () => void
  onSummaryToggle: () => void
  onCitationsToggle: () => void
  onReferencesToggle: () => void
}

export function ActionButtons({
  index,
  paper,
  fileInputRef,
  onAbstractToggle,
  onSummaryToggle,
  onCitationsToggle,
  onReferencesToggle,
}: Props) {
  const openPdfViewer = useAppStore((s) => s.openPdfViewer)
  const projectsList = useAppStore((s) => s.projectsList)
  const addPapersToProject = useAppStore((s) => s.addPapersToProject)
  const downloadPaper = useAppStore((s) => s.downloadPaper)
  const summarizePaper = useAppStore((s) => s.summarizePaper)
  const fetchCitations = useAppStore((s) => s.fetchCitations)
  const fetchReferences = useAppStore((s) => s.fetchReferences)
  const refreshPaper = useAppStore((s) => s.refreshPaper)
  const detachPdf = useAppStore((s) => s.detachPdf)
  const dlStatuses = useAppStore((s) => s.dlStatuses)
  const manualPdfPaths = useAppStore((s) => s.manualPdfPaths)
  const summaryLang = useAppStore((s) => s.summaryLang)
  const summaryLoading = useAppStore((s) => s.summaryLoading)
  const citationsLoading = useAppStore((s) => s.citationsLoading)
  const referencesLoading = useAppStore((s) => s.referencesLoading)
  const refreshLoading = useAppStore((s) => s.refreshLoading)

  const isDownloading = dlStatuses[index]?.loading
  const hasPdfLinked = !!manualPdfPaths[index] || (dlStatuses[index]?.status === 'success')
  const isSummarizing = summaryLoading[index]
  const isCitLoading = citationsLoading[index]
  const isRefLoading = referencesLoading[index]
  const isRefreshing = refreshLoading[index]
  const [showProjectMenu, setShowProjectMenu] = useState(false)

  return (
    <div className="action-buttons">
      <button
        className="action-btn"
        disabled={isDownloading}
        onClick={() => downloadPaper(index)}
      >
        {isDownloading ? <><span className="spinner" /> 다운로드 중</> : '다운로드'}
      </button>
      {hasPdfLinked && (
        <button
          className="action-btn"
          onClick={() => openPdfViewer(index)}
          title="다운로드된 PDF 보기"
        >
          논문보기
        </button>
      )}
      <select
        className="lang-select"
        value={summaryLang}
        onChange={(e) => useAppStore.setState({ summaryLang: e.target.value })}
        style={{
          height: '38px',
          fontSize: '0.75rem',
          padding: '0 0.3rem',
          borderRadius: '6px',
          border: '1px solid #4338ca',
          background: '#312e81',
          color: '#e0e7ff',
          cursor: 'pointer',
          minWidth: '55px',
        }}
      >
        <option value="한국어">한국어</option>
        <option value="English">EN</option>
        <option value="日本語">日本語</option>
        <option value="中文">中文</option>
      </select>
      <button
        className="action-btn"
        disabled={isSummarizing}
        onClick={() => {
          summarizePaper(index)
          onSummaryToggle()
        }}
      >
        {isSummarizing ? <><span className="spinner" /> 요약 중</> : 'AI 요약'}
      </button>
      <button
        className="action-btn"
        disabled={isCitLoading}
        onClick={() => {
          fetchCitations(index, 10)
          onCitationsToggle()
        }}
      >
        {isCitLoading ? <><span className="spinner" /> 로딩</> : '인용'}
      </button>
      <button
        className="action-btn"
        disabled={isRefLoading}
        onClick={() => {
          fetchReferences(index, 10)
          onReferencesToggle()
        }}
      >
        {isRefLoading ? <><span className="spinner" /> 로딩</> : '참고문헌'}
      </button>
      {hasPdfLinked ? (
        <button className="action-btn secondary" onClick={() => detachPdf(index)}>
          PDF 해제
        </button>
      ) : (
        <button className="action-btn secondary" onClick={() => fileInputRef.current?.click()}>
          PDF 첨부
        </button>
      )}
      {paper.abstract && (
        <button className="action-btn secondary" onClick={onAbstractToggle}>
          초록
        </button>
      )}
      <button
        className="action-btn secondary"
        disabled={isRefreshing}
        onClick={() => refreshPaper(index)}
        title="논문 정보 재검색 (DOI, 초록 등 업데이트)"
      >
        {isRefreshing ? <><span className="spinner" /> 검색 중</> : '재검색'}
      </button>
      {projectsList.length > 0 && (
        <div style={{ position: 'relative', display: 'inline-block' }}>
          <button
            className="action-btn secondary"
            onClick={() => setShowProjectMenu(!showProjectMenu)}
          >
            프로젝트 추가
          </button>
          {showProjectMenu && (
            <div className="project-add-menu">
              {projectsList.map((proj) => (
                <button
                  key={proj.name}
                  className="project-add-menu-item"
                  onClick={() => {
                    addPapersToProject(proj.name, [index])
                    setShowProjectMenu(false)
                  }}
                >
                  {proj.name} ({proj.paper_count}편)
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
