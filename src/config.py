"""Configuration management for LLM Quant Lab (ROCm).

This module loads and validates all configuration from environment variables.
It will fail fast with clear error messages if required variables are missing.
"""

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


def _get_project_root() -> Path:
    """Get the project root directory."""
    # Assume this file is at src/config.py
    return Path(__file__).parent.parent.resolve()


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    
    host: str = Field(..., validation_alias="POSTGRES_HOST")
    port: int = Field(..., validation_alias="POSTGRES_PORT")
    user: str = Field(..., validation_alias="POSTGRES_USER")
    password: str = Field(..., validation_alias="POSTGRES_PASSWORD")
    database: str = Field(..., validation_alias="POSTGRES_DB")
    
    @property
    def url(self) -> str:
        """Get the full database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class ROCmConfig(BaseSettings):
    """ROCm GPU configuration for AMD GPUs."""
    
    hip_visible_devices: str = Field(..., validation_alias="HIP_VISIBLE_DEVICES")
    hsa_override_gfx_version: str | None = Field(None, validation_alias="HSA_OVERRIDE_GFX_VERSION")
    pytorch_rocm_arch: str | None = Field(None, validation_alias="PYTORCH_ROCM_ARCH")
    
    @field_validator("hip_visible_devices")
    @classmethod
    def validate_hip_devices(cls, v: str) -> str:
        """Validate HIP_VISIBLE_DEVICES format."""
        if not v or not v.strip():
            raise ValueError(
                "HIP_VISIBLE_DEVICES must be set to GPU indices (e.g., '0' or '0,1'). "
                "Run `rocm-smi` to see available GPUs."
            )
        # Validate format: should be comma-separated integers
        try:
            devices = [int(d.strip()) for d in v.split(",")]
            if any(d < 0 for d in devices):
                raise ValueError("GPU indices must be non-negative")
        except ValueError as e:
            raise ValueError(
                f"Invalid HIP_VISIBLE_DEVICES format: '{v}'. "
                "Must be comma-separated GPU indices (e.g., '0' or '0,1')."
            ) from e
        return v
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class HuggingFaceConfig(BaseSettings):
    """HuggingFace configuration."""
    
    token: str = Field(..., validation_alias="HF_TOKEN")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class ScientistLLMConfig(BaseSettings):
    """Scientist LLM configuration for AI-generated reports."""
    
    provider: Literal["openai", "anthropic", "local", "openrouter"] = Field(
        ..., validation_alias="SCIENTIST_LLM_PROVIDER"
    )
    base_url: str = Field(..., validation_alias="SCIENTIST_LLM_BASE_URL")
    api_key: str = Field(..., validation_alias="SCIENTIST_LLM_API_KEY")
    model: str = Field(..., validation_alias="SCIENTIST_LLM_MODEL")
    timeout: int = Field(..., validation_alias="SCIENTIST_LLM_TIMEOUT")
    
    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("SCIENTIST_LLM_TIMEOUT must be a positive integer")
        return v
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class PathsConfig(BaseSettings):
    """Local path configuration."""
    
    models_dir: str = Field(".local/models", validation_alias="LOCAL_MODELS_DIR")
    data_dir: str = Field(".local/data", validation_alias="LOCAL_DATA_DIR")
    cache_dir: str = Field(".local/cache", validation_alias="LOCAL_CACHE_DIR")
    reports_dir: str = Field("reports", validation_alias="LOCAL_REPORTS_DIR")
    outputs_dir: str = Field("outputs", validation_alias="LOCAL_OUTPUTS_DIR")
    
    _project_root: Path = _get_project_root()
    
    @property
    def models_path(self) -> Path:
        """Get absolute path to models directory."""
        return self._project_root / self.models_dir
    
    @property
    def data_path(self) -> Path:
        """Get absolute path to data directory."""
        return self._project_root / self.data_dir
    
    @property
    def cache_path(self) -> Path:
        """Get absolute path to cache directory."""
        return self._project_root / self.cache_dir
    
    @property
    def reports_path(self) -> Path:
        """Get absolute path to reports directory."""
        return self._project_root / self.reports_dir
    
    @property
    def outputs_path(self) -> Path:
        """Get absolute path to outputs directory."""
        return self._project_root / self.outputs_dir
    
    def ensure_directories(self) -> None:
        """Create all directories if they don't exist."""
        for path in [
            self.models_path,
            self.data_path,
            self.cache_path,
            self.reports_path,
            self.outputs_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class PortsConfig(BaseSettings):
    """Service port configuration."""
    
    api: int = Field(..., validation_alias="API_PORT")
    frontend: int = Field(..., validation_alias="FRONTEND_PORT")
    vllm: int | None = Field(None, validation_alias="VLLM_PORT")
    pgadmin: int | None = Field(None, validation_alias="PGADMIN_PORT")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", validation_alias="LOG_LEVEL"
    )
    format: Literal["json", "text"] = Field("text", validation_alias="LOG_FORMAT")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class Settings:
    """Main settings class that aggregates all configuration."""
    
    _instance: "Settings | None" = None
    _initialized: bool = False
    
    def __new__(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._load_config()
        self._initialized = True
    
    def _load_config(self) -> None:
        """Load and validate all configuration."""
        errors: list[str] = []
        
        # Load each config section, collecting errors
        try:
            self.database = DatabaseConfig()
        except Exception as e:
            errors.append(f"Database configuration error: {e}")
            self.database = None  # type: ignore
        
        try:
            self.rocm = ROCmConfig()
        except Exception as e:
            errors.append(f"ROCm GPU configuration error: {e}")
            self.rocm = None  # type: ignore
        
        try:
            self.huggingface = HuggingFaceConfig()
        except Exception as e:
            errors.append(f"HuggingFace configuration error: {e}")
            self.huggingface = None  # type: ignore
        
        try:
            self.scientist_llm = ScientistLLMConfig()
        except Exception as e:
            errors.append(f"Scientist LLM configuration error: {e}")
            self.scientist_llm = None  # type: ignore
        
        try:
            self.paths = PathsConfig()
        except Exception as e:
            errors.append(f"Paths configuration error: {e}")
            self.paths = None  # type: ignore
        
        try:
            self.ports = PortsConfig()
        except Exception as e:
            errors.append(f"Ports configuration error: {e}")
            self.ports = None  # type: ignore
        
        try:
            self.logging = LoggingConfig()
        except Exception as e:
            errors.append(f"Logging configuration error: {e}")
            self.logging = LoggingConfig.model_construct(level="INFO", format="text")
        
        # If there are errors, fail fast with clear message
        if errors:
            error_msg = "\n".join([
                "",
                "=" * 70,
                "CONFIGURATION ERROR - LLM Quant Lab failed to start",
                "=" * 70,
                "",
                "The following configuration errors were found:",
                "",
                *[f"  • {e}" for e in errors],
                "",
                "Please copy config/env.template to .env and fill in all required values.",
                "",
                "=" * 70,
            ])
            print(error_msg, file=sys.stderr)
            raise ConfigurationError(f"Configuration validation failed: {len(errors)} error(s)")
    
    def setup_environment(self) -> None:
        """Set up environment variables for libraries."""
        if self.paths:
            self.paths.ensure_directories()
            
            # Set HuggingFace environment variables
            os.environ["HF_HOME"] = str(self.paths.cache_path)
            os.environ["TRANSFORMERS_CACHE"] = str(self.paths.cache_path)
            os.environ["HF_DATASETS_CACHE"] = str(self.paths.data_path)
        
        if self.huggingface:
            os.environ["HF_TOKEN"] = self.huggingface.token
        
        if self.rocm:
            os.environ["HIP_VISIBLE_DEVICES"] = self.rocm.hip_visible_devices
            if self.rocm.hsa_override_gfx_version:
                os.environ["HSA_OVERRIDE_GFX_VERSION"] = self.rocm.hsa_override_gfx_version
            if self.rocm.pytorch_rocm_arch:
                os.environ["PYTORCH_ROCM_ARCH"] = self.rocm.pytorch_rocm_arch


def get_settings() -> Settings:
    """Get the global settings instance.
    
    This will fail fast if configuration is invalid.
    """
    return Settings()


def get_database_url() -> str:
    """Get the database URL, failing fast if not configured."""
    settings = get_settings()
    if settings.database is None:
        raise ConfigurationError("Database not configured")
    return settings.database.url


# Convenience function for optional loading (e.g., in tests)
def try_load_settings() -> Settings | None:
    """Try to load settings, returning None if configuration is invalid."""
    try:
        return get_settings()
    except ConfigurationError:
        return None
