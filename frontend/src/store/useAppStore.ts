import { create } from 'zustand';
import type { Paper, AIAnalysis, CitationData, SessionMeta, Settings, ProjectMeta, ProjectDetail, ChatMessage } from '../types';
import * as api from '../api/client';

interface PdfLink {
  url: string;
  source: string;
}

interface DlStatus {
  loading: boolean;
  status: string;
  path?: string;
  pdfLinks?: PdfLink[];
}

interface AppState {
  papers: Paper[];
  selectedIndices: Set<number>;
  aiAnalysis: AIAnalysis | null;
  dlStatuses: Record<number, DlStatus>;
  manualPdfPaths: Record<number, string>;
  citationsData: Record<number, CitationData>;
  referencesData: Record<number, CitationData>;
  settings: Settings;
  sessions: SessionMeta[];
  isSearching: boolean;
  lastQuery: string;
  searchMode: 'keyword' | 'ai';
  summaryLang: string;
  summaryLoading: Record<number, boolean>;
  citationsLoading: Record<number, boolean>;
  referencesLoading: Record<number, boolean>;
  translating: Record<string, boolean>;
  translatedTexts: Record<string, string>;

  // PDF Viewer
  viewerPaperIdx: number | null;
  openPdfViewer: (idx: number) => void;
  closePdfViewer: () => void;

  // Actions
  search: (query: string, databases: string[], maxResults: number) => Promise<void>;
  searchAI: (description: string, databases: string[], maxResults: number) => Promise<void>;
  toggleSelect: (idx: number) => void;
  selectAll: () => void;
  deselectAll: () => void;
  downloadPaper: (idx: number) => Promise<void>;
  summarizePaper: (idx: number) => Promise<void>;
  fetchCitations: (idx: number, maxResults: number) => Promise<void>;
  fetchReferences: (idx: number, maxResults: number) => Promise<void>;
  refreshPaper: (idx: number) => Promise<void>;
  refreshLoading: Record<number, boolean>;
  attachPdf: (idx: number, file: File) => Promise<void>;
  detachPdf: (idx: number) => Promise<void>;
  loadSessions: () => Promise<void>;
  loadSession: (name: string) => Promise<void>;
  saveSession: (name: string) => Promise<void>;
  deleteSession: (name: string) => Promise<void>;
  updateSettings: (s: Partial<Settings>) => Promise<void>;
  loadSettings: () => Promise<void>;
  clearSearch: () => void;
  exportMarkdown: () => Promise<void>;
  autosave: () => Promise<void>;
  loadCurrentWorkspace: () => Promise<void>;
  translateText: (key: string, text: string) => Promise<void>;

  // Toast
  toastMessage: string;
  showToast: (msg: string) => void;

  // Projects
  projectsList: ProjectMeta[];
  activeView: 'search' | 'project';
  activeProject: ProjectDetail | null;
  chatLoading: boolean;
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<void>;
  deleteProjectByName: (name: string) => Promise<void>;
  openProject: (name: string) => Promise<void>;
  closeProject: () => void;
  addPapersToProject: (name: string, indices: number[]) => Promise<void>;
  removePaperFromProject: (idx: number) => Promise<void>;
  sendChat: (message: string, paperIndices?: number[]) => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  papers: [],
  selectedIndices: new Set(),
  aiAnalysis: null,
  dlStatuses: {},
  manualPdfPaths: {},
  citationsData: {},
  referencesData: {},
  settings: {
    anthropic_api_key: '',
    scopus_api_key: '',
    core_api_key: '',
    springer_api_key: '',
    proxy_url: '',
    proxy_mode: 'none',
    download_dir: './downloads',
    use_browser: false,
  },
  sessions: [],
  isSearching: false,
  lastQuery: '',
  searchMode: 'keyword',
  summaryLang: '한국어',
  summaryLoading: {},
  citationsLoading: {},
  referencesLoading: {},
  refreshLoading: {},
  translating: {},
  translatedTexts: {},
  viewerPaperIdx: null,

  openPdfViewer: (idx) => set({ viewerPaperIdx: idx }),
  closePdfViewer: () => set({ viewerPaperIdx: null }),

  search: async (query, databases, maxResults) => {
    set({ isSearching: true, lastQuery: query, searchMode: 'keyword', aiAnalysis: null });
    try {
      const data = await api.searchKeyword(query, databases, maxResults);
      set({
        papers: data.papers as Paper[],
        isSearching: false,
        selectedIndices: new Set(),
        dlStatuses: {},
        manualPdfPaths: {},
        citationsData: {},
        referencesData: {},
      });
    } catch (e) {
      console.error('Search failed:', e);
      set({ isSearching: false });
    }
  },

  searchAI: async (description, databases, maxResults) => {
    set({ isSearching: true, lastQuery: description, searchMode: 'ai' });
    try {
      const data = await api.searchAI(description, databases, maxResults);
      set({
        papers: data.papers as Paper[],
        aiAnalysis: data.ai_analysis ?? data.analysis ?? null,
        isSearching: false,
        selectedIndices: new Set(),
        dlStatuses: {},
        manualPdfPaths: {},
        citationsData: {},
        referencesData: {},
      });
    } catch (e) {
      console.error('AI Search failed:', e);
      set({ isSearching: false });
    }
  },

  toggleSelect: (idx) => {
    const s = new Set(get().selectedIndices);
    if (s.has(idx)) s.delete(idx);
    else s.add(idx);
    set({ selectedIndices: s });
  },

  selectAll: () => {
    set({ selectedIndices: new Set(get().papers.map((_, i) => i)) });
  },

  deselectAll: () => {
    set({ selectedIndices: new Set() });
  },

  downloadPaper: async (idx) => {
    set((s) => ({ dlStatuses: { ...s.dlStatuses, [idx]: { loading: true, status: '다운로드 중...' } } }));
    try {
      const res = await api.downloadPaper(idx);
      set((s) => ({
        dlStatuses: {
          ...s.dlStatuses,
          [idx]: {
            loading: false,
            status: res.success ? 'success' : res.message,
            path: res.filepath,
            pdfLinks: res.pdf_links,
          },
        },
      }));
    } catch (e) {
      set((s) => ({
        dlStatuses: { ...s.dlStatuses, [idx]: { loading: false, status: `오류: ${e}` } },
      }));
    }
  },

  summarizePaper: async (idx) => {
    set((s) => ({ summaryLoading: { ...s.summaryLoading, [idx]: true } }));
    try {
      const { settings, manualPdfPaths, summaryLang } = get();
      const langCodeMap: Record<string, string> = {
        '한국어': 'ko', 'English': 'en', '日本語': 'ja', '中文': 'zh',
      };
      const langCode = langCodeMap[summaryLang] || summaryLang;
      const res = await api.summarizePaper(idx, langCode, settings.download_dir, manualPdfPaths[idx]);
      set((s) => {
        const papers = [...s.papers];
        papers[idx] = { ...papers[idx], summary: res.summary };
        return { papers, summaryLoading: { ...s.summaryLoading, [idx]: false } };
      });
    } catch {
      set((s) => ({ summaryLoading: { ...s.summaryLoading, [idx]: false } }));
    }
  },

  fetchCitations: async (idx, maxResults) => {
    set((s) => ({ citationsLoading: { ...s.citationsLoading, [idx]: true } }));
    try {
      const data = await api.getCitations(idx, maxResults);
      set((s) => ({
        citationsData: { ...s.citationsData, [idx]: data },
        citationsLoading: { ...s.citationsLoading, [idx]: false },
      }));
    } catch {
      set((s) => ({ citationsLoading: { ...s.citationsLoading, [idx]: false } }));
    }
  },

  fetchReferences: async (idx, maxResults) => {
    set((s) => ({ referencesLoading: { ...s.referencesLoading, [idx]: true } }));
    try {
      const data = await api.getReferences(idx, maxResults);
      set((s) => ({
        referencesData: { ...s.referencesData, [idx]: data },
        referencesLoading: { ...s.referencesLoading, [idx]: false },
      }));
    } catch {
      set((s) => ({ referencesLoading: { ...s.referencesLoading, [idx]: false } }));
    }
  },

  refreshPaper: async (idx) => {
    set((s) => ({ refreshLoading: { ...s.refreshLoading, [idx]: true } }));
    try {
      const res = await api.refreshPaper(idx);
      if (res.success && res.paper) {
        set((s) => {
          const papers = [...s.papers];
          papers[idx] = { ...papers[idx], ...res.paper as Paper };
          // Clear stale caches
          const dlStatuses = { ...s.dlStatuses };
          delete dlStatuses[idx];
          const citationsData = { ...s.citationsData };
          delete citationsData[idx];
          const referencesData = { ...s.referencesData };
          delete referencesData[idx];
          return { papers, dlStatuses, citationsData, referencesData, refreshLoading: { ...s.refreshLoading, [idx]: false } };
        });
      } else {
        set((s) => ({ refreshLoading: { ...s.refreshLoading, [idx]: false } }));
      }
    } catch {
      set((s) => ({ refreshLoading: { ...s.refreshLoading, [idx]: false } }));
    }
  },

  attachPdf: async (idx, file) => {
    try {
      const res = await api.attachPdf(idx, file);
      if (res.success && res.path) {
        set((s) => ({
          manualPdfPaths: { ...s.manualPdfPaths, [idx]: res.path! },
        }));
      }
    } catch (e) {
      console.error('Attach failed:', e);
    }
  },

  detachPdf: async (idx) => {
    try {
      await api.detachPdf(idx);
      set((s) => {
        const paths = { ...s.manualPdfPaths };
        delete paths[idx];
        return { manualPdfPaths: paths };
      });
    } catch { /* noop */ }
  },

  loadSessions: async () => {
    try {
      const sessions = await api.listSessions();
      set({ sessions });
    } catch { /* noop */ }
  },

  loadSession: async (name) => {
    try {
      const data = await api.loadSession(name);
      set({
        papers: data.papers as Paper[],
        lastQuery: data.query,
        selectedIndices: new Set(),
        dlStatuses: {},
        citationsData: {},
        referencesData: {},
      });
    } catch { /* noop */ }
  },

  saveSession: async (name) => {
    try {
      await api.saveSession(name);
      await get().loadSessions();
    } catch { /* noop */ }
  },

  deleteSession: async (name) => {
    try {
      await api.deleteSession(name);
      await get().loadSessions();
    } catch { /* noop */ }
  },

  updateSettings: async (s) => {
    try {
      const updated = await api.updateSettings(s);
      // Merge with existing settings to preserve fields not in response
      set((state) => ({ settings: { ...state.settings, ...updated } }));
    } catch { /* noop */ }
  },

  loadSettings: async () => {
    try {
      const loaded = await api.getSettings();
      // Merge with defaults to preserve frontend-only fields like proxy_mode
      set((state) => ({ settings: { ...state.settings, ...loaded } }));
    } catch { /* noop */ }
  },

  clearSearch: () => {
    set({
      papers: [],
      selectedIndices: new Set(),
      aiAnalysis: null,
      dlStatuses: {},
      citationsData: {},
      referencesData: {},
      lastQuery: '',
    });
  },

  exportMarkdown: async () => {
    const { selectedIndices, papers } = get();
    const indices = selectedIndices.size > 0 ? Array.from(selectedIndices) : papers.map((_, i) => i);
    try {
      const blob = await api.exportMarkdown(indices);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'papers_export.md';
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* noop */ }
  },

  autosave: async () => {
    try {
      await api.autosave();
    } catch { /* noop */ }
  },

  loadCurrentWorkspace: async () => {
    try {
      const data = await api.getCurrentWorkspace();
      if (data.papers && data.papers.length > 0) {
        const dlStatuses: Record<number, DlStatus> = {};
        for (const [k, v] of Object.entries(data.dl_statuses || {})) {
          dlStatuses[Number(k)] = { loading: false, status: v as string };
        }
        const manualPdfPaths: Record<number, string> = {};
        for (const [k, v] of Object.entries(data.manual_pdf_paths || {})) {
          manualPdfPaths[Number(k)] = v as string;
        }
        const citationsData: Record<number, CitationData> = {};
        for (const [k, v] of Object.entries(data.citations_data || {})) {
          const raw = v as Record<string, unknown>;
          citationsData[Number(k)] = {
            items: (raw.items ?? raw.citations ?? []) as CitationData['items'],
            total: (raw.total ?? raw.total_count ?? 0) as number,
            error: raw.error as string | undefined,
          };
        }
        const referencesData: Record<number, CitationData> = {};
        for (const [k, v] of Object.entries(data.references_data || {})) {
          const raw = v as Record<string, unknown>;
          referencesData[Number(k)] = {
            items: (raw.items ?? raw.references ?? []) as CitationData['items'],
            total: (raw.total ?? raw.total_count ?? 0) as number,
            error: raw.error as string | undefined,
          };
        }
        set({
          papers: data.papers as Paper[],
          lastQuery: data.last_query || '',
          searchMode: (data.search_mode as 'keyword' | 'ai') || 'keyword',
          aiAnalysis: data.ai_analysis as AIAnalysis | null,
          selectedIndices: new Set(data.selected || []),
          dlStatuses,
          manualPdfPaths,
          citationsData,
          referencesData,
        });
      }
    } catch (e) {
      console.error('Failed to load workspace:', e);
    }
  },

  translateText: async (key, text) => {
    set((s) => ({ translating: { ...s.translating, [key]: true } }));
    try {
      const res = await api.translateText(text);
      set((s) => ({
        translatedTexts: { ...s.translatedTexts, [key]: res.translated },
        translating: { ...s.translating, [key]: false },
      }));
    } catch {
      set((s) => ({ translating: { ...s.translating, [key]: false } }));
    }
  },

  // ── Toast ──
  toastMessage: '',
  showToast: (msg) => {
    set({ toastMessage: msg });
    setTimeout(() => set({ toastMessage: '' }), 3000);
  },

  // ── Projects ──
  projectsList: [],
  activeView: 'search',
  activeProject: null,
  chatLoading: false,

  loadProjects: async () => {
    try {
      const projects = await api.listProjects();
      set({ projectsList: projects });
    } catch { /* noop */ }
  },

  createProject: async (name) => {
    try {
      await api.createProject(name);
      await get().loadProjects();
    } catch { /* noop */ }
  },

  deleteProjectByName: async (name) => {
    try {
      await api.deleteProject(name);
      const active = get().activeProject;
      if (active?.name === name) {
        set({ activeProject: null, activeView: 'search' });
      }
      await get().loadProjects();
    } catch { /* noop */ }
  },

  openProject: async (name) => {
    try {
      const detail = await api.getProject(name);
      set({ activeProject: detail, activeView: 'project' });
    } catch { /* noop */ }
  },

  closeProject: () => {
    set({ activeView: 'search', activeProject: null });
  },

  addPapersToProject: async (name, indices) => {
    try {
      const res = await api.addPapersToProject(name, indices);
      get().showToast(`"${name}" 프로젝트에 ${res.message}`);
      if (get().activeProject?.name === name) {
        const detail = await api.getProject(name);
        set({ activeProject: detail });
      }
      await get().loadProjects();
    } catch { /* noop */ }
  },

  removePaperFromProject: async (idx) => {
    const proj = get().activeProject;
    if (!proj) return;
    try {
      await api.removePaperFromProject(proj.name, idx);
      const detail = await api.getProject(proj.name);
      set({ activeProject: detail });
      await get().loadProjects();
    } catch { /* noop */ }
  },

  sendChat: async (message, paperIndices) => {
    const proj = get().activeProject;
    if (!proj) return;
    // Optimistically add user message
    const userMsg: ChatMessage = { role: 'user', content: message };
    set((s) => ({
      activeProject: s.activeProject ? {
        ...s.activeProject,
        chat_history: [...s.activeProject.chat_history, userMsg],
      } : null,
      chatLoading: true,
    }));
    try {
      const langMap: Record<string, string> = { '한국어': 'ko', 'English': 'en', '日本語': 'ja', '中文': 'zh' };
      const lang = langMap[get().summaryLang] || 'ko';
      const reply = await api.sendProjectChat(proj.name, message, lang, paperIndices);
      set((s) => ({
        activeProject: s.activeProject ? {
          ...s.activeProject,
          chat_history: [...s.activeProject.chat_history, reply],
        } : null,
        chatLoading: false,
      }));
    } catch {
      set({ chatLoading: false });
    }
  },
}));
