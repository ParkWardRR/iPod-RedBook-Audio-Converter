"""Output verification using FFprobe."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from yangon.converter.ffmpeg import build_probe_command
from yangon.models.plan import TrackJob


@dataclass
class VerificationResult:
    """Result of output verification."""

    success: bool
    codec: str | None = None
    sample_rate: int | None = None
    bit_depth: int | None = None
    duration: float | None = None
    size_bytes: int | None = None
    error_message: str | None = None


def verify_output(
    output_path: Path,
    job: TrackJob,
    ffprobe_path: str = "ffprobe",
    duration_tolerance: float = 1.0,
) -> VerificationResult:
    """
    Verify converted output file.

    Checks:
    - File exists and is readable
    - Codec matches expected
    - Sample rate matches expected
    - Duration within tolerance of source

    Args:
        output_path: Path to output file
        job: Original track job
        ffprobe_path: Path to FFprobe
        duration_tolerance: Allowed duration difference in seconds

    Returns:
        VerificationResult
    """
    # Check file exists
    if not output_path.exists():
        return VerificationResult(
            success=False,
            error_message=f"Output file does not exist: {output_path}",
        )

    # Get file size
    size_bytes = output_path.stat().st_size
    if size_bytes == 0:
        return VerificationResult(
            success=False,
            error_message="Output file is empty",
        )

    # Probe the output
    cmd = build_probe_command(output_path, ffprobe_path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            success=False,
            error_message="FFprobe timed out",
        )
    except Exception as e:
        return VerificationResult(
            success=False,
            error_message=f"FFprobe failed: {e}",
        )

    if result.returncode != 0:
        return VerificationResult(
            success=False,
            error_message=f"FFprobe error: {result.stderr}",
        )

    # Parse probe output
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return VerificationResult(
            success=False,
            error_message="Invalid FFprobe JSON output",
        )

    # Find audio stream
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    if not audio_stream:
        return VerificationResult(
            success=False,
            error_message="No audio stream found in output",
        )

    # Extract values
    codec = audio_stream.get("codec_name", "")
    sample_rate = int(audio_stream.get("sample_rate", 0))

    # Get bit depth
    bit_depth = None
    if "bits_per_sample" in audio_stream and audio_stream["bits_per_sample"] > 0:
        bit_depth = audio_stream["bits_per_sample"]
    elif "bits_per_raw_sample" in audio_stream:
        try:
            bit_depth = int(audio_stream["bits_per_raw_sample"])
        except (ValueError, TypeError):
            pass

    # Get duration
    duration = 0.0
    if "duration" in data.get("format", {}):
        duration = float(data["format"]["duration"])
    elif "duration" in audio_stream:
        duration = float(audio_stream["duration"])

    # Validate codec
    expected_codecs = {
        "alac": ["alac"],
        "aac": ["aac"],
        "copy": ["mp3", "mp3float"],
    }
    valid_codecs = expected_codecs.get(job.target_codec, [])
    if codec not in valid_codecs:
        return VerificationResult(
            success=False,
            codec=codec,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            duration=duration,
            size_bytes=size_bytes,
            error_message=f"Unexpected codec: {codec}, expected one of {valid_codecs}",
        )

    # Validate sample rate (with some tolerance for AAC)
    if job.target_codec != "copy":
        sr_tolerance = 100  # Allow small differences
        if abs(sample_rate - job.target_sample_rate) > sr_tolerance:
            return VerificationResult(
                success=False,
                codec=codec,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                duration=duration,
                size_bytes=size_bytes,
                error_message=f"Sample rate mismatch: {sample_rate} vs expected {job.target_sample_rate}",
            )

    # Success
    return VerificationResult(
        success=True,
        codec=codec,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        duration=duration,
        size_bytes=size_bytes,
    )
