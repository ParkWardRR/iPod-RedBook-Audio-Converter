"""Single track transcoding."""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from ipodrb.converter.ffmpeg import build_ffmpeg_command
from ipodrb.converter.tagger import write_tags_and_artwork
from ipodrb.converter.verifier import verify_output
from ipodrb.models.config import Config
from ipodrb.models.plan import Action, TrackJob, TrackResult
from ipodrb.models.status import ErrorCode


def convert_track(
    job: TrackJob,
    config: Config | None = None,
) -> TrackResult:
    """
    Convert a single track according to job specification.

    Steps:
    1. Build FFmpeg command
    2. Execute transcoding to temp file
    3. Verify output
    4. Write tags and artwork
    5. Atomic rename to final path
    6. Return result

    Args:
        job: Track job with all conversion parameters
        config: Optional global config

    Returns:
        TrackResult with success/failure and details
    """
    started_at = datetime.now()
    ffmpeg_path = config.ffmpeg_path if config else "ffmpeg"
    ffprobe_path = config.ffprobe_path if config else "ffprobe"
    timeout = config.ffmpeg_timeout if config else 300

    # Ensure output directory exists
    job.output_path.parent.mkdir(parents=True, exist_ok=True)

    # Temp output path
    temp_path = job.output_path.with_suffix(f".tmp{job.output_path.suffix}")

    try:
        # Handle passthrough differently - just copy the file
        if job.action == Action.PASS_MP3:
            return _handle_passthrough(job, temp_path, ffprobe_path, started_at)

        # Build FFmpeg command
        cmd = build_ffmpeg_command(job, temp_path, ffmpeg_path)

        # Execute transcoding
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            return TrackResult(
                source_path=job.source_path,
                output_path=None,
                success=False,
                error_code=ErrorCode.ENCODE_FAIL.value,
                error_message=f"FFmpeg failed: {result.stderr[:500]}",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Verify output
        verify_result = verify_output(temp_path, job, ffprobe_path)
        if not verify_result.success:
            _cleanup(temp_path)
            return TrackResult(
                source_path=job.source_path,
                output_path=None,
                success=False,
                error_code=ErrorCode.VERIFICATION_FAIL.value,
                error_message=verify_result.error_message,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Write tags and artwork
        try:
            write_tags_and_artwork(temp_path, job)
        except Exception as e:
            _cleanup(temp_path)
            return TrackResult(
                source_path=job.source_path,
                output_path=None,
                success=False,
                error_code=ErrorCode.TAG_WRITE_FAIL.value,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Atomic rename
        os.replace(temp_path, job.output_path)

        return TrackResult(
            source_path=job.source_path,
            output_path=job.output_path,
            success=True,
            output_codec=verify_result.codec,
            output_sample_rate=verify_result.sample_rate,
            output_bit_depth=verify_result.bit_depth,
            output_size_bytes=verify_result.size_bytes,
            duration_seconds=verify_result.duration,
            started_at=started_at,
            completed_at=datetime.now(),
        )

    except subprocess.TimeoutExpired:
        _cleanup(temp_path)
        return TrackResult(
            source_path=job.source_path,
            output_path=None,
            success=False,
            error_code=ErrorCode.ENCODE_FAIL.value,
            error_message=f"FFmpeg timed out after {timeout} seconds",
            started_at=started_at,
            completed_at=datetime.now(),
        )
    except Exception as e:
        _cleanup(temp_path)
        return TrackResult(
            source_path=job.source_path,
            output_path=None,
            success=False,
            error_code=ErrorCode.ENCODE_FAIL.value,
            error_message=str(e),
            started_at=started_at,
            completed_at=datetime.now(),
        )


def _handle_passthrough(
    job: TrackJob,
    temp_path: Path,
    ffprobe_path: str,
    started_at: datetime,
) -> TrackResult:
    """
    Handle MP3 passthrough by copying the file.
    """
    try:
        # Copy file
        shutil.copy2(job.source_path, temp_path)

        # Verify
        verify_result = verify_output(temp_path, job, ffprobe_path)
        if not verify_result.success:
            _cleanup(temp_path)
            return TrackResult(
                source_path=job.source_path,
                output_path=None,
                success=False,
                error_code=ErrorCode.VERIFICATION_FAIL.value,
                error_message=verify_result.error_message,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Write tags if needed
        try:
            write_tags_and_artwork(temp_path, job)
        except Exception as e:
            _cleanup(temp_path)
            return TrackResult(
                source_path=job.source_path,
                output_path=None,
                success=False,
                error_code=ErrorCode.TAG_WRITE_FAIL.value,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Atomic rename
        os.replace(temp_path, job.output_path)

        return TrackResult(
            source_path=job.source_path,
            output_path=job.output_path,
            success=True,
            output_codec=verify_result.codec,
            output_sample_rate=verify_result.sample_rate,
            output_bit_depth=verify_result.bit_depth,
            output_size_bytes=verify_result.size_bytes,
            duration_seconds=verify_result.duration,
            started_at=started_at,
            completed_at=datetime.now(),
        )

    except Exception as e:
        _cleanup(temp_path)
        return TrackResult(
            source_path=job.source_path,
            output_path=None,
            success=False,
            error_code=ErrorCode.IO_ERROR.value,
            error_message=str(e),
            started_at=started_at,
            completed_at=datetime.now(),
        )


def _cleanup(path: Path) -> None:
    """Remove file if it exists."""
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
