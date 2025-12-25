"""Dashboard view routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard."""
    db = request.app.state.db.db
    templates = request.app.state.templates

    # Get summary metrics
    metrics = {
        "total_responses": 0,
        "total_conversations": 0,
        "total_tokens": 0,
        "avg_duration_ms": 0,
        "unique_models": 0,
    }

    if "responses" in db.table_names():
        row = db.execute(
            """
            SELECT
                COUNT(*) as total_responses,
                COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) as total_tokens,
                AVG(duration_ms) as avg_duration_ms,
                COUNT(DISTINCT model) as unique_models
            FROM responses
        """
        ).fetchone()
        metrics["total_responses"] = row[0]
        metrics["total_tokens"] = row[1]
        metrics["avg_duration_ms"] = round(row[2]) if row[2] else 0
        metrics["unique_models"] = row[3]

    if "conversations" in db.table_names():
        metrics["total_conversations"] = db["conversations"].count

    # Get recent responses
    recent_responses = []
    if "responses" in db.table_names():
        recent_responses = list(
            db["responses"].rows_where(order_by="datetime_utc desc", limit=10)
        )

    # Get model usage
    model_usage = []
    if "responses" in db.table_names():
        rows = db.execute(
            """
            SELECT model, COUNT(*) as count
            FROM responses
            GROUP BY model
            ORDER BY count DESC
            LIMIT 10
        """
        ).fetchall()
        model_usage = [{"model": row[0], "count": row[1]} for row in rows]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "recent_responses": recent_responses,
            "model_usage": model_usage,
        },
    )
