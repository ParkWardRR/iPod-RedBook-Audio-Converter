"""CSV/TSV plan writer for open-source users.

Generates a human-readable CSV or TSV file as an alternative to XLSX.
The CSV/TSV format is:
- Easy to edit in any spreadsheet app (Excel, Numbers, Google Sheets, LibreOffice)
- Also editable in any text editor
- Version control friendly (good diffs)
- No proprietary software required
- TSV (tab-separated) is default since it handles commas in data better
"""

import csv
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from yangon.models.album import Album
from yangon.planner.defaults import compute_default_action
from yangon.xlsx.schemas import SCHEMA_VERSION


# Column definitions for the CSV/TSV file
CSV_COLUMNS = [
    # User-editable columns
    "album_id",
    "user_action",
    "aac_bitrate_kbps",
    "skip",
    # Album info (read-only)
    "artist",
    "album",
    "year",
    "track_count",
    "path",
    # Analysis (read-only)
    "default_action",
    "tag_status",
    "art_status",
    "formats",
    "sample_rates",
    "bit_depths",
    "total_size_mb",
]


def write_csv_plan(
    albums: list[Album],
    csv_path: Path,
    library_root: Path,
    preserve_user_edits: bool = True,
    use_tsv: bool = True,
) -> None:
    """
    Write conversion plan to CSV/TSV file.

    Args:
        albums: List of scanned albums
        csv_path: Path to output CSV/TSV file
        library_root: Root directory of music library
        preserve_user_edits: If True, preserve user edits from existing file
        use_tsv: If True, use tab separator (TSV), otherwise comma (CSV)
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine delimiter from extension or parameter
    delimiter = "\t" if use_tsv or csv_path.suffix.lower() == ".tsv" else ","

    # Load existing data if preserving edits
    existing_data: dict[str, dict] = {}
    if preserve_user_edits and csv_path.exists():
        existing_data = read_existing_csv(csv_path, delimiter)

    # Write with atomic replacement
    temp_path = csv_path.parent / f"{csv_path.name}.tmp"
    try:
        # Backup existing file
        if csv_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = csv_path.parent / f"{csv_path.stem}.{timestamp}{csv_path.suffix}"
            shutil.copy2(csv_path, backup_path)

        with open(temp_path, "w", newline="", encoding="utf-8") as f:
            # Write header comment with metadata
            write_header_comments(f, albums, library_root, delimiter)

            # Write CSV data
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=delimiter)
            writer.writeheader()

            for album in albums:
                existing = existing_data.get(album.album_id, {})
                row = build_album_row(album, existing)
                writer.writerow(row)

        # Atomic replace
        os.replace(temp_path, csv_path)

    finally:
        if temp_path.exists():
            temp_path.unlink()


def read_existing_csv(csv_path: Path, delimiter: str = "\t") -> dict[str, dict]:
    """Read existing CSV/TSV plan file and extract user edits."""
    existing_data: dict[str, dict] = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            # Skip comment lines
            lines = []
            for line in f:
                if not line.startswith("#"):
                    lines.append(line)

            if not lines:
                return {}

            # Parse CSV from non-comment lines
            import io
            reader = csv.DictReader(io.StringIO("".join(lines)), delimiter=delimiter)
            for row in reader:
                album_id = row.get("album_id", "")
                if album_id:
                    existing_data[album_id] = {
                        "user_action": row.get("user_action") or None,
                        "aac_bitrate_kbps": int(row["aac_bitrate_kbps"]) if row.get("aac_bitrate_kbps") else None,
                        "skip": row.get("skip", "").lower() in ("true", "yes", "1"),
                    }
    except Exception:
        pass

    return existing_data


def write_header_comments(
    f,
    albums: list[Album],
    library_root: Path,
    delimiter: str,
) -> None:
    """Write header comments with metadata and instructions."""
    total_tracks = sum(a.track_count for a in albums)
    total_size = sum(sum(t.size_bytes for t in a.tracks) for a in albums)
    size_mb = round(total_size / (1024 * 1024), 1)

    fmt = "TSV" if delimiter == "\t" else "CSV"

    lines = [
        f"# iPod Audio Converter - Conversion Plan ({fmt})",
        f"# Generated: {datetime.now().isoformat()}",
        f"# Schema: {SCHEMA_VERSION}",
        "#",
        f"# Library: {library_root}",
        f"# Albums: {len(albums)}",
        f"# Tracks: {total_tracks}",
        f"# Size: {size_mb} MB",
        "#",
        "# ─── EDITABLE COLUMNS ───",
        "# user_action     - Override default (ALAC_PRESERVE, ALAC_16_44, AAC, PASS_MP3, SKIP)",
        "# aac_bitrate_kbps - AAC bitrate if action is AAC (128, 192, 256, 320)",
        "# skip            - Set to TRUE to skip this album",
        "#",
        "# ─── READ-ONLY COLUMNS ───",
        "# default_action  - Recommended action based on source format",
        "# tag_status      - GREEN (good), YELLOW (minor issues), RED (major issues)",
        "# art_status      - GREEN (good artwork), YELLOW (issues), RED (missing)",
        "#",
        "# To apply: yangon apply --plan <this_file> --out <output_dir>",
        "#",
    ]

    for line in lines:
        f.write(line + "\n")


def build_album_row(album: Album, existing: dict) -> dict[str, Any]:
    """Build a single album row for CSV."""
    meta = album.metadata
    default_action = compute_default_action(album)

    # Get formats and sample rates as strings
    formats = ",".join(str(t.format) for t in album.tracks if t.format)
    formats = formats.replace("AudioFormat.", "")  # Clean up enum names
    sample_rates = ",".join(str(sr) for sr in sorted(set(t.sample_rate for t in album.tracks)))
    bit_depths = ",".join(str(bd) for bd in sorted(set(t.bit_depth for t in album.tracks if t.bit_depth)))

    # Compute album size
    album_size = sum(t.size_bytes for t in album.tracks)

    # Preserve user edits
    user_action = existing.get("user_action") or ""
    aac_bitrate = existing.get("aac_bitrate_kbps") or ""
    skip = "TRUE" if existing.get("skip") else ""

    return {
        "album_id": album.album_id,
        "user_action": user_action,
        "aac_bitrate_kbps": aac_bitrate,
        "skip": skip,
        "artist": meta.album_artist or meta.artist or "Unknown",
        "album": meta.album or "Unknown",
        "year": meta.year or "",
        "track_count": album.track_count,
        "path": str(album.source_path),
        "default_action": default_action.value,
        "tag_status": album.tag_status.value if album.tag_status else "UNKNOWN",
        "art_status": album.art_status.value if album.art_status else "UNKNOWN",
        "formats": formats,
        "sample_rates": sample_rates,
        "bit_depths": bit_depths,
        "total_size_mb": round(album_size / (1024 * 1024), 2),
    }
