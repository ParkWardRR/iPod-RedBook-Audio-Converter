"""Track and album analysis using FFprobe."""

import hashlib
import json
import subprocess
from pathlib import Path

from ipodrb.models.album import Album, AlbumMetadata, AudioFormat, Track
from ipodrb.models.config import Config, ScanConfig
from ipodrb.models.status import ArtStatus, TagStatus
from ipodrb.scanner.metadata import extract_metadata, get_image_dimensions
from ipodrb.scanner.walker import find_artwork_candidates


class ProbeError(Exception):
    """Error during FFprobe analysis."""

    pass


def probe_track(path: Path, config: Config | None = None) -> dict:
    """
    Run FFprobe to extract technical audio data.

    Args:
        path: Path to audio file
        config: Optional config for FFprobe path

    Returns:
        Dict with codec, sample_rate, bit_depth, channels, duration

    Raises:
        ProbeError: If FFprobe fails
    """
    ffprobe_path = config.ffprobe_path if config else "ffprobe"

    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as e:
        raise ProbeError(f"FFprobe timed out for {path}") from e
    except FileNotFoundError as e:
        raise ProbeError(f"FFprobe not found at {ffprobe_path}") from e

    if result.returncode != 0:
        raise ProbeError(f"FFprobe failed for {path}: {result.stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ProbeError(f"Invalid FFprobe output for {path}") from e

    # Find audio stream
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    if not audio_stream:
        raise ProbeError(f"No audio stream found in {path}")

    # Extract bit depth - try multiple fields
    bit_depth = None
    if "bits_per_sample" in audio_stream and audio_stream["bits_per_sample"] > 0:
        bit_depth = audio_stream["bits_per_sample"]
    elif "bits_per_raw_sample" in audio_stream:
        try:
            bit_depth = int(audio_stream["bits_per_raw_sample"])
        except (ValueError, TypeError):
            pass

    # Get duration from format or stream
    duration = 0.0
    if "duration" in data.get("format", {}):
        duration = float(data["format"]["duration"])
    elif "duration" in audio_stream:
        duration = float(audio_stream["duration"])

    return {
        "codec": audio_stream.get("codec_name", "unknown"),
        "sample_rate": int(audio_stream.get("sample_rate", 44100)),
        "bit_depth": bit_depth,
        "channels": int(audio_stream.get("channels", 2)),
        "duration": duration,
    }


def analyze_track(
    path: Path,
    config: Config | None = None,
) -> Track:
    """
    Fully analyze a single track: probe + metadata extraction.

    Args:
        path: Path to audio file
        config: Optional config

    Returns:
        Track model with all data populated
    """
    # Get file stats for caching
    stat = path.stat()

    # Probe technical data
    probe_data = probe_track(path, config)

    # Determine format from codec
    audio_format = AudioFormat.from_codec(probe_data["codec"])
    if audio_format == AudioFormat.UNKNOWN:
        audio_format = AudioFormat.from_extension(path.suffix)

    # Extract metadata with mutagen
    metadata = extract_metadata(path)

    return Track(
        path=path,
        format=audio_format,
        sample_rate=probe_data["sample_rate"],
        bit_depth=probe_data["bit_depth"],
        channels=probe_data["channels"],
        duration_seconds=probe_data["duration"],
        title=metadata.get("title"),
        artist=metadata.get("artist"),
        album=metadata.get("album"),
        album_artist=metadata.get("album_artist"),
        track_number=metadata.get("track_number"),
        track_total=metadata.get("track_total"),
        disc_number=metadata.get("disc_number"),
        disc_total=metadata.get("disc_total"),
        year=metadata.get("year"),
        compilation=metadata.get("compilation", False),
        has_embedded_art=metadata.get("has_embedded_art", False),
        embedded_art_width=metadata.get("art_width"),
        embedded_art_height=metadata.get("art_height"),
        mtime=stat.st_mtime,
        size_bytes=stat.st_size,
    )


def generate_album_id(library_root: Path, album_path: Path) -> str:
    """
    Generate stable album ID from relative path.

    Uses SHA256 hash truncated to 16 chars for readability.
    """
    try:
        rel_path = album_path.relative_to(library_root)
    except ValueError:
        rel_path = album_path

    hash_input = str(rel_path).encode("utf-8")
    return hashlib.sha256(hash_input).hexdigest()[:16]


def compute_tag_status(tracks: list[Track]) -> tuple[TagStatus, list[str]]:
    """
    Compute tag quality status for an album.

    Returns:
        Tuple of (status, notes)
    """
    notes = []

    if not tracks:
        return TagStatus.RED, ["No tracks found"]

    # Check for required tags
    missing_title = [t for t in tracks if not t.title]
    missing_album = [t for t in tracks if not t.album]
    missing_artist = [t for t in tracks if not t.artist]

    if missing_title:
        notes.append(f"{len(missing_title)} tracks missing title")
    if missing_album:
        notes.append(f"{len(missing_album)} tracks missing album")
    if missing_artist:
        notes.append(f"{len(missing_artist)} tracks missing artist")

    # Critical missing = RED
    if missing_title or missing_album:
        return TagStatus.RED, notes

    # Check consistency
    albums = {t.album for t in tracks if t.album}
    if len(albums) > 1:
        notes.append(f"Inconsistent album names: {albums}")
        return TagStatus.RED, notes

    # Check track numbering
    track_nums = [t.track_number for t in tracks if t.track_number]
    if track_nums:
        if len(track_nums) != len(set(track_nums)):
            notes.append("Duplicate track numbers")
            return TagStatus.RED, notes

    # Check for year
    years = {t.year for t in tracks if t.year}
    if not years:
        notes.append("Missing year")
        return TagStatus.YELLOW, notes

    if len(years) > 1:
        notes.append(f"Inconsistent years: {years}")
        return TagStatus.YELLOW, notes

    # All good
    return TagStatus.GREEN, notes


def compute_art_status(
    tracks: list[Track],
    folder_art: list[Path],
    folder_art_sizes: list[tuple[int, int]],
    min_size: int = 300,
) -> tuple[ArtStatus, list[str]]:
    """
    Compute artwork quality status for an album.

    Args:
        tracks: List of tracks in album
        folder_art: List of folder artwork candidates
        folder_art_sizes: Sizes of folder art (width, height)
        min_size: Minimum pixel size for GREEN status

    Returns:
        Tuple of (status, notes)
    """
    notes = []

    # Check embedded art
    tracks_with_art = [t for t in tracks if t.has_embedded_art]
    has_embedded = len(tracks_with_art) > 0

    # Check embedded art size
    embedded_meets_threshold = False
    if tracks_with_art:
        for track in tracks_with_art:
            if track.embedded_art_width and track.embedded_art_height:
                if (
                    track.embedded_art_width >= min_size
                    and track.embedded_art_height >= min_size
                ):
                    embedded_meets_threshold = True
                    break

    # Check folder art
    folder_meets_threshold = False
    for w, h in folder_art_sizes:
        if w >= min_size and h >= min_size:
            folder_meets_threshold = True
            break

    # No art at all
    if not has_embedded and not folder_art:
        return ArtStatus.RED, ["No artwork found"]

    # Multiple folder art = ambiguous
    if len(folder_art) > 1:
        notes.append(f"Multiple folder images: {[p.name for p in folder_art]}")
        return ArtStatus.YELLOW, notes

    # Check threshold
    if embedded_meets_threshold or folder_meets_threshold:
        return ArtStatus.GREEN, notes

    # Has art but below threshold
    if has_embedded:
        notes.append(f"Embedded art below {min_size}x{min_size}")
    if folder_art:
        notes.append(f"Folder art below {min_size}x{min_size}")

    return ArtStatus.YELLOW, notes


def analyze_album(
    library_root: Path,
    album_path: Path,
    audio_files: list[Path],
    scan_config: ScanConfig,
    config: Config | None = None,
) -> Album:
    """
    Fully analyze an album directory.

    Args:
        library_root: Root of music library
        album_path: Path to album directory
        audio_files: List of audio files in directory
        scan_config: Scan configuration
        config: Optional global config

    Returns:
        Album model with all data populated
    """
    # Analyze all tracks
    tracks = []
    for audio_file in audio_files:
        try:
            track = analyze_track(audio_file, config)
            tracks.append(track)
        except ProbeError:
            # Skip files that can't be probed
            continue

    if not tracks:
        # Return empty album if no valid tracks
        return Album(
            album_id=generate_album_id(library_root, album_path),
            source_path=album_path,
            tracks=[],
            metadata=AlbumMetadata(),
            tag_status=TagStatus.RED,
            art_status=ArtStatus.RED,
            status_notes=["No valid audio files found"],
        )

    # Aggregate metadata
    # Pick most common values for artist/album
    artists = [t.artist for t in tracks if t.artist]
    albums = [t.album for t in tracks if t.album]
    album_artists = [t.album_artist for t in tracks if t.album_artist]
    years = [t.year for t in tracks if t.year]
    compilations = [t.compilation for t in tracks]

    def most_common(items: list) -> str | int | None:
        if not items:
            return None
        from collections import Counter

        counter = Counter(items)
        return counter.most_common(1)[0][0]

    # Find folder artwork
    folder_art = find_artwork_candidates(album_path, scan_config.art_patterns)
    folder_art_sizes = []
    for art_path in folder_art:
        try:
            size = get_image_dimensions(art_path)
            if size:
                folder_art_sizes.append(size)
        except Exception:
            pass

    metadata = AlbumMetadata(
        artist=most_common(artists) or "",
        album=most_common(albums) or "",
        album_artist=most_common(album_artists),
        year=most_common(years),
        is_compilation=any(compilations),
        folder_art_candidates=folder_art,
        folder_art_sizes=folder_art_sizes,
    )

    # Compute technical rollup
    max_sr = max(t.sample_rate for t in tracks)
    bit_depths = [t.bit_depth for t in tracks if t.bit_depth]
    max_bd = max(bit_depths) if bit_depths else None
    formats = {t.format for t in tracks}

    # Compute status
    tag_status, tag_notes = compute_tag_status(tracks)
    art_status, art_notes = compute_art_status(
        tracks, folder_art, folder_art_sizes, scan_config.art_min_size
    )

    return Album(
        album_id=generate_album_id(library_root, album_path),
        source_path=album_path,
        tracks=tracks,
        metadata=metadata,
        max_sample_rate=max_sr,
        max_bit_depth=max_bd,
        source_formats=formats,
        tag_status=tag_status,
        art_status=art_status,
        status_notes=tag_notes + art_notes,
    )
