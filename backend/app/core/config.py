"""Application settings, loaded from environment variables / backend/.env."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FitBot API"
    environment: str = "development"            # set ENVIRONMENT=production when deployed
    frontend_dist: str = str(PROJECT_ROOT / "frontend" / "dist")   # served by FastAPI if the folder exists
    chat_rate_per_min: int = 20                 # per-user /chat requests per minute (protects a shared CPU)
    database_url: str = f"sqlite:///{BACKEND_DIR / 'fitbot.db'}"
    jwt_secret: str = "change-me-in-backend-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- SLM ---
    # local folder (relative to the project root) OR a Hugging Face Hub repo id such as "you/fitbot-smollm2-360m"
    fitbot_model_path: str = "models/fitbot-smollm2-360m-lora/merged"
    fitbot_base_model: str = "HuggingFaceTB/SmolLM2-360M-Instruct"       # fallback if no fine-tuned model
    fitbot_device: str = "auto"                                          # auto | cpu | mps | cuda
    fitbot_max_new_tokens: int = 220
    fitbot_load_model: bool = True                                       # tests set this to false
    fitbot_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    fitbot_use_embeddings: bool = True
    # previous exchanges sent to the SLM; 1 worked best in evaluation (longer histories make the 360M model
    # copy the previous answer's style). Topic/constraints are carried by the dialogue state instead.
    fitbot_history_turns: int = 1

    data_dir: str = str(PROJECT_ROOT / "data")
    models_dir: str = str(PROJECT_ROOT / "models")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")

    def model_ref(self) -> Path | str:
        """Local model folder if it exists, otherwise a Hub repo id ("owner/name"), otherwise the local path."""
        local = self.resolve(self.fitbot_model_path)
        if local.exists():
            return local
        if re.fullmatch(r"[\w.-]+/[\w.-]+", self.fitbot_model_path):
            return self.fitbot_model_path
        return local

    def resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
