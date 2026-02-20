import re
import requests
import requests.exceptions
import threading
import orjson
from pathlib import Path
import time
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from portprotonqt.localization import get_egs_language, _
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import load_pixmap_async
from portprotonqt.time_utils import parse_playtime_file, format_playtime, get_last_launch, get_last_launch_timestamp
from portprotonqt.config_utils import get_portproton_location, get_portproton_start_command
from portprotonqt.steam_api import (
    get_weanticheatyet_status_async, get_steam_apps_and_index_async, get_protondb_tier_async,
    search_app, get_steam_home, get_last_steam_user, convert_steam_id, generate_thumbnail, call_steam_api
)
import vdf
import shutil
import zlib
from portprotonqt.downloader import Downloader
from PySide6.QtGui import QPixmap
import base64

logger = get_logger(__name__)
downloader = Downloader()

def read_installed_json(legendary_config_path: str) -> dict | None:
    """Read installed.json and return dictionary with data or None on error."""
    installed_json_path = os.path.join(legendary_config_path, "installed.json")
    try:
        with open(installed_json_path, "rb") as f:
            return orjson.loads(f.read())
    except FileNotFoundError:
        logger.error(f"installed.json not found at {installed_json_path}")
        return None
    except orjson.JSONDecodeError:
        logger.error(f"Invalid JSON in {installed_json_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading installed.json: {e}")
        return None

def get_egs_executable(app_name: str, legendary_config_path: str) -> str | None:
    """Get path to EGS game executable from installed.json."""
    installed_data = read_installed_json(legendary_config_path)
    if installed_data is None or app_name not in installed_data:
        return None
    install_path = installed_data[app_name].get("install_path", "").decode('utf-8') if isinstance(installed_data[app_name].get("install_path"), bytes) else installed_data[app_name].get("install_path", "")
    executable = installed_data[app_name].get("executable", "").decode('utf-8') if isinstance(installed_data[app_name].get("executable"), bytes) else installed_data[app_name].get("executable", "")
    if install_path and executable:
        return os.path.join(install_path, executable)
    return None

def get_cache_dir() -> Path:
    """Returns the path to the cache directory, creating it if necessary."""
    xdg_cache_home = os.getenv(
        "XDG_CACHE_HOME",
        os.path.join(os.path.expanduser("~"), ".cache")
    )
    cache_dir = Path(xdg_cache_home) / "PortProtonQt"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def remove_egs_from_steam(game_name: str, portproton_dir: str, callback: Callable[[tuple[bool, str]], None]) -> None:
    """
    Removes an EGS game from Steam using CEF API or by modifying shortcuts.vdf and deleting the launch script.
    Also deletes associated cover files in the Steam grid directory.
    Calls the callback with (success, message).

    Args:
        game_name: The display name of the game.
        portproton_dir: Path to the PortProton directory.
        callback: Callback function to handle the result (success, message).
    """

    if not portproton_dir:
        logger.error("PortProton directory not found")
        callback((False, "PortProton directory not found"))
        return

    steam_scripts_dir = os.path.join(portproton_dir, "steam_scripts")
    safe_game_name = re.sub(r'[<>:"/\\|?*]', '_', game_name.strip())
    script_path = os.path.join(steam_scripts_dir, f"{safe_game_name}_egs.sh")
    quoted_script_path = f'"{script_path}"'

    steam_home = get_steam_home()
    if not steam_home:
        logger.error("Steam directory not found")
        callback((False, "Steam directory not found"))
        return

    last_user = get_last_steam_user(steam_home)
    if not last_user or 'SteamID' not in last_user:
        logger.error("Failed to retrieve Steam user ID")
        callback((False, "Failed to get Steam user ID"))
        return

    userdata_dir = os.path.join(steam_home, "userdata")
    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = os.path.join(userdata_dir, str(unsigned_id))
    steam_shortcuts_path = os.path.join(user_dir, "config", "shortcuts.vdf")
    grid_dir = os.path.join(user_dir, "config", "grid")

    if not os.path.exists(steam_shortcuts_path):
        logger.error("Steam shortcuts file not found")
        callback((False, "Steam shortcuts file not found"))
        return

    # Find appid for the shortcut
    try:
        with open(steam_shortcuts_path, 'rb') as f:
            shortcuts_data = vdf.binary_load(f)
        shortcuts = shortcuts_data.get("shortcuts", {})
        appid = None
        for _key, entry in shortcuts.items():
            if entry.get("AppName") == game_name and entry.get("Exe") == quoted_script_path:
                appid = convert_steam_id(int(entry.get("appid")))
                logger.info(f"Found matching shortcut for '{game_name}' with AppID {appid}")
                break
        if not appid:
            logger.info(f"Game '{game_name}' not found in Steam shortcuts")
            callback((False, f"Game '{game_name}' not found in Steam"))
            return
    except Exception as e:
        logger.error(f"Failed to load shortcuts.vdf: {e}")
        callback((False, f"Failed to load shortcuts.vdf: {e}"))
        return

    # Try CEF API first
    logger.info(f"Attempting to remove EGS game '{game_name}' via Steam CEF API with AppID {appid}")
    api_response = call_steam_api("removeShortcut", appid)
    if api_response is not None:  # API responded, even if empty
        logger.info(f"Shortcut for AppID {appid} successfully removed via CEF API")

        # Delete cover files
        cover_files = [
            os.path.join(grid_dir, f"{appid}.jpg"),
            os.path.join(grid_dir, f"{appid}p.jpg"),
            os.path.join(grid_dir, f"{appid}_hero.jpg"),
            os.path.join(grid_dir, f"{appid}_logo.png")
        ]
        for cover_file in cover_files:
            if os.path.exists(cover_file):
                try:
                    os.remove(cover_file)
                    logger.info(f"Deleted cover file: {cover_file}")
                except Exception as e:
                    logger.error(f"Failed to delete cover file {cover_file}: {e}")

        # Delete launch script
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
                logger.info(f"Removed EGS script: {script_path}")
            except OSError as e:
                logger.warning(f"Failed to remove EGS script '{script_path}': {str(e)}")

        callback((True, f"Game '{game_name}' was removed from Steam. Please restart Steam for changes to take effect."))
        return

    # Fallback to VDF modification
    logger.warning("CEF API failed for EGS game removal; falling back to VDF modification")
    backup_path = f"{steam_shortcuts_path}.backup"
    try:
        shutil.copy2(steam_shortcuts_path, backup_path)
        logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup of shortcuts.vdf: {e}")
        callback((False, f"Failed to create backup of shortcuts.vdf: {e}"))
        return

    try:
        new_shortcuts = {}
        index = 0
        for _key, entry in shortcuts.items():
            if entry.get("AppName") == game_name and entry.get("Exe") == quoted_script_path:
                logger.info(f"Removing EGS game '{game_name}' from Steam shortcuts")
                continue
            new_shortcuts[str(index)] = entry
            index += 1

        with open(steam_shortcuts_path, 'wb') as f:
            vdf.binary_dump({"shortcuts": new_shortcuts}, f)
        logger.info(f"Updated shortcuts.vdf, removed '{game_name}'")
    except Exception as e:
        logger.error(f"Failed to update shortcuts.vdf: {e}")
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, steam_shortcuts_path)
                logger.info("Restored shortcuts.vdf from backup")
            except Exception as restore_err:
                logger.error(f"Failed to restore shortcuts.vdf: {restore_err}")
        callback((False, f"Failed to update shortcuts.vdf: {e}"))
        return

    # Delete cover files
    cover_files = [
        os.path.join(grid_dir, f"{appid}.jpg"),
        os.path.join(grid_dir, f"{appid}p.jpg"),
        os.path.join(grid_dir, f"{appid}_hero.jpg"),
        os.path.join(grid_dir, f"{appid}_logo.png")
    ]
    for cover_file in cover_files:
        if os.path.exists(cover_file):
            try:
                os.remove(cover_file)
                logger.info(f"Deleted cover file: {cover_file}")
            except Exception as e:
                logger.error(f"Failed to delete cover file {cover_file}: {e}")

    # Delete launch script
    if os.path.exists(script_path):
        try:
            os.remove(script_path)
            logger.info(f"Removed EGS script: {script_path}")
        except OSError as e:
            logger.warning(f"Failed to remove EGS script '{script_path}': {str(e)}")

    callback((True, f"Game '{game_name}' was removed from Steam. Please restart Steam for changes to take effect."))

def add_egs_to_steam(app_name: str, game_title: str, legendary_path: str, callback: Callable[[tuple[bool, str]], None]) -> None:
    """
    Asynchronously adds an EGS game to Steam via CEF API or shortcuts.vdf with PortProton tag.
    Creates a launch script using legendary CLI with --no-wine and PortProton wrapper.
    Wrapper is flatpak run if portproton_location is None or contains .var, otherwise start.sh.
    Downloads Steam Grid covers if the game exists in Steam, and generates a thumbnail.
    Calls the callback with (success, message).

    Args:
        app_name: The Legendary app_name (unique identifier for the game).
        game_title: The display name of the game.
        legendary_path: Path to the Legendary CLI executable.
        callback: Callback function to handle the result (success, message).
    """
    if not app_name or not app_name.strip() or not game_title or not game_title.strip():
        logger.error("Invalid app_name or game_title: empty or whitespace")
        callback((False, "Game name or app name is empty or invalid"))
        return

    if not os.path.exists(legendary_path):
        logger.error(f"Legendary executable not found: {legendary_path}")
        callback((False, f"Legendary executable not found: {legendary_path}"))
        return

    portproton_dir = get_portproton_location()
    if not portproton_dir:
        logger.error("PortProton directory not found")
        callback((False, "PortProton directory not found"))
        return

    # Determine wrapper
    wrapper = get_portproton_start_command()

    # Create launch script
    steam_scripts_dir = os.path.join(portproton_dir, "steam_scripts")
    os.makedirs(steam_scripts_dir, exist_ok=True)
    safe_game_name = re.sub(r'[<>:"/\\|?*]', '_', game_title.strip())
    script_path = os.path.join(steam_scripts_dir, f"{safe_game_name}_egs.sh")
    legendary_config_path = os.path.dirname(legendary_path)

    script_content = f"""#!/usr/bin/env bash
export LD_PRELOAD=
export LEGENDARY_CONFIG_PATH="{legendary_config_path}"
"{legendary_path}" launch {app_name} --no-wine --wrapper "env START_FROM_STEAM=1 {wrapper}" "$@"
"""
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        logger.info(f"Created launch script for EGS game: {script_path}")
    except Exception as e:
        logger.error(f"Failed to create launch script {script_path}: {e}")
        callback((False, f"Failed to create launch script: {e}"))
        return

    # Generate thumbnail
    generated_icon_path = os.path.join(portproton_dir, "data", "img", f"{safe_game_name}_egs.png")
    try:
        img_dir = os.path.join(portproton_dir, "data", "img")
        os.makedirs(img_dir, exist_ok=True)
        game_exe = get_egs_executable(app_name, legendary_config_path)
        if not game_exe or not os.path.exists(game_exe):
            logger.warning(f"Executable not found for {app_name}, skipping thumbnail generation")
            icon_path = ""
        elif os.path.exists(generated_icon_path):
            logger.info(f"Reusing existing thumbnail: {generated_icon_path}")
            icon_path = generated_icon_path
        else:
            success = generate_thumbnail(game_exe, generated_icon_path, size=128, force_resize=True)
            if not success or not os.path.exists(generated_icon_path):
                logger.warning(f"generate_thumbnail failed for {game_exe}")
                icon_path = ""
            else:
                logger.info(f"Generated thumbnail: {generated_icon_path}")
                icon_path = generated_icon_path
    except Exception as e:
        logger.error(f"Error generating thumbnail for {app_name}: {e}")
        icon_path = ""

    # Get Steam directories
    steam_home = get_steam_home()
    if not steam_home:
        logger.error("Steam home directory not found")
        callback((False, "Steam directory not found"))
        return

    last_user = get_last_steam_user(steam_home)
    if not last_user or 'SteamID' not in last_user:
        logger.error("Failed to retrieve Steam user ID")
        callback((False, "Failed to get Steam user ID"))
        return

    userdata_dir = steam_home / "userdata"
    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(unsigned_id)
    steam_shortcuts_path = user_dir / "config" / "shortcuts.vdf"
    grid_dir = user_dir / "config" / "grid"
    os.makedirs(grid_dir, exist_ok=True)

    # Try CEF API first
    logger.info(f"Attempting to add EGS game '{game_title}' via Steam CEF API")
    api_response = call_steam_api(
        "createShortcut",
        game_title,
        script_path,
        str(Path(script_path).parent),
        icon_path,
        ""
    )

    appid = None
    was_api_used = False

    if api_response and isinstance(api_response, dict) and 'id' in api_response:
        appid = api_response['id']
        was_api_used = True
        logger.info(f"EGS game '{game_title}' successfully added via CEF API. AppID: {appid}")
    else:
        logger.warning("CEF API failed for EGS game addition; falling back to VDF modification")
        # Backup shortcuts.vdf
        backup_path = f"{steam_shortcuts_path}.backup"
        if os.path.exists(steam_shortcuts_path):
            try:
                shutil.copy2(steam_shortcuts_path, backup_path)
                logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
            except Exception as e:
                logger.error(f"Failed to create backup of shortcuts.vdf: {e}")
                callback((False, f"Failed to create backup of shortcuts.vdf: {e}"))
                return

        # Generate unique appid
        unique_string = f"{script_path}{game_title}"
        baseid = zlib.crc32(unique_string.encode('utf-8')) & 0xffffffff
        appid = baseid | 0x80000000
        if appid > 0x7FFFFFFF:
            aidvdf = appid - 0x100000000
        else:
            aidvdf = appid

        # Create shortcut entry
        shortcut = {
            "appid": aidvdf,
            "AppName": game_title,
            "Exe": f'"{script_path}"',
            "StartDir": f'"{os.path.dirname(script_path)}"',
            "icon": icon_path,
            "LaunchOptions": "",
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "openvr": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "LastPlayTime": 0,
            "tags": {'0': 'PortProton'}
        }
        logger.info(f"Shortcut entry for EGS game: {shortcut}")

        try:
            if not os.path.exists(steam_shortcuts_path):
                os.makedirs(os.path.dirname(steam_shortcuts_path), exist_ok=True)
                open(steam_shortcuts_path, 'wb').close()

            try:
                if os.path.getsize(steam_shortcuts_path) > 0:
                    with open(steam_shortcuts_path, 'rb') as f:
                        shortcuts_data = vdf.binary_load(f)
                else:
                    shortcuts_data = {"shortcuts": {}}
            except Exception as load_err:
                logger.warning(f"Failed to load shortcuts.vdf, starting fresh: {load_err}")
                shortcuts_data = {"shortcuts": {}}

            shortcuts = shortcuts_data.get("shortcuts", {})
            for _key, entry in shortcuts.items():
                if entry.get("AppName") == game_title and entry.get("Exe") == f'"{script_path}"':
                    logger.info(f"EGS game '{game_title}' already exists in Steam shortcuts")
                    callback((False, f"Game '{game_title}' already exists in Steam"))
                    return

            new_index = str(len(shortcuts))
            shortcuts[new_index] = shortcut

            with open(steam_shortcuts_path, 'wb') as f:
                vdf.binary_dump({"shortcuts": shortcuts}, f)
            logger.info(f"EGS game '{game_title}' added to Steam via VDF")
        except Exception as e:
            logger.error(f"Failed to update shortcuts.vdf: {e}")
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, steam_shortcuts_path)
                    logger.info("Restored shortcuts.vdf from backup")
                except Exception as restore_err:
                    logger.error(f"Failed to restore shortcuts.vdf: {restore_err}")
            callback((False, f"Failed to update shortcuts.vdf: {e}"))
            return

    if not appid:
        callback((False, "Failed to create shortcut via any method"))
        return

    steam_appid = None
    downloaded_count = 0
    total_covers = 4
    download_lock = threading.Lock()

    def on_cover_download(cover_file: str | None, cover_type: str, index: int):
        nonlocal downloaded_count
        try:
            if cover_file is None or not os.path.exists(cover_file):
                logger.warning(f"Failed to download cover {cover_type} for appid {steam_appid}")
                with download_lock:
                    downloaded_count += 1
                    if downloaded_count == total_covers:
                        callback((True, f"Game '{game_title}' added to Steam with covers"))
                return

            logger.info(f"Downloaded cover {cover_type} to {cover_file}")
            if was_api_used:
                try:
                    with open(cover_file, 'rb') as f:
                        img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    logger.info(f"Applying cover type '{cover_type}' via API for AppID {appid}")
                    ext = Path(cover_type).suffix.lstrip('.')
                    call_steam_api("setGrid", appid, index, ext, img_b64)
                except Exception as e:
                    logger.error(f"Error applying cover '{cover_type}' via API: {e}")
        except Exception as e:
            logger.error(f"Error processing cover {cover_type} for appid {steam_appid}: {e}")
        with download_lock:
            downloaded_count += 1
            if downloaded_count == total_covers:
                callback((True, f"Game '{game_title}' added to Steam with covers"))

    def on_steam_apps(steam_data: tuple[list | None, dict | None]):
        nonlocal steam_appid
        steam_apps, steam_apps_index = steam_data
        if not steam_apps or not steam_apps_index:
            logger.info(f"No Steam data available for EGS game {game_title}, skipping cover download")
            callback((True, f"Game '{game_title}' added to Steam"))
            return
        matching_app = search_app(game_title, steam_apps_index)
        steam_appid = matching_app.get("appid") if matching_app else None

        if not steam_appid:
            logger.info(f"No Steam appid found for EGS game {game_title}, skipping cover download")
            callback((True, f"Game '{game_title}' added to Steam"))
            return

        cover_types = [
            (".jpg", "header.jpg", 0),
            ("p.jpg", "library_600x900_2x.jpg", 1),
            ("_hero.jpg", "library_hero.jpg", 2),
            ("_logo.png", "logo.png", 3)
        ]

        for suffix, cover_type, index in cover_types:
            cover_file = os.path.join(grid_dir, f"{appid}{suffix}")
            cover_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_appid}/{cover_type}"
            downloader.download_async(
                cover_url,
                cover_file,
                timeout=5,
                callback=lambda result, ctype=cover_type, idx=index: on_cover_download(result, ctype, idx)
            )

    get_steam_apps_and_index_async(on_steam_apps)

def get_egs_game_description_async(
    app_name: str,
    callback: Callable[[str], None],
    namespace: str | None = None,
    cache_ttl: int = 3600
) -> None:
    """
    Asynchronously fetches the game description from the Epic Games Store API.
    Prioritizes GraphQL API with namespace for slug and description.
    Falls back to legacy API if GraphQL provides a slug but no description.
    Caches results in ~/.cache/PortProtonQt/egs_app_{app_name}.json.
    Handles DNS resolution failures gracefully.
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / f"egs_app_{app_name.lower().replace(':', '_').replace(' ', '_')}.json"

    # Check cache
    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                content = f.read()
            cached_entry = orjson.loads(content)
            if not isinstance(cached_entry, dict):
                logger.warning(
                    "Invalid cache format in %s: expected dict, got %s",
                    cache_file,
                    type(cached_entry)
                )
                cache_file.unlink(missing_ok=True)
            else:
                cached_time = cached_entry.get("timestamp", 0)
                if time.time() - cached_time < cache_ttl:
                    description = cached_entry.get("description", "")
                    logger.debug(
                        "Using cached description for %s: %s",
                        app_name,
                        (description[:100] + "...") if len(description) > 100 else description
                    )
                    callback(description)
                    return
        except orjson.JSONDecodeError as e:
            logger.warning(
                "Failed to parse description cache for %s: %s",
                app_name,
                str(e)
            )
            cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(
                "Unexpected error reading description cache for %s: %s",
                app_name,
                str(e)
            )
            cache_file.unlink(missing_ok=True)

    lang = get_egs_language()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) EpicGamesLauncher"
    }

    def slug_from_title(title: str) -> str:
        """Derives a slug from the game title, preserving numbers and handling special characters."""
        # Keep letters, numbers, and spaces; replace spaces with hyphens
        cleaned = re.sub(r'[^a-z0-9 ]', '', title.lower()).strip()
        return re.sub(r'\s+', '-', cleaned)


    def fetch_legacy_description(url: str) -> str:
        """Fetches description from the legacy API, handling DNS failures."""
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = orjson.loads(response.content)
            if not isinstance(data, dict):
                logger.warning("Invalid JSON structure for %s in legacy API: %s", app_name, type(data))
                return ""
            pages = data.get("pages", [])
            if pages:
                for page in pages:
                    if page.get("type") == "productHome":
                        return page.get("data", {}).get("about", {}).get("shortDescription", "")
                return pages[0].get("data", {}).get("about", {}).get("shortDescription", "")
            return ""
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.info("Legacy API returned 404 for %s", app_name)
            else:
                logger.warning("HTTP error in legacy API for %s: %s", app_name, str(e))
            return ""
        except requests.exceptions.ConnectionError as e:
            logger.error("DNS resolution failed for legacy API %s: %s", url, str(e))
            return ""
        except requests.exceptions.Timeout:
            logger.warning("Request timeout for legacy API %s", url)
            return ""
        except requests.RequestException as e:
            logger.warning("Failed to fetch legacy API for %s: %s", app_name, str(e))
            return ""
        except orjson.JSONDecodeError:
            logger.warning("Invalid JSON response for %s in legacy API", app_name)
            return ""

    def fetch_graphql_description(namespace: str | None, locale: str) -> tuple[str, str]:
        """Fetches description and slug from GraphQL API using namespace or title."""
        if namespace:
            search_query = {
                "query": """
                    query {
                        Product {
                            sandbox(sandboxId: $namespace) {
                                configuration {
                                    ... on StoreConfiguration {
                                        configs {
                                            shortDescription
                                        }
                                    }
                                }
                            }
                            catalogNs {
                                mappings(pageType: "productHome") {
                                    pageSlug
                                    pageType
                                }
                            }
                        }
                    }
                """,
                "variables": {"namespace": namespace}
            }
            url = "https://launcher.store.epicgames.com/graphql"
        else:
            search_query = {
                "query": """
                    query search($keywords: String!, $locale: String) {
                        Catalog {
                            searchStore(keywords: $keywords, locale: $locale) {
                                elements { title namespace productSlug description }
                            }
                        }
                    }
                """,
                "variables": {"keywords": app_name, "locale": locale}
            }
            url = "https://graphql.epicgames.com/graphql"

        try:
            response = requests.post(url, json=search_query, headers=headers, timeout=10)
            response.raise_for_status()
            data = orjson.loads(response.content)
            if namespace:
                configs = data.get("data", {}).get("Product", {}).get("sandbox", {}).get("configuration", [{}])[0].get("configs", {})
                description = configs.get("shortDescription", "")
                mappings = data.get("data", {}).get("Product", {}).get("catalogNs", {}).get("mappings", [])
                slug = next((m.get("pageSlug", "") for m in mappings if m.get("pageType") == "productHome"), "")
                return description, slug
            else:
                elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
                for element in elements:
                    if (isinstance(element, dict) and
                        element.get("title", "").lower() == app_name.lower() and
                        element.get("productSlug") and
                        not any(substring in element.get("title", "").lower()
                                for substring in ["bundle", "pack", "edition", "dlc", "upgrade", "chapter", "набор", "пак", "дополнение"])):
                        return element.get("description", ""), element.get("productSlug", "")
                return "", ""
        except requests.exceptions.Timeout:
            logger.warning("GraphQL request timeout for %s with locale %s", app_name, locale)
            return "", ""
        except requests.RequestException as e:
            logger.warning("Failed to fetch GraphQL data for %s with locale %s: %s", app_name, locale, str(e))
            return "", ""
        except orjson.JSONDecodeError:
            logger.warning("Invalid JSON response for %s with locale %s", app_name, locale)
            return "", ""

    def fetch_description():
        description = ""
        product_slug = ""

        # Step 1: Try GraphQL with namespace to get description and slug
        if namespace:
            description, product_slug = fetch_graphql_description(namespace, lang)
            if description:
                logger.debug("Fetched description from GraphQL for %s: %s", app_name, (description[:100] + "...") if len(description) > 100 else description)

        # Step 2: If no description or no namespace, try legacy API with slug
        if not description:
            if not product_slug:
                product_slug = slug_from_title(app_name)
            legacy_url = f"https://store-content.ak.epicgames.com/api/{lang}/content/products/{product_slug}"
            try:
                description = fetch_legacy_description(legacy_url)
                if description:
                    logger.debug("Fetched description from legacy API for %s: %s", app_name, (description[:100] + "...") if len(description) > 100 else description)
            except requests.exceptions.ConnectionError:
                logger.error("Skipping legacy API due to DNS resolution failure for %s", app_name)
            except requests.exceptions.Timeout:
                logger.warning("Legacy API request timed out for %s", app_name)
            except Exception as e:
                logger.error("Unexpected error fetching legacy API for %s: %s", app_name, str(e))

        # Step 3: If still no description and no namespace, try GraphQL with title
        if not description and not namespace:
            description, _ = fetch_graphql_description(None, lang)
            if description:
                logger.debug("Fetched description from GraphQL title search for %s: %s", app_name, (description[:100] + "...") if len(description) > 100 else description)

        # Step 4: If no description found, log and return empty
        if not description:
            logger.warning("No valid description found for %s", app_name)

        # Save to cache
        cache_entry = {"description": description, "timestamp": time.time()}
        try:
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, "wb") as f:
                f.write(orjson.dumps(cache_entry))
            temp_file.replace(cache_file)
            logger.debug("Saved description to cache for %s", app_name)
        except Exception as e:
            logger.error("Failed to save description cache for %s: %s", app_name, str(e))

        callback(description)

    thread = threading.Thread(target=fetch_description, daemon=True)
    thread.start()

def run_legendary_list_async(legendary_path: str, callback: Callable[[list | None], None]):
    """
    Asynchronously executes legendary list --json command and returns result via callback.
    """
    def execute_command():
        process = None
        try:
            process = subprocess.Popen(
                [legendary_path, "list", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
            stdout, stderr = process.communicate(timeout=30)
            if process.returncode != 0:
                logger.error("Legendary list command failed: %s", stderr.decode('utf-8', errors='replace'))
                callback(None)
                return
            try:
                result = orjson.loads(stdout)
                if not isinstance(result, list):
                    logger.error("Invalid legendary output format: expected list, got %s", type(result))
                    callback(None)
                    return
                callback(result)
            except orjson.JSONDecodeError as e:
                logger.error("Failed to parse JSON output from legendary list: %s", str(e))
                callback(None)
        except subprocess.TimeoutExpired:
            logger.error("Legendary list command timed out")
            if process:
                process.kill()
            callback(None)
        except FileNotFoundError:
            logger.error("Legendary executable not found at %s", legendary_path)
            callback(None)
        except Exception as e:
            logger.error("Unexpected error executing legendary list: %s", str(e))
            callback(None)

    threading.Thread(target=execute_command, daemon=True).start()

def load_egs_games_async(legendary_path: str, callback: Callable[[list[tuple]], None], downloader, update_progress: Callable[[int], None], update_status_message: Callable[[str, int], None]):
    """
    Asynchronously loads Epic Games Store games using legendary CLI.
    Reads playtime and last launch statistics from statistics file.
    Checks if game exists in Steam to get ProtonDB status.
    """
    logger.debug("Starting to load Epic Games Store games")
    games: list[tuple] = []
    cache_dir = Path(os.path.dirname(legendary_path))
    metadata_dir = cache_dir / "metadata"
    cache_file = cache_dir / "legendary_games.json"
    cache_ttl = 3600  # Cache TTL in seconds (1 hour)

    # Path to statistics file
    portproton_location = get_portproton_location()
    if portproton_location is None:
        logger.error("PortProton location is not set, cannot locate statistics file")
        statistics_file = ""
    else:
        statistics_file = os.path.join(portproton_location, "data", "tmp", "statistics")

    if not os.path.exists(legendary_path):
        logger.info("Legendary binary not found, downloading...")
        def on_legendary_downloaded(result):
            if result:
                logger.info("Legendary binary downloaded successfully")
                try:
                    os.chmod(legendary_path, 0o755)
                except Exception as e:
                    logger.error(f"Failed to make legendary binary executable: {e}")
                    callback(games)  # Return empty games list on failure
                    return
                _continue_loading_egs_games(legendary_path, callback, metadata_dir, cache_dir, cache_file, cache_ttl, update_progress, update_status_message, statistics_file)
            else:
                logger.error("Failed to download legendary binary")
                callback(games)  # Return empty games list on failure
        try:
            downloader.download_legendary_binary(on_legendary_downloaded)
        except Exception as e:
            logger.error(f"Error initiating legendary binary download: {e}")
            callback(games)
        return
    else:
        _continue_loading_egs_games(legendary_path, callback, metadata_dir, cache_dir, cache_file, cache_ttl, update_progress, update_status_message, statistics_file)

def _continue_loading_egs_games(legendary_path: str, callback: Callable[[list[tuple]], None], metadata_dir: Path, cache_dir: Path, cache_file: Path, cache_ttl: int, update_progress: Callable[[int], None], update_status_message: Callable[[str, int], None], statistics_file: str):
    """
    Continues EGS games loading process, either from cache or via legendary CLI.
    """
    games: list[tuple] = []
    cache_dir.mkdir(parents=True, exist_ok=True)

    user_json_path = cache_dir / "user.json"
    if not user_json_path.exists():
        callback(games)
        return

    def process_games(installed_games: list | None):
        if installed_games is None:
            logger.info("No installed Epic Games Store games found")
            callback(games)
            return

        # Save to cache
        try:
            with open(cache_file, "wb") as f:
                f.write(orjson.dumps(installed_games))
            logger.debug("Saved Epic Games Store games to cache: %s", cache_file)
        except Exception as e:
            logger.error("Failed to save cache: %s", str(e))

        # Filter games
        valid_games = [game for game in installed_games if isinstance(game, dict) and game.get("app_name") and not game.get("is_dlc", False)]
        if len(valid_games) != len(installed_games):
            logger.warning("Filtered out %d invalid game records", len(installed_games) - len(valid_games))

        if not valid_games:
            logger.info("No valid Epic Games Store games found after filtering")
            callback(games)
            return

        pending_images = len(valid_games)
        total_games = len(valid_games)
        update_progress(0)
        update_status_message(_("Loading Epic Games Store games..."), 3000)

        game_results: dict[int, tuple] = {}
        results_lock = threading.Lock()

        def process_game_metadata(game, index):
            nonlocal pending_images
            app_name = game.get("app_name", "")
            title = game.get("app_title", app_name)
            if not app_name:
                with results_lock:
                    pending_images -= 1
                    update_progress(total_games - pending_images)
                    if pending_images == 0:
                        final_games = [game_results[i] for i in sorted(game_results.keys())]
                        callback(final_games)
                return

            # Get path to .exe for name extraction
            game_exe = get_egs_executable(app_name, os.path.dirname(legendary_path))
            exe_name = ""
            if game_exe:
                exe_name = os.path.splitext(os.path.basename(game_exe))[0]

            # Read statistics from statistics file
            playtime_seconds = 0
            formatted_playtime = ""
            last_launch = _("Never")
            last_launch_timestamp = 0
            if exe_name and os.path.exists(statistics_file):
                try:
                    playtime_data = parse_playtime_file(statistics_file)
                    matching_key = next(
                        (key for key in playtime_data if os.path.basename(key).split('.')[0] == exe_name),
                        None
                    )
                    if matching_key:
                        playtime_seconds = playtime_data[matching_key]
                        formatted_playtime = format_playtime(playtime_seconds)
                except Exception as e:
                    logger.error(f"Failed to parse playtime data for {app_name}: {e}")
            if exe_name:
                last_launch = get_last_launch(exe_name) or _("Never")
                last_launch_timestamp = get_last_launch_timestamp(exe_name)

            metadata_file = metadata_dir / f"{app_name}.json"
            cover_url = ""
            try:
                with open(metadata_file, "rb") as f:
                    metadata = orjson.loads(f.read())
                key_images = metadata.get("metadata", {}).get("keyImages", [])
                for img in key_images:
                    if isinstance(img, dict) and img.get("type") in ["DieselGameBoxTall", "Thumbnail"]:
                        cover_url = img.get("url", "")
                        break
            except Exception as e:
                logger.warning("Error processing metadata for %s: %s", app_name, str(e))

            image_folder = os.path.join(os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "PortProtonQt", "images")
            local_path = os.path.join(image_folder, f"{app_name}.jpg") if cover_url else ""

            def on_steam_apps(steam_data: tuple[list | None, dict | None]):
                steam_apps, steam_apps_index = steam_data
                if not steam_apps or not steam_apps_index:
                    logger.info(f"No Steam data available for EGS game {title}, skipping appid lookup")
                    steam_appid = None
                else:
                    matching_app = search_app(title, steam_apps_index)
                    steam_appid = matching_app.get("appid") if matching_app else None

                def on_protondb_tier(protondb_tier: str):
                    def on_description_fetched(api_description: str):
                        final_description = api_description or _("No description available")

                        def on_cover_loaded(pixmap: QPixmap):
                            def on_anticheat_status(status: str):
                                nonlocal pending_images
                                with results_lock:
                                    game_results[index] = (
                                        title,
                                        final_description,
                                        local_path if os.path.exists(local_path) else "",
                                        app_name,
                                        f"legendary:launch:{app_name}",
                                        "",
                                        last_launch,
                                        formatted_playtime,
                                        protondb_tier,
                                        status or "",
                                        last_launch_timestamp,
                                        playtime_seconds,
                                        "epic"
                                    )
                                    pending_images -= 1
                                    update_progress(total_games - pending_images)
                                    if pending_images == 0:
                                        final_games = [game_results[i] for i in sorted(game_results.keys())]
                                        callback(final_games)

                            get_weanticheatyet_status_async(title, on_anticheat_status)

                        load_pixmap_async(cover_url, 600, 900, on_cover_loaded, app_name=app_name)

                    get_egs_game_description_async(title, on_description_fetched)

                if steam_appid:
                    logger.info(f"Found Steam appid {steam_appid} for EGS game {title}")
                    get_protondb_tier_async(steam_appid, on_protondb_tier)
                else:
                    logger.debug(f"No Steam app found for EGS game {title}")
                    on_protondb_tier("")

            get_steam_apps_and_index_async(on_steam_apps)

        max_workers = min(4, len(valid_games))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i, game in enumerate(valid_games):
                executor.submit(process_game_metadata, game, i)

    # Check cache
    use_cache = False
    if cache_file.exists():
        try:
            cache_mtime = cache_file.stat().st_mtime
            if time.time() - cache_mtime < cache_ttl and metadata_dir.exists() and any(metadata_dir.iterdir()):
                logger.debug("Loading Epic Games Store games from cache: %s", cache_file)
                with open(cache_file, "rb") as f:
                    installed_games = orjson.loads(f.read())
                if not isinstance(installed_games, list):
                    logger.warning("Invalid cache format: expected list, got %s", type(installed_games))
                else:
                    use_cache = True
                    process_games(installed_games)
        except Exception as e:
            logger.error("Error reading cache: %s", str(e))

    if not use_cache:
        logger.info("Fetching Epic Games Store games using legendary list")
        run_legendary_list_async(legendary_path, process_games)
