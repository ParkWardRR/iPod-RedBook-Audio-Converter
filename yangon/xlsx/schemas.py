"""XLSX schema definitions."""

from enum import Enum

SCHEMA_VERSION = "1.0"


class ColumnOwner(str, Enum):
    """Who owns/controls a column."""

    TOOL = "tool"  # Tool-generated, user should not edit
    USER = "user"  # User-editable
    BOTH = "both"  # Tool generates, user can add notes


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
