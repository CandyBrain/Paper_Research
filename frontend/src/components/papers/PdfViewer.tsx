import { useAppStore } from '../../store/useAppStore'

export function PdfViewer() {
  const viewerPaperIdx = useAppStore((s) => s.viewerPaperIdx)
  const closePdfViewer = useAppStore((s) => s.closePdfViewer)
  const papers = useAppStore((s) => s.papers)

  if (viewerPaperIdx === null) return null

  const paper = papers[viewerPaperIdx]
  if (!paper) return null

  const pdfUrl = `/api/papers/${viewerPaperIdx}/pdf`

  return (
    <div className="pdf-viewer-panel">
      <div className="pdf-viewer-header">
        <div className="pdf-viewer-title" title={paper.title}>
          {paper.title.length > 60 ? paper.title.slice(0, 57) + '...' : paper.title}
        </div>
        <button className="pdf-viewer-close" onClick={closePdfViewer}>
          &times;
        </button>
      </div>
      <iframe
        className="pdf-viewer-frame"
        src={pdfUrl}
        title={paper.title}
      />
    </div>
  )
}
