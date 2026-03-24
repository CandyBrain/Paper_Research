import type { AIAnalysis } from '../../types'

interface Props {
  analysis: AIAnalysis
}

export function AIAnalysisBox({ analysis }: Props) {
  return (
    <div className="ai-analysis-box">
      <h4>연구 분석</h4>
      <p>{analysis.research_summary}</p>

      {analysis.keywords.length > 0 && (
        <>
          <h4>키워드</h4>
          <div className="keyword-tags">
            {analysis.keywords.map((kw, i) => (
              <span key={i} className="keyword-tag">
                {kw}
              </span>
            ))}
          </div>
        </>
      )}

      {analysis.queries && analysis.queries.length > 0 && (
        <>
          <h4>생성된 검색 쿼리</h4>
          {analysis.queries.map((q, i) => (
            <div key={i} className="generated-query">
              <span style={{ color: '#e0e7ff' }}>
                {typeof q === 'string' ? q : q.query}
              </span>
              {typeof q !== 'string' && q.purpose && (
                <span style={{ color: '#a5b4fc', fontSize: '0.8rem', marginLeft: '0.5rem' }}>
                  — {q.purpose}
                </span>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  )
}
