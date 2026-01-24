"""Tests for default action computation and target parameters."""

import pytest
from pathlib import Path

from ipodrb.models.album import Album, AlbumMetadata, AudioFormat, Track
from ipodrb.models.plan import Action
from ipodrb.planner.defaults import compute_default_action, compute_target_parameters


def make_album(
    sample_rate: int = 44100,
    bit_depth: int | None = 16,
    formats: set[AudioFormat] | None = None,
) -> Album:
    """Create a test album with specified audio characteristics."""
    if formats is None:
        formats = {AudioFormat.FLAC}

    track = Track(
        path=Path("/test/track.flac"),
        format=AudioFormat.FLAC,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=2,
        duration_seconds=180.0,
        mtime=1234567890.0,
        size_bytes=50_000_000,
    )

    return Album(
        album_id="test123",
        source_path=Path("/test"),
        tracks=[track],
        metadata=AlbumMetadata(artist="Test Artist", album="Test Album"),
        max_sample_rate=sample_rate,
        max_bit_depth=bit_depth,
        source_formats=formats,
    )


class TestComputeDefaultAction:
    """Tests for compute_default_action function."""

    def test_mp3_only_returns_pass_mp3(self):
        """MP3-only albums should pass through unchanged."""
        album = make_album(formats={AudioFormat.MP3})
        assert compute_default_action(album) == Action.PASS_MP3

    def test_cd_quality_lossless_returns_preserve(self):
        """44.1kHz/16-bit lossless should preserve (already iPod-safe)."""
        album = make_album(sample_rate=44100, bit_depth=16)
        assert compute_default_action(album) == Action.ALAC_PRESERVE

    def test_48khz_16bit_lossless_returns_preserve(self):
        """48kHz/16-bit lossless should preserve (within iPod-safe ceiling)."""
        album = make_album(sample_rate=48000, bit_depth=16)
        assert compute_default_action(album) == Action.ALAC_PRESERVE

    def test_hires_96khz_24bit_returns_downconvert(self):
        """96kHz/24-bit lossless should downconvert (exceeds iPod limits)."""
        album = make_album(sample_rate=96000, bit_depth=24)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_hires_44khz_24bit_returns_downconvert(self):
        """44.1kHz/24-bit lossless should downconvert (bit depth exceeds limit)."""
        album = make_album(sample_rate=44100, bit_depth=24)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_hires_88khz_24bit_returns_downconvert(self):
        """88.2kHz/24-bit lossless should downconvert."""
        album = make_album(sample_rate=88200, bit_depth=24)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_hires_192khz_24bit_returns_downconvert(self):
        """192kHz/24-bit lossless should downconvert."""
        album = make_album(sample_rate=192000, bit_depth=24)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_hires_352khz_24bit_returns_downconvert(self):
        """352.8kHz/24-bit (DSD128 rate) should downconvert."""
        album = make_album(sample_rate=352800, bit_depth=24)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_48khz_24bit_returns_downconvert(self):
        """48kHz/24-bit should downconvert (bit depth exceeds limit)."""
        album = make_album(sample_rate=48000, bit_depth=24)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_96khz_16bit_returns_downconvert(self):
        """96kHz/16-bit should downconvert (sample rate exceeds ceiling)."""
        album = make_album(sample_rate=96000, bit_depth=16)
        assert compute_default_action(album) == Action.ALAC_16_44

    def test_lossy_only_returns_aac(self):
        """Lossy-only albums (non-MP3) should convert to AAC."""
        album = make_album(formats={AudioFormat.OGG})
        assert compute_default_action(album) == Action.AAC

    def test_empty_formats_returns_skip(self):
        """Albums with no source formats should be skipped."""
        album = make_album(formats=set())
        assert compute_default_action(album) == Action.SKIP

    def test_custom_max_sample_rate_44100(self):
        """With 44.1kHz ceiling, 48kHz sources should downconvert."""
        album = make_album(sample_rate=48000, bit_depth=16)
        # Default ceiling is 48kHz
        assert compute_default_action(album) == Action.ALAC_PRESERVE
        # With 44.1kHz ceiling, 48kHz should downconvert
        assert compute_default_action(album, max_sample_rate=44100) == Action.ALAC_16_44


class TestComputeTargetParameters:
    """Tests for compute_target_parameters function."""

    def test_cd_quality_preserve(self):
        """44.1kHz/16-bit with ALAC_PRESERVE should stay unchanged."""
        result = compute_target_parameters(44100, 16, Action.ALAC_PRESERVE)
        assert result["target_sample_rate"] == 44100
        assert result["target_bit_depth"] == 16
        assert result["apply_dither"] is False

    def test_48khz_preserve(self):
        """48kHz/16-bit with ALAC_PRESERVE should stay unchanged."""
        result = compute_target_parameters(48000, 16, Action.ALAC_PRESERVE)
        assert result["target_sample_rate"] == 48000
        assert result["target_bit_depth"] == 16
        assert result["apply_dither"] is False

    def test_hires_downconvert(self):
        """96kHz/24-bit should downconvert to 48kHz/16-bit with dither."""
        result = compute_target_parameters(96000, 24, Action.ALAC_16_44)
        assert result["target_sample_rate"] == 48000
        assert result["target_bit_depth"] == 16
        assert result["apply_dither"] is True

    def test_hires_bit_depth_only_downconvert(self):
        """44.1kHz/24-bit should downconvert to 44.1kHz/16-bit with dither."""
        result = compute_target_parameters(44100, 24, Action.ALAC_16_44)
        assert result["target_sample_rate"] == 44100
        assert result["target_bit_depth"] == 16
        assert result["apply_dither"] is True

    def test_hires_sample_rate_only_downconvert(self):
        """96kHz/16-bit should downconvert to 48kHz/16-bit (no dither needed)."""
        result = compute_target_parameters(96000, 16, Action.ALAC_16_44)
        assert result["target_sample_rate"] == 48000
        assert result["target_bit_depth"] == 16
        # No dither needed when bit depth stays the same
        assert result["apply_dither"] is False

    def test_never_upscale_sample_rate(self):
        """Lower sample rates should never be upscaled."""
        result = compute_target_parameters(22050, 16, Action.ALAC_16_44)
        assert result["target_sample_rate"] == 22050  # Not upscaled to 48000

    def test_never_upscale_bit_depth(self):
        """Lower bit depths should never be upscaled."""
        result = compute_target_parameters(44100, 8, Action.ALAC_16_44)
        assert result["target_bit_depth"] == 8  # Not upscaled to 16

    def test_aac_respects_max_sample_rate(self):
        """AAC should cap sample rate at ceiling."""
        result = compute_target_parameters(96000, 24, Action.AAC)
        assert result["target_sample_rate"] == 48000
        assert result["target_bit_depth"] is None  # Lossy has no bit depth

    def test_mp3_passthrough_preserves_all(self):
        """PASS_MP3 should preserve original parameters."""
        result = compute_target_parameters(44100, None, Action.PASS_MP3)
        assert result["target_sample_rate"] == 44100
        assert result["target_bit_depth"] is None
        assert result["apply_dither"] is False

    def test_custom_44100_ceiling(self):
        """With 44.1kHz ceiling, 48kHz should downconvert."""
        result = compute_target_parameters(
            48000, 16, Action.ALAC_16_44, max_sample_rate=44100
        )
        assert result["target_sample_rate"] == 44100


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_at_ceiling(self):
        """Exactly at 48kHz ceiling should not trigger downconvert."""
        album = make_album(sample_rate=48000, bit_depth=16)
        assert compute_default_action(album) == Action.ALAC_PRESERVE

    def test_exactly_at_bit_depth_limit(self):
        """Exactly at 16-bit limit should not trigger downconvert."""
        album = make_album(sample_rate=44100, bit_depth=16)
        assert compute_default_action(album) == Action.ALAC_PRESERVE

    def test_none_bit_depth_treated_as_lossy(self):
        """None bit depth (lossy source) should be handled gracefully."""
        result = compute_target_parameters(44100, None, Action.ALAC_PRESERVE)
        assert result["target_bit_depth"] == 16
