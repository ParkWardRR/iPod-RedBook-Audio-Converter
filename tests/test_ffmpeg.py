"""Tests for FFmpeg command building."""

import pytest
from pathlib import Path

from ipodrb.models.plan import Action, TrackJob
from ipodrb.converter.ffmpeg import (
    build_alac_command,
    build_aac_command,
    build_passthrough_command,
)


def make_job(
    source_sample_rate: int = 44100,
    source_bit_depth: int | None = 16,
    source_channels: int = 2,
    target_sample_rate: int = 44100,
    target_bit_depth: int | None = 16,
    action: Action = Action.ALAC_PRESERVE,
    apply_dither: bool = False,
    aac_bitrate_kbps: int | None = None,
) -> TrackJob:
    """Create a test TrackJob with specified parameters."""
    return TrackJob(
        album_id="test123",
        source_path=Path("/input/track.flac"),
        output_path=Path("/output/track.m4a"),
        source_sample_rate=source_sample_rate,
        source_bit_depth=source_bit_depth,
        source_channels=source_channels,
        action=action,
        target_codec="alac" if action != Action.AAC else "aac",
        target_sample_rate=target_sample_rate,
        target_bit_depth=target_bit_depth,
        aac_bitrate_kbps=aac_bitrate_kbps,
        apply_dither=apply_dither,
        source_mtime=1234567890.0,
        source_size=50_000_000,
    )


class TestBuildAlacCommand:
    """Tests for ALAC command building."""

    def test_no_conversion_needed(self):
        """CD-quality to CD-quality should use minimal processing."""
        job = make_job(
            source_sample_rate=44100,
            source_bit_depth=16,
            target_sample_rate=44100,
            target_bit_depth=16,
            apply_dither=False,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))

        # Should not have aresample filter (no conversion needed)
        cmd_str = " ".join(cmd)
        assert "aresample" not in cmd_str
        assert "-c:a alac" in cmd_str
        assert "-ar 44100" in cmd_str
        assert "-sample_fmt s16p" in cmd_str

    def test_resampling_applies_soxr(self):
        """Sample rate conversion should use soxr resampler."""
        job = make_job(
            source_sample_rate=96000,
            source_bit_depth=16,
            target_sample_rate=48000,
            target_bit_depth=16,
            apply_dither=False,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "aresample=48000" in cmd_str
        assert "resampler=soxr" in cmd_str
        assert "precision=28" in cmd_str

    def test_bit_depth_reduction_applies_dither(self):
        """Bit depth reduction should apply triangular HP dither."""
        job = make_job(
            source_sample_rate=44100,
            source_bit_depth=24,
            target_sample_rate=44100,
            target_bit_depth=16,
            apply_dither=True,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "dither_method=triangular_hp" in cmd_str
        assert "-sample_fmt s16p" in cmd_str

    def test_hires_full_downconvert(self):
        """Full hi-res downconvert should resample AND dither."""
        job = make_job(
            source_sample_rate=96000,
            source_bit_depth=24,
            target_sample_rate=48000,
            target_bit_depth=16,
            apply_dither=True,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "aresample=48000" in cmd_str
        assert "resampler=soxr" in cmd_str
        assert "dither_method=triangular_hp" in cmd_str
        assert "-sample_fmt s16p" in cmd_str

    def test_multichannel_applies_headroom(self):
        """Multichannel sources should apply -3dB headroom for downmix."""
        job = make_job(
            source_channels=6,  # 5.1 surround
            target_sample_rate=48000,
            target_bit_depth=16,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "volume=-3dB" in cmd_str
        assert "-ac 2" in cmd_str

    def test_stereo_no_headroom(self):
        """Stereo sources should not apply headroom reduction."""
        job = make_job(
            source_channels=2,
            target_sample_rate=48000,
            target_bit_depth=16,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "volume=-3dB" not in cmd_str

    def test_24bit_output_uses_s32p(self):
        """24-bit ALAC should use s32p sample format."""
        job = make_job(
            source_bit_depth=24,
            target_bit_depth=24,
            apply_dither=False,
        )
        cmd = build_alac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "-sample_fmt s32p" in cmd_str


class TestBuildAacCommand:
    """Tests for AAC command building."""

    def test_basic_aac_encoding(self):
        """Basic AAC encoding should use AAC-LC profile."""
        job = make_job(
            action=Action.AAC,
            target_sample_rate=48000,
            aac_bitrate_kbps=256,
        )
        cmd = build_aac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "-c:a aac" in cmd_str
        assert "-profile:a aac_low" in cmd_str
        assert "-b:a 256k" in cmd_str

    def test_aac_resampling(self):
        """AAC should resample hi-res sources."""
        job = make_job(
            source_sample_rate=96000,
            action=Action.AAC,
            target_sample_rate=48000,
            aac_bitrate_kbps=256,
        )
        cmd = build_aac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "aresample=48000" in cmd_str
        assert "resampler=soxr" in cmd_str

    def test_aac_multichannel_headroom(self):
        """AAC should apply headroom for multichannel downmix."""
        job = make_job(
            source_channels=6,
            action=Action.AAC,
            target_sample_rate=48000,
            aac_bitrate_kbps=256,
        )
        cmd = build_aac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "volume=-3dB" in cmd_str
        assert "-ac 2" in cmd_str

    def test_aac_default_bitrate(self):
        """AAC should default to 256kbps if not specified."""
        job = make_job(
            action=Action.AAC,
            aac_bitrate_kbps=None,
        )
        cmd = build_aac_command(job, Path("/tmp/out.m4a"))
        cmd_str = " ".join(cmd)

        assert "-b:a 256k" in cmd_str


class TestBuildPassthroughCommand:
    """Tests for MP3 passthrough command building."""

    def test_passthrough_copies_audio(self):
        """MP3 passthrough should copy audio stream without re-encoding."""
        job = make_job(action=Action.PASS_MP3)
        cmd = build_passthrough_command(job, Path("/tmp/out.mp3"))
        cmd_str = " ".join(cmd)

        assert "-c:a copy" in cmd_str
        assert "-vn" in cmd_str
