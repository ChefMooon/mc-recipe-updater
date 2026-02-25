from setuptools import setup

setup(
    name="mc-recipe-updater",
    version="1.0.0",
    py_modules=["cli", "config", "registry", "reporter", "syncer"],
    install_requires=["click>=8.0"],
    entry_points={
        "console_scripts": [
            # After: pip install -e .
            # You can run: mcru <command> from anywhere
            "mcru=cli:cli",
        ],
    },
    python_requires=">=3.10",
)
