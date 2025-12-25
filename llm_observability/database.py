"""Database connection and validation for LLM Observability."""

from pathlib import Path
from typing import Optional

import sqlite_utils


class DatabaseError(Exception):
    """Base exception for database errors."""

    pass


class DatabaseNotFoundError(DatabaseError):
    """Raised when the database file doesn't exist."""

    pass


class InvalidDatabaseError(DatabaseError):
    """Raised when the database is not a valid llm database."""

    pass


class Database:
    """Wrapper for sqlite-utils database connection to llm logs."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[sqlite_utils.Database] = None

    def validate(self) -> None:
        """Validate that the database exists and is a valid llm database."""
        path = Path(self.db_path)
        if not path.exists():
            raise DatabaseNotFoundError(
                f"Database not found: {self.db_path}\n"
                "Make sure the llm database exists at this path."
            )

        # Check if it's a valid llm database by looking for the migrations table
        db = sqlite_utils.Database(self.db_path)
        if "_llm_migrations" not in db.table_names():
            raise InvalidDatabaseError(
                f"Invalid llm database: {self.db_path}\n"
                "This database does not contain llm tables. "
                "Make sure you're pointing to a valid llm logs.db file."
            )

    @property
    def db(self) -> sqlite_utils.Database:
        """Get the database connection."""
        if self._db is None:
            self._db = sqlite_utils.Database(self.db_path)
        return self._db

    def close(self) -> None:
        """Close the database connection."""
        if self._db:
            self._db.close()
            self._db = None

    def has_responses(self) -> bool:
        """Check if the responses table exists and has data."""
        return "responses" in self.db.table_names() and self.db["responses"].count > 0

    def has_conversations(self) -> bool:
        """Check if the conversations table exists and has data."""
        return (
            "conversations" in self.db.table_names()
            and self.db["conversations"].count > 0
        )

    def has_tools(self) -> bool:
        """Check if the tools table exists and has data."""
        return "tools" in self.db.table_names() and self.db["tools"].count > 0

    def has_fts(self) -> bool:
        """Check if full-text search is enabled on responses."""
        return "responses_fts" in self.db.table_names()
