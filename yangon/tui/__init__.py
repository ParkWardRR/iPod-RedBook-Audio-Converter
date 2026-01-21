"""TUI module with Rich-based dashboard."""

from yangon.tui.dashboard import (
    CompactDashboard,
    Dashboard,
    ProfessionalDashboard,
    run_with_dashboard,
)
from yangon.tui.events import Event, EventBus

__all__ = [
    "CompactDashboard",
    "Dashboard",
    "Event",
    "EventBus",
    "ProfessionalDashboard",
    "run_with_dashboard",
]
