"""Tests for JSON helpers used by PortProton shell scripts."""

from pathlib import Path

import orjson

from portprotonqt.scripts_utils import json_tools


def test_wine_url_matches_version_case_insensitive() -> None:
    metadata = {
        "proton": [
            {"name": "GE-Proton10-15", "url": "https://example.org/proton.tar.gz"},
        ],
    }

    assert json_tools._wine_url(metadata, "ge-proton10-15") == "https://example.org/proton.tar.gz"


def test_wine_url_ignores_unexpected_metadata() -> None:
    metadata = {
        "broken": {"name": "GE-Proton10-15"},
        "wine": [{"name": "Wine", "url": "https://example.org/wine.tar.gz"}],
    }

    assert json_tools._wine_url(metadata, "missing") == ""


def test_epic_manifest_fields_reads_launcher_values(tmp_path: Path) -> None:
    manifest_path = tmp_path / "game.item"
    manifest_path.write_bytes(orjson.dumps({
        "InstallLocation": "C:\\Games\\Demo",
        "LaunchExecutable": "Demo.exe",
        "DisplayName": "Demo Game",
        "AppName": "demo-app",
    }))

    manifest = json_tools._load_json_file(str(manifest_path))

    assert json_tools._epic_manifest_fields(manifest) == (
        "C:\\Games\\Demo\\Demo.exe",
        "Demo Game",
        "demo-app",
    )
