"""
Sync execution screen (placeholder).

To be implemented in Phase 4 with progress tracking and threading.
"""

from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding
from config import ConfigManager


class RunProfileScreen(Screen):
    """Sync execution and monitoring screen."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager

    def compose(self):
        """Compose the run screen layout."""
        with Vertical():
            yield Static("▶ Run Profile Screen", classes="header")
            yield Static("Sync execution coming soon...", classes="placeholder")
            yield Button("Back", id="back_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Return to home screen."""
        self.app.pop_screen()
