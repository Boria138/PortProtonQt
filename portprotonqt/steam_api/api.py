"""Steam API functions for PortProtonQt."""

import os
import shlex
import urllib.parse
from collections.abc import Callable

import orjson
import requests

from portprotonqt.logger import get_logger
from portprotonqt.downloader import Downloader
from portprotonqt.localization import get_steam_language
from portprotonqt.steam_api.utils import decode_text
from portprotonqt.steam_api.cache import (
    CACHE_DURATION,
    load_app_details,
    save_app_details,
    get_cache_dir,
    load_steam_apps_async,
    build_index,
    search_app,
    load_weanticheatyet_data_async,
    build_weanticheatyet_index,
    search_anticheat_status,
    CacheManager,
    load_protondb_status,
    save_protondb_status,
)

logger = get_logger(__name__)
downloader = Downloader()

_STEAM_APPS_CACHE = CacheManager("steam_apps")
_ANTICHEAT_CACHE = CacheManager("anticheat")


def fetch_sgdb_cover_async(game_name: str, callback: Callable[[str], None]) -> None:
    """Asynchronously fetch cover image URL from steamgrid.usebottles.com."""
    encoded = urllib.parse.quote(game_name)
    url = f"https://steamgrid.usebottles.com/api/search/{encoded}"

    def process_response(result: str | None) -> None:
        if not result or not os.path.exists(result):
            logger.warning("Failed to download SGDB data for %s", game_name)
            callback("")
            return
        try:
            with open(result, encoding="utf-8") as f:
                text = f.read().strip()
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            if text:
                logger.debug("Got SGDB cover URL for %s: %s", game_name, text)
            callback(text)
        except Exception as e:
            logger.warning("Failed to process SGDB data for %s: %s", game_name, e)
            callback("")

    cache_dir = get_cache_dir()
    safe_name = "".join(c for c in game_name if c.isalnum() or c in " -_")[:50]
    cache_file = os.path.join(cache_dir, f"sgdb_{safe_name}.json")
    downloader.download_async(url, cache_file, timeout=10, callback=process_response)


def check_url_exists_async(url: str, callback: Callable[[bool], None]) -> None:
    """Asynchronously check whether a URL returns HTTP 200 using HEAD request."""
    import threading

    def head_request():
        try:
            r = requests.head(url, timeout=5)
            callback(r.status_code == 200)
        except requests.exceptions.Timeout:
            logger.warning(f"URL check timed out for: {url}")
            callback(False)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error when checking URL {url}: {e}")
            callback(False)
        except Exception as e:
            logger.warning(f"Unexpected error when checking URL {url}: {e}")
            callback(False)

    thread = threading.Thread(target=head_request, daemon=True)
    thread.start()


def check_local_cover_cache(url: str) -> bool:
    """Check if cover exists in local cache."""
    if not url or not url.startswith("https://steamcdn-a.akamaihd.net/steam/apps/"):
        return False

    try:
        parts = url.split("/")
        appid = None
        if "apps" in parts:
            idx = parts.index("apps")
            if idx + 1 < len(parts):
                appid = parts[idx + 1]
        if not appid:
            return False

        xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
        image_folder = os.path.join(xdg_cache_home, "PortProtonQt", "images")
        local_path = os.path.join(image_folder, f"{appid}.jpg")
        return os.path.exists(local_path)
    except Exception as e:
        logger.warning(f"Error checking local cover cache: {e}")
        return False


def fetch_app_info_async(app_id: int, callback: Callable[[dict | None], None]) -> None:
    """Asynchronously fetch detailed app info from Steam API."""
    cached = load_app_details(app_id)
    if cached is not None:
        callback(cached)
        return

    lang = get_steam_language()
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l={lang}"

    def process_response(result: str | None) -> None:
        if not result or not os.path.exists(result):
            logger.error("Failed to download Steam app info for appid %s", app_id)
            callback(None)
            return
        try:
            with open(result, "rb") as f:
                data = orjson.loads(f.read())
            details = data.get(str(app_id), {})
            if not details.get("success"):
                callback(None)
                return
            app_data_full = details.get("data", {})
            app_data = {
                "steam_appid": app_data_full.get("steam_appid", app_id),
                "name": app_data_full.get("name", ""),
                "short_description": app_data_full.get("short_description", ""),
                "controller_support": app_data_full.get("controller_support", "")
            }
            save_app_details(app_id, app_data)
            callback(app_data)
        except Exception as e:
            logger.error("Failed to process Steam app info for appid %s: %s", app_id, e)
            callback(None)

    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    downloader.download_async(url, cache_file, timeout=5, callback=process_response)


def get_protondb_tier_async(appid: int, callback: Callable[[str], None]) -> None:
    """Asynchronously fetch ProtonDB tier for an app."""
    cached = load_protondb_status(appid)
    if cached is not None:
        callback(cached.get("tier", ""))
        return

    url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"

    def process_response(result: str | None) -> None:
        if not result or not os.path.exists(result):
            logger.info("Failed to download ProtonDB data for appid %s", appid)
            callback("")
            return
        try:
            with open(result, "rb") as f:
                data = orjson.loads(f.read())
            filtered_data = {"tier": data.get("tier", "")}
            save_protondb_status(appid, filtered_data)
            callback(filtered_data["tier"])
        except Exception as e:
            logger.info("Failed to process ProtonDB data for appid %s: %s", appid, e)
            callback("")

    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    downloader.download_async(url, cache_file, timeout=5, callback=process_response)


def get_steam_apps_and_index_async(
    callback: Callable[[tuple[list | None, dict | None]], None]
) -> None:
    """Asynchronously load and cache Steam apps and their index."""
    _STEAM_APPS_CACHE.get_data_and_index_async(
        load_steam_apps_async,
        build_index,
        callback,
        CACHE_DURATION
    )


def get_anticheat_data_and_index_async(
    callback: Callable[[tuple[list | None, dict | None]], None]
) -> None:
    """Asynchronously load and cache anti-cheat data and their index."""
    _ANTICHEAT_CACHE.get_data_and_index_async(
        load_weanticheatyet_data_async,
        build_weanticheatyet_index,
        callback,
        CACHE_DURATION
    )


def get_weanticheatyet_status_async(game_name: str, callback: Callable[[str], None]) -> None:
    """Asynchronously retrieve WeAntiCheatYet status for a game by name."""
    def on_anticheat_data_and_index(
        data_and_index: tuple[list | None, dict | None]
    ) -> None:
        anti_cheat_data, anti_cheat_index = data_and_index
        if anti_cheat_data and anti_cheat_index:
            status = search_anticheat_status(game_name, anti_cheat_index)
        else:
            status = ""
        callback(status)

    get_anticheat_data_and_index_async(on_anticheat_data_and_index)


def clear_steam_api_caches() -> None:
    """Clear all cached data to force reload from files."""
    _STEAM_APPS_CACHE.clear()
    _ANTICHEAT_CACHE.clear()
    logger.info("Cleared Steam API caches")


def _build_game_info_result(
    appid: str | int,
    name: str,
    description: str,
    cover: str,
    controller_support: str,
    protondb_tier: str,
    steam_game: str,
    anticheat_status: str,
) -> dict:
    """Build game info result dictionary."""
    return {
        "appid": appid,
        "name": name,
        "description": description,
        "cover": cover,
        "controller_support": controller_support,
        "protondb_tier": protondb_tier,
        "steam_game": steam_game,
        "anticheat_status": anticheat_status,
    }


def get_full_steam_game_info_async(appid: int, callback: Callable[[dict], None]) -> None:
    """Asynchronously retrieve full Steam game info, including WeAntiCheatYet status."""
    def on_app_info(app_info: dict | None) -> None:
        if not app_info:
            callback({})
            return
        title = decode_text(app_info.get("name", ""))
        description = decode_text(app_info.get("short_description", ""))
        cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"

        def on_url_checked(exists: bool) -> None:
            if not exists:
                logger.info("Steam cover not found for %s, trying SGDB", title)

                def on_sgdb_cover(alt_cover: str) -> None:
                    if alt_cover:
                        nonlocal cover
                        cover = alt_cover

                    def on_protondb_tier(tier: str) -> None:
                        def on_anticheat_status(anticheat_status: str) -> None:
                            result = _build_game_info_result(
                                appid=appid,
                                name=title,
                                description=description,
                                cover=cover,
                                controller_support=app_info.get('controller_support', ''),
                                protondb_tier=tier,
                                steam_game="true",
                                anticheat_status=anticheat_status,
                            )
                            callback(result)

                        get_weanticheatyet_status_async(title, on_anticheat_status)

                    get_protondb_tier_async(appid, on_protondb_tier)

                fetch_sgdb_cover_async(title, on_sgdb_cover)
            else:
                def on_protondb_tier_direct(tier: str) -> None:
                    def on_anticheat_status_direct(anticheat_status: str) -> None:
                        result = _build_game_info_result(
                            appid=appid,
                            name=title,
                            description=description,
                            cover=cover,
                            controller_support=app_info.get('controller_support', ''),
                            protondb_tier=tier,
                            steam_game="true",
                            anticheat_status=anticheat_status,
                        )
                        callback(result)

                    get_weanticheatyet_status_async(title, on_anticheat_status_direct)

                get_protondb_tier_async(appid, on_protondb_tier_direct)

        if check_local_cover_cache(cover):
            on_url_checked(True)
        else:
            check_url_exists_async(cover, on_url_checked)

    fetch_app_info_async(appid, on_app_info)


def get_steam_game_info_async(
    desktop_name: str,
    exec_line: str,
    callback: Callable[[dict], None]
) -> None:
    """Asynchronously retrieve game info based on desktop name and exec line."""
    from portprotonqt.steam_api.cache import get_exiftool_data
    from portprotonqt.steam_api.utils import filter_candidates, remove_duplicates

    parts = shlex.split(exec_line)
    game_exe = parts[-1] if parts else exec_line

    if game_exe.lower().endswith('.bat'):
        if os.path.exists(game_exe):
            try:
                with open(game_exe, encoding='utf-8') as f:
                    bat_lines = f.readlines()
                for line in bat_lines:
                    line = line.strip()
                    if '.exe' in line.lower():
                        tokens = shlex.split(line)
                        for token in tokens:
                            if token.lower().endswith('.exe'):
                                game_exe = token
                                break
                        if game_exe.lower().endswith('.exe'):
                            break
            except Exception as e:
                logger.error("Failed to process bat file %s: %s", game_exe, e)
        else:
            logger.error("Bat file not found: %s", game_exe)

    if not game_exe.lower().endswith('.exe'):
        logger.error("Invalid executable path: %s. Expected .exe", game_exe)
        meta_data = {}
    else:
        meta_data = get_exiftool_data(game_exe)

    exe_name = os.path.splitext(os.path.basename(game_exe))[0]
    folder_path = os.path.dirname(game_exe)
    folder_name = os.path.basename(folder_path)
    if folder_name.lower() in ['bin', 'binaries']:
        folder_path = os.path.dirname(folder_path)
        folder_name = os.path.basename(folder_path)
    logger.info("Game folder name: '%s'", folder_name)

    candidates = []
    product_name = meta_data.get("ProductName", "")
    file_description = meta_data.get("FileDescription", "")
    if product_name and product_name not in ['BootstrapPackagedGame']:
        candidates.append(product_name)
    if file_description and file_description not in ['BootstrapPackagedGame']:
        candidates.append(file_description)
    if desktop_name:
        candidates.append(desktop_name)
    if exe_name:
        candidates.append(exe_name)
    if folder_name:
        candidates.append(folder_name)
    logger.info("Initial candidates: %s", candidates)
    candidates = filter_candidates(candidates)
    candidates = remove_duplicates(candidates)
    candidates_ordered = sorted(candidates, key=lambda s: len(s.split()), reverse=True)
    logger.info("Sorted candidates: %s", candidates_ordered)

    def on_steam_apps_and_index(
        data_and_index: tuple[list | None, dict | None]
    ) -> None:
        steam_apps, steam_apps_index = data_and_index
        matching_app = None

        if not steam_apps or not steam_apps_index:
            game_name = desktop_name or exe_name

            def on_sgdb_cover_failure(cover: str) -> None:
                result = _build_game_info_result(
                    appid="",
                    name=decode_text(game_name),
                    description="",
                    cover=cover,
                    controller_support="",
                    protondb_tier="",
                    steam_game="false",
                    anticheat_status="",
                )

                def on_anticheat_status_failure(anticheat_status: str) -> None:
                    result["anticheat_status"] = anticheat_status
                    callback(result)

                get_weanticheatyet_status_async(game_name, on_anticheat_status_failure)

            fetch_sgdb_cover_async(game_name, on_sgdb_cover_failure)
            return

        for candidate in candidates_ordered:
            if not candidate:
                continue
            matching_app = search_app(candidate, steam_apps_index)
            if matching_app:
                logger.info("Match found for candidate '%s': %s", candidate, matching_app.get("normalized_name"))
                break

        game_name = desktop_name or exe_name.capitalize()

        if not matching_app:
            def on_sgdb_cover_non_steam(cover: str) -> None:
                logger.debug("Using SGDB cover URL for non-Steam game '%s': %s", game_name, cover)

                def on_anticheat_status_non_steam(anticheat_status: str) -> None:
                    result = _build_game_info_result(
                        appid="",
                        name=decode_text(game_name),
                        description="",
                        cover=cover,
                        controller_support="",
                        protondb_tier="",
                        steam_game="false",
                        anticheat_status=anticheat_status,
                    )
                    callback(result)

                get_weanticheatyet_status_async(game_name, on_anticheat_status_non_steam)

            fetch_sgdb_cover_async(game_name, on_sgdb_cover_non_steam)
            return

        appid = matching_app["appid"]

        def on_app_info(app_info: dict | None) -> None:
            if not app_info:
                def on_anticheat_status_no_info(anticheat_status: str) -> None:
                    result = _build_game_info_result(
                        appid="",
                        name=decode_text(game_name),
                        description="",
                        cover="",
                        controller_support="",
                        protondb_tier="",
                        steam_game="false",
                        anticheat_status=anticheat_status,
                    )
                    callback(result)

                get_weanticheatyet_status_async(game_name, on_anticheat_status_no_info)
                return

            title = decode_text(app_info.get("name", game_name))
            description = decode_text(app_info.get("short_description", ""))
            cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"

            def on_url_checked_final(exists: bool) -> None:
                if not exists:
                    logger.info("Steam cover not found for %s, trying SGDB", title)

                    def on_sgdb_cover_final(alt_cover: str) -> None:
                        nonlocal cover
                        if alt_cover:
                            cover = alt_cover
                        controller_support = app_info.get("controller_support", "")

                        def on_protondb_tier(tier: str) -> None:
                            def on_anticheat_status_final(anticheat_status: str) -> None:
                                result = _build_game_info_result(
                                    appid=appid,
                                    name=title,
                                    description=description,
                                    cover=cover,
                                    controller_support=controller_support,
                                    protondb_tier=tier,
                                    steam_game="true",
                                    anticheat_status=anticheat_status,
                                )
                                callback(result)

                            get_weanticheatyet_status_async(title, on_anticheat_status_final)

                        get_protondb_tier_async(appid, on_protondb_tier)

                    fetch_sgdb_cover_async(title, on_sgdb_cover_final)
                else:
                    controller_support = app_info.get("controller_support", "")

                    def on_protondb_tier(tier: str) -> None:
                        def on_anticheat_status_final(anticheat_status: str) -> None:
                            result = _build_game_info_result(
                                appid=appid,
                                name=title,
                                description=description,
                                cover=cover,
                                controller_support=controller_support,
                                protondb_tier=tier,
                                steam_game="true",
                                anticheat_status=anticheat_status,
                            )
                            callback(result)

                        get_weanticheatyet_status_async(title, on_anticheat_status_final)

                    get_protondb_tier_async(appid, on_protondb_tier)

            if check_local_cover_cache(cover):
                on_url_checked_final(True)
            else:
                check_url_exists_async(cover, on_url_checked_final)

        fetch_app_info_async(appid, on_app_info)

    get_steam_apps_and_index_async(on_steam_apps_and_index)
