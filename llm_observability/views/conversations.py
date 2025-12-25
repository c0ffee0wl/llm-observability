"""Conversation view routes."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/conversations", response_class=HTMLResponse)
async def list_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Render the conversations list page."""
    db = request.app.state.db.db
    templates = request.app.state.templates

    offset = (page - 1) * limit

    if "conversations" not in db.table_names():
        return templates.TemplateResponse(
            "conversations/list.html",
            {
                "request": request,
                "conversations": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0,
            },
        )

    # Get total count
    total = db["conversations"].count

    # Get conversations with stats
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
    conversations = [
        {
            "id": row[0],
            "name": row[1],
            "model": row[2],
            "response_count": row[3],
            "first_response": row[4],
            "last_response": row[5],
            "total_input_tokens": row[6],
            "total_output_tokens": row[7],
        }
        for row in rows
    ]

    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse(
        "conversations/list.html",
        {
            "request": request,
            "conversations": conversations,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        },
    )


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def view_conversation(request: Request, conversation_id: str):
    """Render a conversation detail page."""
    db = request.app.state.db.db
    templates = request.app.state.templates

    if "conversations" not in db.table_names():
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation
    rows = list(db["conversations"].rows_where("id = ?", [conversation_id]))
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = dict(rows[0])

    # Get all responses in the conversation
    responses = list(
        db["responses"].rows_where(
            "conversation_id = ?",
            [conversation_id],
            order_by="datetime_utc",
        )
    )

    # Calculate totals
    total_input_tokens = sum(r.get("input_tokens") or 0 for r in responses)
    total_output_tokens = sum(r.get("output_tokens") or 0 for r in responses)
    total_duration_ms = sum(r.get("duration_ms") or 0 for r in responses)

    return templates.TemplateResponse(
        "conversations/detail.html",
        {
            "request": request,
            "conversation": conversation,
            "responses": responses,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_duration_ms": total_duration_ms,
        },
    )
