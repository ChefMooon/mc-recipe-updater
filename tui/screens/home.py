"""
Home screen with ASCII art animation and command menu.

The entry point for the TUI, featuring animated title art and 
a navigable list of available commands.
"""

from pathlib import Path
from typing import Optional
from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Static, Input
from textual.binding import Binding
from config import ConfigManager
from tui.screens.asciimtn_loader import load_asciimtn, ASCIImtnAnimation

# Load the custom ASCII animation
ASSETS_DIR = Path(__file__).parent.parent / "assets"
ANIMATION_FILE = ASSETS_DIR / "mcru.asciimtn"

try:
    SPLASH_ANIMATION: ASCIImtnAnimation = load_asciimtn(ANIMATION_FILE)
except (FileNotFoundError, Exception):
    # Fallback if file not found
    SPLASH_ANIMATION = None

# Version and help text
VERSION = "2.0.0"
SUBTITLE = "Tab to autocomplete, ↑↓ for history, Ctrl+C to quit"

COMMANDS = [
    ("profile", "Manage sync profiles"),
    ("suite", "Manage profile suites"),
    ("run", "Run a sync operation"),
    ("reports", "View run history"),
    ("config", "Settings & presets"),
]


class SplashArt(Static):
    """Animated splash art display loaded from .asciimtn file."""

    DEFAULT_CSS = """
    SplashArt {
        width: 1fr;
        height: auto;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.frame_index = 0

    def render(self) -> str:
        """Return current frame of animation from loaded .asciimtn file, centered with offset."""
        if SPLASH_ANIMATION is None:
            return "mcru — Minecraft Recipe Updater"
        
        frame = SPLASH_ANIMATION.get_frame(self.frame_index)
        art_text = frame.render()
        
        # Add offset: move right and up
        lines = art_text.split('\n')
        
        # Find the maximum line width
        max_width = max(len(line) for line in lines) if lines else 0
        
        # Center each line and add right offset
        right_offset = 8  # Move right by this many spaces
        centered_lines = []
        for line in lines:
            # Calculate padding needed (total width / 2 - line width / 2)
            padding = (max_width - len(line)) // 2
            centered_line = ' ' * (padding + right_offset) + line
            centered_lines.append(centered_line)
        
        return '\n'.join(centered_lines)


class CommandList(Static):
    """List of available commands with descriptions in formatted columns."""

    DEFAULT_CSS = """
    CommandList {
        width: 1fr;
        height: auto;
        padding: 1 2;
    }
    """

    def __init__(self):
        super().__init__()
        self.selected_index = 0
        self.command_history = []
        self.history_index = -1

    def render(self) -> str:
        """Render commands in a formatted column list."""
        lines = []
        
        # Column header
        lines.append(f"{'Command':<15} Description")
        lines.append("─" * 50)
        
        for i, (cmd, desc) in enumerate(COMMANDS):
            marker = "► " if i == self.selected_index else "  "
            lines.append(f"{marker}{cmd:<13} {desc}")
        
        return "\n".join(lines)

    def action_select_up(self) -> None:
        """Move selection up."""
        self.selected_index = max(0, self.selected_index - 1)
        self.refresh()

    def action_select_down(self) -> None:
        """Move selection down."""
        self.selected_index = min(len(COMMANDS) - 1, self.selected_index + 1)
        self.refresh()

    def get_selected_command(self) -> str:
        """Return the currently selected command."""
        return COMMANDS[self.selected_index][0]


class HomeScreen(Screen):
    """
    Home screen with ASCII art splash, input, and command navigation.
    
    - Arrow keys: Navigate command list
    - Tab: Autocomplete from commands
    - Up/Down (in input): History navigation
    - Enter: Execute command from input or selected list item
    - Ctrl+C: Quit
    """

    BINDINGS = [
        Binding("up", "select_up", "Up", show=False),
        Binding("down", "select_down", "Down", show=False),
        Binding("enter", "select_command", "Select", show=False),
        Binding("tab", "autocomplete", "Autocomplete", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    HomeScreen {
        background: $surface;
    }

    HomeScreen Vertical {
        width: 1fr;
        height: 1fr;
    }

    #version-info {
        width: 1fr;
        height: auto;
        color: $text;
        padding: 0 1;
    }

    #subtitle {
        width: 1fr;
        height: auto;
        color: $text-muted;
        padding: 0 1;
    }

    #command-input {
        width: 1fr;
        margin: 1 0;
    }

    #command-list {
        width: 1fr;
        height: auto;
    }
    """

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.splash: Optional[SplashArt] = None
        self.command_input: Optional[Input] = None
        self.command_list: Optional[CommandList] = None
        self.command_history = []
        self.history_index = -1

    def compose(self):
        """Compose the home screen layout."""
        with Vertical():
            # Logo
            self.splash = SplashArt()
            yield self.splash
            
            # Version info
            version_widget = Static(f"mcru {VERSION}", id="version-info")
            yield version_widget
            
            # Subtitle/Help text
            subtitle_widget = Static(SUBTITLE, id="subtitle")
            yield subtitle_widget
            
            # Command input
            self.command_input = Input(
                placeholder="> Enter command (profile|suite|run|reports|config)",
                id="command-input"
            )
            yield self.command_input
            
            # Command list
            self.command_list = CommandList()
            self.command_list.id = "command-list"
            yield self.command_list

    def action_select_up(self) -> None:
        """Move selection up in command list."""
        if self.command_list:
            self.command_list.action_select_up()

    def action_select_down(self) -> None:
        """Move selection down in command list."""
        if self.command_list:
            self.command_list.action_select_down()

    def action_select_command(self) -> None:
        """Execute the selected command."""
        if self.command_input and self.command_input.value:
            command = self.command_input.value.strip()
        elif self.command_list:
            command = self.command_list.get_selected_command()
        else:
            return
        
        if command:
            self._handle_command(command)

    def action_autocomplete(self) -> None:
        """Autocomplete command from input."""
        if not self.command_input:
            return
        
        partial = self.command_input.value.strip().lower()
        if not partial:
            return
        
        # Find matching commands
        matches = [cmd for cmd, _ in COMMANDS if cmd.startswith(partial)]
        
        if len(matches) == 1:
            self.command_input.value = matches[0]
            self.command_input.cursor_position = len(matches[0])
        elif len(matches) > 1:
            # Show first match as suggestion
            self.command_input.value = matches[0]
            self.command_input.cursor_position = len(matches[0])

    def action_profile(self) -> None:
        """Navigate to profile screen."""
        self._handle_command("profile")

    def action_suite(self) -> None:
        """Navigate to suite screen."""
        self._handle_command("suite")

    def action_run(self) -> None:
        """Navigate to run screen."""
        self._handle_command("run")

    def action_config(self) -> None:
        """Navigate to config screen."""
        self._handle_command("config")

    def action_reports(self) -> None:
        """Navigate to reports screen."""
        self._handle_command("reports")

    def _handle_command(self, command: str) -> None:
        """Route command to appropriate screen."""
        command = command.strip().lower()
        app = self.app
        
        # Add to history
        if command and command not in ("q", "quit", "exit"):
            if command not in self.command_history:
                self.command_history.append(command)
        
        if command == "profile":
            app.push_profile_screen()
        elif command == "suite":
            app.push_suite_screen()
        elif command == "run":
            app.push_run_screen()
        elif command == "reports":
            app.push_reports_screen()
        elif command == "config":
            app.push_config_screen()
        elif command in ("q", "quit", "exit"):
            app.exit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission when user presses Enter."""
        if event.input.id == "command-input":
            self.action_select_command()
            # Clear input after command
            if self.command_input:
                self.command_input.value = ""
