"""Status enums and error codes."""

from enum import Enum


class TagStatus(str, Enum):
    """Tag quality status for an album."""

    GREEN = "GREEN"  # All required tags present, Year exists, consistent
    YELLOW = "YELLOW"  # Missing Year OR minor inconsistencies
    RED = "RED"  # Missing critical tags or inconsistent numbering


class ArtStatus(str, Enum):
    """Artwork quality status for an album."""

    GREEN = "GREEN"  # One unambiguous cover >= threshold
    YELLOW = "YELLOW"  # Art exists but ambiguous or below threshold
    RED = "RED"  # No art found


class ErrorCode(str, Enum):
    """Machine-readable error codes."""

    DECODE_FAIL = "DECODE_FAIL"
    ENCODE_FAIL = "ENCODE_FAIL"
    PROBE_FAIL = "PROBE_FAIL"
    TAG_READ_FAIL = "TAG_READ_FAIL"
    TAG_WRITE_FAIL = "TAG_WRITE_FAIL"
    ART_NOT_FOUND = "ART_NOT_FOUND"
    ART_AMBIGUOUS = "ART_AMBIGUOUS"
    INVALID_ENUM = "INVALID_ENUM"
    LOCKED_XLSX = "LOCKED_XLSX"
    OUTPUT_COLLISION = "OUTPUT_COLLISION"
    IO_ERROR = "IO_ERROR"
    VERIFICATION_FAIL = "VERIFICATION_FAIL"
