"""CSV/TSV plan reader for open-source users."""

import csv
import io
import re
from pathlib import Path
from typing import Any


def detect_delimiter(csv_path: Path) -> str:
    """Detect delimiter from file extension or content."""
    if csv_path.suffix.lower() == ".tsv":
        return "\t"
    elif csv_path.suffix.lower() == ".csv":
        return ","
    else:
        # Try to auto-detect from first data line
        with open(csv_path, encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    if "\t" in line:
                        return "\t"
                    return ","
        return "\t"  # Default to TSV


def read_csv_plan(csv_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Read CSV/TSV plan file.

    Args:
        csv_path: Path to CSV/TSV plan file

    Returns:
        Tuple of (metadata dict, list of album dicts)
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"Plan file not found: {csv_path}")

    delimiter = detect_delimiter(csv_path)
    metadata: dict[str, Any] = {}
    albums: list[dict[str, Any]] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        lines = []
        for line in f:
            if line.startswith("#"):
                # Parse metadata from comments
                parse_metadata_comment(line, metadata)
            else:
                lines.append(line)

        if not lines:
            return metadata, albums

        # Parse CSV from non-comment lines
        reader = csv.DictReader(io.StringIO("".join(lines)), delimiter=delimiter)
        for row in reader:
            if row.get("album_id"):
                albums.append(dict(row))

    return metadata, albums


def parse_metadata_comment(line: str, metadata: dict[str, Any]) -> None:
    """Parse metadata from comment line."""
    line = line.lstrip("#").strip()

    # Match key: value patterns
    patterns = [
        (r"Library:\s*(.+)", "library_root"),
        (r"Albums:\s*(\d+)", "total_albums"),
        (r"Tracks:\s*(\d+)", "total_tracks"),
        (r"Size:\s*([\d.]+)\s*MB", "total_size_mb"),
        (r"Generated:\s*(.+)", "created_at"),
        (r"Schema:\s*(.+)", "schema_version"),
    ]

    for pattern, key in patterns:
        match = re.match(pattern, line)
        if match:
            value = match.group(1)
            if key in ("total_albums", "total_tracks"):
                metadata[key] = int(value)
            elif key == "total_size_mb":
                metadata[key] = float(value)
            else:
                metadata[key] = value
            break


def get_csv_decisions(csv_path: Path) -> list[dict[str, Any]]:
    """
    Get album decisions from CSV/TSV plan file.

    Args:
        csv_path: Path to CSV/TSV plan file

    Returns:
        List of album decision dicts with keys:
        - album_id
        - user_action
        - aac_target_kbps
        - skip
    """
    _, albums = read_csv_plan(csv_path)

    decisions = []
    for album in albums:
        # Parse aac_bitrate
        aac_bitrate = None
        if album.get("aac_bitrate_kbps"):
            try:
                aac_bitrate = int(album["aac_bitrate_kbps"])
            except ValueError:
                pass

        # Parse skip flag
        skip = album.get("skip", "").lower() in ("true", "yes", "1")

        decision = {
            "album_id": album.get("album_id", ""),
            "user_action": album.get("user_action") or None,
            "aac_target_kbps": aac_bitrate,
            "skip": skip,
        }
        decisions.append(decision)

    return decisions


def get_csv_library_root(csv_path: Path) -> Path | None:
    """
    Get library root from CSV/TSV plan metadata.

    Args:
        csv_path: Path to CSV/TSV plan file

    Returns:
        Library root path or None if not found
    """
    metadata, _ = read_csv_plan(csv_path)
    library_root = metadata.get("library_root")

    if library_root:
        return Path(library_root)

    return None


def get_csv_summary(csv_path: Path) -> dict[str, Any]:
    """
    Get summary information from CSV/TSV plan.

    Args:
        csv_path: Path to CSV/TSV plan file

    Returns:
        Summary dict with album/track counts, statuses, etc.
    """
    metadata, albums = read_csv_plan(csv_path)

    # Count by status
    tag_status_counts: dict[str, int] = {}
    art_status_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}

    for album in albums:
        tag_status = album.get("tag_status", "UNKNOWN")
        tag_status_counts[tag_status] = tag_status_counts.get(tag_status, 0) + 1

        art_status = album.get("art_status", "UNKNOWN")
        art_status_counts[art_status] = art_status_counts.get(art_status, 0) + 1

        # Use user_action if set, otherwise default_action
        action = album.get("user_action") or album.get("default_action", "UNKNOWN")
        if album.get("skip", "").lower() in ("true", "yes", "1"):
            action = "SKIP"
        action_counts[action] = action_counts.get(action, 0) + 1

    return {
        "library_root": metadata.get("library_root"),
        "total_albums": metadata.get("total_albums", len(albums)),
        "total_tracks": metadata.get("total_tracks", 0),
        "total_size_mb": metadata.get("total_size_mb", 0),
        "created_at": metadata.get("created_at"),
        "tag_status_counts": tag_status_counts,
        "art_status_counts": art_status_counts,
        "action_counts": action_counts,
    }
