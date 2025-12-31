"""CLI entry point for LLM Observability."""

import click
import uvicorn

from .config import get_default_db_path, settings
from .database import Database, DatabaseError


@click.command()
@click.option(
    "--db",
    "db_path",
    default=None,
    help="Path to llm database file (default: ~/.config/io.datasette.llm/logs.db)",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1)",
)
@click.option(
    "--port",
    default=8778,
    help="Port to bind to (default: 8778)",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development",
)
def main(db_path: str, host: str, port: int, reload: bool):
    """Start the LLM Observability web server."""
    # Use provided db_path or get default
    if db_path is None:
        db_path = get_default_db_path()

    # Update settings
    settings.db_path = db_path
    settings.host = host
    settings.port = port

    # Validate database before starting server
    try:
        db = Database(db_path)
        db.validate()
        db.close()
    except DatabaseError as e:
        raise click.ClickException(str(e))

    click.echo("Starting LLM Observability server...")
    click.echo(f"Database: {db_path}")
    click.echo(f"Server:   http://{host}:{port}")

    uvicorn.run(
        "llm_observability.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
