import { useAppStore } from '../../store/useAppStore'
import { PaperCard } from './PaperCard'

export function PaperList() {
  const papers = useAppStore((s) => s.papers)
  const selectAll = useAppStore((s) => s.selectAll)
  const deselectAll = useAppStore((s) => s.deselectAll)
  const selectedIndices = useAppStore((s) => s.selectedIndices)

  return (
    <div>
      <div className="select-bar">
        <button className="btn-outline" onClick={selectAll}>
          전체 선택
        </button>
        <button className="btn-outline" onClick={deselectAll}>
          선택 해제
        </button>
        <span style={{ fontSize: '0.78rem', color: '#94a3b8', marginLeft: '0.5rem' }}>
          {selectedIndices.size} / {papers.length} 선택됨
        </span>
      </div>
      {papers.map((paper, idx) => (
        <PaperCard key={idx} paper={paper} index={idx} />
      ))}
    </div>
  )
}
