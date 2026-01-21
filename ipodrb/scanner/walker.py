"""Directory traversal for music library scanning."""

import os
from collections.abc import Iterator
from pathlib import Path


def walk_library(
    library_root: Path,
    audio_extensions: set[str],
) -> Iterator[tuple[Path, list[Path]]]:
    """
    Walk directory tree and yield album directories with their audio files.

    Yields tuples of (directory_path, list_of_audio_files).
    Only yields directories that contain at least one audio file.

    Args:
        library_root: Root directory of the music library
        audio_extensions: Set of audio file extensions (e.g., {".flac", ".mp3"})

    Yields:
        Tuple of (album_dir, audio_files)
    """
    library_root = library_root.resolve()

    for root, _dirs, files in os.walk(library_root, followlinks=True):
        root_path = Path(root)

        # Find audio files in this directory
        audio_files = []
        for filename in files:
            if filename.startswith("."):
                continue  # Skip hidden files
            ext = Path(filename).suffix.lower()
            if ext in audio_extensions:
                audio_files.append(root_path / filename)

        # Only yield if there are audio files
        if audio_files:
            # Sort by filename for consistent ordering
            audio_files.sort(key=lambda p: p.name.lower())
            yield root_path, audio_files


def find_artwork_candidates(
    directory: Path,
    patterns: list[str],
) -> list[Path]:
    """
    Find artwork files in a directory matching common patterns.

    Args:
        directory: Directory to search
        patterns: List of glob patterns (e.g., ["cover.*", "folder.*"])

    Returns:
        List of paths to potential artwork files
    """
    candidates = []
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    for pattern in patterns:
        for match in directory.glob(pattern):
            if match.is_file() and match.suffix.lower() in image_extensions:
                candidates.append(match)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)

    return unique
