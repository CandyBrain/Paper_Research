# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Paper_Research — 학술 논문 검색, 다운로드, AI 요약 및 연구 프로젝트 관리 플랫폼.

## Build & Run

**Backend** (FastAPI):
```bash
pip install -r requirements.txt
python -m playwright install chromium   # 브라우저 자동화용 (최초 1회)
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Frontend** (React + Vite):
```bash
cd frontend
npm install
npm run build    # dist/ 폴더에 빌드 → FastAPI가 자동 서빙
```

**접속**: http://127.0.0.1:8000

> **주의**: `app.py`는 이전 Streamlit UI (레거시)입니다. 사용하지 마세요. 현재 UI는 React 기반이며 FastAPI(`backend/main.py`)로 실행합니다.

## Architecture

```
backend/                  # FastAPI 백엔드
  main.py                 # 앱 진입점, lifespan, 라우터 등록
  workspace.py            # 서버 상태 (논문, 설정 등)
  schemas.py              # Pydantic 요청/응답 모델
  utils.py                # 헬퍼 함수
  routers/
    search.py             # 키워드/AI 검색
    papers.py             # 다운로드, 요약, 인용, PDF 서빙, 재검색
    projects.py           # 연구 프로젝트 CRUD + AI 채팅
    sessions.py           # 세션 저장/로드
    settings.py           # 설정 관리 + 폴더 브라우저
    export.py             # 마크다운 내보내기

src/                      # 핵심 서비스 (backend와 공유)
  config.py               # 환경변수 설정
  models.py               # Paper, SearchResult 모델
  services/
    downloader.py          # PDF 다운로드 (httpx + Playwright + 출판사 API)
    query_generator.py     # AI 쿼리 생성 + 관련도 재평가
    summarizer.py          # AI 논문 요약
    citations.py           # 인용/참고문헌 조회
    session_manager.py     # 세션 파일 관리
    search/                # 검색 API (OpenAlex, PubMed, Semantic Scholar, CORE, Scopus)
  utils/
    dedup.py               # 중복 제거 + 비논문 DOI 필터링

frontend/                 # React + TypeScript + Vite
  src/
    App.tsx                # 메인 레이아웃 (검색뷰/프로젝트뷰 전환)
    store/useAppStore.ts   # Zustand 전역 상태
    api/client.ts          # API 클라이언트
    components/
      layout/              # Header, Sidebar, StepIndicator, FolderPickerModal
      search/              # SearchPanel, AIAnalysisBox
      papers/              # PaperCard, ActionButtons, PdfViewer, SummaryPanel 등
      projects/            # ProjectWorkspace (AI 채팅 + 논문 관리)
      export/              # ExportPanel
      stats/               # StatsBar

sessions/                 # 세션 데이터 (JSON, gitignore)
projects/                 # 연구 프로젝트 데이터 (JSON, gitignore)
papers/                   # 다운로드된 PDF (gitignore)

app.py                    # [레거시] Streamlit UI — 사용하지 마세요
```

## Key Design Decisions

- **PDF 다운로드**: httpx 직접 → 출판사 API (Elsevier, Springer) → Playwright 브라우저 자동화 순서로 시도
- **대학 프록시**: path_prefix (`_Lib_Proxy_Url`), prefix (`?url=`), ezproxy (도메인 리라이트) 3가지 모드 자동 감지
- **AI 모델**: `claude-haiku-4-5-20251001` (쿼리 생성, 요약, 채팅)
- **설정 저장**: `sessions/_settings.json`에 JSON으로 영구 저장, 서버 시작 시 자동 로드/저장
- **프로젝트 데이터**: `projects/` 폴더에 프로젝트별 JSON (논문 + 채팅 기록)
