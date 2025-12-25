"""Response view routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/responses", response_class=HTMLResponse)
async def list_responses(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    model: Optional[str] = None,
):
    """Render the responses list page."""
    db = request.app.state.db.db
    templates = request.app.state.templates

    offset = (page - 1) * limit

    # Check if responses table exists
    if "responses" not in db.table_names():
        return templates.TemplateResponse(
            "responses/list.html",
            {
                "request": request,
                "responses": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0,
                "models": [],
                "selected_model": model,
            },
        )

    # Build query
    where_clauses = []
    params = {}

    if model:
        where_clauses.append("model = :model")
        params["model"] = model

    where = " AND ".join(where_clauses) if where_clauses else None

    # Get total count
    if where:
        total = db.execute(
            f"SELECT COUNT(*) FROM responses WHERE {where}", params
        ).fetchone()[0]
    else:
        total = db["responses"].count

    # Get responses
    responses = list(
        db["responses"].rows_where(
            where=where,
            where_args=params,
            order_by="datetime_utc desc",
            limit=limit,
            offset=offset,
        )
    )

    # Get available models for filter
    model_rows = db.execute(
        "SELECT DISTINCT model FROM responses ORDER BY model"
    ).fetchall()
    models = [row[0] for row in model_rows if row[0]]

    # Calculate pagination
    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse(
        "responses/list.html",
        {
            "request": request,
            "responses": responses,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "models": models,
            "selected_model": model,
        },
    )


@router.get("/responses/{response_id}", response_class=HTMLResponse)
async def view_response(request: Request, response_id: str):
    """Render a single response detail page."""
    db = request.app.state.db.db
    templates = request.app.state.templates

    # Get response
    rows = list(db["responses"].rows_where("id = ?", [response_id]))
    if not rows:
        raise HTTPException(status_code=404, detail="Response not found")

    response = dict(rows[0])

    # Get tool calls
    tool_calls = []
    if "tool_calls" in db.table_names():
        tool_calls = list(db["tool_calls"].rows_where("response_id = ?", [response_id]))

    # Get tool results
    tool_results = []
    if "tool_results" in db.table_names():
        tool_results = list(
            db["tool_results"].rows_where("response_id = ?", [response_id])
        )

    # Get attachments
    attachments = []
    if "prompt_attachments" in db.table_names():
        attachment_links = list(
            db["prompt_attachments"].rows_where("response_id = ?", [response_id])
        )
        for link in attachment_links:
            att_rows = list(
                db["attachments"].rows_where("id = ?", [link["attachment_id"]])
            )
            if att_rows:
                att = dict(att_rows[0])
                # Don't include binary content
                att.pop("content", None)
                att["order"] = link["order"]
                attachments.append(att)
        attachments.sort(key=lambda x: x.get("order", 0))

    # Get conversation if exists
    conversation = None
    if response.get("conversation_id") and "conversations" in db.table_names():
        conv_rows = list(
            db["conversations"].rows_where("id = ?", [response["conversation_id"]])
        )
        if conv_rows:
            conversation = dict(conv_rows[0])

    return templates.TemplateResponse(
        "responses/detail.html",
        {
            "request": request,
            "response": response,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "attachments": attachments,
            "conversation": conversation,
        },
    )
