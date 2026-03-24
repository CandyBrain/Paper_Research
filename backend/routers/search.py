"""Search endpoints."""

import asyncio

from fastapi import APIRouter, HTTPException

from src.models import DatabaseSource, SearchRequest as SrcSearchRequest
from src.services.search import SearchOrchestrator
from src.services.query_generator import QueryGenerator

from backend.schemas import (
    SearchRequest,
    AISearchRequest,
    SearchResponse,
    SearchResultResponse,
)
from backend.workspace import workspace
from backend.utils import paper_to_response

router = APIRouter(prefix="/api/search", tags=["search"])


def _parse_databases(db_names: list[str]) -> list[DatabaseSource]:
    """Convert string database names to DatabaseSource enum values."""
    result = []
    for name in db_names:
        try:
            result.append(DatabaseSource(name))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown database: {name}. "
                f"Valid: {[d.value for d in DatabaseSource]}",
            )
    return result


@router.post("", response_model=SearchResponse)
async def keyword_search(req: SearchRequest):
    """Keyword search across selected databases."""
    databases = _parse_databases(req.databases)

    api_keys = {}
    if workspace.scopus_api_key:
        api_keys["scopus"] = workspace.scopus_api_key
    if workspace.core_api_key:
        api_keys["core"] = workspace.core_api_key

    orchestrator = SearchOrchestrator(
        api_keys=api_keys,
        proxy_url=workspace.proxy_url,
    )

    src_request = SrcSearchRequest(
        query=req.query,
        databases=databases,
        max_results_per_db=req.max_results_per_db,
    )

    workspace.clear_search()
    workspace.last_query = req.query
    workspace.search_mode = "keyword"

    results = await orchestrator.search_all(src_request)
    workspace.search_results = results

    all_papers = orchestrator.deduplicate(results)
    workspace.papers = all_papers

    from backend.utils import do_autosave
    do_autosave()

    return SearchResponse(
        results=[
            SearchResultResponse(
                source=r.source.value,
                papers=[paper_to_response(p) for p in r.papers],
                error=r.error,
                total_found=r.total_found,
            )
            for r in results
        ],
        papers=[paper_to_response(p) for p in all_papers],
        query=req.query,
    )


@router.post("/ai", response_model=SearchResponse)
async def ai_search(req: AISearchRequest):
    """AI-powered search: generate queries from description then search."""
    if not workspace.anthropic_api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key is required for AI search.",
        )

    databases = _parse_databases(req.databases)

    # Generate queries (sync) in a thread
    generator = QueryGenerator(api_key=workspace.anthropic_api_key)
    ai_analysis = await asyncio.to_thread(
        generator.generate_queries, req.description, databases
    )

    workspace.clear_search()
    workspace.last_query = req.description
    workspace.search_mode = "ai"
    workspace.ai_analysis = ai_analysis

    # Run all generated queries
    api_keys = {}
    if workspace.scopus_api_key:
        api_keys["scopus"] = workspace.scopus_api_key
    if workspace.core_api_key:
        api_keys["core"] = workspace.core_api_key

    orchestrator = SearchOrchestrator(
        api_keys=api_keys,
        proxy_url=workspace.proxy_url,
    )

    all_results = []
    queries = ai_analysis.get("queries", [])
    for q_info in queries:
        query_str = q_info.get("query", "")
        if not query_str:
            continue
        src_request = SrcSearchRequest(
            query=query_str,
            databases=databases,
            max_results_per_db=req.max_results_per_db,
        )
        results = await orchestrator.search_all(src_request)
        all_results.extend(results)

    workspace.search_results = all_results

    all_papers = orchestrator.deduplicate(all_results)

    # AI Relevance Reranking
    if all_papers:
        paper_dicts = [
            {"title": p.title, "abstract": p.abstract or ""}
            for p in all_papers
        ]
        rankings = await asyncio.to_thread(
            generator.rerank_papers, req.description, paper_dicts
        )

        if rankings:
            # Reorder papers by relevance score
            ranked_indices = [r["index"] for r in rankings if r["index"] < len(all_papers)]
            ranked_papers = [all_papers[i] for i in ranked_indices]
            # Append remaining unranked papers (scored < 3) at the end
            ranked_set = set(ranked_indices)
            for i, p in enumerate(all_papers):
                if i not in ranked_set:
                    ranked_papers.append(p)
            all_papers = ranked_papers

            # Store ranking info in ai_analysis
            ai_analysis["relevance_rankings"] = rankings

    workspace.papers = all_papers

    from backend.utils import do_autosave
    do_autosave()

    return SearchResponse(
        results=[
            SearchResultResponse(
                source=r.source.value,
                papers=[paper_to_response(p) for p in r.papers],
                error=r.error,
                total_found=r.total_found,
            )
            for r in all_results
        ],
        papers=[paper_to_response(p) for p in all_papers],
        query=req.description,
        ai_analysis=ai_analysis,
    )
