"""Rich-based TUI dashboard."""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
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


@dataclass
class DashboardState:
    """State for dashboard display."""

    phase: str = "IDLE"
    started_at: datetime | None = None

    # Scan state
    scan_total: int = 0
    scan_current: int = 0
    scan_current_dir: str = ""

    # Build state
    build_total: int = 0
    build_completed: int = 0
    build_failed: int = 0
    build_cached: int = 0
    current_album: str = ""
    current_track: str = ""

    # Event log (last N events)
    events: deque = field(default_factory=lambda: deque(maxlen=10))

    # Error summary
    errors: list[tuple[str, str, str]] = field(default_factory=list)  # (album_id, code, message)

    def update(self, event: Event) -> None:
        """Update state from event."""
        if isinstance(event, ScanStartEvent):
            self.phase = "SCANNING"
            self.started_at = datetime.now()
            self.scan_total = event.total_dirs
            self.scan_current = 0

        elif isinstance(event, ScanProgressEvent):
            self.scan_current = event.current
            self.scan_total = event.total
            self.scan_current_dir = event.current_dir

        elif isinstance(event, ScanCompleteEvent):
            self.phase = "SCAN COMPLETE"
            self.events.append(f"Scan complete: {event.albums_found} albums, {event.tracks_found} tracks")

        elif isinstance(event, BuildStartEvent):
            self.phase = "BUILDING"
            self.started_at = datetime.now()
            self.build_total = event.total_jobs

        elif isinstance(event, BuildProgressEvent):
            self.build_completed = event.completed
            self.build_failed = event.failed
            self.build_cached = event.cached
            self.build_total = event.total
            self.current_album = event.current_album
            self.current_track = event.current_track

        elif isinstance(event, BuildCompleteEvent):
            self.phase = "BUILD COMPLETE"
            self.events.append(
                f"Build complete: {event.succeeded} succeeded, "
                f"{event.failed} failed, {event.cached} cached"
            )

        elif isinstance(event, TrackStartEvent):
            self.current_track = event.track_path
            self.events.append(f"Started: {event.track_path}")

        elif isinstance(event, TrackCompleteEvent):
            if event.success:
                self.events.append(f"Done: {event.track_path}")

        elif isinstance(event, TrackErrorEvent):
            self.errors.append((event.album_id, event.error_code, event.error_message))
            self.events.append(f"ERROR [{event.error_code}]: {event.track_path}")

        elif isinstance(event, LogEvent):
            self.events.append(f"[{event.level}] {event.message}")


class Dashboard:
    """
    Rich-based TUI dashboard for progress display.

    Displays:
    - Current phase and elapsed time
    - Progress bars
    - Current item being processed
    - Recent events
    - Error summary
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.state = DashboardState()
        self.console = Console()
        self._stop_event = threading.Event()

    def render(self) -> Group:
        """Render the full dashboard."""
        return Group(
            self._render_header(),
            self._render_progress(),
            self._render_current(),
            self._render_events(),
            self._render_errors(),
        )

    def _render_header(self) -> Panel:
        """Render header with phase and timing."""
        elapsed = ""
        if self.state.started_at:
            delta = datetime.now() - self.state.started_at
            minutes, seconds = divmod(int(delta.total_seconds()), 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                elapsed = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                elapsed = f"{minutes:02d}:{seconds:02d}"

        text = Text()
        text.append("Phase: ", style="bold")
        text.append(self.state.phase, style="cyan bold")
        if elapsed:
            text.append("  |  Elapsed: ", style="bold")
            text.append(elapsed, style="green")

        return Panel(text, title="yangon", border_style="blue")

    def _render_progress(self) -> Panel:
        """Render progress bars."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        )

        if self.state.phase == "SCANNING":
            progress.add_task(
                "Scanning",
                completed=self.state.scan_current,
                total=max(1, self.state.scan_total),
            )
        elif self.state.phase in ("BUILDING", "BUILD COMPLETE"):
            total = max(1, self.state.build_total)
            completed = self.state.build_completed + self.state.build_cached
            progress.add_task("Building", completed=completed, total=total)

            if self.state.build_failed > 0:
                progress.add_task(
                    "[red]Failed",
                    completed=self.state.build_failed,
                    total=total,
                )

        return Panel(progress, title="Progress", border_style="green")

    def _render_current(self) -> Panel:
        """Render current item being processed."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold")
        table.add_column("Value")

        if self.state.phase == "SCANNING":
            table.add_row("Directory:", self.state.scan_current_dir or "-")
        else:
            table.add_row("Album:", self.state.current_album or "-")
            table.add_row("Track:", self.state.current_track or "-")

        return Panel(table, title="Current", border_style="yellow")

    def _render_events(self) -> Panel:
        """Render recent events."""
        if not self.state.events:
            content = Text("No events yet", style="dim")
        else:
            lines = []
            for event in list(self.state.events)[-8:]:
                if "ERROR" in event:
                    lines.append(Text(event, style="red"))
                elif "Done:" in event:
                    lines.append(Text(event, style="green"))
                else:
                    lines.append(Text(event, style="dim"))
            content = Group(*lines)

        return Panel(content, title="Recent Events", border_style="cyan")

    def _render_errors(self) -> Panel:
        """Render error summary."""
        if not self.state.errors:
            return Panel(
                Text("No errors", style="green"),
                title="Errors",
                border_style="red",
            )

        table = Table(show_header=True, box=None)
        table.add_column("Album", style="dim")
        table.add_column("Code", style="red bold")
        table.add_column("Message")

        # Show last 5 errors
        for album_id, code, message in self.state.errors[-5:]:
            table.add_row(album_id[:16], code, message[:50])

        total_errors = len(self.state.errors)
        title = f"Errors ({total_errors})" if total_errors > 5 else "Errors"

        return Panel(table, title=title, border_style="red")

    def run(
        self,
        work_fn: Callable[[], None],
        refresh_rate: int = 4,
    ) -> None:
        """
        Run dashboard with work function.

        Args:
            work_fn: Function to run in background thread
            refresh_rate: Display refresh rate per second
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
            ) as live:
                while work_thread.is_alive() or not self.event_bus._queue.empty():
                    # Process events
                    events = self.event_bus.poll()
                    for event in events:
                        self.state.update(event)

                    # Update display
                    live.update(self.render())

                    # Check for stop
                    if self._stop_event.is_set():
                        break

                    time.sleep(1 / refresh_rate)

                # Final update
                live.update(self.render())

        except KeyboardInterrupt:
            self._stop_event.set()
            self.console.print("\n[yellow]Interrupted by user[/yellow]")

    def stop(self) -> None:
        """Signal the dashboard to stop."""
        self._stop_event.set()


def run_with_dashboard(
    event_bus: EventBus,
    work_fn: Callable[[], None],
    show_tui: bool = True,
) -> None:
    """
    Run work function with optional TUI dashboard.

    Args:
        event_bus: Event bus for progress updates
        work_fn: Work function to execute
        show_tui: Whether to show TUI (False for quiet mode)
    """
    if show_tui:
        dashboard = Dashboard(event_bus)
        dashboard.run(work_fn)
    else:
        # Just run without TUI
        work_fn()
