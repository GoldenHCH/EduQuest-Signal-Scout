"""Configuration management for Utah Board Signal Scout."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Model configuration
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Pipeline configuration
    max_docs_per_district: int = 10
    chunk_size_tokens: int = 1200
    chunk_overlap_tokens: int = 100
    confidence_threshold: float = 0.7
    score_threshold: int = 50
    crawl_depth: int = 2
    request_delay: float = 1.0

    # Paths (relative to project root)
    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent

    @property
    def data_dir(self) -> Path:
        """Get data directory."""
        return self.project_root / "data"

    @property
    def raw_docs_dir(self) -> Path:
        """Get raw documents directory."""
        return self.data_dir / "raw_docs"

    @property
    def extracted_text_dir(self) -> Path:
        """Get extracted text directory."""
        return self.data_dir / "extracted_text"

    @property
    def outputs_dir(self) -> Path:
        """Get outputs directory."""
        return self.data_dir / "outputs"

    @property
    def logs_dir(self) -> Path:
        """Get logs directory."""
        return self.data_dir / "logs"

    @property
    def districts_csv(self) -> Path:
        """Get path to districts CSV."""
        return self.data_dir / "utah_districts.csv"

    @property
    def artifacts_csv(self) -> Path:
        """Get path to artifacts CSV."""
        return self.outputs_dir / "artifacts.csv"

    @property
    def chunks_jsonl(self) -> Path:
        """Get path to chunks JSONL."""
        return self.outputs_dir / "chunks.jsonl"

    @property
    def evaluations_jsonl(self) -> Path:
        """Get path to evaluations JSONL."""
        return self.outputs_dir / "evaluations.jsonl"

    @property
    def signals_csv(self) -> Path:
        """Get path to signals CSV."""
        return self.outputs_dir / "signals.csv"

    @property
    def signals_json(self) -> Path:
        """Get path to signals JSON."""
        return self.outputs_dir / "signals.json"

    @property
    def top_signals_md(self) -> Path:
        """Get path to top signals markdown."""
        return self.outputs_dir / "top_signals.md"


# Global settings instance
settings = Settings()
