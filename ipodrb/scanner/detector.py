"""Album detection and library scanning orchestration."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from ipodrb.models.album import Album
from ipodrb.models.config import Config, ScanConfig
from ipodrb.scanner.analyzer import analyze_album
from ipodrb.scanner.walker import walk_library


def detect_albums(
    library_root: Path,
    scan_config: ScanConfig,
    config: Config | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Album]:
    """
    Scan library and detect all albums.

    Uses parallel processing for I/O-bound operations.

    Args:
        library_root: Root directory of music library
        scan_config: Scan configuration
        config: Optional global config
        progress_callback: Optional callback(current, total, album_name)

    Returns:
        List of detected albums
    """
    # First pass: collect all album directories
    album_dirs = []
    for album_path, audio_files in walk_library(library_root, scan_config.audio_extensions):
        album_dirs.append((album_path, audio_files))

    total = len(album_dirs)
    if progress_callback:
        progress_callback(0, total, "Scanning...")

    albums = []

    # Process albums in parallel
    with ThreadPoolExecutor(max_workers=scan_config.threads) as executor:
        # Submit all analysis jobs
        futures = {
            executor.submit(
                analyze_album,
                library_root,
                album_path,
                audio_files,
                scan_config,
                config,
            ): album_path
            for album_path, audio_files in album_dirs
        }

        # Collect results
        completed = 0
        for future in as_completed(futures):
            album_path = futures[future]
            completed += 1

            try:
                album = future.result()
                if album.tracks:  # Only add albums with valid tracks
                    albums.append(album)
            except Exception:
                # Log error but continue
                pass

            if progress_callback:
                progress_callback(completed, total, album_path.name)

    # Sort by path for consistent ordering
    albums.sort(key=lambda a: str(a.source_path).lower())

    return albums


def scan_library(
    scan_config: ScanConfig,
    config: Config | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Album]:
    """
    High-level scan entry point.

    Args:
        scan_config: Scan configuration
        config: Optional global config
        progress_callback: Optional progress callback

    Returns:
        List of detected albums
    """
    return detect_albums(
        scan_config.library_root,
        scan_config,
        config,
        progress_callback,
    )
