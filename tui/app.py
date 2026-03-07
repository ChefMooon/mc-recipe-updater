"""
Main TUI application class.

MCRecipeApp is the root Textual App that manages all screens and navigation.
"""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer

from config import ConfigManager
from tui.screens.home import HomeScreen


class MCRecipeApp(App):
    """
    Main mc-recipe-updater TUI application.
    
    Manages screen navigation, color scheme, and ConfigManager instance.
    Provides methods for screens to request navigation to other screens.
    """

    CSS = """
    Screen {
        background: $surface;
        color: $text;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    TITLE = "mc-recipe-updater (mcru)"
    SUB_TITLE = "TUI Mode"

    def __init__(self):
        """Initialize the app and load configuration."""
        super().__init__()
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Compose the app layout with header and footer."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted. Push the home screen."""
        self.push_screen(HomeScreen(self.config_manager))

    def push_profile_screen(self) -> None:
        """Navigate to profile management screen."""
        from tui.screens.profiles import ProfilesScreen
        self.push_screen(ProfilesScreen(self.config_manager))

    def push_suite_screen(self) -> None:
        """Navigate to suite management screen."""
        from tui.screens.suites import SuitesScreen
        self.push_screen(SuitesScreen(self.config_manager))

    def push_run_screen(self) -> None:
        """Navigate to sync execution screen."""
        from tui.screens.run_profile import RunProfileScreen
        self.push_screen(RunProfileScreen(self.config_manager))

    def push_reports_screen(self) -> None:
        """Navigate to reports view screen."""
        from tui.screens.reports import ReportsScreen
        self.push_screen(ReportsScreen(self.config_manager))

    def push_config_screen(self) -> None:
        """Navigate to configuration screen."""
        from tui.screens.config import ConfigScreen
        self.push_screen(ConfigScreen(self.config_manager))

    def push_backups_screen(self) -> None:
        """Navigate to backups management screen."""
        from tui.screens.backups import BackupsScreen
        self.push_screen(BackupsScreen(self.config_manager))
