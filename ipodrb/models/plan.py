"""Build plan and action models."""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Action(str, Enum):
    """Album conversion action types."""

    ALAC_PRESERVE = "ALAC_PRESERVE"  # Convert to ALAC, downconvert only if needed
    ALAC_16_44 = "ALAC_16_44"  # Force 16/44.1 ALAC (never upconvert)
    AAC = "AAC"  # Convert to AAC
    PASS_MP3 = "PASS_MP3"  # Pass through MP3 unchanged
    SKIP = "SKIP"  # Skip this album entirely


class ResolvedAction(BaseModel):
    """Per-album resolved decision."""

    album_id: str
    action: Action
    aac_bitrate_kbps: int | None = None  # Only if action == AAC
    skip: bool = False

    # Provenance
    default_action: Action
    user_action: Action | None = None
    source: str = "default"  # "default" | "user_override"


class TrackJob(BaseModel):
    """Individual track work unit for conversion pipeline."""

    album_id: str
    source_path: Path
    output_path: Path

    # Processing parameters
    action: Action
    target_codec: str  # "alac", "aac", "copy"
    target_sample_rate: int
    target_bit_depth: int | None
    aac_bitrate_kbps: int | None = None
    apply_dither: bool = False

    # Metadata to write
    tags: dict[str, str | int | None] = Field(default_factory=dict)
    artwork_source: Path | None = None  # Path to artwork file or None for embedded

    # Cache key components
    source_mtime: float
    source_size: int
    settings_hash: str = ""

    model_config = {"arbitrary_types_allowed": True}


class TrackResult(BaseModel):
    """Result of processing a single track."""

    source_path: Path
    output_path: Path | None = None
    success: bool = False
    error_code: str | None = None
    error_message: str | None = None

    # Output info
    output_codec: str | None = None
    output_sample_rate: int | None = None
    output_bit_depth: int | None = None
    output_size_bytes: int | None = None
    duration_seconds: float | None = None

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"arbitrary_types_allowed": True}


class BuildPlan(BaseModel):
    """Full build plan for apply command."""

    jobs: list[TrackJob] = Field(default_factory=list)
    skipped_albums: list[str] = Field(default_factory=list)  # album_ids
    validation_errors: list[dict] = Field(default_factory=list)

    @property
    def total_tracks(self) -> int:
        """Total number of tracks to process."""
        return len(self.jobs)
