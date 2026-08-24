
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(
    __file__
).resolve().parents[2]

PROJECT_ROOT = BASE_DIR

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(
    ENV_FILE
)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Application configuration.

    Configuration is loaded from environment variables and the project's
    .env file.

    Environment variable names are case-insensitive.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------

    app_name: str = Field(
        default="HR Screening Tool",
    )

    app_version: str = Field(
        default="1.0.0",
    )

    debug: bool = Field(
        default=False,
    )

    # -----------------------------------------------------------------------
    # Groq LLM
    # -----------------------------------------------------------------------

    groq_api_key: str = Field(
        default="",
    )

    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
    )

    groq_model: str = Field(
        default="openai/gpt-oss-20b",
    )

    # -----------------------------------------------------------------------
    # LLM Reliability
    # -----------------------------------------------------------------------

    llm_max_retries: int = Field(
        default=3,
        ge=0,
    )

    llm_retry_delay: float = Field(
        default=1.0,
        ge=0.0,
    )

    llm_request_timeout_seconds: float = Field(
        default=60.0,
        gt=0.0,
    )

    # -----------------------------------------------------------------------
    # File Uploads
    # -----------------------------------------------------------------------

    upload_dir: str = Field(
        default="uploads",
    )

    max_file_size_mb: int = Field(
        default=10,
        ge=1,
    )

    # -----------------------------------------------------------------------
    # Firebase
    # -----------------------------------------------------------------------

    firebase_credentials_path: str = Field(
        default="",
    )

    firebase_api_key: str = Field(default="")
    firebase_auth_domain: str = Field(default="")
    firebase_project_id: str = Field(default="")
    firebase_storage_bucket: str = Field(default="")
    firebase_messaging_sender_id: str = Field(default="")
    firebase_app_id: str = Field(default="")

    # -----------------------------------------------------------------------
    # CV Processing
    # -----------------------------------------------------------------------

    max_cv_file_size_mb: int = Field(
        default=10,
        ge=1,
    )

    ocr_enabled: bool = Field(
        default=True,
    )

    ocr_language: str = Field(
        default="eng",
    )

    @property
    def max_file_size_bytes(self) -> int:
        """
        Return the maximum general upload size in bytes.
        """

        return (
            self.max_file_size_mb
            * 1024
            * 1024
        )

    @property
    def max_cv_file_size_bytes(self) -> int:
        """
        Return the maximum CV upload size in bytes.
        """

        return (
            self.max_cv_file_size_mb
            * 1024
            * 1024
        )

    @property
    def upload_path(self) -> Path:
        """
        Return the absolute upload directory path.
        """

        upload_directory = Path(
            self.upload_dir
        )

        if upload_directory.is_absolute():
            return upload_directory

        return PROJECT_ROOT / upload_directory


# ---------------------------------------------------------------------------
# Global Settings Instance
# ---------------------------------------------------------------------------

settings = Settings()


# ---------------------------------------------------------------------------
# Backwards-Compatible Configuration Constants
# ---------------------------------------------------------------------------

# Groq
GROQ_API_KEY = settings.groq_api_key

GROQ_BASE_URL = settings.groq_base_url

GROQ_MODEL = settings.groq_model


# LLM reliability
LLM_MAX_RETRIES = settings.llm_max_retries

LLM_RETRY_DELAY = settings.llm_retry_delay

LLM_REQUEST_TIMEOUT_SECONDS = (
    settings.llm_request_timeout_seconds
)


# Firebase
FIREBASE_CREDENTIALS_PATH = (
    settings.firebase_credentials_path
)

FIREBASE_WEB_CONFIG = {
    "apiKey": settings.firebase_api_key,
    "authDomain": settings.firebase_auth_domain,
    "projectId": settings.firebase_project_id,
    "storageBucket": settings.firebase_storage_bucket,
    "messagingSenderId": settings.firebase_messaging_sender_id,
    "appId": settings.firebase_app_id,
}


# CV configuration
MAX_CV_FILE_SIZE_MB = (
    settings.max_cv_file_size_mb
)

MAX_CV_FILE_SIZE_BYTES = (
    settings.max_cv_file_size_bytes
)

OCR_ENABLED = settings.ocr_enabled

OCR_LANGUAGE = settings.ocr_language


# Upload configuration
UPLOAD_DIR = settings.upload_path

MAX_FILE_SIZE_MB = settings.max_file_size_mb

MAX_FILE_SIZE_BYTES = settings.max_file_size_bytes


# ---------------------------------------------------------------------------
# Supported CV Extensions
# ---------------------------------------------------------------------------

ALLOWED_CV_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


# ---------------------------------------------------------------------------
# Directory Initialization
# ---------------------------------------------------------------------------

def initialize_directories() -> None:
    """
    Create application directories required at runtime.
    """

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ---------------------------------------------------------------------------
# Environment Helpers
# ---------------------------------------------------------------------------

def get_groq_api_key() -> str:
    """
    Return the configured Groq API key.
    """

    return GROQ_API_KEY


def get_firebase_credentials_path() -> Path | None:
    """
    Return the configured Firebase credentials path.

    Returns None when no credentials path has been configured.
    """

    if not FIREBASE_CREDENTIALS_PATH:
        return None

    credentials_path = Path(
        FIREBASE_CREDENTIALS_PATH
    )

    if not credentials_path.is_absolute():
        credentials_path = (
            PROJECT_ROOT
            / credentials_path
        )

    return credentials_path
