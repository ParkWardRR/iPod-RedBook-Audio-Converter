"""Action and parameter validation."""

from yangon.models.plan import Action


class ValidationError(Exception):
    """Validation error with details."""

    def __init__(self, message: str, error_code: str = "INVALID_ENUM"):
        super().__init__(message)
        self.error_code = error_code


def validate_action(action_str: str) -> Action:
    """
    Validate and parse action string.

    Args:
        action_str: Action string from XLSX

    Returns:
        Validated Action enum

    Raises:
        ValidationError: If action is invalid
    """
    if not action_str:
        raise ValidationError("Action cannot be empty", "INVALID_ENUM")

    action_str = action_str.strip().upper()

    # Handle common variations
    action_map = {
        "ALAC": Action.ALAC_PRESERVE,
        "ALAC_PRESERVE": Action.ALAC_PRESERVE,
        "ALAC-PRESERVE": Action.ALAC_PRESERVE,
        "ALAC_16_44": Action.ALAC_16_44,
        "ALAC_16/44": Action.ALAC_16_44,
        "ALAC-16-44": Action.ALAC_16_44,
        "AAC": Action.AAC,
        "PASS_MP3": Action.PASS_MP3,
        "PASS-MP3": Action.PASS_MP3,
        "MP3": Action.PASS_MP3,
        "PASSTHROUGH": Action.PASS_MP3,
        "SKIP": Action.SKIP,
        "NONE": Action.SKIP,
    }

    if action_str in action_map:
        return action_map[action_str]

    # Try direct enum parse
    try:
        return Action(action_str)
    except ValueError:
        valid_actions = ", ".join(a.value for a in Action)
        raise ValidationError(
            f"Invalid action '{action_str}'. Valid actions: {valid_actions}",
            "INVALID_ENUM",
        )


def validate_aac_bitrate(bitrate: int | None, allowed: set[int] | None = None) -> int:
    """
    Validate AAC bitrate.

    Args:
        bitrate: Bitrate in kbps
        allowed: Set of allowed bitrates (default: {128, 192, 256, 320})

    Returns:
        Validated bitrate

    Raises:
        ValidationError: If bitrate is invalid
    """
    if allowed is None:
        allowed = {128, 192, 256, 320}

    if bitrate is None:
        return 256  # Default

    if not isinstance(bitrate, int):
        try:
            bitrate = int(bitrate)
        except (ValueError, TypeError):
            raise ValidationError(
                f"Invalid AAC bitrate: {bitrate}. Must be an integer.",
                "INVALID_ENUM",
            )

    if bitrate not in allowed:
        raise ValidationError(
            f"Invalid AAC bitrate {bitrate}. Allowed: {sorted(allowed)}",
            "INVALID_ENUM",
        )

    return bitrate


def validate_album_decision(decision: dict) -> list[str]:
    """
    Validate a single album decision from XLSX.

    Args:
        decision: Dict with album_id, resolved_action, aac_target_kbps, skip

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate action if present
    resolved_action = decision.get("resolved_action")
    if resolved_action:
        try:
            action = validate_action(resolved_action)
            decision["resolved_action"] = action
        except ValidationError as e:
            errors.append(f"[{decision.get('album_id', 'unknown')}] {e}")

    # Validate AAC bitrate if AAC action
    if decision.get("resolved_action") == Action.AAC:
        try:
            bitrate = validate_aac_bitrate(decision.get("aac_target_kbps"))
            decision["aac_target_kbps"] = bitrate
        except ValidationError as e:
            errors.append(f"[{decision.get('album_id', 'unknown')}] {e}")

    return errors
