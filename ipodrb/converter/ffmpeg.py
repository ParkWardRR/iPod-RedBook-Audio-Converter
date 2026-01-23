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

    Audiophile-quality conversion:
    - Uses soxr resampler (high precision) for sample rate conversion
    - Applies triangular high-pass dither when reducing bit depth
    - Applies headroom reduction for multichannel->stereo downmix to prevent clipping
    - Never upscales (sample rate or bit depth)
    """
    cmd = [
        ffmpeg_path,
        "-y",  # Overwrite output
        "-i", str(job.source_path),
        "-vn",  # No video
    ]

    # Build audio filter chain
    filters = []

    # 1. Multichannel to stereo downmix with headroom protection
    # Apply -3dB headroom to prevent clipping when downmixing surround to stereo
    if job.source_channels > 2:
        filters.append("volume=-3dB")

    # 2. Check if we need to resample (source != target sample rate)
    needs_resample = job.source_sample_rate != job.target_sample_rate

    # 3. Check if we need dithering (reducing bit depth)
    source_bd = job.source_bit_depth or 16
    target_bd = job.target_bit_depth or 16
    needs_dither = source_bd > target_bd

    # Build aresample filter for high-quality conversion
    # Use soxr even for same-rate conversion if we need dithering
    if needs_resample or needs_dither:
        # Use soxr resampler with high precision
        # dither_method=triangular_hp provides high-pass triangular dither
        # which is preferred for audio to shape noise away from sensitive frequencies
        filter_parts = [
            f"aresample={job.target_sample_rate}",
            "resampler=soxr",
            "precision=28",  # Maximum precision
        ]
        if needs_dither:
            filter_parts.append("dither_method=triangular_hp")
        filters.append(":".join(filter_parts))

    if filters:
        cmd.extend(["-af", ",".join(filters)])

    # Stereo output for iPod compatibility
    cmd.extend(["-ac", "2"])

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

    Uses AAC-LC profile for maximum iPod compatibility.
    Applies proper resampling and multichannel downmix with headroom.
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(job.source_path),
        "-vn",
    ]

    # Build filter chain
    filters = []

    # 1. Multichannel to stereo downmix with headroom protection
    if job.source_channels > 2:
        filters.append("volume=-3dB")

    # 2. Resample if needed (use soxr for high quality)
    needs_resample = job.source_sample_rate != job.target_sample_rate
    if needs_resample:
        filters.append(
            f"aresample={job.target_sample_rate}:resampler=soxr:precision=28"
        )

    if filters:
        cmd.extend(["-af", ",".join(filters)])

    # Stereo output
    cmd.extend(["-ac", "2"])

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
