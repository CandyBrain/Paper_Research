export interface Paper {
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  abstract: string | null;
  journal: string | null;
  url: string | null;
  is_oa: boolean;
  pdf_url: string | null;
  source: string;
  raw_id: string | null;
  summary: string | null;
}

export interface SearchResult {
  papers: Paper[];
  source: string;
  error: string | null;
  total_found: number;
}

export interface CiteItem {
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  abstract: string | null;
  journal: string | null;
  is_oa: boolean;
  pdf_url: string | null;
  source: string;
}

export interface CitationData {
  items: CiteItem[];
  total: number;
  error?: string;
}

export interface AIQuery {
  query: string;
  purpose?: string;
}

export interface AIAnalysis {
  research_summary: string;
  keywords: string[];
  queries: AIQuery[];
}

export interface SessionMeta {
  name: string;
  saved_at: string;
  query: string;
  paper_count: number;
  mode_label: string;
  filepath: string;
}

export interface ProjectMeta {
  name: string;
  created_at: string;
  paper_count: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ProjectDetail {
  name: string;
  papers: Paper[];
  chat_history: ChatMessage[];
}

export interface Settings {
  anthropic_api_key: string;
  scopus_api_key: string;
  core_api_key: string;
  springer_api_key: string;
  proxy_url: string;
  proxy_mode: string;
  download_dir: string;
  use_browser: boolean;
  // from GET /api/settings (read-only)
  has_anthropic_key?: boolean;
  has_scopus_key?: boolean;
  has_core_key?: boolean;
}
