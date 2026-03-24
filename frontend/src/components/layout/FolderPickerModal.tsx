import { useState, useEffect, useCallback } from 'react'
import * as api from '../../api/client'

interface Props {
  isOpen: boolean
  initialPath: string
  onSelect: (path: string) => void
  onClose: () => void
}

export function FolderPickerModal({ isOpen, initialPath, onSelect, onClose }: Props) {
  const [currentPath, setCurrentPath] = useState('')
  const [dirs, setDirs] = useState<string[]>([])
  const [drives, setDrives] = useState<string[]>([])
  const [parent, setParent] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [showNewFolder, setShowNewFolder] = useState(false)

  const browse = useCallback(async (path: string) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.browseDirs(path)
      setCurrentPath(res.current)
      setDirs(res.dirs)
      setParent(res.parent)
      setDrives(res.drives || [])
      if (res.error) setError(res.error)
    } catch (e) {
      setError(`탐색 실패: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      browse(initialPath || '')
    }
  }, [isOpen, initialPath, browse])

  if (!isOpen) return null

  const handleSelect = () => {
    onSelect(currentPath)
    onClose()
  }

  const handleDirClick = (dirName: string) => {
    const sep = currentPath.includes('\\') ? '\\' : '/'
    const newPath = currentPath.endsWith(sep) || currentPath.endsWith('/')
      ? currentPath + dirName
      : currentPath + sep + dirName
    browse(newPath)
  }

  const handleDriveClick = (drive: string) => {
    browse(drive + '/')
  }

  const handleGoUp = () => {
    if (parent) browse(parent)
  }

  return (
    <div className="folder-picker-overlay" onClick={onClose}>
      <div className="folder-picker-modal" onClick={(e) => e.stopPropagation()}>
        <div className="folder-picker-header">
          <h3>폴더 선택</h3>
          <button className="folder-picker-close" onClick={onClose}>&times;</button>
        </div>

        <div className="folder-picker-path-bar">
          <button
            className="folder-picker-up-btn"
            onClick={handleGoUp}
            disabled={!parent}
            title="상위 폴더"
          >
            &#8593;
          </button>
          <span className="folder-picker-current-path" title={currentPath}>
            {currentPath}
          </span>
        </div>

        {error && <div className="folder-picker-error">{error}</div>}

        <div className="folder-picker-list">
          {loading ? (
            <div className="folder-picker-loading">로딩 중...</div>
          ) : (
            <>
              {drives.length > 0 && !parent && (
                <div className="folder-picker-drives">
                  {drives.map((d) => (
                    <button key={d} className="folder-picker-drive" onClick={() => handleDriveClick(d)}>
                      {d}\
                    </button>
                  ))}
                </div>
              )}
              {dirs.length === 0 && !error && (
                <div className="folder-picker-empty">하위 폴더가 없습니다</div>
              )}
              {dirs.map((d) => (
                <div key={d} className="folder-picker-item" onDoubleClick={() => handleDirClick(d)} onClick={() => handleDirClick(d)}>
                  <span className="folder-picker-icon">&#128193;</span>
                  <span className="folder-picker-name">{d}</span>
                </div>
              ))}
            </>
          )}
        </div>

        {showNewFolder ? (
          <div className="folder-picker-new-folder">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="새 폴더 이름"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newFolderName.trim()) {
                  handleDirClick(newFolderName.trim())
                  setNewFolderName('')
                  setShowNewFolder(false)
                } else if (e.key === 'Escape') {
                  setShowNewFolder(false)
                  setNewFolderName('')
                }
              }}
            />
            <button
              className="btn-primary btn-sm"
              onClick={() => {
                if (newFolderName.trim()) {
                  handleDirClick(newFolderName.trim())
                  setNewFolderName('')
                  setShowNewFolder(false)
                }
              }}
            >
              이동
            </button>
          </div>
        ) : (
          <button
            className="folder-picker-new-folder-btn"
            onClick={() => setShowNewFolder(true)}
          >
            + 직접 입력
          </button>
        )}

        <div className="folder-picker-actions">
          <button className="btn-primary" onClick={handleSelect}>
            이 폴더 선택
          </button>
          <button className="btn-secondary" onClick={onClose}>
            취소
          </button>
        </div>
      </div>
    </div>
  )
}
