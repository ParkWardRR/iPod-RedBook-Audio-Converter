"""Library scanner module."""

from ipodrb.scanner.analyzer import analyze_album, analyze_track
from ipodrb.scanner.detector import detect_albums
from ipodrb.scanner.metadata import extract_metadata
from ipodrb.scanner.walker import walk_library

__all__ = [
    "walk_library",
    "detect_albums",
    "analyze_track",
    "analyze_album",
    "extract_metadata",
]
