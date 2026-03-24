"""Export endpoints."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.schemas import ExportMarkdownRequest
from backend.workspace import workspace

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/markdown")
async def export_markdown(req: ExportMarkdownRequest):
    """Generate and return a Markdown summary of papers."""
    if not workspace.papers:
        return PlainTextResponse("No papers available.", status_code=400)

    # Use selected indices if provided, otherwise all papers
    if req.selected_indices:
        selected_papers = [
            workspace.papers[i]
            for i in req.selected_indices
            if 0 <= i < len(workspace.papers)
        ]
    elif workspace.selected:
        selected_papers = [
            workspace.papers[i] for i in sorted(workspace.selected)
        ]
    else:
        selected_papers = workspace.papers

    md_lines = ["# Paper Search Results\n"]
    md_lines.append(f"**Query**: {workspace.last_query}\n")
    md_lines.append(f"**Total**: {len(selected_papers)} papers\n")
    md_lines.append("---\n")

    for i, p in enumerate(selected_papers):
        oa = "Yes" if p.is_oa else "No"
        md_lines.append(f"### {i + 1}. {p.title}")
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

    return PlainTextResponse(
        md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=paper_search_results.md"},
    )
