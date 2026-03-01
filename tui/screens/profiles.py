"""
Profile management screen (placeholder).

To be implemented in Phase 2 with full profile CRUD operations.
"""

from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Static, Button
from textual.binding import Binding
from config import ConfigManager


class ProfilesScreen(Screen):
    """Profile management screen."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager

    def compose(self):
        """Compose the profile screen layout."""
        with Vertical():
            yield Static("📋 Profiles Screen", classes="header")
            yield Static("Profile management coming soon...", classes="placeholder")
            yield Button("Back", id="back_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Return to home screen."""
        self.app.pop_screen()
