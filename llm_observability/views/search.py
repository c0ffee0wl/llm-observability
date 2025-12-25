"""Search view routes."""

from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def create_snippet(text: str, query: str, max_length: int = 200) -> str:
    """Create a snippet with the query term context."""
    if not text:
        return ""

    # Find the query in the text (case-insensitive)
    lower_text = text.lower()
    lower_query = query.lower()
    pos = lower_text.find(lower_query)

    if pos == -1:
        return text[:max_length] + "..." if len(text) > max_length else text

    # Calculate snippet window
    start = max(0, pos - 50)
    end = min(len(text), pos + len(query) + 150)

    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Render the search page."""
    db = request.app.state.db.db
    templates = request.app.state.templates

    results = []
    total = 0

    if q and "responses" in db.table_names():
        offset = (page - 1) * limit

        # Check if FTS is available
        use_fts = "responses_fts" in db.table_names()

        if use_fts:
            try:
                # Use FTS search
                safe_query = q.replace('"', '""')

                # Get total count
                count_query = f"""
                    SELECT COUNT(*) FROM responses_fts
                    WHERE responses_fts MATCH '"{safe_query}"'
                """
                total = db.execute(count_query).fetchone()[0]

                # Get results
                search_query = f"""
                    SELECT r.id, r.model, r.prompt, r.response, r.datetime_utc, r.conversation_id
                    FROM responses r
                    JOIN responses_fts fts ON r.rowid = fts.rowid
                    WHERE responses_fts MATCH '"{safe_query}"'
                    ORDER BY r.datetime_utc DESC
                    LIMIT :limit OFFSET :offset
                """

                rows = db.execute(
                    search_query, {"limit": limit, "offset": offset}
                ).fetchall()

                for row in rows:
                    results.append(
                        {
                            "id": row[0],
                            "model": row[1],
                            "prompt": row[2],
                            "response": row[3],
                            "datetime_utc": row[4],
                            "conversation_id": row[5],
                            "prompt_snippet": create_snippet(row[2], q)
                            if row[2]
                            else None,
                            "response_snippet": create_snippet(row[3], q)
                            if row[3]
                            else None,
                        }
                    )
            except Exception:
                use_fts = False

        if not use_fts:
            # Fallback to LIKE search
            safe_query = q.replace("%", "\\%").replace("_", "\\_")
            like_pattern = f"%{safe_query}%"

            # Get total count
            count_query = """
                SELECT COUNT(*) FROM responses
                WHERE prompt LIKE :pattern ESCAPE '\\'
                   OR response LIKE :pattern ESCAPE '\\'
            """
            total = db.execute(count_query, {"pattern": like_pattern}).fetchone()[0]

            # Get results
            search_query = """
                SELECT id, model, prompt, response, datetime_utc, conversation_id
                FROM responses
                WHERE prompt LIKE :pattern ESCAPE '\\'
                   OR response LIKE :pattern ESCAPE '\\'
                ORDER BY datetime_utc DESC
                LIMIT :limit OFFSET :offset
            """

            rows = db.execute(
                search_query,
                {"pattern": like_pattern, "limit": limit, "offset": offset},
            ).fetchall()

            for row in rows:
                results.append(
                    {
                        "id": row[0],
                        "model": row[1],
                        "prompt": row[2],
                        "response": row[3],
                        "datetime_utc": row[4],
                        "conversation_id": row[5],
                        "prompt_snippet": create_snippet(row[2], q) if row[2] else None,
                        "response_snippet": create_snippet(row[3], q)
                        if row[3]
                        else None,
                    }
                )

    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q or "",
            "results": results,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        },
    )
