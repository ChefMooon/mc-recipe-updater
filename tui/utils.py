"""
TUI utility functions and threading wrapper.

Provides ThreadedSyncer for running syncs in background threads,
and helper functions for formatting output.
"""

import threading
from typing import Callable, Any, Optional
from syncer import MCRU


class ThreadedSyncer:
    """
    Wrapper around MCRU that runs sync in a background thread.
    
    Allows TUI to remain responsive while sync operations execute.
    Posts progress updates and final results via callback.
    """

    def __init__(
        self,
        config: dict,
        dry_run: bool = False,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_complete: Optional[Callable[[dict, Optional[Exception]], None]] = None,
    ):
        """
        Initialize ThreadedSyncer.
        
        Args:
            config: Syncer config dict (source, target, parsers, mapping)
            dry_run: If True, preview only without writing
            on_progress: Optional callback(current_file, total_files, operation_name)
            on_complete: Optional callback(results, error) - error is None on success
        """
        self.config = config
        self.dry_run = dry_run
        self.on_progress = on_progress or (lambda c, t, o: None)
        self.on_complete = on_complete or (lambda r, e: None)
        self.thread: Optional[threading.Thread] = None
        self.results: Optional[dict] = None
        self.error: Optional[Exception] = None

    def start(self) -> None:
        """Start the sync in a background thread."""
        self.thread = threading.Thread(target=self._run_sync, daemon=False)
        self.thread.start()

    def _run_sync(self) -> None:
        """Internal: run sync and post result."""
        try:
            mcru = MCRU(self.config, dry_run=self.dry_run)
            self.results = mcru.run()
            self.on_complete(self.results, None)
        except Exception as e:
            self.error = e
            self.on_complete(None, e)

    def is_running(self) -> bool:
        """Check if sync is still running."""
        if self.thread is None:
            return False
        return self.thread.is_alive()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for sync to complete.
        
        Args:
            timeout: Max seconds to wait, or None for indefinite
        
        Returns:
            True if completed, False if timeout
        """
        if self.thread is None:
            return True
        self.thread.join(timeout)
        return not self.thread.is_alive()


def format_path(path: str, max_length: int = 50) -> str:
    """
    Truncate long paths for display.
    
    Args:
        path: Full path
        max_length: Max chars to display
    
    Returns:
        Truncated path (with ellipsis if needed)
    """
    if len(path) <= max_length:
        return path
    
    # Try to keep the filename visible
    parts = path.split("\\")  # Windows
    if len(parts) == 1:
        parts = path.split("/")  # Unix
    
    filename = parts[-1]
    available = max_length - len(" ... / ")
    
    if len(filename) > available:
        return filename[:available] + "..."
    
    return f".../{filename}"


def format_file_count(count: int) -> str:
    """Format file count with thousands separator."""
    return f"{count:,}"


def format_bytes(size_bytes: int) -> str:
    """
    Format bytes as human-readable string.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted size (e.g. "1.5 MB")
    """
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
