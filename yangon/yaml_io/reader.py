"""YAML plan reader for open-source users."""

from pathlib import Path
from typing import Any

import yaml


def read_yaml_plan(yaml_path: Path) -> dict[str, Any]:
    """
    Read YAML plan file.

    Args:
        yaml_path: Path to YAML plan file

    Returns:
        Parsed plan data
    """
    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Plan file not found: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty or invalid YAML file: {yaml_path}")

    return data


def get_yaml_decisions(yaml_path: Path) -> list[dict[str, Any]]:
    """
    Get album decisions from YAML plan file.

    Args:
        yaml_path: Path to YAML plan file

    Returns:
        List of album decision dicts with keys:
        - album_id
        - user_action
        - aac_target_kbps
        - skip
    """
    data = read_yaml_plan(yaml_path)
    albums = data.get("albums", [])

    decisions = []
    for album in albums:
        decision = {
            "album_id": album.get("album_id", ""),
            "user_action": album.get("user_action"),
            "aac_target_kbps": album.get("aac_bitrate_kbps"),
            "skip": album.get("skip", False),
        }
        decisions.append(decision)

    return decisions


def get_yaml_library_root(yaml_path: Path) -> Path | None:
    """
    Get library root from YAML plan metadata.

    Args:
        yaml_path: Path to YAML plan file

    Returns:
        Library root path or None if not found
    """
    data = read_yaml_plan(yaml_path)
    metadata = data.get("metadata", {})
    library_root = metadata.get("library_root")

    if library_root:
        return Path(library_root)

    return None


def get_yaml_summary(yaml_path: Path) -> dict[str, Any]:
    """
    Get summary information from YAML plan.

    Args:
        yaml_path: Path to YAML plan file

    Returns:
        Summary dict with album/track counts, statuses, etc.
    """
    data = read_yaml_plan(yaml_path)
    metadata = data.get("metadata", {})
    albums = data.get("albums", [])

    # Count by status
    tag_status_counts: dict[str, int] = {}
    art_status_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}

    for album in albums:
        analysis = album.get("analysis", {})

        tag_status = analysis.get("tag_status", "UNKNOWN")
        tag_status_counts[tag_status] = tag_status_counts.get(tag_status, 0) + 1

        art_status = analysis.get("art_status", "UNKNOWN")
        art_status_counts[art_status] = art_status_counts.get(art_status, 0) + 1

        # Use user_action if set, otherwise default_action
        action = album.get("user_action") or analysis.get("default_action", "UNKNOWN")
        if album.get("skip"):
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
