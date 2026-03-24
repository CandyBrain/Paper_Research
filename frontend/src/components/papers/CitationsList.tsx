import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  index: number
}

export function CitationsList({ index }: Props) {
  const citationsData = useAppStore((s) => s.citationsData)
  const citationsLoading = useAppStore((s) => s.citationsLoading)
  const data = citationsData[index]
  const isLoading = citationsLoading[index]
  const [isOpen, setIsOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="collapsible-body">
        <span className="spinner" /> 인용 논문을 불러오는 중...
      </div>
    )
  }

  if (!data) {
    return null
  }

  if (data.error) {
    return (
      <div className="collapsible-body" style={{ color: '#f87171', fontSize: '0.82rem' }}>
        오류: {data.error}
      </div>
    )
  }

  const count = data.items?.length ?? 0

  return (
    <div className="cite-ref-section">
      <div
        className="cite-ref-header citation-header"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="cite-ref-header-icon">{isOpen ? '▼' : '▶'}</span>
        <span className="cite-ref-header-title">📚 인용 논문 (Citations)</span>
        <span className="cite-ref-header-count">
          {count === 0 ? '없음' : `${count}건 / 총 ${data.total}건`}
        </span>
      </div>

      {isOpen && (
        <div className="cite-ref-body">
          {count === 0 ? (
            <div style={{ color: '#94a3b8', fontSize: '0.82rem', padding: '0.5rem' }}>
              인용 논문이 없습니다.
            </div>
          ) : (
            data.items.map((item, i) => (
              <div key={i} className="cite-ref-card citation">
                <div className="cr-title">{i + 1}. {item.title}</div>
                <div className="cr-meta">
                  {item.authors?.join(', ')} {item.year && `(${item.year})`}
                  {item.journal && ` - ${item.journal}`}
                  {item.doi && (
                    <a
                      href={`https://doi.org/${item.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: '#818cf8', marginLeft: '0.5rem' }}
                    >
                      DOI
                    </a>
                  )}
                  {item.is_oa && <span className="badge badge-oa" style={{ marginLeft: '0.35rem' }}>OA</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
