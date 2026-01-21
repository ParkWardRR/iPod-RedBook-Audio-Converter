"""TUI module with Rich-based dashboard."""

from ipodrb.tui.dashboard import (
    CompactDashboard,
    Dashboard,
    ProfessionalDashboard,
    run_with_dashboard,
)
from ipodrb.tui.events import Event, EventBus

__all__ = [
    "CompactDashboard",
    "Dashboard",
    "Event",
    "EventBus",
    "ProfessionalDashboard",
    "run_with_dashboard",
]
