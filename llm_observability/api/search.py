"""API endpoints for search."""

from typing import List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter()


class SearchResult(BaseModel):
    """A search result."""

    id: str
    model: str
    prompt: Optional[str] = None
    response: Optional[str] = None
    datetime_utc: Optional[str] = None
    conversation_id: Optional[str] = None
    # Snippets with highlighted matches
    prompt_snippet: Optional[str] = None
    response_snippet: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response with results."""

    query: str
    results: List[SearchResult]
    total: int
    limit: int
    offset: int


def create_snippet(text: str, query: str, max_length: int = 200) -> str:
    """Create a snippet with the query term highlighted."""
    if not text:
        return ""

    # Find the query in the text (case-insensitive)
    lower_text = text.lower()
    lower_query = query.lower()
    pos = lower_text.find(lower_query)

    if pos == -1:
        # Query not found, return start of text
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


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Full-text search across prompts and responses."""
    db = request.app.state.db.db

    # Check if FTS is available
    if "responses_fts" not in db.table_names():
        # Fall back to LIKE search
        return _search_like(db, q, limit, offset)

    # Use FTS search
    try:
        return _search_fts(db, q, limit, offset)
    except Exception:
        # Fall back to LIKE if FTS fails
        return _search_like(db, q, limit, offset)


def _search_fts(db, query: str, limit: int, offset: int) -> SearchResponse:
    """Search using SQLite FTS."""
    # Escape special FTS characters
    safe_query = query.replace('"', '""')

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

    rows = db.execute(search_query, {"limit": limit, "offset": offset}).fetchall()

    results = []
    for row in rows:
        result = SearchResult(
            id=row[0],
            model=row[1],
            prompt=row[2],
            response=row[3],
            datetime_utc=row[4],
            conversation_id=row[5],
            prompt_snippet=create_snippet(row[2], query) if row[2] else None,
            response_snippet=create_snippet(row[3], query) if row[3] else None,
        )
        results.append(result)

    return SearchResponse(
        query=query,
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )


def _search_like(db, query: str, limit: int, offset: int) -> SearchResponse:
    """Fallback search using LIKE."""
    # Escape special characters
    safe_query = query.replace("%", "\\%").replace("_", "\\_")
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
        search_query, {"pattern": like_pattern, "limit": limit, "offset": offset}
    ).fetchall()

    results = []
    for row in rows:
        result = SearchResult(
            id=row[0],
            model=row[1],
            prompt=row[2],
            response=row[3],
            datetime_utc=row[4],
            conversation_id=row[5],
            prompt_snippet=create_snippet(row[2], query) if row[2] else None,
            response_snippet=create_snippet(row[3], query) if row[3] else None,
        )
        results.append(result)

    return SearchResponse(
        query=query,
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )
