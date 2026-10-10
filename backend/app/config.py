"""
Centralized application configuration.
Everything is sourced from environment variables (or a local .env file)
so nothing sensitive or environment-specific is hardcoded.
"""
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    APP_NAME: str = "Sentiment Analysis Dashboard"
    ENV: str = "development"

    # --- Database ---
    # Any SQLAlchemy-compatible URL. Defaults to a local SQLite file for
    # zero-config local development.
    DATABASE_URL: str = "sqlite:///./sentiment_app.db"

    # --- Security / Auth ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    COOKIE_NAME: str = "session_token"
    # Set to True in production when served over HTTPS.
    COOKIE_SECURE: bool = False

    # --- CORS ---
    # Comma-separated list. Defaults cover the common local-dev combos
    # (localhost vs 127.0.0.1, on either the frontend's default port or
    # common alternates like VS Code Live Server's 5500/5501) so people
    # don't get silently blocked by an exact-string mismatch. Override
    # with your real frontend URL(s) in production.
    FRONTEND_ORIGINS: str = (
        "http://localhost:5500,http://127.0.0.1:5500,"
        "http://localhost:5501,http://127.0.0.1:5501,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    @property
    def frontend_origins_list(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    # --- Model ---
    # Directory containing config.json, model.safetensors, tokenizer files, etc.
    MODEL_PATH: str = "../model"
    # Only used when the checkpoint's own config.json names its classes
    # generically (LABEL_0, LABEL_1, ...). Format "index:name,index:name".
    # MUST match the label order used when the model was trained.
    LABEL_MAP: str = "0:negative,1:neutral,2:positive"
    MAX_BATCH_SIZE: int = 32
    MAX_INPUT_LENGTH: int = 2000  # characters, hard guard against abuse

    # --- Media upload (photo / short video) ---
    # Deliberately small: this is for screenshots, photos and short clips,
    # not long files. Mirrored in frontend/js/config.js for instant feedback.
    MAX_IMAGE_BYTES: int = 5 * 1024 * 1024
    MAX_VIDEO_BYTES: int = 20 * 1024 * 1024
    MAX_VIDEO_SECONDS: int = 30
    VIDEO_FRAME_SAMPLES: int = 6  # frames sampled evenly across the clip
    OCR_LANG: str = "eng"  # Tesseract language code(s), e.g. "eng+hin"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _require_real_secret_in_production(self):
        if self.ENV.lower() == "production" and self.SECRET_KEY in (
            "CHANGE_ME_IN_PRODUCTION",
            "",
        ):
            raise ValueError("SECRET_KEY must be set to a real secret when ENV=production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
