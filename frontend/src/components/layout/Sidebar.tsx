import { useState, useEffect } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { FolderPickerModal } from './FolderPickerModal'

export function Sidebar() {
  const settings = useAppStore((s) => s.settings)
  const updateSettings = useAppStore((s) => s.updateSettings)
  const sessions = useAppStore((s) => s.sessions)
  const loadSession = useAppStore((s) => s.loadSession)
  const saveSession = useAppStore((s) => s.saveSession)
  const deleteSession = useAppStore((s) => s.deleteSession)
  const summaryLang = useAppStore((s) => s.summaryLang)
  const projectsList = useAppStore((s) => s.projectsList)
  const createProject = useAppStore((s) => s.createProject)
  const deleteProjectByName = useAppStore((s) => s.deleteProjectByName)
  const openProject = useAppStore((s) => s.openProject)
  const addPapersToProject = useAppStore((s) => s.addPapersToProject)
  const selectedIndices = useAppStore((s) => s.selectedIndices)

  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(true)
  const [projectsOpen, setProjectsOpen] = useState(true)
  const [langOpen, setLangOpen] = useState(false)
  const [sessionName, setSessionName] = useState('')
  const [projectName, setProjectName] = useState('')

  const [folderPickerOpen, setFolderPickerOpen] = useState(false)
  const [localSettings, setLocalSettings] = useState(settings)

  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  const handleSettingChange = (key: string, value: string) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }))
  }

  const handleSettingSave = () => {
    // Send all settings, but skip empty API key fields to avoid overwriting server values
    const apiKeyFields = ['anthropic_api_key', 'scopus_api_key', 'core_api_key', 'springer_api_key']
    const payload: Record<string, unknown> = {}

    for (const [key, value] of Object.entries(localSettings)) {
      if (apiKeyFields.includes(key)) {
        // Only send API key if user actually typed something
        if (value && value !== settings[key as keyof typeof settings]) {
          payload[key] = value
        }
        // If unchanged or empty, don't send (server keeps existing value)
      } else {
        payload[key] = value
      }
    }

    updateSettings(payload)
  }

  const handleSaveSession = () => {
    if (sessionName.trim()) {
      saveSession(sessionName.trim())
      setSessionName('')
    }
  }

  return (
    <aside className="sidebar">
      {/* Settings */}
      <div className="sidebar-section">
        <div className="sidebar-section-title" onClick={() => setSettingsOpen(!settingsOpen)}>
          <span>설정</span>
          <span className={`chevron ${settingsOpen ? 'open' : ''}`}>&#9654;</span>
        </div>
        {settingsOpen && (
          <div>
            <label>Anthropic API Key</label>
            <input
              type="password"
              value={localSettings.anthropic_api_key}
              onChange={(e) => handleSettingChange('anthropic_api_key', e.target.value)}
              placeholder="sk-ant-..."
            />
            <label>Scopus API Key</label>
            <input
              type="password"
              value={localSettings.scopus_api_key}
              onChange={(e) => handleSettingChange('scopus_api_key', e.target.value)}
              placeholder="Scopus API key"
            />
            <label>CORE API Key</label>
            <input
              type="password"
              value={localSettings.core_api_key}
              onChange={(e) => handleSettingChange('core_api_key', e.target.value)}
              placeholder="CORE API key"
            />
            <label>Springer Nature API Key</label>
            <input
              type="password"
              value={localSettings.springer_api_key}
              onChange={(e) => handleSettingChange('springer_api_key', e.target.value)}
              placeholder="Springer Nature API key"
            />
            <label>프록시 URL</label>
            <input
              type="text"
              value={localSettings.proxy_url}
              onChange={(e) => handleSettingChange('proxy_url', e.target.value)}
              placeholder="http://proxy:port"
            />
            <label>다운로드 디렉토리</label>
            <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
              <input
                type="text"
                value={localSettings.download_dir}
                onChange={(e) => handleSettingChange('download_dir', e.target.value)}
                placeholder="./downloads"
                style={{ flex: 1, marginBottom: 0 }}
              />
              <button
                className="btn-secondary btn-sm"
                style={{ whiteSpace: 'nowrap', padding: '0.35rem 0.5rem' }}
                onClick={() => setFolderPickerOpen(true)}
                title="폴더 찾아보기"
              >
                &#128193;
              </button>
            </div>
            <label className="browser-toggle" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={localSettings.use_browser ?? false}
                onChange={(e) => setLocalSettings((prev) => ({ ...prev, use_browser: e.target.checked }))}
                style={{ width: 'auto', margin: 0 }}
              />
              <span style={{ fontSize: '0.8rem' }}>브라우저 자동화 (Cloudflare 우회)</span>
            </label>
            <button className="btn-primary btn-sm" style={{ width: '100%', marginTop: '0.25rem' }} onClick={handleSettingSave}>
              설정 저장
            </button>
          </div>
        )}
      </div>

      {/* Sessions */}
      <div className="sidebar-section">
        <div className="sidebar-section-title" onClick={() => setSessionsOpen(!sessionsOpen)}>
          <span>세션</span>
          <span className={`chevron ${sessionsOpen ? 'open' : ''}`}>&#9654;</span>
        </div>
        {sessionsOpen && (
          <div>
            <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.5rem' }}>
              <input
                type="text"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                placeholder="세션 이름"
                style={{ flex: 1, marginBottom: 0 }}
                onKeyDown={(e) => e.key === 'Enter' && handleSaveSession()}
              />
              <button className="btn-primary btn-sm" onClick={handleSaveSession}>
                저장
              </button>
            </div>
            {sessions.map((s) => (
              <div key={s.name} className="session-item">
                <span className="session-name" onClick={() => loadSession(s.name)} title={s.query}>
                  {s.name}
                </span>
                <span className="session-meta-info">{s.paper_count}편</span>
                <button className="btn-danger" style={{ marginLeft: '0.35rem' }} onClick={() => deleteSession(s.name)}>
                  삭제
                </button>
              </div>
            ))}
            {sessions.length === 0 && (
              <div style={{ fontSize: '0.75rem', color: '#64748b', padding: '0.3rem' }}>저장된 세션이 없습니다</div>
            )}
          </div>
        )}
      </div>

      {/* Research Projects */}
      <div className="sidebar-section">
        <div className="sidebar-section-title" onClick={() => setProjectsOpen(!projectsOpen)}>
          <span>연구 프로젝트</span>
          <span className={`chevron ${projectsOpen ? 'open' : ''}`}>&#9654;</span>
        </div>
        {projectsOpen && (
          <div>
            <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.5rem' }}>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="프로젝트 이름"
                style={{ flex: 1, marginBottom: 0 }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && projectName.trim()) {
                    createProject(projectName.trim())
                    setProjectName('')
                  }
                }}
              />
              <button className="btn-primary btn-sm" onClick={() => {
                if (projectName.trim()) {
                  createProject(projectName.trim())
                  setProjectName('')
                }
              }}>
                생성
              </button>
            </div>
            {selectedIndices.size > 0 && projectsList.length > 0 && (
              <div style={{ marginBottom: '0.5rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#a5b4fc', marginBottom: '0.25rem' }}>
                  선택한 {selectedIndices.size}편을 프로젝트에 추가:
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                  {projectsList.map((proj) => (
                    <button
                      key={proj.name}
                      className="btn-primary btn-sm"
                      style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => addPapersToProject(proj.name, Array.from(selectedIndices))}
                    >
                      + {proj.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {projectsList.map((proj) => (
              <div key={proj.name} className="session-item">
                <span className="session-name" onClick={() => openProject(proj.name)} title={`${proj.paper_count}편의 논문`}>
                  {proj.name}
                </span>
                <span className="session-meta-info">{proj.paper_count}편</span>
                <button className="btn-danger" style={{ marginLeft: '0.35rem' }} onClick={() => deleteProjectByName(proj.name)}>
                  삭제
                </button>
              </div>
            ))}
            {projectsList.length === 0 && (
              <div style={{ fontSize: '0.75rem', color: '#64748b', padding: '0.3rem' }}>프로젝트가 없습니다</div>
            )}
          </div>
        )}
      </div>

      {/* Summary language */}
      <div className="sidebar-section">
        <div className="sidebar-section-title" onClick={() => setLangOpen(!langOpen)}>
          <span>요약 언어</span>
          <span className={`chevron ${langOpen ? 'open' : ''}`}>&#9654;</span>
        </div>
        {langOpen && (
          <select
            value={summaryLang}
            onChange={(e) => useAppStore.setState({ summaryLang: e.target.value })}
          >
            <option value="한국어">한국어</option>
            <option value="English">English</option>
            <option value="日本語">日本語</option>
            <option value="中文">中文</option>
          </select>
        )}
      </div>
      <FolderPickerModal
        isOpen={folderPickerOpen}
        initialPath={localSettings.download_dir}
        onSelect={(path) => {
          handleSettingChange('download_dir', path)
        }}
        onClose={() => setFolderPickerOpen(false)}
      />
    </aside>
  )
}
