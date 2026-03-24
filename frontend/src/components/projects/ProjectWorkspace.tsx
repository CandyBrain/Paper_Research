import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAppStore } from '../../store/useAppStore'

const READABLE_EXTENSIONS = [
  '.md', '.txt', '.csv', '.json', '.xml', '.html', '.htm',
  '.py', '.js', '.ts', '.r', '.m', '.tex', '.bib', '.yaml', '.yml',
  '.log', '.cfg', '.ini', '.toml',
]

function isReadableFile(name: string): boolean {
  const lower = name.toLowerCase()
  return READABLE_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

async function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error('파일 읽기 실패'))
    reader.readAsText(file)
  })
}

export function ProjectWorkspace() {
  const project = useAppStore((s) => s.activeProject)
  const closeProject = useAppStore((s) => s.closeProject)
  const removePaper = useAppStore((s) => s.removePaperFromProject)
  const sendChat = useAppStore((s) => s.sendChat)
  const chatLoading = useAppStore((s) => s.chatLoading)

  const [input, setInput] = useState('')
  const [selectedPapers, setSelectedPapers] = useState<Set<number>>(new Set())
  const [attachedFiles, setAttachedFiles] = useState<{ name: string; content: string }[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (project) {
      setSelectedPapers(new Set(project.papers.map((_, i) => i)))
    }
  }, [project?.name, project?.papers.length])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [project?.chat_history.length])

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const newFiles: { name: string; content: string }[] = []
    for (const file of Array.from(files)) {
      if (isReadableFile(file.name)) {
        try {
          const content = await readFileAsText(file)
          newFiles.push({ name: file.name, content })
        } catch {
          /* skip unreadable */
        }
      }
    }
    if (newFiles.length > 0) {
      setAttachedFiles((prev) => [...prev, ...newFiles])
    }
    return newFiles.length
  }, [])

  if (!project) return null

  const togglePaper = (idx: number) => {
    setSelectedPapers((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const selectAllPapers = () => setSelectedPapers(new Set(project.papers.map((_, i) => i)))
  const deselectAllPapers = () => setSelectedPapers(new Set())

  const removeAttachedFile = (idx: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleSend = () => {
    const textMsg = input.trim()
    if ((!textMsg && attachedFiles.length === 0) || chatLoading) return

    // Build message with attached file contents
    let fullMessage = textMsg
    if (attachedFiles.length > 0) {
      const fileParts = attachedFiles.map(
        (f) => `\n\n--- 첨부 파일: ${f.name} ---\n${f.content}`
      ).join('')
      fullMessage = textMsg + fileParts
    }

    sendChat(fullMessage, Array.from(selectedPapers))
    setInput('')
    setAttachedFiles([])
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files.length > 0) {
      await processFiles(e.dataTransfer.files)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = () => setIsDragOver(false)

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFiles(e.target.files)
    }
    e.target.value = ''
  }

  const selectedCount = selectedPapers.size
  const totalCount = project.papers.length

  return (
    <div className="project-workspace">
      {/* Left: Paper list */}
      <div className="project-papers">
        <div className="project-papers-header">
          <button className="project-back-btn" onClick={closeProject}>&#8592; 검색으로</button>
          <h3>{project.name}</h3>
          <span className="project-paper-count">{totalCount}편</span>
        </div>
        {totalCount > 0 && (
          <div className="project-select-bar">
            <span style={{ fontSize: '0.75rem', color: '#a5b4fc' }}>
              AI 대화에 사용: {selectedCount}/{totalCount}편
            </span>
            <div style={{ display: 'flex', gap: '0.3rem', marginLeft: 'auto' }}>
              <button className="project-select-btn" onClick={selectAllPapers}>전체</button>
              <button className="project-select-btn" onClick={deselectAllPapers}>해제</button>
            </div>
          </div>
        )}
        <div className="project-papers-list">
          {totalCount === 0 && (
            <div className="project-empty">
              논문이 없습니다. 검색 결과에서 논문을 추가하세요.
            </div>
          )}
          {project.papers.map((p, i) => (
            <div key={i} className={`project-paper-item ${selectedPapers.has(i) ? 'selected' : ''}`}>
              <input
                type="checkbox"
                checked={selectedPapers.has(i)}
                onChange={() => togglePaper(i)}
                className="project-paper-checkbox"
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="project-paper-title">{p.title}</div>
                <div className="project-paper-meta">
                  {p.authors?.slice(0, 2).join(', ')}
                  {p.year ? ` (${p.year})` : ''}
                  {p.journal ? ` - ${p.journal}` : ''}
                </div>
                {p.summary && (
                  <div className="project-paper-summary">
                    {p.summary.length > 150 ? p.summary.slice(0, 147) + '...' : p.summary}
                  </div>
                )}
              </div>
              <button className="project-paper-remove" onClick={() => removePaper(i)} title="프로젝트에서 제거">
                &times;
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Chat */}
      <div
        className={`project-chat ${isDragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <div className="project-chat-header">
          <span>AI 연구 어시스턴트</span>
          {selectedCount < totalCount && selectedCount > 0 && (
            <span style={{ fontSize: '0.72rem', color: '#94a3b8', marginLeft: '0.5rem' }}>
              ({selectedCount}편 선택됨)
            </span>
          )}
        </div>

        {isDragOver && (
          <div className="chat-drop-overlay">
            파일을 여기에 놓으세요 (.md, .txt, .csv, .json 등)
          </div>
        )}

        <div className="project-chat-messages">
          {project.chat_history.length === 0 && (
            <div className="project-chat-welcome">
              {selectedCount === 0 ? (
                <>왼쪽에서 AI 대화에 사용할 논문을 선택하세요.</>
              ) : (
                <>
                  선택한 논문들을 기반으로 질문하세요.
                  <br /><br />
                  예시:
                  <ul>
                    <li>이 논문들의 공통 연구 방법론을 비교해줘</li>
                    <li>주요 발견을 종합해서 정리해줘</li>
                    <li>이 연구들의 한계점은 무엇인가?</li>
                    <li>향후 연구 방향을 제안해줘</li>
                  </ul>
                  <div style={{ marginTop: '0.5rem', color: '#64748b', fontSize: '0.78rem' }}>
                    파일을 드래그하거나 클립 버튼으로 첨부할 수 있습니다
                  </div>
                </>
              )}
            </div>
          )}
          {project.chat_history.map((msg, i) => (
            <div key={i} className={`chat-bubble chat-${msg.role}`}>
              <div className="chat-bubble-label">
                {msg.role === 'user' ? 'You' : 'AI'}
              </div>
              <div className="chat-bubble-content">
                {msg.role === 'assistant' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="chat-bubble chat-assistant">
              <div className="chat-bubble-label">AI</div>
              <div className="chat-bubble-content">
                <span className="spinner" /> 응답 생성 중...
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Attached files preview */}
        {attachedFiles.length > 0 && (
          <div className="chat-attached-files">
            {attachedFiles.map((f, i) => (
              <div key={i} className="chat-attached-file">
                <span className="chat-attached-name">{f.name}</span>
                <span className="chat-attached-size">
                  ({(f.content.length / 1024).toFixed(1)}KB)
                </span>
                <button className="chat-attached-remove" onClick={() => removeAttachedFile(i)}>
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="project-chat-input">
          <button
            className="chat-file-btn"
            onClick={() => fileInputRef.current?.click()}
            title="파일 첨부 (.md, .txt, .csv 등)"
            disabled={selectedCount === 0}
          >
            &#128206;
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={READABLE_EXTENSIONS.join(',')}
            style={{ display: 'none' }}
            onChange={handleFileInput}
          />
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={selectedCount === 0 ? '논문을 먼저 선택하세요' : '논문에 대해 질문하세요... (파일 드래그 가능)'}
            rows={2}
            disabled={selectedCount === 0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          <button
            className="btn-primary"
            onClick={handleSend}
            disabled={chatLoading || (!input.trim() && attachedFiles.length === 0) || selectedCount === 0}
          >
            {chatLoading ? '...' : '전송'}
          </button>
        </div>
      </div>
    </div>
  )
}
