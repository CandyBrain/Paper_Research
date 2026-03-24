import json

import streamlit as st
import streamlit.components.v1 as components
import asyncio
import threading
from pathlib import Path

from src.config import settings
from src.models import DatabaseSource, SearchRequest
from src.services.search import SearchOrchestrator
from src.services.summarizer import PaperSummarizer
from src.services.downloader import PaperDownloader
from src.services.query_generator import QueryGenerator
from src.services.session_manager import (
    save_session, load_session, list_sessions, delete_session,
    autosave, load_autosave,
)


# ── Helpers ──────────────────────────────────────────────────


def run_async(coro):
    """Run async coroutine in a separate thread to avoid Streamlit event loop conflicts."""
    result = [None]
    exception = [None]

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result[0] = loop.run_until_complete(coro)
        except Exception as e:
            exception[0] = e
        finally:
            loop.close()

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join()

    if exception[0]:
        raise exception[0]
    return result[0]


def pick_folder() -> str:
    """Open native folder picker dialog using tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(
            title="PDF 저장 폴더 선택",
            initialdir=str(Path.home()),
        )
        root.destroy()
        return folder or ""
    except Exception:
        return ""


def pick_folder_or_file() -> str:
    """Open native file picker dialog for PDF files."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        filepath = filedialog.askopenfilename(
            title="PDF 파일 선택",
            initialdir=str(Path.home()),
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        root.destroy()
        return filepath or ""
    except Exception:
        return ""


def translate_abstract(text: str, api_key: str) -> str:
    """Translate abstract to Korean using Claude."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                "다음 학술 논문 초록을 한국어로 번역해주세요. "
                "학술 용어는 적절히 번역하되, 필요한 경우 괄호 안에 영문 원어를 병기해주세요. "
                "번역문만 출력하세요.\n\n"
                f"{text}"
            ),
        }],
    )
    return response.content[0].text.strip()


def copy_button_html(text: str, key: str):
    """Render an HTML copy button that works inside Streamlit's iframe."""
    escaped = json.dumps(text)
    components.html(
        f"""
        <style>
            body {{ margin: 0; padding: 0; }}
            .copy-wrap {{
                display: flex;
                align-items: center;
                height: 32px;
            }}
            #copyBtn_{key} {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                cursor: pointer;
                font-size: 12px;
                color: #fff;
                white-space: nowrap;
                font-weight: 500;
                letter-spacing: 0.3px;
                transition: all 0.2s ease;
                box-shadow: 0 2px 4px rgba(102,126,234,0.25);
            }}
            #copyBtn_{key}:hover {{
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(102,126,234,0.35);
            }}
            #copyMsg_{key} {{
                color: #10b981;
                font-size: 13px;
                margin-left: 10px;
                opacity: 0;
                transition: opacity 0.3s;
                white-space: nowrap;
                font-weight: 500;
            }}
        </style>
        <div class="copy-wrap">
            <button id="copyBtn_{key}" onclick="doCopy_{key}()">Copy</button>
            <span id="copyMsg_{key}">Copied!</span>
        </div>
        <script>
        function doCopy_{key}() {{
            var text = {escaped};
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text).then(showMsg_{key}, fallback_{key});
            }} else {{
                fallback_{key}();
            }}
        }}
        function fallback_{key}() {{
            var ta = document.createElement('textarea');
            ta.value = {escaped};
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            try {{ document.execCommand('copy'); }} catch(e) {{}}
            document.body.removeChild(ta);
            showMsg_{key}();
        }}
        function showMsg_{key}() {{
            var msg = document.getElementById('copyMsg_{key}');
            msg.style.opacity = '1';
            setTimeout(function() {{ msg.style.opacity = '0'; }}, 2000);
        }}
        </script>
        """,
        height=38,
    )


def _collect_manual_pdfs() -> dict[int, str]:
    """Collect all manual_pdf_{i} entries from session state."""
    paths = {}
    for key, val in st.session_state.items():
        if key.startswith("manual_pdf_") and val:
            try:
                idx = int(key.replace("manual_pdf_", ""))
                paths[idx] = val
            except ValueError:
                pass
    return paths


def _collect_dl_statuses() -> dict[int, str]:
    """Collect all dl_status_{i} entries from session state."""
    statuses = {}
    for key, val in st.session_state.items():
        if key.startswith("dl_status_") and val:
            try:
                idx = int(key.replace("dl_status_", ""))
                statuses[idx] = val
            except ValueError:
                pass
    return statuses


def _collect_citations() -> dict[int, dict]:
    """Collect all citations_{i} entries from session state."""
    data = {}
    for key, val in st.session_state.items():
        if key.startswith("citations_") and isinstance(val, dict):
            try:
                idx = int(key.replace("citations_", ""))
                data[idx] = val
            except ValueError:
                pass
    return data


def _collect_references() -> dict[int, dict]:
    """Collect all references_{i} entries from session state."""
    data = {}
    for key, val in st.session_state.items():
        if key.startswith("references_") and isinstance(val, dict):
            try:
                idx = int(key.replace("references_", ""))
                data[idx] = val
            except ValueError:
                pass
    return data


def _clear_per_paper_state():
    """Clear all per-paper session state (citations, references, pdf links, etc.)."""
    keys_to_delete = [
        key for key in st.session_state
        if key.startswith((
            "citations_", "references_", "manual_pdf_", "dl_status_",
            "attach_expand_", "abstract_trans_", "abstract_show_trans_",
            "pdf_uploader_",
        ))
    ]
    for key in keys_to_delete:
        del st.session_state[key]


def do_autosave():
    """Auto-save current state to disk."""
    if st.session_state.all_papers:
        try:
            autosave(
                query=st.session_state.get("last_query", ""),
                search_results=st.session_state.search_results,
                all_papers=st.session_state.all_papers,
                selected=st.session_state.selected,
                dl_results=st.session_state.dl_results,
                ai_analysis=st.session_state.get("ai_analysis"),
                search_mode=st.session_state.get("last_search_mode", ""),
                manual_pdf_paths=_collect_manual_pdfs(),
                dl_statuses=_collect_dl_statuses(),
                citations_data=_collect_citations(),
                references_data=_collect_references(),
            )
        except Exception:
            pass


def restore_session(data: dict):
    """Restore session state from loaded data."""
    st.session_state.search_results = data.get("search_results", [])
    st.session_state.all_papers = data.get("all_papers", [])
    st.session_state.selected = data.get("selected", set())
    st.session_state.dl_results = data.get("dl_results", [])
    st.session_state.last_query = data.get("query", "")
    st.session_state.restored_query = data.get("query", "")
    st.session_state.ai_analysis = data.get("ai_analysis")
    st.session_state.last_search_mode = data.get("search_mode", "")

    # Restore manual PDF paths
    for idx, path in data.get("manual_pdf_paths", {}).items():
        st.session_state[f"manual_pdf_{idx}"] = path

    # Restore download statuses
    for idx, status in data.get("dl_statuses", {}).items():
        st.session_state[f"dl_status_{idx}"] = status

    # Restore citations
    for idx, cite_data in data.get("citations_data", {}).items():
        st.session_state[f"citations_{idx}"] = cite_data

    # Restore references
    for idx, ref_data in data.get("references_data", {}).items():
        st.session_state[f"references_{idx}"] = ref_data


# ── Custom CSS ───────────────────────────────────────────────

CUSTOM_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global ── */
.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Hero Header ── */
.hero-header {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    padding: 2.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    color: white;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(102,126,234,0.3) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-header h1 {
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.5px;
}
.hero-header p {
    font-size: 0.95rem;
    opacity: 0.8;
    margin: 0;
    font-weight: 300;
}

/* ── Step Indicator ── */
.step-indicator {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 1.5rem 0 2rem 0;
    padding: 0 1rem;
}
.step-item {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
}
.step-number {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 0.85rem;
    flex-shrink: 0;
    transition: all 0.3s ease;
}
.step-number.active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    box-shadow: 0 4px 12px rgba(102,126,234,0.35);
}
.step-number.inactive {
    background: #e5e7eb;
    color: #9ca3af;
}
.step-number.done {
    background: #10b981;
    color: white;
}
.step-label {
    font-size: 0.8rem;
    font-weight: 500;
    white-space: nowrap;
}
.step-label.active { color: #667eea; }
.step-label.inactive { color: #9ca3af; }
.step-label.done { color: #10b981; }
.step-line {
    flex: 1;
    height: 2px;
    background: #e5e7eb;
    margin: 0 8px;
}
.step-line.done { background: #10b981; }

/* ── Section Header ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 2rem 0 1rem 0;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid #f0f0f5;
}
.section-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    flex-shrink: 0;
}
.section-icon.search { background: linear-gradient(135deg, #667eea22, #764ba222); }
.section-icon.results { background: linear-gradient(135deg, #f093fb22, #f5576c22); }
.section-icon.ai { background: linear-gradient(135deg, #4facfe22, #00f2fe22); }
.section-icon.download { background: linear-gradient(135deg, #43e97b22, #38f9d722); }
.section-icon.export { background: linear-gradient(135deg, #fa709a22, #fee14022); }
.section-title {
    font-size: 1.3rem;
    font-weight: 600;
    color: #1f2937;
    letter-spacing: -0.3px;
}

/* ── Paper Card ── */
.paper-card {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.5rem;
    transition: all 0.2s ease;
    position: relative;
}
.paper-card:hover {
    border-color: #4f46e5;
    box-shadow: 0 4px 16px rgba(99,102,241,0.25);
    transform: translateY(-1px);
    background: #312e81;
}
.paper-card:hover .paper-title {
    color: #e0e7ff !important;
}
.paper-card:hover .paper-meta,
.paper-card:hover .paper-meta span,
.paper-card:hover .meta-item {
    color: #c7d2fe !important;
}
.paper-card:hover .doi-link {
    color: #a5b4fc !important;
}

/* ── Citation / Reference sub-cards ── */
.cite-ref-card {
    background: #1e1b4b !important;
    border: 1px solid #3730a3 !important;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
}
.cite-ref-card .cr-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #e0e7ff;
    line-height: 1.4;
    margin-bottom: 4px;
}
.cite-ref-card .cr-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    font-size: 0.75rem;
    color: #a5b4fc;
    align-items: center;
}
.cite-ref-card .doi-link {
    color: #93c5fd !important;
}
.cite-ref-card .badge-oa {
    background: #065f46 !important;
    color: #a7f3d0 !important;
}
.cite-ref-card .badge-closed {
    background: #7f1d1d !important;
    color: #fca5a5 !important;
}
.cite-ref-card .badge-source {
    background: #312e81 !important;
    color: #c7d2fe !important;
}
.cite-ref-card.ref-card {
    border-left: 3px solid #f59e0b !important;
}
.cite-ref-card.cite-card {
    border-left: 3px solid #6366f1 !important;
}

/* ── Paper Divider (between cards) ── */
.paper-divider {
    border: none;
    border-top: 1px dashed #c7d2fe;
    margin: 1.2rem 0;
}
.paper-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1f2937;
    line-height: 1.45;
    margin-bottom: 8px;
}
.paper-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    font-size: 0.8rem;
    color: #6b7280;
    margin-bottom: 6px;
}
.meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
}
.badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-oa {
    background: #d1fae5;
    color: #065f46;
}
.badge-closed {
    background: #fee2e2;
    color: #991b1b;
}
.badge-source {
    background: #ede9fe;
    color: #5b21b6;
}
.doi-link {
    font-size: 0.78rem;
    color: #6366f1;
    text-decoration: none;
    transition: color 0.2s;
}
.doi-link:hover {
    color: #4338ca;
    text-decoration: underline;
}

/* ── Stats Bar ── */
.stats-bar {
    display: flex;
    gap: 1rem;
    margin: 1rem 0;
}
.stat-card {
    flex: 1;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    text-align: center;
}
.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1e293b;
}
.stat-label {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}
.stat-card.purple { border-top: 3px solid #8b5cf6; }
.stat-card.blue { border-top: 3px solid #3b82f6; }
.stat-card.green { border-top: 3px solid #10b981; }
.stat-card.orange { border-top: 3px solid #f59e0b; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #1e1b4b !important;
}
section[data-testid="stSidebar"] * {
    color: #e0e7ff !important;
}
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 1.1rem;
    font-weight: 600;
    color: #a5b4fc !important;
    letter-spacing: -0.3px;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] select {
    background: #312e81 !important;
    color: #e0e7ff !important;
    border-color: #4338ca !important;
}
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder {
    color: #818cf8 !important;
}
section[data-testid="stSidebar"] .stSlider [data-testid="stThumbValue"],
section[data-testid="stSidebar"] .stSlider [data-testid="stTickBarMin"],
section[data-testid="stSidebar"] .stSlider [data-testid="stTickBarMax"] {
    color: #c7d2fe !important;
}
section[data-testid="stSidebar"] button {
    background: #4338ca !important;
    color: #ffffff !important;
    border: 1px solid #6366f1 !important;
}
section[data-testid="stSidebar"] button:hover {
    background: #4f46e5 !important;
}
section[data-testid="stSidebar"] .stDivider {
    border-color: #3730a3 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #312e81 !important;
    border-color: #3730a3 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] small {
    color: #a5b4fc !important;
}

/* ── All column layouts: tight gap ── */
div[data-testid="stHorizontalBlock"],
div[data-testid="column"],
.stColumns,
.row-widget {
    gap: 5px !important;
    column-gap: 5px !important;
}
div[data-testid="stHorizontalBlock"] > div,
div[data-testid="stColumn"],
div[data-testid="column"] {
    padding-left: 0 !important;
    padding-right: 0 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}
/* Force via wildcard */
section.main div[style*="gap"] {
    gap: 5px !important;
    column-gap: 5px !important;
}

/* ── Buttons ── */
.stButton > button {
    padding: 0.35rem 0.8rem !important;
    font-size: 0.78rem !important;
    white-space: nowrap !important;
    min-height: 0 !important;
    line-height: 1.3 !important;
    height: 38px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: auto !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1.5rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 12px rgba(102,126,234,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(102,126,234,0.35) !important;
}

/* ── AI Analysis Box ── */
.ai-analysis-box {
    background: #1e1b4b;
    border: 1px solid #3730a3;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin: 1rem 0;
    color: #c7d2fe;
}
.ai-analysis-box h4 {
    color: #a5b4fc;
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
}
.ai-analysis-box p {
    color: #e0e7ff;
}
.ai-analysis-box strong {
    color: #a5b4fc;
}

/* ── Download Result ── */
.dl-success {
    background: #065f46;
    color: #d1fae5;
    border-left: 4px solid #10b981;
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
}
.dl-success strong { color: #a7f3d0; }
.dl-fail {
    background: #7f1d1d;
    color: #fecaca;
    border-left: 4px solid #ef4444;
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
}
.dl-fail strong { color: #fca5a5; }
.dl-fail em { color: #fde68a; }

/* ── Keyword Tag ── */
.keyword-tag {
    display: inline-block;
    background: #312e81;
    border: 1px solid #4f46e5;
    color: #c7d2fe;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    margin: 2px 4px 2px 0;
}

/* ── Multiselect Tag (selected DB) ── */
span[data-baseweb="tag"] {
    background-color: #0ea5e9 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
}
span[data-baseweb="tag"] > span[role="presentation"] {
    color: #ffffff !important;
}
span[data-baseweb="tag"]:nth-child(even) {
    background-color: #10b981 !important;
}
span[data-baseweb="tag"]:hover {
    opacity: 0.85 !important;
}
/* Tag close (x) button */
span[data-baseweb="tag"] [data-baseweb="tag-close-button"],
span[data-baseweb="tag"] svg {
    color: #ffffff !important;
    fill: #ffffff !important;
}

/* ── Hide default Streamlit branding ── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* ── Expander styling ── */
.streamlit-expanderHeader {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #4b5563 !important;
    border-radius: 8px !important;
}

/* ── AI Summary content: smaller headings ── */
[data-testid="stExpander"] p strong {
    font-size: 0.85rem !important;
}
[data-testid="stExpander"] h1 {
    font-size: 1rem !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] h2 {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] h3 {
    font-size: 0.9rem !important;
    font-weight: 600 !important;
}

/* ── Toast / Alert improvements ── */
.stAlert {
    border-radius: 10px !important;
}

/* ── Dark mode adaptations ── */
@media (prefers-color-scheme: dark) {
    .paper-card {
        background: #1e1e2e;
        border-color: #313244;
    }
    .paper-card:hover {
        border-color: #585b70;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }
    .paper-title { color: #cdd6f4; }
    .paper-meta { color: #a6adc8; }
    .section-title { color: #cdd6f4; }
    .stat-card {
        background: #1e1e2e;
        border-color: #313244;
    }
    .stat-value { color: #cdd6f4; }
    .stat-label { color: #a6adc8; }
}
</style>
"""


def render_hero():
    """Render the hero header."""
    st.markdown("""
    <div class="hero-header">
        <h1>Paper Research Platform</h1>
        <p>Academic Paper Search &middot; AI Summary &middot; Download &middot; Export</p>
    </div>
    """, unsafe_allow_html=True)


def render_step_indicator(current_step: int):
    """Render workflow step indicator. Steps: 1=Search, 2=Results, 3=Summary, 4=Download, 5=Export"""
    steps = [
        ("1", "Search"),
        ("2", "Results"),
        ("3", "AI Summary"),
        ("4", "Download"),
        ("5", "Export"),
    ]
    html_parts = ['<div class="step-indicator">']
    for i, (num, label) in enumerate(steps):
        step_num = i + 1
        if step_num < current_step:
            state = "done"
            display = "✓"
        elif step_num == current_step:
            state = "active"
            display = num
        else:
            state = "inactive"
            display = num

        html_parts.append(f"""
            <div class="step-item">
                <div class="step-number {state}">{display}</div>
                <span class="step-label {state}">{label}</span>
            </div>
        """)
        if i < len(steps) - 1:
            line_state = "done" if step_num < current_step else ""
            html_parts.append(f'<div class="step-line {line_state}"></div>')

    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_section_header(icon: str, title: str, icon_class: str):
    """Render a styled section header."""
    st.markdown(f"""
    <div class="section-header">
        <div class="section-icon {icon_class}">{icon}</div>
        <span class="section-title">{title}</span>
    </div>
    """, unsafe_allow_html=True)


def render_paper_card(i: int, paper):
    """Render a single paper as a styled card."""
    oa_badge = '<span class="badge badge-oa">Open Access</span>' if paper.is_oa else '<span class="badge badge-closed">Closed</span>'
    year_str = str(paper.year) if paper.year else "N/A"
    source_badge = f'<span class="badge badge-source">{paper.source.value}</span>'
    doi_html = f'<a class="doi-link" href="https://doi.org/{paper.doi}" target="_blank">DOI: {paper.doi}</a>' if paper.doi else ""

    st.markdown(f"""
    <div class="paper-card">
        <div class="paper-title">{i+1}. {paper.title}</div>
        <div class="paper-meta">
            <span class="meta-item">{paper.display_authors}</span>
            <span class="meta-item">{year_str}</span>
            <span class="meta-item">{paper.journal or 'N/A'}</span>
            {oa_badge} {source_badge}
        </div>
        {f'<div style="margin-top:6px">{doi_html}</div>' if doi_html else ''}
    </div>
    """, unsafe_allow_html=True)


def render_stats_bar(total: int, selected: int, oa_count: int, sources: int):
    """Render statistics cards."""
    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-card purple">
            <div class="stat-value">{total}</div>
            <div class="stat-label">Total Papers</div>
        </div>
        <div class="stat-card blue">
            <div class="stat-value">{selected}</div>
            <div class="stat-label">Selected</div>
        </div>
        <div class="stat-card green">
            <div class="stat-value">{oa_count}</div>
            <div class="stat-label">Open Access</div>
        </div>
        <div class="stat-card orange">
            <div class="stat-value">{sources}</div>
            <div class="stat-label">Sources</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Paper Research",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Session State Init ───────────────────────────────────────
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.search_results = []
    st.session_state.all_papers = []
    st.session_state.selected = set()
    st.session_state.download_dir = str(Path.cwd() / "papers")
    st.session_state.dl_results = []
    st.session_state.last_query = ""
    st.session_state.restored_query = ""
    st.session_state.ai_analysis = None
    st.session_state.last_search_mode = ""

    # Try to restore autosave on first load
    auto_data = load_autosave()
    if auto_data and auto_data.get("all_papers"):
        restore_session(auto_data)
        st.toast("이전 세션이 자동 복원되었습니다.", icon="🔄")

# ── Hero ─────────────────────────────────────────────────────
render_hero()

# Determine current step
current_step = 1
if st.session_state.all_papers:
    current_step = 2
    if any(p.summary for p in st.session_state.all_papers):
        current_step = 3
    if st.session_state.dl_results:
        current_step = 4

render_step_indicator(current_step)

# ── Sidebar: Configuration ───────────────────────────────────
with st.sidebar:
    st.markdown("## Settings")

    # API Keys
    with st.expander("API Keys", expanded=False):
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=settings.anthropic_api_key,
            type="password",
            help="Claude 요약에 필요",
        )
        scopus_key = st.text_input(
            "Scopus API Key",
            value=settings.scopus_api_key,
            type="password",
            help="Scopus 검색에 필요",
        )
        core_key = st.text_input(
            "CORE API Key",
            value=settings.core_api_key,
            type="password",
            help="CORE 검색에 필요 (무료 발급)",
        )

    # Proxy
    with st.expander("Proxy (교외접속)", expanded=False):
        proxy_url = st.text_input(
            "Proxy URL",
            value=settings.proxy_url,
            placeholder="https://libproxy.university.ac.kr/login?url=",
            help="교외접속 프록시 주소",
        )
        if proxy_url:
            from src.services.downloader import ProxyHelper
            ph = ProxyHelper(proxy_url)
            mode_labels = {"prefix": "URL 접두사", "ezproxy": "EZProxy 도메인 치환", "none": "없음"}
            st.caption(f"감지된 모드: **{mode_labels.get(ph.mode, ph.mode)}**")

    # Download directory
    with st.expander("Download Folder", expanded=False):
        col_path, col_browse = st.columns([3, 1])
        with col_path:
            download_dir = st.text_input(
                "저장 경로",
                value=st.session_state.download_dir,
                key="download_dir_input",
                label_visibility="collapsed",
            )
        with col_browse:
            if st.button("📁", help="폴더 선택"):
                picked = pick_folder()
                if picked:
                    st.session_state.download_dir = picked
                    st.rerun()

        if download_dir != st.session_state.download_dir:
            st.session_state.download_dir = download_dir

    # Max results
    max_results = st.slider("DB당 최대 결과 수", 5, 30, 10)

    # ── Session Management ───────────────────────────────────
    st.divider()
    st.markdown("## Sessions")

    # Save session
    session_name = st.text_input("세션 이름", placeholder="예: my_research_session")
    if st.button("Save Session", use_container_width=True):
        if not session_name.strip():
            st.warning("세션 이름을 입력해주세요.")
        elif not st.session_state.all_papers:
            st.warning("저장할 검색 결과가 없습니다.")
        else:
            filepath = save_session(
                name=session_name.strip(),
                query=st.session_state.get("last_query", ""),
                search_results=st.session_state.search_results,
                all_papers=st.session_state.all_papers,
                selected=st.session_state.selected,
                dl_results=st.session_state.dl_results,
                ai_analysis=st.session_state.get("ai_analysis"),
                search_mode=st.session_state.get("last_search_mode", ""),
                manual_pdf_paths=_collect_manual_pdfs(),
                dl_statuses=_collect_dl_statuses(),
                citations_data=_collect_citations(),
                references_data=_collect_references(),
            )
            st.success(f"Saved: {filepath.name}")

    # Load session
    saved_sessions = list_sessions()
    display_sessions = [s for s in saved_sessions if s["name"] != "_autosave"]

    if display_sessions:
        st.caption("Saved Sessions:")
        for sess in display_sessions:
            col_name, col_load, col_del = st.columns([3, 1, 1])
            with col_name:
                st.caption(
                    f"**{sess['name']}**  \n"
                    f"{sess['paper_count']} papers · {sess['saved_at'][:10]}"
                )
            with col_load:
                if st.button("📂", key=f"load_{sess['name']}", help="불러오기"):
                    data = load_session(sess["filepath"])
                    restore_session(data)
                    st.toast(f"Session '{sess['name']}' restored", icon="📂")
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{sess['name']}", help="삭제"):
                    delete_session(sess["filepath"])
                    st.toast(f"Session '{sess['name']}' deleted", icon="🗑️")
                    st.rerun()

# ── Main: Search ─────────────────────────────────────────────
render_section_header("🔍", "Search", "search")

search_mode = st.radio(
    "검색 방법",
    ["Keyword Search", "AI Research Search"],
    horizontal=True,
    help="Keyword: 직접 키워드 입력 | AI: 연구 설명을 입력하면 AI가 키워드를 생성하여 검색",
)

# DB selection (shared)
db_options = {
    DatabaseSource.OPENALEX: "OpenAlex (키 불필요)",
    DatabaseSource.PUBMED: "PubMed (키 불필요)",
    DatabaseSource.SEMANTIC_SCHOLAR: "Semantic Scholar (키 불필요)",
    DatabaseSource.CORE: "CORE (API 키 필요)",
    DatabaseSource.SCOPUS: "Scopus (API 키 필요)",
}

selected_dbs = st.multiselect(
    "검색할 DB 선택",
    options=list(db_options.keys()),
    default=[DatabaseSource.OPENALEX, DatabaseSource.PUBMED, DatabaseSource.SEMANTIC_SCHOLAR],
    format_func=lambda x: db_options[x],
)

if DatabaseSource.SCOPUS in selected_dbs and not scopus_key:
    st.warning("Scopus를 선택하셨지만 API Key가 입력되지 않았습니다.")
if DatabaseSource.CORE in selected_dbs and not core_key:
    st.warning("CORE를 선택하셨지만 API Key가 입력되지 않았습니다.")

# ── Mode A: Keyword Search ──
if search_mode == "Keyword Search":
    default_query = st.session_state.get("restored_query", "")
    query = st.text_area(
        "검색 키워드",
        value=default_query,
        height=100,
        placeholder='예: "chamber equivalence" OR "environmental uniformity" AND "growth chamber"',
    )

    if st.button("Search", type="primary", use_container_width=True, key="search_keyword"):
        if not query.strip():
            st.error("검색 키워드를 입력해주세요.")
        elif not selected_dbs:
            st.error("최소 하나의 DB를 선택해주세요.")
        else:
            api_keys = {"scopus": scopus_key, "core": core_key}
            orchestrator = SearchOrchestrator(api_keys=api_keys, proxy_url=proxy_url)
            request = SearchRequest(
                query=query.strip(),
                databases=selected_dbs,
                max_results_per_db=max_results,
            )

            with st.spinner("Searching across selected databases..."):
                results = run_async(orchestrator.search_all(request))

            _clear_per_paper_state()
            st.session_state.search_results = results
            all_papers = SearchOrchestrator.deduplicate(results)
            st.session_state.all_papers = all_papers
            st.session_state.selected = set()
            st.session_state.dl_results = []
            st.session_state.last_query = query.strip()
            st.session_state.ai_analysis = None
            st.session_state.last_search_mode = "keyword"
            do_autosave()

            for r in results:
                if r.error:
                    st.error(f"{r.source.value}: {r.error}")
                else:
                    st.success(f"{r.source.value}: {len(r.papers)} papers found (of {r.total_found} total)")

            st.info(f"**{len(all_papers)}** unique papers after deduplication")

# ── Mode B: AI Research Description Search ──
else:
    query = ""

    if not anthropic_key:
        st.warning("AI 검색을 사용하려면 사이드바에서 Anthropic API Key를 입력해주세요.")

    research_desc = st.text_area(
        "연구 주제 설명",
        height=150,
        placeholder=(
            "예: 통제된 환경(식물 생장 챔버 등)을 병렬로 운용할 때 챔버 간 환경 동등성을 "
            "어떻게 정의하고 검증하는지 연구하고 있습니다."
        ),
    )

    if st.button(
        "AI Search",
        type="primary",
        use_container_width=True,
        disabled=not anthropic_key or not research_desc.strip(),
        key="search_ai",
    ):
        if not selected_dbs:
            st.error("최소 하나의 DB를 선택해주세요.")
        else:
            with st.spinner("AI가 연구 주제를 분석하고 검색 키워드를 생성 중..."):
                generator = QueryGenerator(api_key=anthropic_key)
                ai_result = generator.generate_queries(research_desc.strip(), selected_dbs)

            # Display AI analysis
            keywords = ai_result.get("keywords", [])
            queries = ai_result.get("queries", [])

            st.markdown(f"""
            <div class="ai-analysis-box">
                <h4>AI Analysis</h4>
                <p><strong>연구 요약:</strong> {ai_result.get('research_summary', 'N/A')}</p>
                <p><strong>키워드:</strong> {''.join(f'<span class="keyword-tag">{kw}</span>' for kw in keywords)}</p>
            </div>
            """, unsafe_allow_html=True)

            if queries:
                st.markdown("**생성된 검색 쿼리:**")
                for i, q in enumerate(queries):
                    st.caption(f"  {i+1}. `{q['query']}`  — {q.get('purpose', '')}")

            with st.spinner(f"{len(queries)}개 쿼리로 검색 중..."):
                api_keys = {"scopus": scopus_key, "core": core_key}
                orchestrator = SearchOrchestrator(api_keys=api_keys, proxy_url=proxy_url)

                all_results = []
                for q in queries:
                    request = SearchRequest(
                        query=q["query"],
                        databases=selected_dbs,
                        max_results_per_db=max_results,
                    )
                    results = run_async(orchestrator.search_all(request))
                    all_results.extend(results)

            all_papers = SearchOrchestrator.deduplicate(all_results)

            _clear_per_paper_state()
            st.session_state.search_results = all_results
            st.session_state.all_papers = all_papers
            st.session_state.selected = set()
            st.session_state.dl_results = []
            st.session_state.last_query = research_desc.strip()
            st.session_state.ai_analysis = ai_result
            st.session_state.last_search_mode = "ai"
            query = research_desc.strip()
            do_autosave()

            db_counts = {}
            db_errors = {}
            for r in all_results:
                db_name = r.source.value
                if r.error:
                    db_errors[db_name] = r.error
                else:
                    db_counts[db_name] = db_counts.get(db_name, 0) + len(r.papers)

            for db_name, count in db_counts.items():
                st.success(f"{db_name}: {count} papers ({len(queries)} queries)")
            for db_name, error in db_errors.items():
                if db_name not in db_counts:
                    st.error(f"{db_name}: {error}")

            st.info(f"**{len(all_papers)}** unique papers after deduplication")

# ── Display AI Analysis (persistent from session state) ──────
if st.session_state.get("ai_analysis") and st.session_state.get("last_search_mode") == "ai":
    ai_data = st.session_state.ai_analysis
    with st.expander("AI Analysis Details", expanded=False):
        keywords = ai_data.get("keywords", [])
        st.markdown(f"""
        <div class="ai-analysis-box">
            <h4>AI Analysis</h4>
            <p><strong>연구 요약:</strong> {ai_data.get('research_summary', 'N/A')}</p>
            <p><strong>키워드:</strong> {''.join(f'<span class="keyword-tag">{kw}</span>' for kw in keywords)}</p>
        </div>
        """, unsafe_allow_html=True)
        queries = ai_data.get("queries", [])
        if queries:
            for i, q in enumerate(queries):
                st.caption(f"  {i+1}. `{q['query']}`  — {q.get('purpose', '')}")

# ── Main: Results ────────────────────────────────────────────
if st.session_state.all_papers:
    render_section_header("📄", "Search Results", "results")

    papers = st.session_state.all_papers

    # Stats bar
    oa_count = sum(1 for p in papers if p.is_oa)
    sources_used = len(set(p.source.value for p in papers))
    render_stats_bar(len(papers), len(st.session_state.selected), oa_count, sources_used)

    # Select all / none
    col1, col2, col_spacer = st.columns([1, 1, 4])
    with col1:
        if st.button("Select All", use_container_width=True):
            st.session_state.selected = set(range(len(papers)))
            st.rerun()
    with col2:
        if st.button("Deselect All", use_container_width=True):
            st.session_state.selected = set()
            st.rerun()

    # Summary language selector (above paper list)
    st.selectbox(
        "AI 요약 언어",
        ["한국어", "English"],
        index=0,
        key="summary_lang",
    )

    # Paper list
    for i, paper in enumerate(papers):
        col_check, col_info = st.columns([0.3, 9.7])

        with col_check:
            checked = st.checkbox(
                "sel",
                value=i in st.session_state.selected,
                key=f"paper_{i}",
                label_visibility="hidden",
            )
            if checked:
                st.session_state.selected.add(i)
            else:
                st.session_state.selected.discard(i)

        with col_info:
            render_paper_card(i, paper)

            # ── Check if PDF exists (auto-detect) ──
            from src.services.summarizer import find_downloaded_pdf
            manual_pdf_key = f"manual_pdf_{i}"
            manual_path = st.session_state.get(manual_pdf_key, "")
            detected_pdf = find_downloaded_pdf(
                paper,
                st.session_state.download_dir,
                manual_path=manual_path,
            )

            dl_status_key = f"dl_status_{i}"
            has_summary = bool(paper.summary)
            dl_status = st.session_state.get(dl_status_key)

            # Show PDF status
            if detected_pdf:
                pdf_name = Path(detected_pdf).name
                pdf_status_col, pdf_unlink_col, _pdf_sp = st.columns([4, 1, 10], gap="small")
                with pdf_status_col:
                    st.markdown(f"""
                    <div class="dl-success">
                        📄 PDF 연결됨: <strong>{pdf_name}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                with pdf_unlink_col:
                    if st.button("❌ 해제", key=f"unlink_btn_{i}"):
                        if manual_pdf_key in st.session_state:
                            del st.session_state[manual_pdf_key]
                        if dl_status_key in st.session_state:
                            del st.session_state[dl_status_key]
                        do_autosave()
                        st.toast(f"PDF 연결 해제: {pdf_name}", icon="❌")
                        st.rerun()

            # ── Action buttons row ──
            btn_dl, btn_sum, btn_cite, btn_ref, btn_attach = st.columns(5)
            with btn_dl:
                if detected_pdf and not (dl_status and dl_status.startswith("fail:")):
                    st.button("✅ Downloaded", key=f"dl_btn_{i}", disabled=True)
                else:
                    if st.button("⬇️ Download", key=f"dl_btn_{i}"):
                        output_path = Path(st.session_state.download_dir)
                        output_path.mkdir(parents=True, exist_ok=True)
                        downloader = PaperDownloader(
                            email=settings.unpaywall_email, proxy_url=proxy_url,
                            elsevier_api_key=settings.scopus_api_key,
                            springer_api_key=getattr(settings, 'springer_api_key', ''),
                        )

                        async def _download_one(p, out):
                            return await downloader.download_pdf(p, out)

                        with st.spinner("Downloading..."):
                            try:
                                success, msg = run_async(_download_one(paper, output_path))
                            except Exception as e:
                                success, msg = False, f"Error: {str(e)}"

                        if success:
                            st.session_state[dl_status_key] = "success"
                            st.toast(f"Downloaded: {paper.title[:40]}...", icon="✅")
                        else:
                            reason = msg.split("\n")[0]
                            st.session_state[dl_status_key] = f"fail:{reason}"
                            st.toast(f"Failed: {reason[:50]}", icon="❌")
                        do_autosave()
                        st.rerun()

            with btn_sum:
                summary_label = "🔄 Re-summarize" if has_summary else "🤖 AI Summary"
                if not detected_pdf and not has_summary:
                    summary_label = "🤖 Summary (초록)"
                if st.button(
                    summary_label,
                    key=f"summarize_btn_{i}",
                    disabled=not anthropic_key,
                ):
                    # Re-read manual_path from session state (may have been updated)
                    current_manual = st.session_state.get(manual_pdf_key, "")
                    current_pdf = find_downloaded_pdf(
                        paper, st.session_state.download_dir, manual_path=current_manual
                    )
                    lang_code = "ko" if st.session_state.get("summary_lang", "한국어") == "한국어" else "en"
                    summarizer = PaperSummarizer(api_key=anthropic_key)
                    spinner_msg = f"PDF 전문 분석 중... ({Path(current_pdf).name})" if current_pdf else "초록 기반 요약 중..."
                    with st.spinner(spinner_msg):
                        try:
                            summary_text = summarizer.summarize_paper(
                                paper,
                                language=lang_code,
                                download_dir=st.session_state.download_dir,
                                manual_path=current_manual,
                            )
                            # Directly update in session state list
                            st.session_state.all_papers[i].summary = summary_text
                        except Exception as e:
                            st.session_state.all_papers[i].summary = f"Summary failed: {str(e)}"
                    do_autosave()
                    st.rerun()

            with btn_cite:
                cite_key = f"citations_{i}"
                has_citations = cite_key in st.session_state
                if st.button(
                    f"📚 Citations" + (f" ({len(st.session_state[cite_key]['items'])})" if has_citations else ""),
                    key=f"cite_btn_{i}",
                ):
                    from src.services.citations import fetch_all_citations
                    with st.spinner("인용 논문 검색 중..."):
                        try:
                            citations, total = run_async(fetch_all_citations(paper, max_results=20))
                            st.session_state[cite_key] = {
                                "items": citations,
                                "total": total,
                            }
                        except Exception as e:
                            st.session_state[cite_key] = {
                                "items": [],
                                "total": 0,
                                "error": str(e),
                            }
                    do_autosave()
                    st.rerun()

            with btn_ref:
                ref_key = f"references_{i}"
                has_refs = ref_key in st.session_state
                if st.button(
                    f"📖 References" + (f" ({len(st.session_state[ref_key]['items'])})" if has_refs else ""),
                    key=f"ref_btn_{i}",
                ):
                    from src.services.citations import fetch_all_references
                    with st.spinner("참고 문헌 검색 중..."):
                        try:
                            refs, total = run_async(fetch_all_references(paper, max_results=50))
                            st.session_state[ref_key] = {
                                "items": refs,
                                "total": total,
                            }
                        except Exception as e:
                            st.session_state[ref_key] = {
                                "items": [],
                                "total": 0,
                                "error": str(e),
                            }
                    do_autosave()
                    st.rerun()

            with btn_attach:
                attach_expand_key = f"attach_expand_{i}"
                if st.button(
                    "📎 PDF 연결",
                    key=f"attach_btn_{i}",
                    help="수동 다운로드한 PDF를 이 논문에 연결",
                ):
                    st.session_state[attach_expand_key] = not st.session_state.get(attach_expand_key, False)
                    st.rerun()

            # PDF attach file uploader (shown when toggled)
            if st.session_state.get(f"attach_expand_{i}", False):
                uploaded = st.file_uploader(
                    "PDF 파일 선택",
                    type=["pdf"],
                    key=f"pdf_uploader_{i}",
                    label_visibility="collapsed",
                )
                if uploaded is not None:
                    # Save uploaded file to download dir
                    save_dir = Path(st.session_state.download_dir)
                    save_dir.mkdir(parents=True, exist_ok=True)
                    save_path = save_dir / uploaded.name
                    save_path.write_bytes(uploaded.getvalue())
                    st.session_state[manual_pdf_key] = str(save_path)
                    st.session_state[f"attach_expand_{i}"] = False
                    do_autosave()
                    st.toast(f"PDF 연결됨: {uploaded.name}", icon="📎")
                    st.rerun()

            # Download failure message
            if dl_status and dl_status.startswith("fail:") and not detected_pdf:
                fail_reason = dl_status[5:]
                from src.services.downloader import ProxyHelper
                proxy_helper = ProxyHelper(proxy_url)
                has_proxy = proxy_helper.mode != "none"

                st.markdown(f"""
                <div class="dl-fail">
                    <em>{fail_reason}</em>
                </div>
                """, unsafe_allow_html=True)
                if paper.doi:
                    doi_url = f"https://doi.org/{paper.doi}"
                    if has_proxy:
                        proxied_url = proxy_helper.make_doi_link(paper.doi)
                        st.markdown(f"[교외접속으로 열기]({proxied_url})  |  [직접 열기]({doi_url})")
                    else:
                        st.markdown(f"[논문 페이지 열기]({doi_url})")

            # ── Abstract expander ──
            with st.expander("Abstract"):
                abstract_text = paper.abstract or "초록 없음"
                trans_key = f"abstract_trans_{i}"
                show_trans_key = f"abstract_show_trans_{i}"

                is_translated = st.session_state.get(show_trans_key, False)
                display_text = st.session_state.get(trans_key, abstract_text) if is_translated else abstract_text

                btn_col, copy_col, spacer = st.columns([1, 2, 5])
                with btn_col:
                    if is_translated:
                        if st.button("Original", key=f"trans_btn_{i}"):
                            st.session_state[show_trans_key] = False
                            st.rerun()
                    else:
                        if st.button(
                            "Translate", key=f"trans_btn_{i}",
                            disabled=not anthropic_key or not paper.abstract,
                        ):
                            if trans_key not in st.session_state:
                                with st.spinner("Translating..."):
                                    translated = translate_abstract(abstract_text, anthropic_key)
                                    st.session_state[trans_key] = translated
                            st.session_state[show_trans_key] = True
                            st.rerun()
                with copy_col:
                    copy_button_html(display_text, f"abs_{i}")

                st.write(display_text)

            # ── AI Summary expander ──
            if paper.summary:
                with st.expander("AI Summary", expanded=False):
                    st.markdown(paper.summary)

            # ── Citations expander ──
            cite_key = f"citations_{i}"
            if cite_key in st.session_state:
                cite_data = st.session_state[cite_key]
                cite_items = cite_data.get("items", [])
                cite_total = cite_data.get("total", 0)
                cite_error = cite_data.get("error")

                with st.expander(
                    f"📚 Citing Papers ({len(cite_items)} shown / {cite_total} total)",
                    expanded=False,
                ):
                    if cite_error:
                        st.error(f"Citation 조회 실패: {cite_error}")
                    elif not cite_items:
                        st.info("인용 논문이 없거나 조회할 수 없습니다.")
                    else:
                        for ci, cite in enumerate(cite_items):
                            c_authors = cite.get("authors", [])
                            if len(c_authors) > 3:
                                c_author_str = f"{c_authors[0]} et al."
                            elif c_authors:
                                c_author_str = ", ".join(c_authors)
                            else:
                                c_author_str = "Unknown"

                            c_year = cite.get("year") or "N/A"
                            c_journal = cite.get("journal") or ""
                            c_doi = cite.get("doi")
                            c_oa = cite.get("is_oa", False)
                            c_source = cite.get("source", "")

                            oa_badge = '<span class="badge badge-oa">OA</span>' if c_oa else '<span class="badge badge-closed">Closed</span>'
                            doi_html = f' · <a class="doi-link" href="https://doi.org/{c_doi}" target="_blank">{c_doi}</a>' if c_doi else ""

                            st.markdown(f"""
                            <div class="cite-ref-card cite-card">
                                <div class="cr-title">{ci+1}. {cite['title']}</div>
                                <div class="cr-meta">
                                    <span>{c_author_str}</span>
                                    <span>{c_year}</span>
                                    <span>{c_journal}</span>
                                    {oa_badge}
                                    <span class="badge badge-source">{c_source}</span>
                                </div>
                                {f'<div style="margin-top:4px">{doi_html}</div>' if doi_html else ''}
                            </div>
                            """, unsafe_allow_html=True)

                            # Show abstract if available
                            if cite.get("abstract"):
                                with st.expander(f"Abstract #{ci+1}", expanded=False):
                                    st.write(cite["abstract"])

            # ── References expander ──
            ref_key = f"references_{i}"
            if ref_key in st.session_state:
                ref_data = st.session_state[ref_key]
                ref_items = ref_data.get("items", [])
                ref_total = ref_data.get("total", 0)
                ref_error = ref_data.get("error")

                with st.expander(
                    f"📖 References ({len(ref_items)} shown / {ref_total} total)",
                    expanded=False,
                ):
                    if ref_error:
                        st.error(f"Reference 조회 실패: {ref_error}")
                    elif not ref_items:
                        st.info("참고 문헌 정보가 없거나 조회할 수 없습니다.")
                    else:
                        for ri, ref in enumerate(ref_items):
                            r_authors = ref.get("authors", [])
                            if len(r_authors) > 3:
                                r_author_str = f"{r_authors[0]} et al."
                            elif r_authors:
                                r_author_str = ", ".join(r_authors)
                            else:
                                r_author_str = "Unknown"

                            r_year = ref.get("year") or "N/A"
                            r_journal = ref.get("journal") or ""
                            r_doi = ref.get("doi")
                            r_oa = ref.get("is_oa", False)
                            r_source = ref.get("source", "")

                            oa_badge = '<span class="badge badge-oa">OA</span>' if r_oa else '<span class="badge badge-closed">Closed</span>'
                            doi_html = f' · <a class="doi-link" href="https://doi.org/{r_doi}" target="_blank">{r_doi}</a>' if r_doi else ""

                            st.markdown(f"""
                            <div class="cite-ref-card ref-card">
                                <div class="cr-title">{ri+1}. {ref['title']}</div>
                                <div class="cr-meta">
                                    <span>{r_author_str}</span>
                                    <span>{r_year}</span>
                                    <span>{r_journal}</span>
                                    {oa_badge}
                                    <span class="badge badge-source">{r_source}</span>
                                </div>
                                {f'<div style="margin-top:4px">{doi_html}</div>' if doi_html else ''}
                            </div>
                            """, unsafe_allow_html=True)

                            if ref.get("abstract"):
                                with st.expander(f"Abstract #{ri+1}", expanded=False):
                                    st.write(ref["abstract"])

            # ── Divider between paper cards ──
            st.markdown('<hr class="paper-divider">', unsafe_allow_html=True)

    selected_count = len(st.session_state.selected)

    # ── Export ────────────────────────────────────────────────
    render_section_header("📤", "Export", "export")

    if st.button("Export to Markdown", type="primary", use_container_width=True):
        selected_papers = [papers[i] for i in sorted(st.session_state.selected)]
        if not selected_papers:
            selected_papers = papers

        md_lines = ["# Paper Search Results\n"]
        md_lines.append(f"**Query**: {st.session_state.get('last_query', query)}\n")
        md_lines.append(f"**Databases**: {', '.join(db.value for db in selected_dbs)}\n")
        md_lines.append(f"**Total**: {len(selected_papers)} papers\n")
        md_lines.append("---\n")

        for i, p in enumerate(selected_papers):
            oa = "Yes" if p.is_oa else "No"
            md_lines.append(f"### {i+1}. {p.title}")
            md_lines.append(f"- **Authors**: {p.display_authors}")
            md_lines.append(f"- **Year**: {p.year or 'N/A'}")
            md_lines.append(f"- **Journal**: {p.journal or 'N/A'}")
            md_lines.append(f"- **DOI**: {p.doi or 'N/A'}")
            md_lines.append(f"- **OA**: {oa}")
            md_lines.append(f"- **Source**: {p.source.value}")
            if p.abstract:
                md_lines.append(f"\n**Abstract**: {p.abstract[:500]}...")
            if p.summary:
                md_lines.append(f"\n**AI Summary**:\n{p.summary}")
            md_lines.append("\n---\n")

        md_content = "\n".join(md_lines)

        st.download_button(
            "Download Markdown",
            data=md_content,
            file_name="paper_search_results.md",
            mime="text/markdown",
            use_container_width=True,
        )
