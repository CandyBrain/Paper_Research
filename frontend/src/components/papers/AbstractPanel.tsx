import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  abstract: string
  index: number
}

export function AbstractPanel({ abstract, index }: Props) {
  const [showTranslated, setShowTranslated] = useState(false)
  const translateText = useAppStore((s) => s.translateText)
  const translating = useAppStore((s) => s.translating)
  const translatedTexts = useAppStore((s) => s.translatedTexts)

  const key = `abstract-${index}`
  const isTranslating = translating[key]
  const translated = translatedTexts[key]

  const handleTranslate = () => {
    if (!translated) {
      translateText(key, abstract)
    }
    setShowTranslated(!showTranslated)
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(showTranslated && translated ? translated : abstract)
  }

  return (
    <div className="collapsible-body">
      <div style={{ display: 'flex', gap: '5px', marginBottom: '0.5rem' }}>
        <button className="action-btn secondary" onClick={handleTranslate} disabled={isTranslating}>
          {isTranslating ? <><span className="spinner" /> 번역 중</> : showTranslated ? '원문' : '번역'}
        </button>
        <button className="action-btn secondary" onClick={handleCopy}>
          복사
        </button>
      </div>
      <div className="abstract-text">
        {showTranslated && translated ? translated : abstract}
      </div>
    </div>
  )
}
