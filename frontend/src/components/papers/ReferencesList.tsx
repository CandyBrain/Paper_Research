import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  index: number
}

export function ReferencesList({ index }: Props) {
  const referencesData = useAppStore((s) => s.referencesData)
  const referencesLoading = useAppStore((s) => s.referencesLoading)
  const data = referencesData[index]
  const isLoading = referencesLoading[index]
  const [isOpen, setIsOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="collapsible-body">
        <span className="spinner" /> 참고문헌을 불러오는 중...
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
        className="cite-ref-header reference-header"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="cite-ref-header-icon">{isOpen ? '▼' : '▶'}</span>
        <span className="cite-ref-header-title">📖 참고문헌 (References)</span>
        <span className="cite-ref-header-count">
          {count === 0 ? '없음' : `${count}건 / 총 ${data.total}건`}
        </span>
      </div>

      {isOpen && (
        <div className="cite-ref-body">
          {count === 0 ? (
            <div style={{ color: '#94a3b8', fontSize: '0.82rem', padding: '0.5rem' }}>
              참고문헌이 없습니다.
            </div>
          ) : (
            data.items.map((item, i) => (
              <div key={i} className="cite-ref-card reference">
                <div className="cr-title">{i + 1}. {item.title}</div>
                <div className="cr-meta">
                  {item.authors?.join(', ')} {item.year && `(${item.year})`}
                  {item.journal && ` - ${item.journal}`}
                  {item.doi && (
                    <a
                      href={`https://doi.org/${item.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: '#fb923c', marginLeft: '0.5rem' }}
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
