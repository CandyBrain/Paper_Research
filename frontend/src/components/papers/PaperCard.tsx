import { useState, useRef, useMemo } from 'react'
import type { Paper } from '../../types'
import { useAppStore } from '../../store/useAppStore'
import { ActionButtons } from './ActionButtons'
import { AbstractPanel } from './AbstractPanel'
import { SummaryPanel } from './SummaryPanel'
import { CitationsList } from './CitationsList'
import { ReferencesList } from './ReferencesList'

interface Props {
  paper: Paper
  index: number
}

export function PaperCard({ paper, index }: Props) {
  const selectedIndices = useAppStore((s) => s.selectedIndices)
  const toggleSelect = useAppStore((s) => s.toggleSelect)
  const dlStatuses = useAppStore((s) => s.dlStatuses)
  const manualPdfPaths = useAppStore((s) => s.manualPdfPaths)
  const citationsData = useAppStore((s) => s.citationsData)
  const referencesData = useAppStore((s) => s.referencesData)
  const aiAnalysis = useAppStore((s) => s.aiAnalysis)
  const isSelected = selectedIndices.has(index)
  const hasPdfLinked = !!manualPdfPaths[index] || (dlStatuses[index]?.status === 'success')

  // Find relevance ranking for this paper
  const ranking = useMemo(() => {
    const rankings = aiAnalysis?.relevance_rankings as { index: number; score: number; reason: string }[] | undefined
    return rankings?.find((r) => r.index === index)
  }, [aiAnalysis, index])

  const hasCitations = !!citationsData[index]
  const hasReferences = !!referencesData[index]

  const [abstractOpen, setAbstractOpen] = useState(false)
  const [isAttaching, setIsAttaching] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const dlStatus = dlStatuses[index]
  const authors = paper.authors?.join(', ') || '저자 미상'
  const yearStr = paper.year ? `(${paper.year})` : ''

  return (
    <div className="paper-card">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <input
          type="checkbox"
          className="paper-checkbox"
          checked={isSelected}
          onChange={() => toggleSelect(index)}
          style={{ marginTop: '0.2rem' }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="paper-title">{paper.title}</div>
          <div className="paper-meta">
            {authors} {yearStr}
            {paper.journal && ` - ${paper.journal}`}
          </div>
          <div>
            <span className={`badge ${paper.is_oa ? 'badge-oa' : 'badge-closed'}`}>
              {paper.is_oa ? 'Open Access' : 'Closed'}
            </span>
            <span className="badge badge-source">{paper.source}</span>
            {paper.doi && (
              <a
                href={`https://doi.org/${paper.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: '0.72rem', color: '#6366f1', marginLeft: '0.35rem' }}
              >
                DOI
              </a>
            )}
            {ranking && (
              <span
                className="badge"
                style={{
                  marginLeft: '0.35rem',
                  background: ranking.score >= 5 ? '#065f46' : ranking.score >= 4 ? '#1e40af' : '#4338ca',
                  color: ranking.score >= 5 ? '#a7f3d0' : '#c7d2fe',
                }}
                title={ranking.reason}
              >
                {'★'.repeat(ranking.score)} 관련도 {ranking.score}/5
              </span>
            )}
          </div>
          {ranking?.reason && (
            <div style={{ fontSize: '0.73rem', color: '#a5b4fc', marginTop: '0.15rem', fontStyle: 'italic' }}>
              {ranking.reason}
            </div>
          )}

          {hasPdfLinked && (
            <div className="pdf-bar" style={{ background: '#065f46', color: '#a7f3d0', marginTop: '0.25rem' }}>
              📄 PDF 연결됨{manualPdfPaths[index] ? `: ${manualPdfPaths[index].split(/[/\\]/).pop()}` : ''}
            </div>
          )}

          {dlStatus && dlStatus.loading && (
            <div className="pdf-bar" style={{ marginTop: '0.25rem' }}>
              <span className="spinner" /> 다운로드 중...
            </div>
          )}

          {dlStatus && !dlStatus.loading && dlStatus.status !== 'success' && !hasPdfLinked && (
            <div style={{ marginTop: '0.25rem' }}>
              <div className="pdf-bar" style={{ background: '#7f1d1d', color: '#fca5a5' }}>
                ❌ 자동 다운로드 실패
              </div>
              {dlStatus.status?.includes('프록시 로그인') && (() => {
                const match = dlStatus.status.match(/https?:\/\/[^\s]+/)
                const loginUrl = match ? match[0] : ''
                return loginUrl ? (
                  <div style={{ marginTop: '0.35rem', padding: '0.5rem 0.75rem', background: '#312e81', borderRadius: '8px', border: '1px solid #4338ca' }}>
                    <div style={{ fontSize: '0.78rem', color: '#fbbf24', marginBottom: '0.3rem', fontWeight: 500 }}>
                      🔑 대학 프록시 로그인이 필요합니다
                    </div>
                    <a
                      href={loginUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ fontSize: '0.78rem', color: '#93c5fd', textDecoration: 'underline', wordBreak: 'break-all' }}
                    >
                      로그인 페이지 열기
                    </a>
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                      로그인 후 다시 다운로드를 시도하세요
                    </div>
                  </div>
                ) : null
              })()}
              {dlStatus.pdfLinks && dlStatus.pdfLinks.length > 0 && (
                <div style={{ marginTop: '0.35rem', padding: '0.5rem 0.75rem', background: '#1e1b4b', borderRadius: '8px', border: '1px solid #3730a3' }}>
                  <div style={{ fontSize: '0.75rem', color: '#a5b4fc', marginBottom: '0.4rem', fontWeight: 500 }}>
                    📎 아래 링크를 클릭하여 브라우저에서 직접 다운로드하세요:
                  </div>
                  {dlStatus.pdfLinks.map((link, li) => (
                    <div key={li} style={{ marginBottom: '0.25rem' }}>
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: '0.78rem', color: '#93c5fd', textDecoration: 'none', wordBreak: 'break-all' }}
                        onMouseOver={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                        onMouseOut={(e) => (e.currentTarget.style.textDecoration = 'none')}
                      >
                        {link.source}: {link.url.length > 80 ? link.url.slice(0, 77) + '...' : link.url}
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <ActionButtons
            index={index}
            paper={paper}
            fileInputRef={fileInputRef}
            onAbstractToggle={() => setAbstractOpen(!abstractOpen)}
            onSummaryToggle={() => {}}
            onCitationsToggle={() => {}}
            onReferencesToggle={() => {}}
          />

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={async (e) => {
              const file = e.target.files?.[0]
              if (file) {
                setIsAttaching(true)
                await useAppStore.getState().attachPdf(index, file)
                setIsAttaching(false)
              }
              e.target.value = ''
            }}
          />

          {isAttaching && (
            <div className="pdf-bar" style={{ marginTop: '0.25rem', background: '#312e81', color: '#a5b4fc' }}>
              <span className="spinner" /> PDF 첨부 중: 업로드 진행 중...
            </div>
          )}

          {abstractOpen && paper.abstract && <AbstractPanel abstract={paper.abstract} index={index} />}
          {paper.summary && <SummaryPanel summary={paper.summary} index={index} />}
          {hasCitations && <CitationsList index={index} />}
          {hasReferences && <ReferencesList index={index} />}
        </div>
      </div>
    </div>
  )
}
