"""Event system for TUI updates."""

from dataclasses import dataclass, field
from datetime import datetime
from queue import Empty, Queue
from typing import Any


@dataclass
class Event:
    """Base event class."""

    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "generic"


@dataclass
class ScanStartEvent(Event):
    """Scan operation started."""

    total_dirs: int = 0
    event_type: str = "scan_start"


@dataclass
class ScanProgressEvent(Event):
    """Scan progress update."""

    current: int = 0
    total: int = 0
    current_dir: str = ""
    event_type: str = "scan_progress"


@dataclass
class ScanCompleteEvent(Event):
    """Scan operation completed."""

    albums_found: int = 0
    tracks_found: int = 0
    event_type: str = "scan_complete"


@dataclass
class BuildStartEvent(Event):
    """Build operation started."""

    total_jobs: int = 0
    event_type: str = "build_start"


@dataclass
class BuildProgressEvent(Event):
    """Build progress update."""

    completed: int = 0
    failed: int = 0
    cached: int = 0
    total: int = 0
    current_album: str = ""
    current_track: str = ""
    event_type: str = "build_progress"


@dataclass
class BuildCompleteEvent(Event):
    """Build operation completed."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    cached: int = 0
    event_type: str = "build_complete"


@dataclass
class TrackStartEvent(Event):
    """Track processing started."""

    album_id: str = ""
    track_path: str = ""
    action: str = ""
    event_type: str = "track_start"


@dataclass
class TrackCompleteEvent(Event):
    """Track processing completed."""

    album_id: str = ""
    track_path: str = ""
    output_path: str = ""
    success: bool = True
    event_type: str = "track_complete"


@dataclass
class TrackErrorEvent(Event):
    """Track processing failed."""

    album_id: str = ""
    track_path: str = ""
    error_code: str = ""
    error_message: str = ""
    event_type: str = "track_error"


@dataclass
class LogEvent(Event):
    """General log message."""

    level: str = "INFO"
    message: str = ""
    event_type: str = "log"


class EventBus:
    """Thread-safe event bus for TUI updates."""

    def __init__(self):
        self._queue: Queue[Event] = Queue()
        self._listeners: list[callable] = []

    def emit(self, event: Event) -> None:
        """
        Emit an event to the bus.

        Args:
            event: Event to emit
        """
        self._queue.put(event)

    def poll(self, timeout: float = 0.1) -> list[Event]:
        """
        Poll for pending events.

        Args:
            timeout: Max time to wait for events

        Returns:
            List of events (may be empty)
        """
        events = []
        try:
            while True:
                event = self._queue.get_nowait()
                events.append(event)
        except Empty:
            pass
        return events

    def poll_one(self, timeout: float = 0.1) -> Event | None:
        """
        Poll for a single event.

        Args:
            timeout: Max time to wait

        Returns:
            Event or None
        """
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def clear(self) -> None:
        """Clear all pending events."""
        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            pass
