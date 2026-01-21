"""FFmpeg command builders for audio conversion."""

from pathlib import Path

from ipodrb.models.plan import Action, TrackJob


def build_ffmpeg_command(
    job: TrackJob,
    temp_output: Path,
    ffmpeg_path: str = "ffmpeg",
) -> list[str]:
    """
    Build FFmpeg command for track conversion.

    Args:
        job: Track job with conversion parameters
        temp_output: Temporary output path
        ffmpeg_path: Path to FFmpeg executable

    Returns:
        Command as list of strings
    """
    if job.action == Action.PASS_MP3:
        return build_passthrough_command(job, temp_output, ffmpeg_path)
    elif job.action in (Action.ALAC_PRESERVE, Action.ALAC_16_44):
        return build_alac_command(job, temp_output, ffmpeg_path)
    elif job.action == Action.AAC:
        return build_aac_command(job, temp_output, ffmpeg_path)
    else:
        raise ValueError(f"Unsupported action: {job.action}")


def build_alac_command(
    job: TrackJob,
    temp_output: Path,
    ffmpeg_path: str = "ffmpeg",
) -> list[str]:
    """
    Build FFmpeg command for ALAC encoding.

    Uses soxr resampler for high-quality sample rate conversion.
    Applies triangular dither when reducing bit depth.
    """
    cmd = [
        ffmpeg_path,
        "-y",  # Overwrite output
        "-i", str(job.source_path),
        "-vn",  # No video
    ]

    # Build audio filter chain
    filters = []

    # Check if we need to resample
    needs_resample = job.target_sample_rate != 48000  # Assume we might need it
    needs_dither = job.apply_dither

    if needs_resample or needs_dither:
        # Use soxr for high-quality resampling with optional dither
        filter_parts = [
            f"aresample={job.target_sample_rate}",
            "resampler=soxr",
            "precision=28",
        ]
        if needs_dither:
            filter_parts.append("dither_method=triangular")
        filters.append(":".join(filter_parts))

    if filters:
        cmd.extend(["-af", ",".join(filters)])

    # Output settings
    cmd.extend([
        "-c:a", "alac",
        "-ar", str(job.target_sample_rate),
    ])

    # Set bit depth via sample format
    if job.target_bit_depth:
        if job.target_bit_depth <= 16:
            cmd.extend(["-sample_fmt", "s16p"])
        elif job.target_bit_depth <= 24:
            cmd.extend(["-sample_fmt", "s32p"])  # ALAC uses s32p for 24-bit

    cmd.append(str(temp_output))

    return cmd


def build_aac_command(
    job: TrackJob,
    temp_output: Path,
    ffmpeg_path: str = "ffmpeg",
) -> list[str]:
    """
    Build FFmpeg command for AAC encoding.

    Uses AAC-LC profile for maximum compatibility.
    Always outputs 44.1kHz for iPod optimization.
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(job.source_path),
        "-vn",
    ]

    # AAC always gets resampled to target (usually 44.1kHz)
    filters = [
        f"aresample={job.target_sample_rate}:resampler=soxr:precision=28"
    ]
    cmd.extend(["-af", ",".join(filters)])

    # Get bitrate
    bitrate = job.aac_bitrate_kbps or 256

    # Output settings
    cmd.extend([
        "-c:a", "aac",
        "-profile:a", "aac_low",  # AAC-LC for compatibility
        "-b:a", f"{bitrate}k",
        "-ar", str(job.target_sample_rate),
    ])

    cmd.append(str(temp_output))

    return cmd


def build_passthrough_command(
    job: TrackJob,
    temp_output: Path,
    ffmpeg_path: str = "ffmpeg",
) -> list[str]:
    """
    Build command for MP3 passthrough.

    Just copies the audio stream without re-encoding.
    """
    return [
        ffmpeg_path,
        "-y",
        "-i", str(job.source_path),
        "-vn",
        "-c:a", "copy",
        str(temp_output),
    ]


def build_probe_command(
    path: Path,
    ffprobe_path: str = "ffprobe",
) -> list[str]:
    """
    Build FFprobe command to verify output.
    """
    return [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
