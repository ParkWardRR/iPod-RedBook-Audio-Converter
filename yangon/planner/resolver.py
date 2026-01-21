"""Build plan resolution from XLSX decisions."""

import hashlib
from pathlib import Path

from yangon.models.album import Album
from yangon.models.config import ApplyConfig
from yangon.models.plan import Action, BuildPlan, ResolvedAction, TrackJob
from yangon.planner.defaults import compute_default_action, compute_target_parameters
from yangon.planner.validator import ValidationError, validate_action, validate_aac_bitrate


def resolve_album_action(
    album: Album,
    decision: dict,
    config: ApplyConfig,
) -> ResolvedAction:
    """
    Resolve the final action for an album.

    Args:
        album: Album to resolve
        decision: Dict from XLSX with user_action, aac_target_kbps, skip
        config: Apply configuration

    Returns:
        ResolvedAction with final decision
    """
    default_action = compute_default_action(album)

    # Check skip flag
    skip = decision.get("skip", False)
    if skip:
        return ResolvedAction(
            album_id=album.album_id,
            action=Action.SKIP,
            skip=True,
            default_action=default_action,
            user_action=Action.SKIP,
            source="user_override",
        )

    # Parse user action
    user_action_str = decision.get("user_action")
    user_action = None

    if user_action_str:
        try:
            user_action = validate_action(user_action_str)
        except ValidationError:
            user_action = None  # Fall back to default

    # Resolve final action
    resolved_action = user_action if user_action else default_action

    # Parse AAC bitrate
    aac_bitrate = None
    if resolved_action == Action.AAC:
        aac_bitrate = validate_aac_bitrate(
            decision.get("aac_target_kbps"),
            config.allowed_aac_bitrates,
        )

    return ResolvedAction(
        album_id=album.album_id,
        action=resolved_action,
        aac_bitrate_kbps=aac_bitrate,
        skip=False,
        default_action=default_action,
        user_action=user_action,
        source="user_override" if user_action else "default",
    )


def generate_conversion_tag(
    action: Action,
    source_sample_rate: int,
    source_bit_depth: int | None,
    target_sample_rate: int,
    target_bit_depth: int | None,
    aac_bitrate: int | None,
) -> str:
    """
    Generate a tag string describing the conversion for the filename.

    Returns tags like:
    - [ALAC] - lossless, no downconversion needed
    - [ALAC-RedBook] - lossless, downconverted to 16-bit/44.1kHz
    - [AAC-256k] - AAC at 256kbps
    - [MP3] - passthrough
    """
    if action == Action.PASS_MP3:
        return "[MP3]"

    if action == Action.AAC:
        bitrate = aac_bitrate or 256
        return f"[AAC-{bitrate}k]"

    # ALAC actions
    if action in (Action.ALAC_PRESERVE, Action.ALAC_16_44):
        # Check if downconversion occurred
        was_downsampled = source_sample_rate > 44100 and target_sample_rate == 44100
        was_bit_reduced = (source_bit_depth or 16) > 16 and target_bit_depth == 16

        if was_downsampled or was_bit_reduced:
            return "[ALAC-RedBook]"
        else:
            return "[ALAC]"

    return ""


def generate_output_path(
    track,
    album: Album,
    config: ApplyConfig,
    action: Action,
    target_sample_rate: int,
    target_bit_depth: int | None,
    aac_bitrate: int | None = None,
) -> Path:
    """
    Generate output path for a track with conversion spec in filename.

    Args:
        track: Track to generate path for
        album: Parent album
        config: Apply configuration
        action: Resolved action
        target_sample_rate: Target sample rate after conversion
        target_bit_depth: Target bit depth after conversion
        aac_bitrate: AAC bitrate if applicable

    Returns:
        Output path with conversion spec tag in filename
    """
    # Determine extension
    if action == Action.PASS_MP3:
        ext = ".mp3"
    else:
        ext = ".m4a"  # ALAC and AAC both use .m4a

    # Build path components
    album_artist = album.metadata.album_artist or album.metadata.artist or "Unknown Artist"
    album_name = album.metadata.album or "Unknown Album"
    year = album.metadata.year or 0
    title = track.title or track.path.stem
    track_num = track.track_number or 0
    disc_num = track.disc_number or 1

    # Sanitize path components
    def sanitize(s: str) -> str:
        """Remove/replace characters invalid in file paths."""
        invalid = '<>:"/\\|?*'
        for char in invalid:
            s = s.replace(char, "_")
        return s.strip().rstrip(".")

    album_artist = sanitize(album_artist)
    album_name = sanitize(album_name)
    title = sanitize(title)

    # Build disc prefix
    disc_prefix = ""
    if album.metadata.is_compilation or (track.disc_total and track.disc_total > 1):
        disc_prefix = f"{disc_num}-"

    # Build path
    if year:
        album_folder = f"{year} - {album_name}"
    else:
        album_folder = album_name

    # Generate conversion tag for filename
    conversion_tag = generate_conversion_tag(
        action=action,
        source_sample_rate=track.sample_rate,
        source_bit_depth=track.bit_depth,
        target_sample_rate=target_sample_rate,
        target_bit_depth=target_bit_depth,
        aac_bitrate=aac_bitrate,
    )

    filename = f"{disc_prefix}{track_num:02d} {title} {conversion_tag}{ext}"

    return config.output_root / album_artist / album_folder / filename


def compute_settings_hash(
    track,
    action: Action,
    aac_bitrate: int | None,
    target_sr: int,
    target_bd: int | None,
    tool_version: str,
) -> str:
    """
    Compute hash of conversion settings for cache keying.
    """
    components = [
        str(track.mtime),
        str(track.size_bytes),
        action.value,
        str(aac_bitrate or 0),
        str(target_sr),
        str(target_bd or 0),
        tool_version,
    ]
    return hashlib.sha256(":".join(components).encode()).hexdigest()[:16]


def resolve_track_jobs(
    album: Album,
    resolved_action: ResolvedAction,
    config: ApplyConfig,
    tool_version: str,
) -> list[TrackJob]:
    """
    Expand album-level decision into per-track jobs.

    Args:
        album: Album to process
        resolved_action: Resolved album action
        config: Apply configuration
        tool_version: Tool version for cache invalidation

    Returns:
        List of TrackJob instances
    """
    if resolved_action.skip or resolved_action.action == Action.SKIP:
        return []

    jobs = []
    action = resolved_action.action

    for track in album.tracks:
        # Compute target parameters
        params = compute_target_parameters(
            track.sample_rate,
            track.bit_depth,
            action,
        )

        # Determine target codec
        if action in (Action.ALAC_PRESERVE, Action.ALAC_16_44):
            target_codec = "alac"
        elif action == Action.AAC:
            target_codec = "aac"
        elif action == Action.PASS_MP3:
            target_codec = "copy"
        else:
            continue

        # Generate output path with conversion specs
        output_path = generate_output_path(
            track=track,
            album=album,
            config=config,
            action=action,
            target_sample_rate=params["target_sample_rate"],
            target_bit_depth=params["target_bit_depth"],
            aac_bitrate=resolved_action.aac_bitrate_kbps,
        )

        # Compute settings hash
        settings_hash = compute_settings_hash(
            track,
            action,
            resolved_action.aac_bitrate_kbps,
            params["target_sample_rate"],
            params["target_bit_depth"],
            tool_version,
        )

        # Build tags dict
        tags = {
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "album_artist": track.album_artist or album.metadata.album_artist,
            "track_number": track.track_number,
            "track_total": track.track_total,
            "disc_number": track.disc_number,
            "disc_total": track.disc_total,
            "year": track.year or album.metadata.year,
            "compilation": track.compilation or album.metadata.is_compilation,
        }

        # Determine artwork source
        artwork_source = None
        if album.metadata.folder_art_candidates:
            artwork_source = album.metadata.folder_art_candidates[0]

        job = TrackJob(
            album_id=album.album_id,
            source_path=track.path,
            output_path=output_path,
            action=action,
            target_codec=target_codec,
            target_sample_rate=params["target_sample_rate"],
            target_bit_depth=params["target_bit_depth"],
            aac_bitrate_kbps=resolved_action.aac_bitrate_kbps,
            apply_dither=params["apply_dither"],
            tags=tags,
            artwork_source=artwork_source,
            source_mtime=track.mtime,
            source_size=track.size_bytes,
            settings_hash=settings_hash,
        )
        jobs.append(job)

    return jobs


def resolve_build_plan(
    albums: list[Album],
    decisions: dict[str, dict],
    config: ApplyConfig,
    tool_version: str = "0.1.0",
) -> BuildPlan:
    """
    Create complete build plan from albums and XLSX decisions.

    Args:
        albums: List of scanned albums
        decisions: Dict mapping album_id to XLSX row data
        config: Apply configuration
        tool_version: Tool version for cache

    Returns:
        BuildPlan with all jobs
    """
    all_jobs = []
    skipped_albums = []
    validation_errors = []

    for album in albums:
        # Get decision for this album
        decision = decisions.get(album.album_id, {})

        try:
            # Resolve album action
            resolved = resolve_album_action(album, decision, config)

            if resolved.skip:
                skipped_albums.append(album.album_id)
                continue

            # Generate track jobs
            jobs = resolve_track_jobs(album, resolved, config, tool_version)
            all_jobs.extend(jobs)

        except ValidationError as e:
            validation_errors.append({
                "album_id": album.album_id,
                "error_code": e.error_code,
                "message": str(e),
            })

    return BuildPlan(
        jobs=all_jobs,
        skipped_albums=skipped_albums,
        validation_errors=validation_errors,
    )
