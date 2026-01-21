"""YAML plan writer for open-source users.

Generates a human-readable YAML file as an alternative to XLSX.
The YAML format is:
- Easy to edit in any text editor
- Version control friendly (good diffs)
- No proprietary software required
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from yangon.models.album import Album
from yangon.planner.defaults import compute_default_action
from yangon.xlsx.schemas import SCHEMA_VERSION


def write_yaml_plan(
    albums: list[Album],
    yaml_path: Path,
    library_root: Path,
    preserve_user_edits: bool = True,
) -> None:
    """
    Write conversion plan to YAML file.

    Args:
        albums: List of scanned albums
        yaml_path: Path to output YAML file
        library_root: Root directory of music library
        preserve_user_edits: If True, preserve user edits from existing file
    """
    yaml_path = Path(yaml_path)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data if preserving edits
    existing_data: dict[str, dict] = {}
    if preserve_user_edits and yaml_path.exists():
        existing = read_existing_yaml(yaml_path)
        existing_data = {a["album_id"]: a for a in existing.get("albums", [])}

    # Build plan data
    plan_data = build_plan_data(albums, library_root, existing_data)

    # Write with atomic replacement
    temp_path = yaml_path.parent / f"{yaml_path.name}.tmp"
    try:
        # Backup existing file
        if yaml_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = yaml_path.parent / f"{yaml_path.stem}.{timestamp}.yaml"
            shutil.copy2(yaml_path, backup_path)

        # Write YAML with nice formatting
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(generate_yaml_header())
            yaml.dump(plan_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Atomic replace
        os.replace(temp_path, yaml_path)

    finally:
        if temp_path.exists():
            temp_path.unlink()


def read_existing_yaml(yaml_path: Path) -> dict:
    """Read existing YAML plan file."""
    try:
        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def compute_album_size(album: Album) -> int:
    """Compute total size of all tracks in album."""
    return sum(t.size_bytes for t in album.tracks)


def build_plan_data(
    albums: list[Album],
    library_root: Path,
    existing_data: dict[str, dict],
) -> dict[str, Any]:
    """Build the plan data structure."""
    # Summary metadata
    total_tracks = sum(a.track_count for a in albums)
    total_size = sum(compute_album_size(a) for a in albums)

    plan = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now().isoformat(),
            "library_root": str(library_root),
            "total_albums": len(albums),
            "total_tracks": total_tracks,
            "total_size_mb": round(total_size / (1024 * 1024), 1),
        },
        "reference": {
            "actions": {
                "ALAC_PRESERVE": "Convert to ALAC, preserve source sample rate/bit depth",
                "ALAC_16_44": "Convert to ALAC, force 16-bit/44.1kHz (Red Book)",
                "AAC": "Convert to AAC lossy (set aac_bitrate_kbps: 128/192/256/320)",
                "PASS_MP3": "Pass through MP3 files unchanged",
                "SKIP": "Skip this album entirely",
            },
            "statuses": {
                "GREEN": "All metadata present and consistent",
                "YELLOW": "Minor issues (missing year, slight inconsistencies)",
                "RED": "Major issues (missing required tags, no artwork)",
            },
            "aac_bitrates": [128, 192, 256, 320],
        },
        "albums": [],
    }

    # Build album entries
    for album in albums:
        existing = existing_data.get(album.album_id, {})
        album_entry = build_album_entry(album, existing)
        plan["albums"].append(album_entry)

    return plan


def build_album_entry(album: Album, existing: dict) -> dict[str, Any]:
    """Build a single album entry."""
    meta = album.metadata
    default_action = compute_default_action(album)

    # Get formats and sample rates
    formats = list(set(t.format for t in album.tracks if t.format))
    sample_rates = list(set(t.sample_rate for t in album.tracks))
    bit_depths = list(set(t.bit_depth for t in album.tracks if t.bit_depth))

    # Preserve user edits
    user_action = existing.get("user_action")
    aac_bitrate = existing.get("aac_bitrate_kbps")
    skip = existing.get("skip", False)

    # Compute album size
    album_size = compute_album_size(album)

    entry = {
        "album_id": album.album_id,
        # ─── User-editable fields (edit these!) ───
        "user_action": user_action,  # Set to override default_action
        "aac_bitrate_kbps": aac_bitrate,  # Only used if action is AAC
        "skip": skip,  # Set to true to skip this album
        # ─── Album info (read-only) ───
        "info": {
            "artist": meta.album_artist or meta.artist or "Unknown",
            "album": meta.album or "Unknown",
            "year": meta.year,
            "track_count": album.track_count,
            "path": str(album.source_path),
        },
        # ─── Analysis results (read-only) ───
        "analysis": {
            "default_action": default_action.value,
            "tag_status": album.tag_status.value if album.tag_status else "UNKNOWN",
            "art_status": album.art_status.value if album.art_status else "UNKNOWN",
            "formats": [str(f) for f in formats],  # Convert to strings
            "sample_rates": sample_rates,
            "bit_depths": bit_depths,
            "total_size_mb": round(album_size / (1024 * 1024), 2),
        },
    }

    return entry


def generate_yaml_header() -> str:
    """Generate helpful header comment for the YAML file."""
    return """# ═══════════════════════════════════════════════════════════════════════════
# iPod Audio Converter - Conversion Plan
# ═══════════════════════════════════════════════════════════════════════════
#
# This file contains the conversion plan for your music library.
# Edit this file to customize how each album is converted.
#
# ─── QUICK START ───
# 1. Review each album's analysis (tag_status, art_status, default_action)
# 2. To override the default action, set 'user_action' to your choice
# 3. To skip an album, set 'skip: true'
# 4. For AAC encoding, set 'user_action: AAC' and optionally 'aac_bitrate_kbps'
# 5. Save and run: yangon apply --plan <this_file> --out <output_dir>
#
# ─── EDITABLE FIELDS ───
# - user_action: Override the default conversion action
# - aac_bitrate_kbps: Set AAC bitrate (128, 192, 256, 320)
# - skip: Set to true to exclude album from conversion
#
# ─── STATUS COLORS ───
# - GREEN: Metadata is complete and consistent
# - YELLOW: Minor issues (might want to fix source files)
# - RED: Major issues (consider fixing or skipping)
#
# ═══════════════════════════════════════════════════════════════════════════

"""
