import { useAppStore } from '../../store/useAppStore'

export function ExportPanel() {
  const exportMarkdown = useAppStore((s) => s.exportMarkdown)
  const selectedIndices = useAppStore((s) => s.selectedIndices)
  const papers = useAppStore((s) => s.papers)

  const count = selectedIndices.size > 0 ? selectedIndices.size : papers.length

  return (
    <div className="export-panel">
      <button className="btn-primary" onClick={exportMarkdown}>
        Markdown으로 내보내기 ({count}편)
      </button>
    </div>
  )
}
