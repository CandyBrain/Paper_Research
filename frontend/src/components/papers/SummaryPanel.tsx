import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  summary: string | null
  index: number
}

export function SummaryPanel({ summary, index }: Props) {
  const summaryLoading = useAppStore((s) => s.summaryLoading)
  const isLoading = summaryLoading[index]
  const [isOpen, setIsOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="collapsible-body">
        <span className="spinner" /> AI 요약을 생성하고 있습니다...
      </div>
    )
  }

  if (!summary) {
    return null
  }

  return (
    <div className="cite-ref-section">
      <div
        className="cite-ref-header summary-header"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="cite-ref-header-icon">{isOpen ? '▼' : '▶'}</span>
        <span className="cite-ref-header-title">🤖 AI 요약 (Summary)</span>
      </div>

      {isOpen && (
        <div className="cite-ref-body">
          <div className="summary-content">{summary}</div>
        </div>
      )}
    </div>
  )
}
