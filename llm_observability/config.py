"""Configuration settings for LLM Observability."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


def get_default_db_path() -> str:
    """Get the default llm database path, matching llm's logic."""
    llm_user_path = os.environ.get("LLM_USER_PATH")
    if llm_user_path:
        base_path = Path(llm_user_path)
    else:
        # Default to ~/.config/io.datasette.llm
        base_path = Path.home() / ".config" / "io.datasette.llm"
    return str(base_path / "logs.db")


class Settings(BaseSettings):
    """Application settings."""

    db_path: str = ""
    host: str = "127.0.0.1"
    port: int = 8778
    debug: bool = False

    model_config = {
        "env_prefix": "OBSERVABILITY_",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.db_path:
            self.db_path = get_default_db_path()


settings = Settings()
