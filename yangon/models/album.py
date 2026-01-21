"""Album and track data models."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from yangon.models.status import ArtStatus, TagStatus


class AudioFormat(str, Enum):
    """Supported audio formats."""

    FLAC = "FLAC"
    WAV = "WAV"
    AIFF = "AIFF"
    ALAC = "ALAC"
    AAC = "AAC"
    MP3 = "MP3"
    OGG = "OGG"
    OPUS = "OPUS"
    WMA = "WMA"
    M4A = "M4A"  # Generic M4A (could be AAC or ALAC)
    APE = "APE"  # Monkey's Audio
    WV = "WV"  # WavPack
    SHN = "SHN"  # Shorten
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_codec(cls, codec: str) -> "AudioFormat":
        """Map FFmpeg codec name to AudioFormat."""
        codec_map = {
            "flac": cls.FLAC,
            "pcm_s16le": cls.WAV,
            "pcm_s24le": cls.WAV,
            "pcm_s32le": cls.WAV,
            "pcm_f32le": cls.WAV,
            "pcm_s16be": cls.AIFF,
            "pcm_s24be": cls.AIFF,
            "pcm_s32be": cls.AIFF,
            "alac": cls.ALAC,
            "aac": cls.AAC,
            "mp3": cls.MP3,
            "mp3float": cls.MP3,
            "vorbis": cls.OGG,
            "opus": cls.OPUS,
            "wmav2": cls.WMA,
            "wmav1": cls.WMA,
            "wmalossless": cls.WMA,
            "ape": cls.APE,
            "wavpack": cls.WV,
            "shorten": cls.SHN,
        }
        return codec_map.get(codec.lower(), cls.UNKNOWN)

    @classmethod
    def from_extension(cls, ext: str) -> "AudioFormat":
        """Map file extension to AudioFormat."""
        ext = ext.lower().lstrip(".")
        ext_map = {
            "flac": cls.FLAC,
            "wav": cls.WAV,
            "aiff": cls.AIFF,
            "aif": cls.AIFF,
            "m4a": cls.M4A,
            "mp3": cls.MP3,
            "ogg": cls.OGG,
            "oga": cls.OGG,
            "opus": cls.OPUS,
            "wma": cls.WMA,
            "ape": cls.APE,
            "wv": cls.WV,
            "shn": cls.SHN,
        }
        return ext_map.get(ext, cls.UNKNOWN)

    @property
    def is_lossless(self) -> bool:
        """Check if format is lossless."""
        return self in {
            AudioFormat.FLAC,
            AudioFormat.WAV,
            AudioFormat.AIFF,
            AudioFormat.ALAC,
            AudioFormat.APE,
            AudioFormat.WV,
            AudioFormat.SHN,
        }


class Track(BaseModel):
    """Individual track technical data and metadata."""

    path: Path
    format: AudioFormat
    sample_rate: int
    bit_depth: int | None = None  # None for lossy formats
    channels: int
    duration_seconds: float

    # Metadata
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    track_total: int | None = None
    disc_number: int | None = None
    disc_total: int | None = None
    year: int | None = None
    compilation: bool = False

    # Artwork
    has_embedded_art: bool = False
    embedded_art_width: int | None = None
    embedded_art_height: int | None = None

    # Fingerprint for caching
    mtime: float
    size_bytes: int

    model_config = {"arbitrary_types_allowed": True}


class AlbumMetadata(BaseModel):
    """Aggregated album-level metadata."""

    artist: str = ""
    album: str = ""
    album_artist: str | None = None
    year: int | None = None
    is_compilation: bool = False

    # Folder art candidates
    folder_art_candidates: list[Path] = Field(default_factory=list)
    folder_art_sizes: list[tuple[int, int]] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class Album(BaseModel):
    """Album detection result with all tracks and metadata."""

    album_id: str  # SHA256(relative_path)[:16]
    source_path: Path
    tracks: list[Track]
    metadata: AlbumMetadata

    # Technical rollup
    max_sample_rate: int = 44100
    max_bit_depth: int | None = 16
    source_formats: set[AudioFormat] = Field(default_factory=set)

    # Status
    tag_status: TagStatus = TagStatus.RED
    art_status: ArtStatus = ArtStatus.RED
    status_notes: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def track_count(self) -> int:
        """Number of tracks in album."""
        return len(self.tracks)

    @property
    def has_lossless(self) -> bool:
        """Check if album contains lossless sources."""
        return any(fmt.is_lossless for fmt in self.source_formats)

    @property
    def is_mp3_only(self) -> bool:
        """Check if album is MP3-only."""
        return self.source_formats == {AudioFormat.MP3}
