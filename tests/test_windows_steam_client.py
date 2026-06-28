"""Tests for Windows Steam client preparation."""

from pathlib import Path
from unittest.mock import patch

from portprotonqt.steam_api.windows_client import (
    STEAM_STEALTH_FLAGS,
    _download_steam_seed,
    find_native_steam_app,
    get_native_steam_app_executable,
    get_windows_steam_app_launcher,
    get_windows_steam_launch_commands,
)


def _write_vdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_download_steam_seed_uses_official_manifest(tmp_path: Path) -> None:
    steam_dir = tmp_path / "steam"
    archive_name = "steam_win64.zip.0123456789abcdef"

    def download(url: str, target: Path, progress_callback=None) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith("steam_client_win64"):
            target.write_text(
                f'"file" "{archive_name}"\n"size" "100"',
                encoding="utf-8",
            )
        else:
            import zipfile

            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("steam.exe", "seed")
                archive.writestr("SteamUI.dll", "client")
            if progress_callback:
                progress_callback(100, 100)
        return True

    progress = []
    with patch("portprotonqt.steam_api.windows_client._download_file", side_effect=download):
        assert _download_steam_seed(steam_dir, progress.append) is True

    assert (steam_dir / "steam.exe").is_file()
    assert (steam_dir / "SteamUI.dll").is_file()
    assert (steam_dir / "package" / archive_name).is_file()
    assert (steam_dir / "package" / "steam_client_win64.installed").is_file()
    assert progress[-1] == 100


def test_find_native_steam_app(tmp_path: Path) -> None:
    steam_home = tmp_path / "Steam"
    game_dir = steam_home / "steamapps" / "common" / "Test Game"
    game_dir.mkdir(parents=True)
    (game_dir / "TestGame.exe").touch()
    manifest = steam_home / "steamapps" / "appmanifest_730.acf"
    _write_vdf(
        manifest,
        '"AppState"\n{\n\t"appid"\t"730"\n\t"name"\t"Test Game"\n\t"installdir"\t"Test Game"\n}\n',
    )

    with patch("portprotonqt.steam_api.windows_client.get_steam_libs", return_value={steam_home}):
        app = find_native_steam_app(steam_home, "730")

    assert app is not None
    assert app.install_path == game_dir
    assert app.manifest_path == manifest


def test_get_native_steam_app_executable_prefers_game_name(tmp_path: Path) -> None:
    steam_home = tmp_path / "Steam"
    game_dir = steam_home / "steamapps" / "common" / "Test Game"
    (game_dir / "redist").mkdir(parents=True)
    (game_dir / "TestGame.exe").touch()
    (game_dir / "redist" / "setup.exe").touch()
    _write_vdf(
        steam_home / "steamapps" / "appmanifest_730.acf",
        '"AppState"\n{\n\t"appid"\t"730"\n\t"name"\t"Test Game"\n\t"installdir"\t"Test Game"\n}\n',
    )

    with (
        patch("portprotonqt.steam_api.windows_client.get_steam_home", return_value=steam_home),
        patch("portprotonqt.steam_api.windows_client.get_steam_libs", return_value={steam_home}),
    ):
        result = get_native_steam_app_executable("730")

    assert result == game_dir / "TestGame.exe"


def test_get_windows_steam_launch_commands_real_steam(tmp_path: Path) -> None:
    steam_home = tmp_path / "Steam"
    prefix_dir = tmp_path / "prefix"
    portproton_dir = tmp_path / "PortProton"
    portproton_dir.mkdir()
    steam_exe_dir = prefix_dir / "drive_c" / "Program Files (x86)" / "Steam"
    steam_exe_dir.mkdir(parents=True)
    (steam_exe_dir / "steam.exe").touch()
    game_dir = steam_home / "steamapps" / "common" / "Test Game"
    game_dir.mkdir(parents=True)
    (game_dir / "TestGame.exe").touch()
    _write_vdf(
        steam_home / "steamapps" / "appmanifest_730.acf",
        (
            '"AppState"\n{\n'
            '\t"appid"\t"730"\n'
            '\t"name"\t"Test Game"\n'
            '\t"installdir"\t"Test Game"\n'
            '}\n'
        ),
    )
    with (
        patch(
            "portprotonqt.steam_api.windows_client._get_shared_steam_dir",
            return_value=steam_exe_dir,
        ),
        patch("portprotonqt.steam_api.windows_client.get_steam_home", return_value=steam_home),
        patch("portprotonqt.steam_api.windows_client.get_steam_libs", return_value={steam_home}),
        patch(
            "portprotonqt.steam_api.windows_client.get_portproton_start_command",
            return_value=["start.sh"],
        ),
        patch("portprotonqt.steam_api.windows_client.get_portproton_location", return_value=str(portproton_dir)),
    ):
        result = get_windows_steam_launch_commands("730")

    assert len(result) == 1
    cmd = result[0]
    assert cmd[0] == "start.sh"
    assert cmd[-1].endswith("portprotonqt_steam_730.bat")

    launcher_path = portproton_dir / "steam_scripts" / "portprotonqt_steam_730.bat"
    assert launcher_path.is_file()
    launcher_text = launcher_path.read_text(encoding="utf-8")
    assert launcher_text == (
        "@echo off\n"
        f"rem PORTPROTON_GAME_EXE={game_dir / 'TestGame.exe'}\n"
        'cd /d "C:\\Program Files (x86)\\Steam"\n'
        f'start "" "steam.exe" {STEAM_STEALTH_FLAGS} -applaunch 730\n'
    )
    assert "-nooverlay" not in launcher_text

    assert not launcher_path.with_name(launcher_path.name + ".ppdb").exists()
    assert (steam_exe_dir / "steamapps" / "appmanifest_730.acf").is_file()
    assert (steam_exe_dir / "steamapps" / "common" / "Test Game").is_symlink()


def test_get_windows_steam_launch_commands_no_prefix(tmp_path: Path) -> None:
    with patch(
        "portprotonqt.steam_api.windows_client._get_shared_steam_dir",
        return_value=None,
    ):
        result = get_windows_steam_launch_commands("730")

    assert result == []

def test_get_windows_steam_app_launcher_creates_app_files(tmp_path: Path) -> None:
    prefix_dir = tmp_path / "prefix"
    portproton_dir = tmp_path / "PortProton"
    portproton_dir.mkdir()
    steam_exe_dir = prefix_dir / "drive_c" / "Program Files (x86)" / "Steam"
    steam_exe_dir.mkdir(parents=True)
    (steam_exe_dir / "steam.exe").touch()

    with patch(
        "portprotonqt.steam_api.windows_client._get_shared_steam_dir",
        return_value=steam_exe_dir,
    ), patch(
        "portprotonqt.steam_api.windows_client.get_portproton_location",
        return_value=str(portproton_dir),
    ):
        launcher_path = get_windows_steam_app_launcher("730")

    assert launcher_path == portproton_dir / "steam_scripts" / "portprotonqt_steam_730.bat"
    assert launcher_path is not None
    assert launcher_path.is_file()
    assert not (portproton_dir / "steam_scripts" / "portprotonqt_steam_730.bat.ppdb").exists()
    assert not (steam_exe_dir / "steam.exe.ppdb").exists()


def test_get_windows_steam_app_launcher_installs_missing_steam(tmp_path: Path) -> None:
    portproton_dir = tmp_path / "PortProton"
    portproton_dir.mkdir()

    with (
        patch("portprotonqt.steam_api.windows_client._get_shared_steam_dir", return_value=None),
        patch("portprotonqt.steam_api.windows_client.get_portproton_location", return_value=str(portproton_dir)),
    ):
        launcher_path = get_windows_steam_app_launcher("730")

    assert launcher_path is not None
    assert not launcher_path.with_name(launcher_path.name + ".ppdb").exists()


def test_get_windows_steam_launch_commands_no_prefix_returns_empty(tmp_path: Path) -> None:
    steam_home = tmp_path / "Steam"
    game_dir = steam_home / "steamapps" / "common" / "Test Game"
    game_dir.mkdir(parents=True)
    _write_vdf(
        steam_home / "steamapps" / "appmanifest_730.acf",
        '"AppState"\n{\n\t"appid"\t"730"\n\t"name"\t"Test Game"\n\t"installdir"\t"Test Game"\n}\n',
    )

    with (
        patch("portprotonqt.steam_api.windows_client._get_shared_steam_dir", return_value=None),
        patch("portprotonqt.steam_api.windows_client.get_steam_home", return_value=steam_home),
        patch("portprotonqt.steam_api.windows_client.get_steam_libs", return_value={steam_home}),
        patch(
            "portprotonqt.steam_api.windows_client.get_portproton_start_command",
            return_value=["start.sh"],
        ),
    ):
        result = get_windows_steam_launch_commands("730")

    assert result == []


def test_get_windows_steam_launch_commands_keeps_app_ppdb(tmp_path: Path) -> None:
    steam_home = tmp_path / "Steam"
    prefix_dir = tmp_path / "prefix"
    portproton_dir = tmp_path / "PortProton"
    steam_scripts_dir = portproton_dir / "steam_scripts"
    steam_scripts_dir.mkdir(parents=True)
    steam_exe_dir = prefix_dir / "drive_c" / "Program Files (x86)" / "Steam"
    steam_exe_dir.mkdir(parents=True)
    (steam_exe_dir / "steam.exe").touch()
    ppdb_path = steam_scripts_dir / "portprotonqt_steam_730.bat.ppdb"
    ppdb_path.write_text("#custom\nexport PW_WINE_USE=\"CUSTOM\"\n", encoding="utf-8")
    game_dir = steam_home / "steamapps" / "common" / "Test Game"
    game_dir.mkdir(parents=True)
    _write_vdf(
        steam_home / "steamapps" / "appmanifest_730.acf",
        '"AppState"\n{\n\t"appid"\t"730"\n\t"name"\t"Test Game"\n\t"installdir"\t"Test Game"\n}\n',
    )

    with (
        patch(
            "portprotonqt.steam_api.windows_client._get_shared_steam_dir",
            return_value=steam_exe_dir,
        ),
        patch("portprotonqt.steam_api.windows_client.get_steam_home", return_value=steam_home),
        patch("portprotonqt.steam_api.windows_client.get_steam_libs", return_value={steam_home}),
        patch(
            "portprotonqt.steam_api.windows_client.get_portproton_start_command",
            return_value=["start.sh"],
        ),
        patch("portprotonqt.steam_api.windows_client.get_portproton_location", return_value=str(portproton_dir)),
    ):
        result = get_windows_steam_launch_commands("730")

    assert result == [["start.sh", str(steam_scripts_dir / "portprotonqt_steam_730.bat")]]
    assert ppdb_path.read_text(encoding="utf-8") == "#custom\nexport PW_WINE_USE=\"CUSTOM\"\n"


def test_get_windows_steam_launch_commands_no_steam_exe(tmp_path: Path) -> None:
    prefix_dir = tmp_path / "prefix"
    (prefix_dir / "drive_c" / "Program Files (x86)" / "Steam").mkdir(parents=True)

    with (
        patch(
            "portprotonqt.steam_api.windows_client._get_shared_steam_dir",
            return_value=None,
        ),
    ):
        result = get_windows_steam_launch_commands("730")

    assert result == []


def test_get_windows_steam_launch_commands_invalid_appid() -> None:
    with patch(
        "portprotonqt.steam_api.windows_client._get_shared_steam_dir",
        return_value=Path("/fake"),
    ):
        result = get_windows_steam_launch_commands("abc")

    assert result == []
