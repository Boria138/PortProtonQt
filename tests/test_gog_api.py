from pathlib import Path
from unittest.mock import Mock

import orjson
import pytest

from portprotonqt.gog_api import GOGAPI, GOG_PRODUCT_LOCALES
from portprotonqt.localization import LOCALE_MAP


def test_default_games_directory_is_user_games_folder() -> None:
    api = GOGAPI()

    assert api.games_dir == Path.home() / "Games"


def test_extract_auth_code() -> None:
    url = "https://embed.gog.com/on_login_success?origin=client&code=test%20code"

    assert GOGAPI.extract_auth_code(url) == "test code"


def test_load_installed_uses_isolated_data_dir(tmp_path: Path) -> None:
    api = GOGAPI()
    api.installed_path = tmp_path / "installed.json"
    api.installed_path.write_bytes(orjson.dumps({"123": {"title": "Game"}}))

    assert api.load_installed() == {"123": {"title": "Game"}}


def test_remove_installed_game_keeps_other_records(tmp_path: Path) -> None:
    api = GOGAPI()
    api.installed_path = tmp_path / "installed.json"
    api.installed_path.write_bytes(orjson.dumps({"123": {}, "456": {}}))

    api.remove_installed_game("123")

    assert api.load_installed() == {"456": {}}


def test_get_launch_target_reads_primary_task(tmp_path: Path) -> None:
    api = GOGAPI()
    api.installed_path = tmp_path / "installed.json"
    game_dir = tmp_path / "game"
    executable = game_dir / "BIN/Game.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    api.installed_path.write_bytes(orjson.dumps({"123": {"install_path": str(game_dir)}}))
    info = {
        "playTasks": [{
            "type": "FileTask", "path": "bin\\game.exe",
            "arguments": '-conf "..\\game.conf"', "isPrimary": True,
        }]
    }
    (game_dir / "goggame-123.info").write_bytes(orjson.dumps(info))

    assert api.get_launch_target("123") == str(executable)

    api.ensure_launch_parameters("123")
    assert 'export LAUNCH_PARAMETERS="-conf ../game.conf"' in Path(
        f"{executable}.ppdb"
    ).read_text()


def test_is_game_installed_requires_gogdl_metadata(tmp_path: Path) -> None:
    api = GOGAPI()
    api.installed_path = tmp_path / "installed.json"
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    api.installed_path.write_bytes(orjson.dumps({"123": {"install_path": str(game_dir)}}))

    assert api.is_game_installed("123") is False

    (game_dir / "goggame-123.info").write_text("{}")
    assert api.is_game_installed("123") is True


def test_find_install_path_returns_gogdl_directory(tmp_path: Path) -> None:
    api = GOGAPI()
    game_dir = tmp_path / "Game created by gogdl"
    game_dir.mkdir()
    (game_dir / "goggame-123.info").write_text("{}")

    assert api.find_install_path("123", tmp_path) == game_dir


def test_is_game_installed_discovers_default_gogdl_directory(tmp_path: Path) -> None:
    api = GOGAPI()
    api.installed_path = tmp_path / "installed.json"
    api.games_dir = tmp_path / "games"
    game_dir = api.games_dir / "Game created by gogdl"
    game_dir.mkdir(parents=True)
    (game_dir / "goggame-123.info").write_text("{}")

    assert api.is_game_installed("123") is True


def test_localized_value_prefers_current_language(monkeypatch) -> None:
    monkeypatch.setattr("portprotonqt.gog_api.get_metadata_language", lambda: "ru")

    assert GOGAPI._localized_value({"*": "English", "ru-RU": "Русский"}) == "Русский"


def test_product_locales_cover_supported_languages() -> None:
    assert set(GOG_PRODUCT_LOCALES) == {language.lower() for language in LOCALE_MAP}


def test_parse_download_sizes_includes_language_data() -> None:
    output = (
        b'{"size":{"*":{"download_size":100,"disk_size":200},'
        b'"en-US":{"download_size":30,"disk_size":40}},'
        b'"languages":["en-US"]}'
    )

    assert GOGAPI.parse_download_sizes(output) == (130, 240)


def test_download_sizes_cache(tmp_path: Path) -> None:
    api = GOGAPI()
    api.sizes_path = tmp_path / "sizes.json"

    assert api.get_cached_download_sizes("123") is None
    api.save_download_sizes("123", (100, 200))

    assert api.get_cached_download_sizes("123") == (100, 200)


@pytest.mark.parametrize(
    ("lead", "expected"),
    [
        (
            "Description française.<br><br>Deuxième paragraphe.",
            "Description française.",
        ),
        (
            "<b>Avertissement.</b><br><br>Description.<br><br>Troisième paragraphe.",
            "<b>Avertissement.</b><br><br>Description.",
        ),
    ],
)
def test_get_game_loads_localized_product_description(
    monkeypatch: pytest.MonkeyPatch, lead: str, expected: str
) -> None:
    gamesdb_response = Mock()
    gamesdb_response.json.return_value = {
        "game": {
            "title": {"*": "Game"},
            "visible_in_library": True,
            "releases": [{"platform_id": "steam", "external_id": "358180"}],
        },
        "summary": {"*": "English description"},
    }
    product_response = Mock()
    product_response.json.return_value = {
        "description": {"lead": lead},
    }
    request = Mock(side_effect=[gamesdb_response, product_response])
    monkeypatch.setattr("portprotonqt.gog_api.get_metadata_language", lambda: "fr")
    monkeypatch.setattr("portprotonqt.gog_api.requests.get", request)

    game = GOGAPI()._get_game(
        {"platform_id": "gog", "external_id": "1207666073"}, "token"
    )

    assert game["description"] == expected
    assert game["steam_appid"] == "358180"
    assert request.call_args_list[1].kwargs["params"]["locale"] == "fr-FR"


def test_is_authenticated_requires_token_and_user_id(monkeypatch) -> None:
    api = GOGAPI()

    monkeypatch.setattr(api, "get_credentials", lambda: {"access_token": "token"})
    assert api.is_authenticated() is False

    monkeypatch.setattr(
        api, "get_credentials", lambda: {"access_token": "token", "user_id": "123"}
    )
    assert api.is_authenticated() is True


def test_ensure_gogdl_downloads_matching_architecture(tmp_path: Path, monkeypatch) -> None:
    api = GOGAPI()
    api.data_dir = tmp_path
    asset = {"name": "gogdl_linux_x86_64"}
    response = Mock()
    response.json.return_value = {"assets": [asset]}
    monkeypatch.setattr("portprotonqt.gog_api.platform.machine", lambda: "x86_64")
    monkeypatch.setattr("portprotonqt.gog_api.requests.get", lambda *args, **kwargs: response)
    monkeypatch.setattr(api, "_download_gogdl_asset", lambda selected: str(selected["name"]))

    assert api.ensure_gogdl() == "gogdl_linux_x86_64"


def test_authenticate_returns_gogdl_error(monkeypatch) -> None:
    api = GOGAPI()
    result = Mock(returncode=1, stdout=b"", stderr=b"authorization failed")
    monkeypatch.setattr(api, "ensure_gogdl", lambda: "/bin/gogdl")
    monkeypatch.setattr(api, "build_command", lambda arguments: ["gogdl", *arguments])
    monkeypatch.setattr("portprotonqt.gog_api.subprocess.run", lambda *args, **kwargs: result)

    assert api.authenticate("code") == (False, "authorization failed")
