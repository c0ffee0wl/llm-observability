"""API endpoints for metrics and analytics."""

from typing import List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter()


class MetricsSummary(BaseModel):
    """Summary metrics for the dashboard."""

    total_responses: int = 0
    total_conversations: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_duration_ms: Optional[float] = None
    avg_input_tokens: Optional[float] = None
    avg_output_tokens: Optional[float] = None
    total_tool_calls: int = 0
    total_tool_errors: int = 0
    unique_models: int = 0


class ModelUsage(BaseModel):
    """Usage statistics for a model."""

    model: str
    response_count: int
    input_tokens: int
    output_tokens: int
    avg_duration_ms: Optional[float] = None


class TimeSeriesPoint(BaseModel):
    """A point in a time series."""

    date: str
    value: int


class LatencyBucket(BaseModel):
    """A bucket in a latency histogram."""

    range: str
    count: int


@router.get("/metrics/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get summary metrics for the dashboard."""
    db = request.app.state.db.db

    if "responses" not in db.table_names():
        return MetricsSummary()

    # Build date filter
    date_filter = ""
    params = {}
    if start_date:
        date_filter += " AND datetime_utc >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND datetime_utc <= :end_date"
        params["end_date"] = end_date

    # Get response metrics
    query = f"""
        SELECT
            COUNT(*) as total_responses,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(output_tokens), 0) as total_output_tokens,
            AVG(duration_ms) as avg_duration_ms,
            AVG(input_tokens) as avg_input_tokens,
            AVG(output_tokens) as avg_output_tokens,
            COUNT(DISTINCT model) as unique_models
        FROM responses
        WHERE 1=1 {date_filter}
    """
    row = db.execute(query, params).fetchone()

    total_responses = row[0]
    total_input_tokens = row[1]
    total_output_tokens = row[2]
    avg_duration_ms = row[3]
    avg_input_tokens = row[4]
    avg_output_tokens = row[5]
    unique_models = row[6]

    # Get conversation count
    total_conversations = 0
    if "conversations" in db.table_names():
        total_conversations = db["conversations"].count

    # Get tool metrics
    total_tool_calls = 0
    total_tool_errors = 0
    if "tool_calls" in db.table_names():
        total_tool_calls = db["tool_calls"].count
    if "tool_results" in db.table_names():
        error_row = db.execute(
            "SELECT COUNT(*) FROM tool_results WHERE exception IS NOT NULL"
        ).fetchone()
        total_tool_errors = error_row[0] if error_row else 0

    return MetricsSummary(
        total_responses=total_responses,
        total_conversations=total_conversations,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_tokens=total_input_tokens + total_output_tokens,
        avg_duration_ms=avg_duration_ms,
        avg_input_tokens=avg_input_tokens,
        avg_output_tokens=avg_output_tokens,
        total_tool_calls=total_tool_calls,
        total_tool_errors=total_tool_errors,
        unique_models=unique_models,
    )


@router.get("/metrics/models", response_model=List[ModelUsage])
async def get_model_usage(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get usage breakdown by model."""
    db = request.app.state.db.db

    if "responses" not in db.table_names():
        return []

    # Build date filter
    date_filter = ""
    params = {"limit": limit}
    if start_date:
        date_filter += " AND datetime_utc >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND datetime_utc <= :end_date"
        params["end_date"] = end_date

    query = f"""
        SELECT
            model,
            COUNT(*) as response_count,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            AVG(duration_ms) as avg_duration_ms
        FROM responses
        WHERE 1=1 {date_filter}
        GROUP BY model
        ORDER BY response_count DESC
        LIMIT :limit
    """

    rows = db.execute(query, params).fetchall()
    return [
        ModelUsage(
            model=row[0],
            response_count=row[1],
            input_tokens=row[2],
            output_tokens=row[3],
            avg_duration_ms=row[4],
        )
        for row in rows
    ]


@router.get("/metrics/tokens", response_model=List[TimeSeriesPoint])
async def get_token_usage_over_time(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = Query("day", pattern="^(hour|day|week|month)$"),
):
    """Get token usage over time."""
    db = request.app.state.db.db

    if "responses" not in db.table_names():
        return []

    # Date format based on granularity
    date_formats = {
        "hour": "%Y-%m-%d %H:00",
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }
    date_format = date_formats[granularity]

    # Build date filter
    date_filter = ""
    params = {}
    if start_date:
        date_filter += " AND datetime_utc >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND datetime_utc <= :end_date"
        params["end_date"] = end_date

    query = f"""
        SELECT
            strftime('{date_format}', datetime_utc) as date,
            COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) as value
        FROM responses
        WHERE datetime_utc IS NOT NULL {date_filter}
        GROUP BY date
        ORDER BY date
    """

    rows = db.execute(query, params).fetchall()
    return [TimeSeriesPoint(date=row[0], value=row[1]) for row in rows if row[0]]


@router.get("/metrics/latency", response_model=List[LatencyBucket])
async def get_latency_distribution(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get latency distribution as histogram buckets."""
    db = request.app.state.db.db

    if "responses" not in db.table_names():
        return []

    # Build date filter
    date_filter = ""
    params = {}
    if start_date:
        date_filter += " AND datetime_utc >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND datetime_utc <= :end_date"
        params["end_date"] = end_date

    # Define latency buckets (in ms)
    buckets = [
        (0, 100, "0-100ms"),
        (100, 500, "100-500ms"),
        (500, 1000, "500ms-1s"),
        (1000, 2000, "1-2s"),
        (2000, 5000, "2-5s"),
        (5000, 10000, "5-10s"),
        (10000, 30000, "10-30s"),
        (30000, 60000, "30-60s"),
        (60000, None, "60s+"),
    ]

    results = []
    for low, high, label in buckets:
        if high is None:
            bucket_filter = f"duration_ms >= {low}"
        else:
            bucket_filter = f"duration_ms >= {low} AND duration_ms < {high}"

        query = f"""
            SELECT COUNT(*) FROM responses
            WHERE duration_ms IS NOT NULL AND {bucket_filter} {date_filter}
        """
        count = db.execute(query, params).fetchone()[0]
        results.append(LatencyBucket(range=label, count=count))

    return results


@router.get("/metrics/responses-over-time", response_model=List[TimeSeriesPoint])
async def get_responses_over_time(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = Query("day", pattern="^(hour|day|week|month)$"),
):
    """Get response count over time."""
    db = request.app.state.db.db

    if "responses" not in db.table_names():
        return []

    # Date format based on granularity
    date_formats = {
        "hour": "%Y-%m-%d %H:00",
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }
    date_format = date_formats[granularity]

    # Build date filter
    date_filter = ""
    params = {}
    if start_date:
        date_filter += " AND datetime_utc >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND datetime_utc <= :end_date"
        params["end_date"] = end_date

    query = f"""
        SELECT
            strftime('{date_format}', datetime_utc) as date,
            COUNT(*) as value
        FROM responses
        WHERE datetime_utc IS NOT NULL {date_filter}
        GROUP BY date
        ORDER BY date
    """

    rows = db.execute(query, params).fetchall()
    return [TimeSeriesPoint(date=row[0], value=row[1]) for row in rows if row[0]]
