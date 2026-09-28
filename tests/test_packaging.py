import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from setuptools import find_packages


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_includes_bundled_mapping_presets(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    for filename in (
        "setup.py",
        "backup.py",
        "cli.py",
        "config.py",
        "registry.py",
        "reporter.py",
        "syncer.py",
    ):
        shutil.copy2(PROJECT_ROOT / filename, source / filename)

    shutil.copytree(PROJECT_ROOT / "mcru_resources", source / "mcru_resources")
    shutil.copytree(PROJECT_ROOT / "tui", source / "tui")

    assert "mcru_resources" in find_packages(where=str(source))

    dist = tmp_path / "dist"
    build = tmp_path / "build"
    result = subprocess.run(
        [
            sys.executable,
            "setup.py",
            "bdist_wheel",
            "--dist-dir",
            str(dist),
            "--bdist-dir",
            str(build),
        ],
        cwd=source,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    wheels = list(dist.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        preset_files = [
            name for name in wheel.namelist() if name.endswith("mapping-presets.json")
        ]

    assert preset_files == ["mcru_resources/mapping-presets.json"]
