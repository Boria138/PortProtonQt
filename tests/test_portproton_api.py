"""Tests for PortProton API helpers."""

from pathlib import Path
from typing import Any, cast

from portprotonqt.portproton_api import PortProtonAPI


class DummyDownloader:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, str, int]] = []

    def download(self, url: str, local_path: str, timeout: int = 5) -> str:
        self.downloads.append((url, local_path, timeout))
        Path(local_path).write_text("cover", encoding="utf-8")
        return local_path


def test_autoinstall_description_falls_back_to_english(tmp_config_dir: Path) -> None:
    api = PortProtonAPI()
    game = {
        "name_ru": None,
        "description_en": "Launcher for the VK Play game library.",
    }

    assert api._get_autoinstall_field(game, "description", "ru") == "Launcher for the VK Play game library."


def test_autoinstall_name_falls_back_to_plain_field(tmp_config_dir: Path) -> None:
    api = PortProtonAPI()
    game = {
        "name": "VK Play",
        "name_en": None,
        "name_ru": None,
    }

    assert api._get_autoinstall_field(game, "name", "ru") == "VK Play"


def test_autoinstall_script_writes_custom_metadata_for_target_exe(
    tmp_config_dir: Path,
    tmp_path: Path,
) -> None:
    api = PortProtonAPI(downloader=cast(Any, DummyDownloader()))
    game_data = {
        "name": "Test Game",
        "description": "English description",
    }
    script_path = tmp_path / "game_42_test.ppai"
    script_path.write_text(
        'export PW_AUTOINSTALL_EXE="${PORT_DATA_PATH}/data/prefixes/GAME/drive_c/Game.exe"\n',
        encoding="utf-8",
    )

    api.write_autoinstall_custom_data(str(script_path), game_data)

    metadata_path = tmp_config_dir.parent / "data" / "PortProtonQt" / "custom_data"
    metadata_path = metadata_path / "Game" / "metadata.txt"
    assert metadata_path.exists()
    assert "name=Test Game" in metadata_path.read_text(encoding="utf-8")
    assert "description=English description" in metadata_path.read_text(encoding="utf-8")


def test_autoinstall_script_caches_cover_for_target_exe(
    tmp_config_dir: Path,
    tmp_path: Path,
) -> None:
    downloader = DummyDownloader()
    api = PortProtonAPI(downloader=cast(Any, downloader))
    game_data = {
        "name": "Cover Game",
        "description": "Description",
        "cover_path": "https://ppdb.linux-gaming.ru/covers/game_43.webp",
    }
    script_path = tmp_path / "game_43_test.ppai"
    script_path.write_text(
        'PW_EXE_FILE="$WINEPREFIX/drive_c/users/steamuser/AppData/Local/VKPlayLoader.exe"\n',
        encoding="utf-8",
    )

    api.write_autoinstall_custom_data(str(script_path), game_data)

    cover_path = tmp_config_dir.parent / "data" / "PortProtonQt" / "custom_data"
    cover_path = cover_path / "VKPlayLoader" / "cover.webp"
    assert cover_path.exists()
    assert downloader.downloads[0][1] == str(cover_path)
    assert downloader.downloads[0][0] == game_data["cover_path"]


def test_autoinstall_script_uses_cached_card_data(
    tmp_config_dir: Path,
    tmp_path: Path,
) -> None:
    api = PortProtonAPI(downloader=cast(Any, DummyDownloader()))
    game_data = {
        "name": "Cached Game",
        "description": "Cached description",
    }
    script_path = tmp_path / "game_44_test.ppai"
    script_path.write_text(
        'PW_EXE_FILE="$WINEPREFIX/drive_c/CachedLauncher.exe"\n',
        encoding="utf-8",
    )

    api.write_autoinstall_custom_data(str(script_path), game_data)

    metadata_path = tmp_config_dir.parent / "data" / "PortProtonQt" / "custom_data"
    metadata_path = metadata_path / "CachedLauncher" / "metadata.txt"
    assert metadata_path.exists()
    assert "name=Cached Game" in metadata_path.read_text(encoding="utf-8")


def test_autoinstall_refresh_clears_cached_ppdb_images(tmp_config_dir: Path) -> None:
    api = PortProtonAPI()
    image_dir = tmp_config_dir.parent / "cache" / "PortProtonQt" / "images"
    image_dir.mkdir(parents=True)
    compact_cache = image_dir / "43_compat.webp"
    full_cache = image_dir / "43.webp"
    unrelated_cache = image_dir / "999.webp"
    compact_cache.write_text("old compact", encoding="utf-8")
    full_cache.write_text("old full", encoding="utf-8")
    unrelated_cache.write_text("keep", encoding="utf-8")
    api._autoinstall_cache = [
        (
            "Game", "", "", "", "", "autoinstall:https://example/game_43.ppai",
            "Never", "0h 0m", "", "", 0, 0, "autoinstall", "game_43",
            "https://ppdb.linux-gaming.ru/covers/game_43_icon_abc.webp",
            "https://ppdb.linux-gaming.ru/covers/game_43_library_abc.webp",
        )
    ]

    api.clear_autoinstall_image_cache()

    assert not compact_cache.exists()
    assert not full_cache.exists()
    assert unrelated_cache.exists()
