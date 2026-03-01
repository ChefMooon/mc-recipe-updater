"""
Configuration and settings screen (placeholder).

To be implemented in Phase 6 with config viewing and reset options.
"""

from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding
from config import ConfigManager


class ConfigScreen(Screen):
    """Configuration and settings screen."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager

    def compose(self):
        """Compose the config screen layout."""
        with Vertical():
            yield Static("⚙ Configuration Screen", classes="header")
            yield Static("Settings management coming soon...", classes="placeholder")
            yield Button("Back", id="back_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_button":
            self.app.pop_screen()

    def action_back(self) -> None:
        """Return to home screen."""
        self.app.pop_screen()
