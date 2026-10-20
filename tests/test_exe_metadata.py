"""Tests for PE metadata consumed by PortProton shell scripts."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from portprotonqt.scripts_utils import exe_metadata


def test_reads_version_strings_and_closes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Game.exe"
    pe = MagicMock()
    table = SimpleNamespace(entries={b"ProductName": b"Game", b"CompanyName": b"Sony"})
    pe.__enter__.return_value.FileInfo = [[SimpleNamespace(StringTable=[table])]]
    constructor = MagicMock(return_value=pe)
    monkeypatch.setattr(exe_metadata.pefile, "PE", constructor)

    assert exe_metadata.read_metadata(str(path)) == {"ProductName": "Game", "CompanyName": "Sony"}
    constructor.assert_called_once_with(str(path), fast_load=True)
    pe.__enter__.return_value.parse_data_directories.assert_called_once_with(
        directories=[exe_metadata.pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]],
    )
    pe.__exit__.assert_called_once()


@pytest.mark.parametrize("error", [exe_metadata.pefile.PEFormatError("invalid"), OSError("unreadable")])
def test_unreadable_pe_allows_exiftool_fallback(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    monkeypatch.setattr(exe_metadata.pefile, "PE", MagicMock(side_effect=error))
    assert exe_metadata.read_metadata("Game.exe") is None


def test_cli_preserves_shell_field_labels(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(exe_metadata.sys, "argv", ["exe_metadata", "/Games/Game.exe"])
    monkeypatch.setattr(exe_metadata, "read_metadata", lambda _path: {
        "ProductName": "Game", "FileDescription": "Description\r\nextra", "CompanyName": "Sony",
    })
    assert exe_metadata.main() == 0
    assert capsys.readouterr().out == (
        "File Name: Game.exe\nProduct Name: Game\nFile Description: Description extra\nCompany Name: Sony\n"
    )


def test_cli_returns_failure_for_unsupported_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(exe_metadata.sys, "argv", ["exe_metadata", "Game.exe"])
    monkeypatch.setattr(exe_metadata, "read_metadata", lambda _path: None)
    assert exe_metadata.main() == 1
