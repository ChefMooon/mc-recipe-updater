"""
Entry point for mcru-tui.

Launches the interactive Textual TUI application.
"""


def run():
    """
    Run the mcru TUI application.
    
    This is the entry point registered in setup.py.
    """
    from tui.app import MCRecipeApp
    
    app = MCRecipeApp()
    app.run()


if __name__ == "__main__":
    run()
