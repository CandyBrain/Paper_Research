import type { CitationData, AIAnalysis, SessionMeta, Settings, ProjectMeta, ProjectDetail, ChatMessage } from '../types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' });
}

// ── Search ──

export async function searchKeyword(
  query: string,
  databases: string[],
  maxResults: number,
): Promise<{ papers: unknown[]; ai_analysis?: AIAnalysis }> {
  return post('/search', { query, databases, max_results_per_db: maxResults });
}

export async function searchAI(
  description: string,
  databases: string[],
  maxResults: number,
): Promise<{ papers: unknown[]; ai_analysis?: AIAnalysis; analysis?: AIAnalysis }> {
  return post('/search/ai', { description, databases, max_results_per_db: maxResults });
}

// ── Papers ──

export async function downloadPaper(idx: number): Promise<{ success: boolean; message: string; filepath?: string; pdf_links?: { url: string; source: string }[] }> {
  return post(`/papers/${idx}/download`, {});
}

export async function summarizePaper(
  idx: number,
  language: string,
  downloadDir: string,
  manualPdfPath?: string,
): Promise<{ summary: string }> {
  return post(`/papers/${idx}/summarize`, {
    language,
    download_dir: downloadDir,
    manual_pdf_path: manualPdfPath || '',
  });
}

export async function getCitations(idx: number, maxResults: number = 20): Promise<CitationData> {
  const raw = await request<{ citations: unknown[]; total_count: number }>(`/papers/${idx}/citations?max_results=${maxResults}`);
  return { items: raw.citations as CitationData['items'], total: raw.total_count };
}

export async function getReferences(idx: number, maxResults: number = 50): Promise<CitationData> {
  const raw = await request<{ references: unknown[]; total_count: number }>(`/papers/${idx}/references?max_results=${maxResults}`);
  return { items: raw.references as CitationData['items'], total: raw.total_count };
}

export async function refreshPaper(idx: number): Promise<{ success: boolean; message: string; paper?: unknown }> {
  return post(`/papers/${idx}/refresh`, {});
}

export async function attachPdf(idx: number, file: File): Promise<{ success: boolean; message: string; path?: string }> {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${BASE}/papers/${idx}/attach`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function detachPdf(idx: number): Promise<void> {
  await del(`/papers/${idx}/attach`);
}

export async function translateText(text: string): Promise<{ translated: string }> {
  return post('/translate', { text });
}

// ── Settings ──

export async function getSettings(): Promise<Settings> {
  return request('/settings');
}

export interface BrowseDirsResult {
  current: string;
  parent: string;
  dirs: string[];
  drives?: string[];
  error?: string;
}

export async function browseDirs(path: string = ''): Promise<BrowseDirsResult> {
  return request(`/settings/browse?path=${encodeURIComponent(path)}`);
}

export async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  return put('/settings', settings);
}

// ── Sessions ──

export async function listSessions(): Promise<SessionMeta[]> {
  const res = await request<{ sessions: SessionMeta[] }>('/sessions');
  return res.sessions ?? res as unknown as SessionMeta[];
}

export async function saveSession(name: string): Promise<{ filepath: string }> {
  return post('/sessions', { name });
}

export async function loadSession(name: string): Promise<{ papers: unknown[]; query: string }> {
  return request(`/sessions/${encodeURIComponent(name)}`);
}

export async function deleteSession(name: string): Promise<void> {
  await del(`/sessions/${encodeURIComponent(name)}`);
}

export async function getCurrentWorkspace(): Promise<{
  papers: unknown[];
  last_query: string;
  search_mode: string;
  ai_analysis: unknown;
  selected: number[];
  dl_statuses: Record<string, string>;
  manual_pdf_paths: Record<string, string>;
  citations_data: Record<string, unknown>;
  references_data: Record<string, unknown>;
}> {
  return request('/sessions/current');
}

export async function autosave(): Promise<void> {
  await post('/sessions/autosave', {});
}

// ── Projects ──

export async function listProjects(): Promise<ProjectMeta[]> {
  const res = await request<{ projects: ProjectMeta[] }>('/projects');
  return res.projects ?? res as unknown as ProjectMeta[];
}

export async function createProject(name: string): Promise<{ message: string }> {
  return post('/projects', { name });
}

export async function getProject(name: string): Promise<ProjectDetail> {
  return request(`/projects/${encodeURIComponent(name)}`);
}

export async function deleteProject(name: string): Promise<void> {
  await del(`/projects/${encodeURIComponent(name)}`);
}

export async function addPapersToProject(name: string, indices: number[]): Promise<{ message: string; paper_count: number }> {
  return post(`/projects/${encodeURIComponent(name)}/papers`, { paper_indices: indices });
}

export async function removePaperFromProject(name: string, idx: number): Promise<void> {
  await del(`/projects/${encodeURIComponent(name)}/papers/${idx}`);
}

export async function sendProjectChat(name: string, message: string, language: string = 'ko', paperIndices?: number[]): Promise<ChatMessage> {
  return post(`/projects/${encodeURIComponent(name)}/chat`, {
    message,
    language,
    paper_indices: paperIndices ?? null,
  });
}

// ── Export ──

export async function exportMarkdown(selectedIndices: number[]): Promise<Blob> {
  const res = await fetch(`${BASE}/export/markdown`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selected_indices: selectedIndices }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}
