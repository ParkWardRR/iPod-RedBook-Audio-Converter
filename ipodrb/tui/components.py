"""Reusable TUI components."""

from rich.align import Align
from rich.box import ROUNDED
from rich.console import Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text


# ─────────────────────────────────────────────────────────────────────────────
# Color Constants (iOS-inspired palette)
# ─────────────────────────────────────────────────────────────────────────────

class Theme:
    """iOS-inspired color theme."""

    # Primary
    BLUE = "#007AFF"
    PURPLE = "#5856D6"

    # Semantic
    GREEN = "#34C759"
    ORANGE = "#FF9500"
    RED = "#FF3B30"

    # Text
    PRIMARY = "#FFFFFF"
    SECONDARY = "#8E8E93"
    TERTIARY = "#48484A"

    # Backgrounds
    BG_ELEVATED = "#2C2C2E"
    BG_CARD = "#3A3A3C"

    # Accents
    TEAL = "#30B0C7"
    MINT = "#00C7BE"
    INDIGO = "#5E5CE6"


# ─────────────────────────────────────────────────────────────────────────────
# Status Badge Components
# ─────────────────────────────────────────────────────────────────────────────

def status_badge(status: str) -> Text:
    """
    Create a colored status badge.

    Args:
        status: Status text (e.g., "GREEN", "YELLOW", "RED", "SUCCESS", "ERROR")

    Returns:
        Rich Text with appropriate styling
    """
    colors = {
        "GREEN": Theme.GREEN,
        "YELLOW": Theme.ORANGE,
        "RED": Theme.RED,
        "SUCCESS": Theme.GREEN,
        "WARNING": Theme.ORANGE,
        "ERROR": Theme.RED,
        "INFO": Theme.BLUE,
    }
    color = colors.get(status.upper(), Theme.SECONDARY)
    return Text(f" {status} ", style=f"bold {color}")


def progress_badge(value: int, total: int, width: int = 20) -> Text:
    """
    Create a text-based progress indicator.

    Args:
        value: Current value
        total: Total value
        width: Width of the bar in characters

    Returns:
        Rich Text with progress bar
    """
    if total == 0:
        pct = 0
    else:
        pct = value / total

    filled = int(width * pct)
    empty = width - filled

    bar = Text()
    bar.append("▓" * filled, style=Theme.GREEN)
    bar.append("░" * empty, style=Theme.TERTIARY)
    bar.append(f" {pct:.0%}", style=Theme.SECONDARY)

    return bar


# ─────────────────────────────────────────────────────────────────────────────
# Summary Cards
# ─────────────────────────────────────────────────────────────────────────────

def stat_card(title: str, value: str | int, subtitle: str = "", style: str = "") -> Panel:
    """
    Create a statistics card.

    Args:
        title: Card title
        value: Main value to display
        subtitle: Optional subtitle
        style: Optional value color style

    Returns:
        Panel containing the stat card
    """
    content = Group(
        Text(str(value), style=f"bold {style or Theme.PRIMARY}"),
        Text(subtitle, style=Theme.SECONDARY) if subtitle else Text(""),
    )

    return Panel(
        Align.center(content),
        title=title,
        border_style=Theme.TERTIARY,
        box=ROUNDED,
        padding=(1, 2),
    )


def completion_summary(
    succeeded: int,
    failed: int,
    cached: int,
    elapsed: str,
    output_path: str = "",
) -> Panel:
    """
    Create a completion summary panel.

    Args:
        succeeded: Number of successful conversions
        failed: Number of failed conversions
        cached: Number of cached (skipped) items
        elapsed: Elapsed time string
        output_path: Path to output directory

    Returns:
        Panel with completion summary
    """
    total = succeeded + failed + cached

    # Header
    if failed == 0:
        header = Text("Conversion Complete!", style=f"bold {Theme.GREEN}")
        icon = "✓"
    else:
        header = Text("Completed with Errors", style=f"bold {Theme.ORANGE}")
        icon = "⚠"

    # Stats table
    stats = Table.grid(padding=(0, 3))
    stats.add_column(style=Theme.SECONDARY)
    stats.add_column(justify="right")

    stats.add_row("Total processed:", Text(str(total), style=Theme.PRIMARY))
    stats.add_row("Converted:", Text(str(succeeded), style=Theme.GREEN))
    stats.add_row("Cached:", Text(str(cached), style=Theme.TEAL))
    if failed > 0:
        stats.add_row("Failed:", Text(str(failed), style=Theme.RED))
    stats.add_row("Duration:", Text(elapsed, style=Theme.MINT))

    if output_path:
        stats.add_row("", Text(""))
        stats.add_row("Output:", Text(output_path, style=Theme.SECONDARY))

    content = Group(
        Text(""),
        Align.center(Text(f"{icon} ", style=Theme.GREEN if failed == 0 else Theme.ORANGE)),
        Align.center(header),
        Text(""),
        stats,
        Text(""),
    )

    return Panel(
        content,
        border_style=Theme.GREEN if failed == 0 else Theme.ORANGE,
        box=ROUNDED,
        padding=(1, 2),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Progress Components
# ─────────────────────────────────────────────────────────────────────────────

def create_spinner_progress() -> Progress:
    """Create a spinner-style progress indicator."""
    return Progress(
        SpinnerColumn(style=Theme.BLUE),
        TextColumn("[bold]{task.description}"),
        BarColumn(
            bar_width=30,
            style=Theme.TERTIARY,
            complete_style=Theme.GREEN,
            finished_style=Theme.GREEN,
        ),
        TaskProgressColumn(),
    )


def create_minimal_progress() -> Progress:
    """Create a minimal progress indicator."""
    return Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=20, style=Theme.TERTIARY, complete_style=Theme.BLUE),
        TextColumn("{task.completed}/{task.total}"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Activity Feed
# ─────────────────────────────────────────────────────────────────────────────

def activity_line(
    timestamp: str,
    icon: str,
    message: str,
    style: str = "",
) -> Text:
    """
    Create a single activity feed line.

    Args:
        timestamp: Time string (e.g., "12:34:56")
        icon: Icon character
        message: Activity message
        style: Optional style for the message

    Returns:
        Rich Text line
    """
    line = Text()
    line.append(f"{timestamp}  ", style=Theme.TERTIARY)
    line.append(f"{icon} ", style=style or Theme.SECONDARY)
    line.append(message, style=style or Theme.PRIMARY)
    return line


# ─────────────────────────────────────────────────────────────────────────────
# Error Display
# ─────────────────────────────────────────────────────────────────────────────

def error_table(errors: list[dict], max_rows: int = 10) -> Table:
    """
    Create an error summary table.

    Args:
        errors: List of error dicts with album_id, error_code, error_message
        max_rows: Maximum rows to display

    Returns:
        Rich Table with error summary
    """
    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Album", style=Theme.SECONDARY, max_width=20)
    table.add_column("Code", style=f"bold {Theme.RED}", width=15)
    table.add_column("Message", style=Theme.SECONDARY)

    for err in errors[:max_rows]:
        album_id = err.get("album_id", "")[:16]
        code = err.get("error_code", "UNKNOWN")
        message = err.get("error_message", "")[:40]
        table.add_row(album_id, code, message)

    if len(errors) > max_rows:
        table.add_row(
            "",
            f"... +{len(errors) - max_rows} more",
            "",
            style=Theme.SECONDARY,
        )

    return table
