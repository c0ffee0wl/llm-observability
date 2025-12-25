# LLM Observability

A web UI for viewing and analyzing data from the [llm](https://github.com/simonw/llm) database.

## Installation

```bash
uv tool install .
```

## Usage

```bash
# Start with default llm database (~/.config/io.datasette.llm/logs.db)
llm-observability

# Start with specific database
llm-observability --db /path/to/logs.db

# Custom host/port
llm-observability --host 0.0.0.0 --port 8778
```

## Features

- **Dashboard**: Summary metrics, model usage, recent responses
- **Responses**: List with filtering by model, detail view with tool calls
- **Conversations**: List with stats, timeline view of conversation threads
- **Search**: Full-text search across prompts and responses
- **API**: REST endpoints for programmatic access

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/responses` | List responses (pagination, filters) |
| `GET /api/responses/{id}` | Get response with tool calls |
| `GET /api/conversations` | List conversations |
| `GET /api/conversations/{id}` | Get conversation with responses |
| `GET /api/tools` | List tools with usage stats |
| `GET /api/metrics/summary` | Aggregated metrics |
| `GET /api/metrics/models` | Usage by model |
| `GET /api/metrics/tokens` | Token usage over time |
| `GET /api/metrics/latency` | Latency distribution |
| `GET /api/search?q=query` | Full-text search |
