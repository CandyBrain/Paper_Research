import { useAppStore } from '../../store/useAppStore'

const steps = [
  { num: 1, label: '검색' },
  { num: 2, label: '결과' },
  { num: 3, label: '요약' },
  { num: 4, label: '다운로드' },
  { num: 5, label: '내보내기' },
]

export function StepIndicator() {
  const papers = useAppStore((s) => s.papers)
  const hasSummary = papers.some((p) => p.summary)
  const hasDl = Object.keys(useAppStore.getState().dlStatuses).length > 0

  let activeStep = 1
  if (papers.length > 0) activeStep = 2
  if (hasSummary) activeStep = 3
  if (hasDl) activeStep = 4

  return (
    <div className="step-indicator">
      {steps.map((s, i) => (
        <div key={s.num} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div className={`step-item ${s.num <= activeStep ? 'active' : ''}`}>
            <span className="step-num">{s.num}</span>
            <span>{s.label}</span>
          </div>
          {i < steps.length - 1 && <span className="step-arrow">&rarr;</span>}
        </div>
      ))}
    </div>
  )
}
