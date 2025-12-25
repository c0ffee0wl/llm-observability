"""API endpoints for conversations."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter()


class ConversationSummary(BaseModel):
    """Summary of a conversation."""

    id: str
    name: Optional[str] = None
    model: Optional[str] = None
    response_count: int = 0
    first_response: Optional[str] = None
    last_response: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class ConversationResponse(BaseModel):
    """A response within a conversation."""

    id: str
    model: str
    prompt: Optional[str] = None
    response: Optional[str] = None
    datetime_utc: Optional[str] = None
    duration_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class ConversationDetail(BaseModel):
    """Detailed conversation with all responses."""

    id: str
    name: Optional[str] = None
    model: Optional[str] = None
    responses: List[ConversationResponse] = []


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""

    items: List[ConversationSummary]
    total: int
    limit: int
    offset: int


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List conversations with response counts."""
    db = request.app.state.db.db

    if "conversations" not in db.table_names():
        return ConversationListResponse(items=[], total=0, limit=limit, offset=offset)

    # Get total count
    total = db["conversations"].count

    # Get conversations with aggregated stats
    query = """
        SELECT
            c.id,
            c.name,
            c.model,
            COUNT(r.id) as response_count,
            MIN(r.datetime_utc) as first_response,
            MAX(r.datetime_utc) as last_response,
            COALESCE(SUM(r.input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(r.output_tokens), 0) as total_output_tokens
        FROM conversations c
        LEFT JOIN responses r ON c.id = r.conversation_id
        GROUP BY c.id
        ORDER BY last_response DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """

    rows = db.execute(query, {"limit": limit, "offset": offset}).fetchall()
    columns = [
        "id",
        "name",
        "model",
        "response_count",
        "first_response",
        "last_response",
        "total_input_tokens",
        "total_output_tokens",
    ]

    items = [ConversationSummary(**dict(zip(columns, row))) for row in rows]

    return ConversationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(request: Request, conversation_id: str):
    """Get a conversation with all its responses."""
    db = request.app.state.db.db

    if "conversations" not in db.table_names():
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation
    rows = list(db["conversations"].rows_where("id = ?", [conversation_id]))
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = dict(rows[0])

    # Get responses in this conversation
    responses = []
    if "responses" in db.table_names():
        response_rows = list(
            db["responses"].rows_where(
                "conversation_id = ?",
                [conversation_id],
                order_by="datetime_utc",
            )
        )
        responses = [ConversationResponse(**row) for row in response_rows]

    return ConversationDetail(
        **conversation,
        responses=responses,
    )
