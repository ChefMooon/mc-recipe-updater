"""
TUI tests (placeholder)

To be implemented with Textual test framework in Phase 7.
"""

import pytest


def test_home_screen_exists():
    """Placeholder test - home screen should be importable."""
    from tui.screens.home import HomeScreen
    assert HomeScreen is not None


def test_profiles_screen_exists():
    """Placeholder test - profiles screen should be importable."""
    from tui.screens.profiles import ProfilesScreen
    assert ProfilesScreen is not None


def test_remaining_screens_exist():
    """Remaining TUI screens should be importable."""
    from tui.screens.backups import BackupsScreen
    from tui.screens.config import ConfigScreen
    from tui.screens.reports import ReportsScreen
    from tui.screens.run_profile import RunProfileScreen
    from tui.screens.suites import SuitesScreen

    assert BackupsScreen is not None
    assert ConfigScreen is not None
    assert ReportsScreen is not None
    assert RunProfileScreen is not None
    assert SuitesScreen is not None
