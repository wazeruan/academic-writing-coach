"""Runtime settings, read from environment variables with local defaults."""

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    # LM Studio serves an OpenAI-compatible API on port 1234 by default.
    llm_base_url: str = os.environ.get("COACH_LLM_URL", "http://localhost:1234/v1")
    # Use the model identifier shown by LM Studio (or `lms ls`).
    llm_model: str = os.environ.get("COACH_LLM_MODEL", "local-model")
    llm_timeout: float = float(os.environ.get("COACH_LLM_TIMEOUT", "240"))
    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("COACH_DB", PROJECT_ROOT / "data" / "coach.sqlite3")
        )
    )
    host: str = os.environ.get("COACH_HOST", "127.0.0.1")
    port: int = int(os.environ.get("COACH_PORT", "8765"))
