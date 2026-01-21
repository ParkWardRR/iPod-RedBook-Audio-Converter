"""Audio conversion module."""

from ipodrb.converter.ffmpeg import build_ffmpeg_command
from ipodrb.converter.pipeline import ConversionPipeline
from ipodrb.converter.transcoder import convert_track
from ipodrb.converter.verifier import verify_output

__all__ = [
    "build_ffmpeg_command",
    "convert_track",
    "verify_output",
    "ConversionPipeline",
]
