"""Default action computation for albums."""

from ipodrb.models.album import Album, AudioFormat
from ipodrb.models.plan import Action


def compute_default_action(album: Album) -> Action:
    """
    Compute the default conversion action for an album.

    Rules:
    1. If album is MP3-only: PASS_MP3 (pass through unchanged)
    2. If album contains lossless formats (FLAC/WAV/AIFF/ALAC): ALAC_PRESERVE
    3. Otherwise (lossy-only, mixed): AAC

    Args:
        album: Album to compute default for

    Returns:
        Default Action enum
    """
    if not album.source_formats:
        return Action.SKIP

    # Check if MP3-only
    if album.is_mp3_only:
        return Action.PASS_MP3

    # Check for lossless formats
    lossless_formats = {
        AudioFormat.FLAC,
        AudioFormat.WAV,
        AudioFormat.AIFF,
        AudioFormat.ALAC,
        AudioFormat.APE,
        AudioFormat.WV,
        AudioFormat.SHN,
    }

    has_lossless = bool(album.source_formats & lossless_formats)

    if has_lossless:
        return Action.ALAC_PRESERVE

    # Fallback for lossy-only albums (e.g., AAC, OGG, OPUS)
    return Action.AAC


def compute_target_parameters(
    source_sample_rate: int,
    source_bit_depth: int | None,
    action: Action,
) -> dict:
    """
    Compute target audio parameters based on source and action.

    Never-upconvert rules:
    - Never increase sample rate
    - Never increase bit depth
    - Downconvert to 44.1kHz if source > 44.1kHz
    - Downconvert to 16-bit if source > 16-bit (with dither)

    Args:
        source_sample_rate: Source sample rate in Hz
        source_bit_depth: Source bit depth (None for lossy)
        action: Resolved conversion action

    Returns:
        Dict with target_sample_rate, target_bit_depth, apply_dither
    """
    # Default targets
    target_sr = source_sample_rate
    target_bd = source_bit_depth
    apply_dither = False

    # iPod max: 44.1kHz/16-bit for optimal compatibility
    max_sample_rate = 44100
    max_bit_depth = 16

    # Downconvert sample rate if needed
    if source_sample_rate > max_sample_rate:
        target_sr = max_sample_rate

    # Handle bit depth based on action
    if action in (Action.ALAC_PRESERVE, Action.ALAC_16_44):
        # For ALAC output
        if source_bit_depth and source_bit_depth > max_bit_depth:
            target_bd = max_bit_depth
            apply_dither = True
        elif source_bit_depth is None:
            # Lossy source being converted to ALAC
            target_bd = 16

        # ALAC_16_44 forces 44.1/16 even for lower sources
        # But we never upconvert, so preserve lower values
        if action == Action.ALAC_16_44:
            target_sr = min(source_sample_rate, max_sample_rate)
            if source_bit_depth:
                target_bd = min(source_bit_depth, max_bit_depth)
            else:
                target_bd = 16

    elif action == Action.AAC:
        # AAC always outputs at 44.1kHz (iPod optimal)
        target_sr = min(source_sample_rate, max_sample_rate)
        # Bit depth not applicable for lossy
        target_bd = None

    elif action == Action.PASS_MP3:
        # Passthrough - preserve everything
        target_sr = source_sample_rate
        target_bd = source_bit_depth

    return {
        "target_sample_rate": target_sr,
        "target_bit_depth": target_bd,
        "apply_dither": apply_dither,
    }
