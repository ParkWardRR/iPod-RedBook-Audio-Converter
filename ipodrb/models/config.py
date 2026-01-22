"""Configuration models."""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ScanConfig(BaseModel):
    """Configuration for scan command."""

    library_root: Path
    xlsx_path: Path
    recreate: bool = False
    normalize_tags: bool = False
    threads: int = 32  # High for I/O-bound NAS scanning
    show_tui: bool = True

    # Status thresholds
    art_min_size: int = 300  # Minimum 300x300 for GREEN

    # File patterns
    audio_extensions: set[str] = Field(
        default_factory=lambda: {
            ".flac",
            ".wav",
            ".aiff",
            ".aif",
            ".m4a",
            ".mp3",
            ".ogg",
            ".oga",
            ".opus",
            ".wma",
            ".ape",
            ".wv",
            ".shn",
        }
    )
    art_patterns: list[str] = Field(
        default_factory=lambda: [
            "cover.*",
            "folder.*",
            "front.*",
            "album.*",
            "art.*",
        ]
    )

    model_config = {"arbitrary_types_allowed": True}


class ApplyConfig(BaseModel):
    """Configuration for apply command."""

    xlsx_path: Path
    output_root: Path
    dry_run: bool = False
    fail_fast: bool = False
    threads: int = Field(default=8)  # CPU-bound encoding
    show_tui: bool = True
    force: bool = False  # Rebuild even if cached

    # Audio encoding defaults
    default_aac_bitrate: int = 256  # kbps
    allowed_aac_bitrates: set[int] = Field(
        default_factory=lambda: {128, 192, 256, 320}
    )
    target_sample_rate: int = 44100  # Target sample rate (44100 or 48000)

    # Output path template
    path_template: str = "{album_artist}/{year} - {album}/{disc_prefix}{track:02d} {title}"

    # Cache settings
    cache_db_name: str = ".ipodrb_cache.db"

    model_config = {"arbitrary_types_allowed": True}


class Config(BaseSettings):
    """Global configuration from environment or defaults."""

    # Tool version for cache invalidation
    tool_version: str = "0.1.0"

    # FFmpeg settings
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    ffmpeg_timeout: int = 300  # 5 minutes per track

    # Logging
    log_level: str = "INFO"
    jsonl_log: bool = True

    model_config = {"env_prefix": "IPODRB_"}
