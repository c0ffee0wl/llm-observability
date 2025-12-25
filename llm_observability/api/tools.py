"""API endpoints for tools."""

from typing import List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter()


class ToolDefinition(BaseModel):
    """Tool definition."""

    id: int
    name: str
    description: Optional[str] = None
    input_schema: Optional[str] = None
    plugin: Optional[str] = None
    call_count: int = 0
    result_count: int = 0
    error_count: int = 0


class ToolListResponse(BaseModel):
    """List of tools with usage stats."""

    items: List[ToolDefinition]
    total: int


class ToolCallDetail(BaseModel):
    """Detailed tool call."""

    id: int
    response_id: str
    tool_id: int
    name: str
    arguments: Optional[str] = None
    tool_call_id: Optional[str] = None
    datetime_utc: Optional[str] = None


class ToolResultDetail(BaseModel):
    """Detailed tool result."""

    id: int
    response_id: str
    tool_id: int
    name: str
    output: Optional[str] = None
    exception: Optional[str] = None
    tool_call_id: Optional[str] = None
    datetime_utc: Optional[str] = None


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(request: Request):
    """List all tools with usage statistics."""
    db = request.app.state.db.db

    if "tools" not in db.table_names():
        return ToolListResponse(items=[], total=0)

    # Check which tables exist for the query
    has_tool_calls = "tool_calls" in db.table_names()
    has_tool_results = "tool_results" in db.table_names()

    # Build query based on available tables
    if has_tool_calls and has_tool_results:
        query = """
            SELECT
                t.id,
                t.name,
                t.description,
                t.input_schema,
                t.plugin,
                COALESCE(tc.call_count, 0) as call_count,
                COALESCE(tr.result_count, 0) as result_count,
                COALESCE(tr.error_count, 0) as error_count
            FROM tools t
            LEFT JOIN (
                SELECT tool_id, COUNT(*) as call_count
                FROM tool_calls
                GROUP BY tool_id
            ) tc ON t.id = tc.tool_id
            LEFT JOIN (
                SELECT tool_id,
                       COUNT(*) as result_count,
                       SUM(CASE WHEN exception IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM tool_results
                GROUP BY tool_id
            ) tr ON t.id = tr.tool_id
            ORDER BY call_count DESC
        """
    elif has_tool_calls:
        query = """
            SELECT
                t.id, t.name, t.description, t.input_schema, t.plugin,
                COALESCE(tc.call_count, 0) as call_count,
                0 as result_count, 0 as error_count
            FROM tools t
            LEFT JOIN (
                SELECT tool_id, COUNT(*) as call_count
                FROM tool_calls GROUP BY tool_id
            ) tc ON t.id = tc.tool_id
            ORDER BY call_count DESC
        """
    else:
        query = """
            SELECT id, name, description, input_schema, plugin,
                   0 as call_count, 0 as result_count, 0 as error_count
            FROM tools
        """

    rows = db.execute(query).fetchall()
    columns = [
        "id",
        "name",
        "description",
        "input_schema",
        "plugin",
        "call_count",
        "result_count",
        "error_count",
    ]

    items = [ToolDefinition(**dict(zip(columns, row))) for row in rows]

    return ToolListResponse(items=items, total=len(items))


@router.get("/tools/{tool_id}/calls")
async def get_tool_calls(
    request: Request,
    tool_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get recent calls for a specific tool."""
    db = request.app.state.db.db

    if "tool_calls" not in db.table_names():
        return {"items": [], "total": 0}

    # Get calls with response datetime
    query = """
        SELECT
            tc.id,
            tc.response_id,
            tc.tool_id,
            tc.name,
            tc.arguments,
            tc.tool_call_id,
            r.datetime_utc
        FROM tool_calls tc
        LEFT JOIN responses r ON tc.response_id = r.id
        WHERE tc.tool_id = :tool_id
        ORDER BY r.datetime_utc DESC
        LIMIT :limit OFFSET :offset
    """

    rows = db.execute(
        query, {"tool_id": tool_id, "limit": limit, "offset": offset}
    ).fetchall()
    columns = [
        "id",
        "response_id",
        "tool_id",
        "name",
        "arguments",
        "tool_call_id",
        "datetime_utc",
    ]

    items = [ToolCallDetail(**dict(zip(columns, row))) for row in rows]

    # Get total count
    total = db.execute(
        "SELECT COUNT(*) FROM tool_calls WHERE tool_id = ?", [tool_id]
    ).fetchone()[0]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/tools/{tool_id}/results")
async def get_tool_results(
    request: Request,
    tool_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    errors_only: bool = False,
):
    """Get recent results for a specific tool."""
    db = request.app.state.db.db

    if "tool_results" not in db.table_names():
        return {"items": [], "total": 0}

    # Build query
    where_clause = "tr.tool_id = :tool_id"
    if errors_only:
        where_clause += " AND tr.exception IS NOT NULL"

    query = f"""
        SELECT
            tr.id,
            tr.response_id,
            tr.tool_id,
            tr.name,
            tr.output,
            tr.exception,
            tr.tool_call_id,
            r.datetime_utc
        FROM tool_results tr
        LEFT JOIN responses r ON tr.response_id = r.id
        WHERE {where_clause}
        ORDER BY r.datetime_utc DESC
        LIMIT :limit OFFSET :offset
    """

    rows = db.execute(
        query, {"tool_id": tool_id, "limit": limit, "offset": offset}
    ).fetchall()
    columns = [
        "id",
        "response_id",
        "tool_id",
        "name",
        "output",
        "exception",
        "tool_call_id",
        "datetime_utc",
    ]

    items = [ToolResultDetail(**dict(zip(columns, row))) for row in rows]

    # Get total count
    count_where = "tool_id = ?"
    if errors_only:
        count_where += " AND exception IS NOT NULL"
    total = db.execute(
        f"SELECT COUNT(*) FROM tool_results WHERE {count_where}", [tool_id]
    ).fetchone()[0]

    return {"items": items, "total": total, "limit": limit, "offset": offset}
