"""Tests for main window library data processing."""

from pathlib import Path
from typing import Any

from portprotonqt.main_window import MainWindow


def test_process_portproton_desktop_calls_callback_without_asset_download(
    tmp_config_dir: Path,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    exe_path = tmp_path / "Game.exe"
    exe_path.write_text("", encoding="utf-8")
    desktop_path = tmp_path / "Game.desktop"
    desktop_path.write_text(
        "[Desktop Entry]\n"
        "Name=Test Game\n"
        f"Exec=portproton {exe_path}\n"
        "Icon=\n",
        encoding="utf-8",
    )

    window = MainWindow.__new__(MainWindow)
    window.portproton_location = str(tmp_path)
    results: list[tuple | None] = []

    def fake_steam_info(_name: str, _exec_line: str, callback: Any) -> None:
        callback({})

    monkeypatch.setattr(
        "portprotonqt.main_window.generate_thumbnail",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr("portprotonqt.main_window.get_steam_game_info_async", fake_steam_info)
    monkeypatch.setattr("portprotonqt.main_window.get_last_launch", lambda _exe_name: "Never")
    monkeypatch.setattr(
        "portprotonqt.main_window.get_last_launch_timestamp",
        lambda _exe_name: 0,
    )
    monkeypatch.setattr("portprotonqt.main_window.get_playtime_for_exe", lambda *_args: None)
    monkeypatch.setattr("portprotonqt.main_window.ui_config.get_economy_mode", lambda: False)

    window._process_desktop_file_async(str(desktop_path), results.append)

    assert len(results) == 1
    assert results[0] is not None
    assert results[0][0] == "Test Game"
    assert results[0][5] == f"portproton {exe_path}"
