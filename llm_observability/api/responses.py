"""API endpoints for responses."""

from typing import List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter()


class ToolCallResponse(BaseModel):
    """Tool call data."""

    id: int
    name: str
    arguments: Optional[str] = None
    tool_call_id: Optional[str] = None


class ToolResultResponse(BaseModel):
    """Tool result data."""

    id: int
    name: str
    output: Optional[str] = None
    exception: Optional[str] = None
    tool_call_id: Optional[str] = None


class ResponseSummary(BaseModel):
    """Summary of an LLM response."""

    id: str
    model: str
    prompt: Optional[str] = None
    response: Optional[str] = None
    conversation_id: Optional[str] = None
    duration_ms: Optional[int] = None
    datetime_utc: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class ResponseDetail(ResponseSummary):
    """Detailed response including tool calls."""

    system: Optional[str] = None
    tool_calls: List[ToolCallResponse] = []
    tool_results: List[ToolResultResponse] = []


class ResponseListResponse(BaseModel):
    """Paginated list of responses."""

    items: List[ResponseSummary]
    total: int
    limit: int
    offset: int


@router.get("/responses", response_model=ResponseListResponse)
async def list_responses(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    model: Optional[str] = None,
    conversation_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """List responses with optional filtering."""
    db = request.app.state.db.db

    if "responses" not in db.table_names():
        return ResponseListResponse(items=[], total=0, limit=limit, offset=offset)

    # Build query
    where_clauses = []
    params = {}

    if model:
        where_clauses.append("model = :model")
        params["model"] = model

    if conversation_id:
        where_clauses.append("conversation_id = :conversation_id")
        params["conversation_id"] = conversation_id

    if start_date:
        where_clauses.append("datetime_utc >= :start_date")
        params["start_date"] = start_date

    if end_date:
        where_clauses.append("datetime_utc <= :end_date")
        params["end_date"] = end_date

    where = " AND ".join(where_clauses) if where_clauses else None

    # Get total count
    if where:
        total = db.execute(
            f"SELECT COUNT(*) FROM responses WHERE {where}", params
        ).fetchone()[0]
    else:
        total = db["responses"].count

    # Get paginated results
    rows = list(
        db["responses"].rows_where(
            where=where,
            where_args=params,
            order_by="datetime_utc desc",
            limit=limit,
            offset=offset,
        )
    )

    items = [ResponseSummary(**row) for row in rows]

    return ResponseListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/responses/{response_id}", response_model=ResponseDetail)
async def get_response(request: Request, response_id: str):
    """Get a single response with details."""
    db = request.app.state.db.db

    # Get response
    rows = list(db["responses"].rows_where("id = ?", [response_id]))
    if not rows:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Response not found")

    response = dict(rows[0])

    # Get tool calls
    tool_calls = []
    if "tool_calls" in db.table_names():
        tool_call_rows = list(
            db["tool_calls"].rows_where("response_id = ?", [response_id])
        )
        tool_calls = [ToolCallResponse(**row) for row in tool_call_rows]

    # Get tool results
    tool_results = []
    if "tool_results" in db.table_names():
        tool_result_rows = list(
            db["tool_results"].rows_where("response_id = ?", [response_id])
        )
        tool_results = [ToolResultResponse(**row) for row in tool_result_rows]

    return ResponseDetail(
        **response,
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


@router.get("/responses/{response_id}/attachments")
async def get_response_attachments(request: Request, response_id: str):
    """Get attachments for a response."""
    db = request.app.state.db.db

    if "prompt_attachments" not in db.table_names():
        return []

    # Get attachment IDs
    attachment_links = list(
        db["prompt_attachments"].rows_where("response_id = ?", [response_id])
    )

    if not attachment_links:
        return []

    # Get attachment details (excluding content for size)
    attachments = []
    for link in attachment_links:
        rows = list(db["attachments"].rows_where("id = ?", [link["attachment_id"]]))
        if rows:
            att = dict(rows[0])
            # Don't include binary content in API response
            att.pop("content", None)
            att["order"] = link["order"]
            attachments.append(att)

    return sorted(attachments, key=lambda x: x.get("order", 0))
