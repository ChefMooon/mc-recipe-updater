"""
Suite management screen (placeholder).

To be implemented in Phase 3 with full suite CRUD operations.
"""

from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding
from config import ConfigManager


class SuitesScreen(Screen):
    """Suite management screen."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager

    def compose(self):
        """Compose the suite screen layout."""
        with Vertical():
            yield Static("📦 Suites Screen", classes="header")
            yield Static("Suite management coming soon...", classes="placeholder")
            yield Button("Back", id="back_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Return to home screen."""
        self.app.pop_screen()
