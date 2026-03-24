import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { AIAnalysisBox } from './AIAnalysisBox'

const DATABASES = ['OpenAlex', 'PubMed', 'Semantic Scholar', 'CORE', 'Scopus']

export function SearchPanel() {
  const lastQuery = useAppStore((s) => s.lastQuery)
  const searchMode = useAppStore((s) => s.searchMode)
  const [tab, setTab] = useState<'keyword' | 'ai'>(searchMode || 'keyword')
  const [query, setQuery] = useState(lastQuery || '')
  const [selectedDBs, setSelectedDBs] = useState<string[]>(['OpenAlex', 'PubMed', 'Semantic Scholar'])
  const [maxResults, setMaxResults] = useState(20)
  const isSearching = useAppStore((s) => s.isSearching)
  const search = useAppStore((s) => s.search)
  const searchAI = useAppStore((s) => s.searchAI)
  const aiAnalysis = useAppStore((s) => s.aiAnalysis)
  const initialized = useRef(false)

  // Sync from store after workspace loads
  useEffect(() => {
    if (!initialized.current && lastQuery) {
      initialized.current = true
      setQuery(lastQuery)
      setTab(searchMode as 'keyword' | 'ai' || 'keyword')
    }
  }, [lastQuery, searchMode])

  const toggleDB = (db: string) => {
    setSelectedDBs((prev) => (prev.includes(db) ? prev.filter((d) => d !== db) : [...prev, db]))
  }

  const handleSearch = () => {
    if (!query.trim() || selectedDBs.length === 0) return
    if (tab === 'keyword') {
      search(query.trim(), selectedDBs, maxResults)
    } else {
      searchAI(query.trim(), selectedDBs, maxResults)
    }
  }

  return (
    <div className="search-panel">
      <div className="search-tabs">
        <button className={`search-tab ${tab === 'keyword' ? 'active' : ''}`} onClick={() => setTab('keyword')}>
          키워드 검색
        </button>
        <button className={`search-tab ${tab === 'ai' ? 'active' : ''}`} onClick={() => setTab('ai')}>
          AI 검색
        </button>
      </div>

      <textarea
        className="search-textarea"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={tab === 'keyword' ? '검색 키워드를 입력하세요...' : '연구 주제를 자세히 설명해 주세요...'}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSearch()
          }
        }}
      />

      <div className="db-checkboxes">
        {DATABASES.map((db) => (
          <label key={db}>
            <input type="checkbox" checked={selectedDBs.includes(db)} onChange={() => toggleDB(db)} />
            {db}
          </label>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <button className="btn-primary" onClick={handleSearch} disabled={isSearching || !query.trim() || selectedDBs.length === 0}>
          {isSearching ? (
            <>
              <span className="spinner" /> 검색 중...
            </>
          ) : tab === 'keyword' ? (
            '검색'
          ) : (
            'AI 검색'
          )}
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>최대 결과:</span>
          <input
            type="number"
            className="max-results-input"
            value={maxResults}
            min={1}
            max={200}
            onChange={(e) => setMaxResults(Number(e.target.value))}
          />
        </div>
      </div>

      {tab === 'ai' && aiAnalysis && <AIAnalysisBox analysis={aiAnalysis} />}
    </div>
  )
}
