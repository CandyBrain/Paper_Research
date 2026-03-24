import { useAppStore } from '../../store/useAppStore'

export function StatsBar() {
  const papers = useAppStore((s) => s.papers)
  const selectedIndices = useAppStore((s) => s.selectedIndices)

  const totalPapers = papers.length
  const selectedCount = selectedIndices.size
  const oaCount = papers.filter((p) => p.is_oa).length
  const sources = new Set(papers.map((p) => p.source)).size

  const stats = [
    { label: '전체 논문', value: totalPapers },
    { label: '선택됨', value: selectedCount },
    { label: 'Open Access', value: oaCount },
    { label: '데이터 소스', value: sources },
  ]

  return (
    <div className="stats-bar">
      {stats.map((s) => (
        <div key={s.label} className="stat-card">
          <div className="stat-value">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  )
}
