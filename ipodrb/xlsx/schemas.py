"""XLSX schema definitions."""

from enum import Enum

SCHEMA_VERSION = "1.0"


class ColumnOwner(str, Enum):
    """Who owns/controls a column."""

    TOOL = "tool"  # Tool-generated, user should not edit
    USER = "user"  # User-editable
    BOTH = "both"  # Tool generates, user can add notes


# Action enum values and their descriptions for the Reference tab
ACTION_OPTIONS = [
    ("ALAC_PRESERVE", "Convert to ALAC, preserve source sample rate/bit depth (downconvert if >44.1kHz/16-bit)"),
    ("ALAC_16_44", "Convert to ALAC, force 16-bit/44.1kHz (Red Book standard)"),
    ("AAC", "Convert to AAC lossy (use aac_target_kbps column to set bitrate: 128/192/256/320)"),
    ("PASS_MP3", "Pass through MP3 files unchanged (no re-encoding)"),
    ("SKIP", "Skip this album entirely (do not convert)"),
]

# Status values and their meanings
STATUS_VALUES = [
    ("GREEN", "All required metadata/artwork present and meets quality threshold"),
    ("YELLOW", "Minor issues (e.g., missing year, ambiguous artwork)"),
    ("RED", "Critical issues (missing required tags or no artwork found)"),
]

# AAC bitrate options
AAC_BITRATE_OPTIONS = [128, 192, 256, 320]

# Column styling categories
COLUMN_STYLES = {
    "editable": {
        "fill_color": "C6EFCE",  # Light green
        "description": "User-editable: You can modify these values",
    },
    "computed": {
        "fill_color": "BDD7EE",  # Light blue
        "description": "Computed: Tool-generated based on analysis",
    },
    "info": {
        "fill_color": "F2F2F2",  # Light gray
        "description": "Informational: Source metadata (read-only)",
    },
}

# Map columns to style categories
COLUMN_STYLE_MAP = {
    # Informational (gray) - source metadata
    "album_id": "info",
    "source_path": "info",
    "artist": "info",
    "album": "info",
    "year": "info",
    "track_count": "info",
    "source_formats": "info",
    "max_sr_hz": "info",
    "max_bit_depth": "info",
    # Computed (blue) - tool analysis
    "default_action": "computed",
    "tag_status": "computed",
    "art_status": "computed",
    "plan_hash": "computed",
    "last_built_at": "computed",
    "error_code": "computed",
    # Editable (green) - user controls
    "user_action": "editable",
    "aac_target_kbps": "editable",
    "skip": "editable",
    "notes": "editable",
}


# Albums sheet column definitions
# Order matters - this is the column order in the sheet
ALBUMS_COLUMNS = [
    # Column name, owner, description
    ("album_id", ColumnOwner.TOOL, "Stable ID for album continuity"),
    ("source_path", ColumnOwner.TOOL, "Album directory path"),
    ("artist", ColumnOwner.TOOL, "Primary artist"),
    ("album", ColumnOwner.TOOL, "Album name"),
    ("year", ColumnOwner.TOOL, "Release year"),
    ("track_count", ColumnOwner.TOOL, "Number of tracks"),
    ("source_formats", ColumnOwner.TOOL, "Source audio formats (e.g., FLAC;MP3)"),
    ("max_sr_hz", ColumnOwner.TOOL, "Max sample rate in album"),
    ("max_bit_depth", ColumnOwner.TOOL, "Max bit depth in album"),
    ("default_action", ColumnOwner.TOOL, "Computed default action"),
    ("user_action", ColumnOwner.USER, "User override action"),
    ("aac_target_kbps", ColumnOwner.USER, "AAC bitrate if AAC action"),
    ("skip", ColumnOwner.USER, "Skip this album (TRUE/FALSE)"),
    ("tag_status", ColumnOwner.TOOL, "Tag quality: GREEN/YELLOW/RED"),
    ("art_status", ColumnOwner.TOOL, "Artwork quality: GREEN/YELLOW/RED"),
    ("plan_hash", ColumnOwner.TOOL, "Hash of resolved plan inputs"),
    ("last_built_at", ColumnOwner.TOOL, "Last successful build timestamp"),
    ("error_code", ColumnOwner.TOOL, "Error code if failed"),
    ("notes", ColumnOwner.BOTH, "Status notes and user comments"),
]

# User-editable columns that should be preserved on update
USER_COLUMNS = [col[0] for col in ALBUMS_COLUMNS if col[1] in (ColumnOwner.USER, ColumnOwner.BOTH)]

# Tool-generated columns
TOOL_COLUMNS = [col[0] for col in ALBUMS_COLUMNS if col[1] == ColumnOwner.TOOL]

# Column name to index mapping
COLUMN_INDEX = {col[0]: i for i, col in enumerate(ALBUMS_COLUMNS)}
