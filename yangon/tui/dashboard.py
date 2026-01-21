"""Professional Rich-based TUI dashboard with Apple-quality design."""

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from rich.align import Align
from rich.box import ROUNDED, SIMPLE
from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from yangon.tui.events import (
    BuildCompleteEvent,
    BuildProgressEvent,
    BuildStartEvent,
    Event,
    EventBus,
    LogEvent,
    ScanCompleteEvent,
    ScanProgressEvent,
    ScanStartEvent,
    TrackCompleteEvent,
    TrackErrorEvent,
    TrackStartEvent,
)


# ─────────────────────────────────────────────────────────────────────────────
# iOS-inspired color palette
# ─────────────────────────────────────────────────────────────────────────────

class Colors:
    """Apple-inspired color palette."""

    # Primary brand colors
    PRIMARY = "#007AFF"       # iOS Blue
    SECONDARY = "#5856D6"     # iOS Purple

    # Semantic colors
    SUCCESS = "#34C759"       # iOS Green
    WARNING = "#FF9500"       # iOS Orange
    ERROR = "#FF3B30"         # iOS Red

    # Neutral tones
    LABEL = "#FFFFFF"         # Primary text
    SECONDARY_LABEL = "#8E8E93"  # Secondary text
    TERTIARY_LABEL = "#48484A"   # Muted text

    # Background elements
    BG_PRIMARY = "#1C1C1E"    # Dark background
    BG_SECONDARY = "#2C2C2E"  # Elevated background
    BG_TERTIARY = "#3A3A3C"   # Card background

    # Accent colors
    TEAL = "#30B0C7"
    INDIGO = "#5E5CE6"
    PINK = "#FF2D55"
    MINT = "#00C7BE"

    # Progress bar gradient simulation
    PROGRESS_COMPLETE = "#34C759"
    PROGRESS_REMAINING = "#3A3A3C"
    PROGRESS_ACTIVE = "#007AFF"


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard State
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ActivityItem:
    """Single activity feed item."""

    timestamp: datetime
    icon: str
    message: str
    style: str = ""
    detail: str = ""


@dataclass
class DashboardState:
    """Comprehensive state for the professional dashboard."""

    # Phase tracking
    phase: str = "READY"
    phase_icon: str = "○"
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Scan metrics
    scan_total: int = 0
    scan_current: int = 0
    scan_current_dir: str = ""
    scan_albums_found: int = 0
    scan_tracks_found: int = 0

    # Build metrics
    build_total: int = 0
    build_completed: int = 0
    build_failed: int = 0
    build_cached: int = 0
    build_in_progress: int = 0

    # Current operation
    current_album: str = ""
    current_album_artist: str = ""
    current_track: str = ""
    current_action: str = ""

    # Throughput tracking
    tracks_per_minute: float = 0.0
    bytes_processed: int = 0
    bytes_total: int = 0
    _track_times: list[datetime] = field(default_factory=list)

    # Activity feed (with rich formatting)
    activity_feed: deque[ActivityItem] = field(default_factory=lambda: deque(maxlen=12))

    # Error tracking
    errors: list[dict] = field(default_factory=list)
    error_counts: dict[str, int] = field(default_factory=dict)

    # Final results
    final_succeeded: int = 0
    final_failed: int = 0
    final_cached: int = 0

    @property
    def elapsed(self) -> timedelta:
        """Get elapsed time."""
        if not self.started_at:
            return timedelta(0)
        end = self.completed_at or datetime.now()
        return end - self.started_at

    @property
    def elapsed_str(self) -> str:
        """Format elapsed time beautifully."""
        delta = self.elapsed
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"

        minutes, seconds = divmod(total_seconds, 60)
        if minutes < 60:
            return f"{minutes}m {seconds:02d}s"

        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m {seconds:02d}s"

    @property
    def eta(self) -> str:
        """Calculate estimated time remaining with early estimates."""
        if self.phase not in ("SCANNING", "CONVERTING"):
            return "—"

        elapsed_sec = self.elapsed.total_seconds()

        if self.phase == "SCANNING":
            if self.scan_total == 0:
                return "estimating..."

            # Show estimate even with minimal progress
            if self.scan_current == 0:
                if elapsed_sec < 2:
                    return "estimating..."
                # Assume ~0.5 items/sec as initial guess
                eta_seconds = self.scan_total * 2
            else:
                rate = self.scan_current / elapsed_sec if elapsed_sec > 0 else 0.5
                remaining = self.scan_total - self.scan_current
                eta_seconds = remaining / rate if rate > 0 else remaining * 2
        else:
            if self.build_total == 0:
                return "estimating..."

            completed = self.build_completed + self.build_cached

            # Show estimate even with minimal progress
            if completed == 0:
                if elapsed_sec < 3:
                    return "estimating..."
                # Use throughput data if available, or assume ~1 track/3sec
                if self.tracks_per_minute > 0:
                    eta_seconds = self.build_total / (self.tracks_per_minute / 60)
                else:
                    eta_seconds = self.build_total * 3
            else:
                rate = completed / elapsed_sec if elapsed_sec > 0 else 0.33
                remaining = self.build_total - completed
                eta_seconds = remaining / rate if rate > 0 else remaining * 3

        # Format the ETA nicely
        if eta_seconds < 0:
            return "almost done"
        elif eta_seconds < 10:
            return "< 10s"
        elif eta_seconds < 60:
            return f"~{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            mins = int(eta_seconds / 60)
            secs = int(eta_seconds % 60)
            if mins < 5:
                return f"~{mins}m {secs:02d}s"
            return f"~{mins}m"
        else:
            hours = int(eta_seconds / 3600)
            mins = int((eta_seconds % 3600) / 60)
            return f"~{hours}h {mins:02d}m"

    @property
    def progress_percent(self) -> float:
        """Get overall progress percentage."""
        if self.phase == "SCANNING":
            return (self.scan_current / max(1, self.scan_total)) * 100
        elif self.phase == "CONVERTING":
            completed = self.build_completed + self.build_cached
            return (completed / max(1, self.build_total)) * 100
        elif self.phase == "COMPLETE":
            return 100.0
        return 0.0

    def update_throughput(self) -> None:
        """Update throughput metrics."""
        self._track_times.append(datetime.now())
        # Keep last 60 seconds of data
        cutoff = datetime.now() - timedelta(seconds=60)
        self._track_times = [t for t in self._track_times if t > cutoff]

        if len(self._track_times) >= 2:
            time_span = (self._track_times[-1] - self._track_times[0]).total_seconds()
            if time_span > 0:
                self.tracks_per_minute = (len(self._track_times) - 1) / time_span * 60

    def add_activity(
        self,
        icon: str,
        message: str,
        style: str = "",
        detail: str = "",
    ) -> None:
        """Add item to activity feed."""
        self.activity_feed.append(ActivityItem(
            timestamp=datetime.now(),
            icon=icon,
            message=message,
            style=style,
            detail=detail,
        ))

    def update(self, event: Event) -> None:
        """Update state from event."""

        if isinstance(event, ScanStartEvent):
            self.phase = "SCANNING"
            self.phase_icon = "◉"
            self.started_at = datetime.now()
            self.scan_total = event.total_dirs
            self.scan_current = 0
            self.add_activity("🔍", "Scan started", Colors.PRIMARY)

        elif isinstance(event, ScanProgressEvent):
            self.scan_current = event.current
            self.scan_total = event.total
            self.scan_current_dir = event.current_dir

        elif isinstance(event, ScanCompleteEvent):
            self.phase = "SCAN COMPLETE"
            self.phase_icon = "✓"
            self.scan_albums_found = event.albums_found
            self.scan_tracks_found = event.tracks_found
            self.add_activity(
                "✓",
                f"Scan complete: {event.albums_found} albums, {event.tracks_found} tracks",
                Colors.SUCCESS,
            )

        elif isinstance(event, BuildStartEvent):
            self.phase = "CONVERTING"
            self.phase_icon = "◉"
            self.started_at = datetime.now()
            self.build_total = event.total_jobs
            self._track_times = []
            self.add_activity("🎵", f"Converting {event.total_jobs} tracks", Colors.PRIMARY)

        elif isinstance(event, BuildProgressEvent):
            self.build_completed = event.completed
            self.build_failed = event.failed
            self.build_cached = event.cached
            self.build_total = event.total
            self.current_album = event.current_album
            self.current_track = event.current_track

        elif isinstance(event, BuildCompleteEvent):
            self.phase = "COMPLETE"
            self.phase_icon = "✓"
            self.completed_at = datetime.now()
            self.final_succeeded = event.succeeded
            self.final_failed = event.failed
            self.final_cached = event.cached

            # Add completion message
            if event.failed == 0:
                self.add_activity(
                    "✓",
                    f"All done! {event.succeeded} converted, {event.cached} cached",
                    Colors.SUCCESS,
                )
            else:
                self.add_activity(
                    "⚠",
                    f"Completed with {event.failed} errors",
                    Colors.WARNING,
                )

        elif isinstance(event, TrackStartEvent):
            self.current_track = Path(event.track_path).name
            self.current_action = event.action
            self.build_in_progress += 1

        elif isinstance(event, TrackCompleteEvent):
            self.build_in_progress = max(0, self.build_in_progress - 1)
            self.update_throughput()

            if event.success:
                track_name = Path(event.track_path).name
                # Only log every Nth track to avoid flooding
                completed = self.build_completed + self.build_cached
                if completed <= 3 or completed % 10 == 0:
                    self.add_activity("✓", track_name, Colors.SUCCESS)

        elif isinstance(event, TrackErrorEvent):
            self.build_in_progress = max(0, self.build_in_progress - 1)

            # Track error counts
            code = event.error_code or "UNKNOWN"
            self.error_counts[code] = self.error_counts.get(code, 0) + 1

            self.errors.append({
                "album_id": event.album_id,
                "track_path": event.track_path,
                "error_code": code,
                "error_message": event.error_message,
            })

            track_name = Path(event.track_path).name
            self.add_activity("✗", f"{track_name}: {code}", Colors.ERROR)

        elif isinstance(event, LogEvent):
            icon = "ℹ" if event.level == "INFO" else "⚠" if event.level == "WARNING" else "✗"
            style = Colors.SECONDARY_LABEL if event.level == "INFO" else Colors.WARNING if event.level == "WARNING" else Colors.ERROR
            self.add_activity(icon, event.message, style)


# ─────────────────────────────────────────────────────────────────────────────
# Professional Dashboard Components
# ─────────────────────────────────────────────────────────────────────────────

class ProfessionalDashboard:
    """
    Apple-quality TUI dashboard with professional design.

    Features:
    - iOS-inspired color palette
    - Elegant progress indicators with ETA
    - Real-time activity feed with timestamps
    - Comprehensive stats panel
    - Beautiful error reporting
    - Keyboard hints
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.state = DashboardState()
        self.console = Console()
        self._stop_event = threading.Event()
        self._paused = False

    def render(self) -> RenderableType:
        """Render the complete dashboard."""
        # Create main layout
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )

        # Split main area
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1),
        )

        # Left side: progress + current + activity
        layout["left"].split_column(
            Layout(name="progress", size=7),
            Layout(name="current", size=6),
            Layout(name="activity", ratio=1),
        )

        # Right side: stats + errors
        layout["right"].split_column(
            Layout(name="stats", ratio=1),
            Layout(name="errors", size=10),
        )

        # Populate layout
        layout["header"].update(self._render_header())
        layout["progress"].update(self._render_progress())
        layout["current"].update(self._render_current())
        layout["activity"].update(self._render_activity())
        layout["stats"].update(self._render_stats())
        layout["errors"].update(self._render_errors())
        layout["footer"].update(self._render_footer())

        return layout

    def _render_header(self) -> Panel:
        """Render elegant header with phase and timing."""
        # Phase indicator with icon
        phase_colors = {
            "READY": Colors.SECONDARY_LABEL,
            "SCANNING": Colors.PRIMARY,
            "SCAN COMPLETE": Colors.SUCCESS,
            "CONVERTING": Colors.PRIMARY,
            "COMPLETE": Colors.SUCCESS,
        }
        phase_color = phase_colors.get(self.state.phase, Colors.SECONDARY_LABEL)

        # Build header content
        header = Table.grid(padding=(0, 2))
        header.add_column(justify="left", width=40)
        header.add_column(justify="center", ratio=1)
        header.add_column(justify="right", width=30)

        # Left: Phase
        phase_text = Text()
        phase_text.append(f"{self.state.phase_icon} ", style=phase_color)
        phase_text.append(self.state.phase, style=f"bold {phase_color}")

        # Center: Title
        title = Text()
        title.append("iPod Audio Converter", style=f"bold {Colors.LABEL}")

        # Right: Timing
        timing = Text()
        if self.state.started_at:
            timing.append("⏱ ", style=Colors.SECONDARY_LABEL)
            timing.append(self.state.elapsed_str, style=Colors.LABEL)
            if self.state.phase in ("SCANNING", "CONVERTING"):
                timing.append("  │  ", style=Colors.TERTIARY_LABEL)
                timing.append("ETA: ", style=Colors.SECONDARY_LABEL)
                timing.append(self.state.eta, style=Colors.MINT)

        header.add_row(phase_text, title, timing)

        # Progress percentage bar (thin accent line)
        progress_pct = self.state.progress_percent
        bar_width = 60
        filled = int(bar_width * progress_pct / 100)

        progress_line = Text()
        progress_line.append("━" * filled, style=Colors.SUCCESS)
        progress_line.append("━" * (bar_width - filled), style=Colors.TERTIARY_LABEL)
        progress_line.append(f"  {progress_pct:.1f}%", style=Colors.SECONDARY_LABEL)

        content = Group(
            Padding(header, (0, 1)),
            Align.center(progress_line),
        )

        return Panel(
            content,
            border_style=Colors.TERTIARY_LABEL,
            box=ROUNDED,
            padding=(0, 1),
        )

    def _render_progress(self) -> Panel:
        """Render beautiful progress bars."""
        progress = Progress(
            SpinnerColumn(style=Colors.PRIMARY),
            TextColumn("[bold]{task.description}"),
            BarColumn(
                bar_width=30,
                style=Colors.PROGRESS_REMAINING,
                complete_style=Colors.SUCCESS,
                finished_style=Colors.SUCCESS,
            ),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            expand=True,
        )

        if self.state.phase == "SCANNING":
            progress.add_task(
                "Scanning directories",
                completed=self.state.scan_current,
                total=max(1, self.state.scan_total),
            )
        elif self.state.phase in ("CONVERTING", "COMPLETE"):
            completed = self.state.build_completed + self.state.build_cached

            # Main progress
            progress.add_task(
                "Converting",
                completed=completed,
                total=max(1, self.state.build_total),
            )

            # Show cached as separate bar if any
            if self.state.build_cached > 0:
                cache_progress = Progress(
                    TextColumn("  [dim]├─"),
                    TextColumn("[dim]Cached"),
                    BarColumn(bar_width=20, style=Colors.TERTIARY_LABEL, complete_style=Colors.TEAL),
                    MofNCompleteColumn(),
                    expand=True,
                )
                cache_progress.add_task(
                    "Cached",
                    completed=self.state.build_cached,
                    total=self.state.build_total,
                )

        return Panel(
            progress,
            title="[bold]Progress",
            border_style=Colors.TERTIARY_LABEL,
            box=ROUNDED,
            padding=(0, 1),
        )

    def _render_current(self) -> Panel:
        """Render current operation with elegant styling."""
        content = Table.grid(padding=(0, 1))
        content.add_column(style=Colors.SECONDARY_LABEL, width=10)
        content.add_column(style=Colors.LABEL)

        if self.state.phase == "SCANNING":
            dir_display = self.state.scan_current_dir or "—"
            if len(dir_display) > 50:
                dir_display = "…" + dir_display[-49:]
            content.add_row("📁 Directory", dir_display)

            # Show discovery stats
            if self.state.scan_albums_found > 0 or self.state.scan_tracks_found > 0:
                content.add_row(
                    "📊 Discovered",
                    f"{self.state.scan_albums_found} albums, {self.state.scan_tracks_found} tracks"
                )
        else:
            # Current album
            album = self.state.current_album or "—"
            if len(album) > 45:
                album = album[:42] + "…"
            content.add_row("💿 Album", album)

            # Current track
            track = self.state.current_track or "—"
            if len(track) > 45:
                track = track[:42] + "…"

            action_badge = ""
            if self.state.current_action:
                action_map = {
                    "ALAC_PRESERVE": "[ALAC]",
                    "ALAC_16_44": "[ALAC→16/44]",
                    "AAC": "[AAC]",
                    "PASS_MP3": "[MP3]",
                }
                action_badge = action_map.get(self.state.current_action, f"[{self.state.current_action}]")

            track_text = Text()
            track_text.append(track)
            if action_badge:
                track_text.append(f"  {action_badge}", style=Colors.TEAL)

            content.add_row("🎵 Track", track_text)

        return Panel(
            content,
            title="[bold]Current",
            border_style=Colors.TERTIARY_LABEL,
            box=ROUNDED,
            padding=(0, 1),
        )

    def _render_activity(self) -> Panel:
        """Render activity feed with timestamps."""
        if not self.state.activity_feed:
            content = Align.center(
                Text("Waiting for activity…", style=Colors.SECONDARY_LABEL),
                vertical="middle",
            )
        else:
            items = []
            for item in list(self.state.activity_feed)[-10:]:
                time_str = item.timestamp.strftime("%H:%M:%S")

                line = Text()
                line.append(f"{time_str}  ", style=Colors.TERTIARY_LABEL)
                line.append(f"{item.icon} ", style=item.style or Colors.SECONDARY_LABEL)

                msg = item.message
                if len(msg) > 45:
                    msg = msg[:42] + "…"
                line.append(msg, style=item.style or Colors.LABEL)

                items.append(line)

            content = Group(*items)

        return Panel(
            content,
            title="[bold]Activity",
            border_style=Colors.TERTIARY_LABEL,
            box=ROUNDED,
            padding=(0, 1),
        )

    def _render_stats(self) -> Panel:
        """Render comprehensive statistics."""
        stats = Table.grid(padding=(0, 2))
        stats.add_column(style=Colors.SECONDARY_LABEL)
        stats.add_column(justify="right", style=Colors.LABEL)

        if self.state.phase in ("CONVERTING", "COMPLETE"):
            # Conversion stats
            stats.add_row(
                "✓ Converted",
                Text(str(self.state.build_completed), style=Colors.SUCCESS),
            )
            stats.add_row(
                "⚡ Cached",
                Text(str(self.state.build_cached), style=Colors.TEAL),
            )
            stats.add_row(
                "✗ Failed",
                Text(str(self.state.build_failed), style=Colors.ERROR if self.state.build_failed > 0 else Colors.SECONDARY_LABEL),
            )
            stats.add_row(
                "⏳ Remaining",
                Text(str(max(0, self.state.build_total - self.state.build_completed - self.state.build_cached - self.state.build_failed)), style=Colors.SECONDARY_LABEL),
            )

            # Divider
            stats.add_row("", "")

            # Performance metrics
            if self.state.tracks_per_minute > 0:
                stats.add_row(
                    "📈 Throughput",
                    Text(f"{self.state.tracks_per_minute:.1f}/min", style=Colors.MINT),
                )

        elif self.state.phase in ("SCANNING", "SCAN COMPLETE"):
            stats.add_row(
                "📁 Directories",
                Text(f"{self.state.scan_current}/{self.state.scan_total}", style=Colors.PRIMARY),
            )
            stats.add_row(
                "💿 Albums",
                Text(str(self.state.scan_albums_found), style=Colors.SUCCESS),
            )
            stats.add_row(
                "🎵 Tracks",
                Text(str(self.state.scan_tracks_found), style=Colors.TEAL),
            )

        return Panel(
            stats,
            title="[bold]Statistics",
            border_style=Colors.TERTIARY_LABEL,
            box=ROUNDED,
            padding=(0, 1),
        )

    def _render_errors(self) -> Panel:
        """Render error summary with counts by type."""
        if not self.state.errors:
            content = Align.center(
                Text("✓ No errors", style=Colors.SUCCESS),
                vertical="middle",
            )
            border_color = Colors.TERTIARY_LABEL
        else:
            # Show error counts by type
            lines = []

            # Header with total
            total = len(self.state.errors)
            header = Text()
            header.append(f"⚠ {total} error{'s' if total != 1 else ''}", style=f"bold {Colors.ERROR}")
            lines.append(header)
            lines.append(Text(""))

            # Breakdown by error code
            for code, count in sorted(self.state.error_counts.items(), key=lambda x: -x[1])[:5]:
                line = Text()
                line.append(f"  {code}: ", style=Colors.SECONDARY_LABEL)
                line.append(str(count), style=Colors.ERROR)
                lines.append(line)

            content = Group(*lines)
            border_color = Colors.ERROR

        return Panel(
            content,
            title="[bold]Errors",
            border_style=border_color,
            box=ROUNDED,
            padding=(0, 1),
        )

    def _render_footer(self) -> Panel:
        """Render footer with keyboard shortcuts."""
        shortcuts = Text()
        shortcuts.append("  q", style=f"bold {Colors.PRIMARY}")
        shortcuts.append(" quit  ", style=Colors.SECONDARY_LABEL)
        shortcuts.append("  Ctrl+C", style=f"bold {Colors.PRIMARY}")
        shortcuts.append(" interrupt  ", style=Colors.SECONDARY_LABEL)

        # Right side: branding
        brand = Text()
        brand.append("yangon ", style=Colors.SECONDARY_LABEL)
        brand.append("v0.1", style=Colors.TERTIARY_LABEL)

        footer = Table.grid(expand=True)
        footer.add_column(justify="left")
        footer.add_column(justify="right")
        footer.add_row(shortcuts, brand)

        return Panel(
            footer,
            border_style=Colors.TERTIARY_LABEL,
            box=SIMPLE,
            padding=(0, 1),
        )

    def run(
        self,
        work_fn: Callable[[], None],
        refresh_rate: int = 8,
    ) -> None:
        """
        Run dashboard with work function.

        Args:
            work_fn: Function to run in background thread
            refresh_rate: Display refresh rate per second (default 8 for smooth updates)
        """
        self._stop_event.clear()

        # Start work in background thread
        work_thread = threading.Thread(target=work_fn, daemon=True)
        work_thread.start()

        try:
            with Live(
                self.render(),
                console=self.console,
                refresh_per_second=refresh_rate,
                screen=True,  # Use alternate screen for clean exit
            ) as live:
                while work_thread.is_alive() or not self.event_bus._queue.empty():
                    # Process all pending events
                    events = self.event_bus.poll()
                    for event in events:
                        self.state.update(event)

                    # Update display
                    live.update(self.render())

                    # Check for stop signal
                    if self._stop_event.is_set():
                        break

                    time.sleep(1 / refresh_rate)

                # Final update to show completion
                time.sleep(0.5)
                events = self.event_bus.poll()
                for event in events:
                    self.state.update(event)
                live.update(self.render())

                # Hold final screen for a moment
                time.sleep(1.5)

        except KeyboardInterrupt:
            self._stop_event.set()
            self.console.print("\n[yellow]Interrupted by user[/yellow]")

    def stop(self) -> None:
        """Signal the dashboard to stop."""
        self._stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# Compact Dashboard (for smaller terminals or --compact flag)
# ─────────────────────────────────────────────────────────────────────────────

class CompactDashboard:
    """Minimal dashboard for smaller terminals."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.state = DashboardState()
        self.console = Console()
        self._stop_event = threading.Event()

    def render(self) -> RenderableType:
        """Render compact view."""
        lines = []

        # Status line
        status = Text()
        status.append(f"{self.state.phase_icon} {self.state.phase}", style=f"bold {Colors.PRIMARY}")
        status.append(f"  ⏱ {self.state.elapsed_str}", style=Colors.SECONDARY_LABEL)
        if self.state.phase in ("SCANNING", "CONVERTING"):
            status.append(f"  ETA: {self.state.eta}", style=Colors.MINT)
        lines.append(status)

        # Progress
        if self.state.phase == "SCANNING":
            pct = self.state.scan_current / max(1, self.state.scan_total) * 100
            lines.append(Text(f"  Scanning: {self.state.scan_current}/{self.state.scan_total} ({pct:.0f}%)"))
        elif self.state.phase in ("CONVERTING", "COMPLETE"):
            completed = self.state.build_completed + self.state.build_cached
            pct = completed / max(1, self.state.build_total) * 100
            lines.append(Text(
                f"  Progress: {completed}/{self.state.build_total} ({pct:.0f}%) | "
                f"✓{self.state.build_completed} ⚡{self.state.build_cached} ✗{self.state.build_failed}"
            ))

        # Current
        if self.state.current_track:
            lines.append(Text(f"  → {self.state.current_track}", style=Colors.SECONDARY_LABEL))

        return Group(*lines)

    def run(self, work_fn: Callable[[], None], refresh_rate: int = 4) -> None:
        """Run with live updates."""
        self._stop_event.clear()
        work_thread = threading.Thread(target=work_fn, daemon=True)
        work_thread.start()

        try:
            with Live(self.render(), console=self.console, refresh_per_second=refresh_rate) as live:
                while work_thread.is_alive() or not self.event_bus._queue.empty():
                    for event in self.event_bus.poll():
                        self.state.update(event)
                    live.update(self.render())
                    if self._stop_event.is_set():
                        break
                    time.sleep(1 / refresh_rate)
                live.update(self.render())
        except KeyboardInterrupt:
            self._stop_event.set()

    def stop(self) -> None:
        """Stop the dashboard."""
        self._stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

# Backwards compatibility aliases
Dashboard = ProfessionalDashboard


def run_with_dashboard(
    event_bus: EventBus,
    work_fn: Callable[[], None],
    show_tui: bool = True,
    compact: bool = False,
) -> None:
    """
    Run work function with optional TUI dashboard.

    Args:
        event_bus: Event bus for progress updates
        work_fn: Work function to execute
        show_tui: Whether to show TUI (False for quiet mode)
        compact: Use compact dashboard (for small terminals)
    """
    if show_tui:
        if compact:
            dashboard = CompactDashboard(event_bus)
        else:
            dashboard = ProfessionalDashboard(event_bus)
        dashboard.run(work_fn)
    else:
        # Run without TUI
        work_fn()
