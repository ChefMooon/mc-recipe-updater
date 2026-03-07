"""
Backups screen for the TUI application.

Placeholder screen directing users to CLI for backup management.
"""

from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button


class BackupsScreen(Screen):
    """Backup management screen (placeholder)."""

    def compose(self):
        """Compose the backups screen layout."""
        with Vertical():
            yield Static("📦  Backups", classes="header")
            yield Static("Backup management coming soon...", classes="info_box")
            yield Button("Back", id="back_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "back_button":
            self.app.pop_screen()



