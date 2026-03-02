from setuptools import setup, find_packages

setup(
    name="mc-recipe-updater",
    version="2.0.0",
    py_modules=["cli", "config", "registry", "reporter", "syncer"],
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "textual>=0.30.0",
    ],
    entry_points={
        "console_scripts": [
            # After: pip install -e .
            # CLI: mcru <command> from anywhere
            # TUI: mcru-tui for interactive mode
            "mcru=cli:cli",
            "mcru-tui=tui.main:run",
            "mcrui=tui.main:run",  # Alias for TUI
        ],
    },
    python_requires=">=3.10",
)
