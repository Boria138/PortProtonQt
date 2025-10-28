import functools
import os
import shlex
import subprocess
import time
import html
import orjson
import vdf
import tarfile
import threading
from pathlib import Path
from portprotonqt.logger import get_logger
from portprotonqt.localization import get_steam_language
from portprotonqt.downloader import Downloader
from portprotonqt.dialogs import generate_thumbnail
from portprotonqt.config_utils import get_portproton_location, get_portproton_start_command
from collections.abc import Callable
import re
import shutil
import zlib
import websocket
import requests
import random
import base64
import glob
import urllib.parse

downloader = Downloader()
logger = get_logger(__name__)
CACHE_DURATION = 30 * 24 * 60 * 60

def safe_vdf_load(path: str | Path) -> dict:
    path = str(path)  # Convert Path to str
    try:
        with open(path, 'rb') as f:
            data = vdf.binary_load(f)
        return data
    except Exception as e:
        try:
            with open(path, encoding='utf-8', errors='ignore') as f:
                data = vdf.load(f)
            return data
        except Exception:
            logger.error(f"Failed to load VDF file {path}: {e}")
            return {}

def decode_text(text: str) -> str:
    """
    Decodes HTML entities in a string.
    For example, "&amp;quot;" is converted to '"'.
    Other characters and HTML tags remain unchanged.
    """
    return html.unescape(text)

def get_cache_dir():
    """Returns the path to the cache directory, creating it if necessary."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQt")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

STEAM_DATA_DIRS = (
    "~/.local/share/Steam",
    "~/snap/steam/common/.local/share/Steam",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
)

def get_steam_home():
    """Returns the path to the Steam directory using a list of possible directories."""
    for dir_path in STEAM_DATA_DIRS:
        expanded_path = Path(os.path.expanduser(dir_path))
        if expanded_path.exists():
            return expanded_path
    return None

def get_last_steam_user(steam_home: Path) -> dict | None:
    """Returns data for the last Steam user from loginusers.vdf."""
    loginusers_path = steam_home / "config/loginusers.vdf"
    data = safe_vdf_load(loginusers_path)
    if not data:
        return None
    users = data.get('users', {})
    for user_id, user_info in users.items():
        if user_info.get('MostRecent') == '1':
            try:
                return {'SteamID': int(user_id)}
            except ValueError:
                logger.error(f"Invalid SteamID format: {user_id}")
                return None
    logger.info("No user found with MostRecent=1")
    return None

def convert_steam_id(steam_id: int) -> int:
    """
    Converts a signed 32-bit integer to an unsigned 32-bit integer.
    Uses bitwise AND with 0xFFFFFFFF to correctly handle negative values.
    """
    return steam_id & 0xFFFFFFFF

def get_steam_libs(steam_dir: Path) -> set[Path]:
    """Returns a set of Steam library folders."""
    libs = set()
    libs_vdf = steam_dir / "steamapps/libraryfolders.vdf"
    data = safe_vdf_load(libs_vdf)
    folders = data.get('libraryfolders', {})
    for key, info in folders.items():
        if key.isdigit():
            path_str = info.get('path') if isinstance(info, dict) else None
            if path_str:
                path = Path(path_str).expanduser()
                if path.exists():
                    libs.add(path)
    libs.add(steam_dir)
    return libs

def get_playtime_data(steam_home: Path | None = None) -> dict[int, tuple[int, int]]:
    """Returns playtime data for the last user."""
    play_data: dict[int, tuple[int, int]] = {}
    if steam_home is None:
        steam_home = get_steam_home()
    if steam_home is None or not steam_home.exists():
        logger.error("Steam home directory not found or does not exist")
        return play_data

    userdata_dir = steam_home / "userdata"
    if not userdata_dir.exists():
        logger.info("Userdata directory not found")
        return play_data

    if steam_home is not None:  # Explicit check for type checker
        last_user = get_last_steam_user(steam_home)
    else:
        logger.info("Steam home is None, cannot retrieve last user")
        return play_data

    if not last_user:
        logger.info("Could not identify the last Steam user")
        return play_data

    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(unsigned_id)
    if not user_dir.exists():
        logger.info(f"User directory {unsigned_id} not found")
        return play_data

    localconfig = user_dir / "config/localconfig.vdf"
    data = safe_vdf_load(localconfig)
    cfg = data.get('UserLocalConfigStore', {})
    apps = cfg.get('Software', {}).get('Valve', {}).get('Steam', {}).get('apps', {})
    for appid_str, info in apps.items():
        try:
            appid = int(appid_str)
            last_played = int(info.get('LastPlayed', 0))
            playtime = int(info.get('Playtime', 0))
            play_data[appid] = (last_played, playtime)
        except ValueError:
            logger.warning(f"Invalid playtime data for app {appid_str}")
    return play_data

def get_steam_installed_games() -> list[tuple[str, int, int, int]]:
    """Returns a list of installed Steam games in the format (name, appid, last_played, playtime_sec)."""
    games: list[tuple[str, int, int, int]] = []
    steam_home = get_steam_home()
    if steam_home is None or not steam_home.exists():
        logger.error("Steam home directory not found or does not exist")
        return games

    play_data = get_playtime_data(steam_home)
    for lib in get_steam_libs(steam_home):
        steamapps_dir = lib / "steamapps"
        if not steamapps_dir.exists():
            continue
        for manifest in steamapps_dir.glob("appmanifest_*.acf"):
            data = safe_vdf_load(manifest)
            app = data.get('AppState', {})
            try:
                appid = int(app.get('appid', 0))
            except ValueError:
                continue
            name = app.get('name', f"Unknown ({appid})")
            lname = name.lower()
            if any(token in lname for token in ["proton", "steamworks", "steam linux runtime"]):
                continue
            last_played, playtime_min = play_data.get(appid, (0, 0))
            games.append((name, appid, last_played, playtime_min * 60))
    return games

def normalize_name(s):
    """
    Normalizes a string by:
      - converting to lowercase,
      - removing ™ and ® symbols,
      - replacing separators (-, :, ,) with spaces,
      - removing extra spaces,
      - removing 'bin' or 'app' suffixes,
      - removing keywords like 'ultimate', 'edition', etc.
    """
    s = s.lower()
    for ch in ["™", "®"]:
        s = s.replace(ch, "")
    for ch in ["-", ":", ","]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    for suffix in ["bin", "app"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    keywords_to_remove = {"ultimate", "edition", "definitive", "complete", "remastered"}
    words = s.split()
    filtered_words = [word for word in words if word not in keywords_to_remove]
    return " ".join(filtered_words)

def is_valid_candidate(candidate):
    """
    Determines whether a given candidate string is valid for use as a game name.

    The function performs the following checks:
      1. Normalizes the candidate using `normalize_name()`.
      2. Rejects the candidate if the normalized name is exactly "game"
         (to avoid overly generic names).
      3. Removes spaces and checks for forbidden substrings:
         - "win32"
         - "win64"
         - "gamelauncher"
         These are checked in the space-free version of the string.
      4. Returns True only if none of the forbidden conditions are met.

    Args:
        candidate (str): The candidate string to validate.

    Returns:
        bool: True if the candidate is valid, False otherwise.
    """
    normalized_candidate = normalize_name(candidate)
    if normalized_candidate == "game":
        return False
    normalized_no_space = normalized_candidate.replace(" ", "")
    forbidden = ["win32", "win64", "gamelauncher"]
    for token in forbidden:
        if token in normalized_no_space:
            return False
    return True

def filter_candidates(candidates):
    """
    Filters a list of candidates, discarding invalid ones.
    """
    valid = []
    dropped = []
    for cand in candidates:
        if cand.strip() and is_valid_candidate(cand):
            valid.append(cand)
        else:
            dropped.append(cand)
    if dropped:
        logger.info("Discarding candidates: %s", dropped)
    return valid

def remove_duplicates(candidates):
    """
    Removes duplicates from a list while preserving order.
    """
    return list(dict.fromkeys(candidates))

@functools.lru_cache(maxsize=256)
def get_exiftool_data(game_exe):
    """Retrieves metadata using exiftool."""
    try:
        proc = subprocess.run(
            ["exiftool", "-j", game_exe],
            capture_output=True,
            text=True,
            check=False
        )
        if proc.returncode != 0:
            logger.error(f"exiftool failed for {game_exe}: {proc.stderr.strip()}")
            return {}
        meta_data_list = orjson.loads(proc.stdout.encode("utf-8"))
        return meta_data_list[0] if meta_data_list else {}
    except Exception as e:
        logger.error(f"Unexpected error in get_exiftool_data for {game_exe}: {e}")
        return {}

def delete_cached_app_files(cache_dir: str, pattern: str):
    """Deletes cached files matching the given pattern in the cache directory."""
    try:
        for file_path in glob.glob(os.path.join(cache_dir, pattern)):
            os.remove(file_path)
            logger.info(f"Deleted cached file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to delete cached files matching {pattern}: {e}")

def load_steam_apps_async(callback: Callable[[list], None]):
    """
    Asynchronously loads the list of Steam applications, using cache if available.
    Calls the callback with the list of apps.
    Deletes cached app detail files when downloading a new steam_apps.json.
    """
    cache_dir = get_cache_dir()
    cache_tar = os.path.join(cache_dir, "games_appid.tar.xz")
    cache_json = os.path.join(cache_dir, "steam_apps.json")

    def process_tar(result: str | None):
        if not result or not os.path.exists(result):
            logger.error("Failed to download Steam apps archive")
            callback([])
            return
        try:
            with tarfile.open(result, mode='r:xz') as tar:
                member = next((m for m in tar.getmembers() if m.name.endswith('.json')), None)
                if member is None:
                    raise RuntimeError("JSON file not found in archive")
                fobj = tar.extractfile(member)
                if fobj is None:
                    raise RuntimeError(f"Failed to extract file {member.name} from archive")
                raw = fobj.read()
                fobj.close()
                data = orjson.loads(raw)
            with open(cache_json, "wb") as f:
                f.write(orjson.dumps(data))
            if os.path.exists(cache_tar):
                os.remove(cache_tar)
                logger.info("Deleted archive: %s", cache_tar)
            # Delete all cached app detail files (steam_app_*.json)
            delete_cached_app_files(cache_dir, "steam_app_*.json")
            steam_apps = data if isinstance(data, list) else []
            logger.info("Loaded %d apps from archive", len(steam_apps))
            callback(steam_apps)
        except Exception as e:
            logger.error("Failed to extract Steam apps archive: %s", e)
            callback([])

    if os.path.exists(cache_json) and (time.time() - os.path.getmtime(cache_json) < CACHE_DURATION):
        logger.info("Using cached Steam apps JSON: %s", cache_json)
        try:
            with open(cache_json, "rb") as f:
                data = orjson.loads(f.read())
            # Validate JSON structure
            if not isinstance(data, list):
                logger.error("Invalid JSON format in %s (not a list), re-downloading", cache_json)
                raise ValueError("Invalid JSON structure")
            # Validate each app entry
            for app in data:
                if not isinstance(app, dict) or "appid" not in app or "normalized_name" not in app:
                    logger.error("Invalid app entry in cached JSON %s, re-downloading", cache_json)
                    raise ValueError("Invalid app entry structure")
            steam_apps = data
            logger.info("Loaded %d apps from cache", len(steam_apps))
            callback(steam_apps)
        except Exception as e:
            logger.error("Failed to read or validate cached JSON %s: %s", cache_json, e)
            # Attempt to re-download if cache is invalid or corrupted
            app_list_url = (
                "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/games_appid.tar.xz"
            )
            # Delete cached app detail files before re-downloading
            delete_cached_app_files(cache_dir, "steam_app_*.json")
            downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)
    else:
        app_list_url = (
            "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/games_appid.tar.xz"
        )
        # Delete cached app detail files before downloading
        delete_cached_app_files(cache_dir, "steam_app_*.json")
        downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)

def build_index(steam_apps):
    """
    Builds an index of applications by normalized_name field.
    """
    steam_apps_index = {}
    if not steam_apps:
        return steam_apps_index
    logger.info("Building Steam apps index")
    for app in steam_apps:
        normalized = app["normalized_name"]
        steam_apps_index[normalized] = app
    return steam_apps_index

def search_app(candidate, steam_apps_index):
    """
    Searches for an application by candidate: tries exact match first, then substring match.
    """
    candidate_norm = normalize_name(candidate)
    logger.info("Searching for app with candidate: '%s' -> '%s'", candidate, candidate_norm)
    if candidate_norm in steam_apps_index:
        logger.info("Found exact match: '%s'", candidate_norm)
        return steam_apps_index[candidate_norm]
    for name_norm, app in steam_apps_index.items():
        if candidate_norm in name_norm:
            ratio = len(candidate_norm) / len(name_norm)
            if ratio > 0.8:
                logger.info("Found partial match: candidate '%s' in '%s' (ratio: %.2f)", candidate_norm, name_norm, ratio)
                return app
    logger.info("No app found for candidate '%s'", candidate_norm)
    return None

def load_app_details(app_id):
    """Loads cached game data by appid if not outdated."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            with open(cache_file, "rb") as f:
                return orjson.loads(f.read())
    return None

def save_app_details(app_id, data):
    """Saves appid data to a cache file."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    with open(cache_file, "wb") as f:
        f.write(orjson.dumps(data))

def fetch_sgdb_cover(game_name: str) -> str:
    """
    Fetch a cover image URL from steamgrid.usebottles.com for the given game.
    The API returns a single string (quoted URL).
    """
    try:
        encoded = urllib.parse.quote(game_name)
        url = f"https://steamgrid.usebottles.com/api/search/{encoded}"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            logger.warning("SGDB request failed for %s: %s", game_name, resp.status_code)
            return ""
        text = resp.text.strip()
        # Убираем возможные кавычки вокруг строки
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text:
            logger.info("Fetched SGDB cover for %s: %s", game_name, text)
        return text
    except Exception as e:
        logger.warning("Failed to fetch SGDB cover for %s: %s", game_name, e)
    return ""


def check_url_exists(url: str) -> bool:
    """Check whether a URL returns HTTP 200."""
    try:
        r = requests.head(url, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def fetch_app_info_async(app_id: int, callback: Callable[[dict | None], None]):
    """
    Asynchronously fetches detailed app info from Steam API.
    Calls the callback with the app data or None if failed.
    """
    cached = load_app_details(app_id)
    if cached is not None:
        callback(cached)
        return

    lang = get_steam_language()
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l={lang}"
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")

    def process_response(result: str | None):
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

    downloader.download_async(url, cache_file, timeout=5, callback=process_response)

def load_weanticheatyet_data_async(callback: Callable[[list], None]):
    """
    Asynchronously loads the list of WeAntiCheatYet data, using cache if available.
    Calls the callback with the list of anti-cheat data.
    Deletes cached anti-cheat files when downloading a new anticheat_games.json.
    """
    cache_dir = get_cache_dir()
    cache_tar = os.path.join(cache_dir, "anticheat_games.tar.xz")
    cache_json = os.path.join(cache_dir, "anticheat_games.json")

    def process_tar(result: str | None):
        if not result or not os.path.exists(result):
            logger.error("Failed to download WeAntiCheatYet archive")
            callback([])
            return
        try:
            with tarfile.open(result, mode='r:xz') as tar:
                member = next((m for m in tar.getmembers() if m.name.endswith('anticheat_games_min.json')), None)
                if member is None:
                    raise RuntimeError("JSON file not found in archive")
                fobj = tar.extractfile(member)
                if fobj is None:
                    raise RuntimeError(f"Failed to extract file {member.name} from archive")
                raw = fobj.read()
                fobj.close()
                data = orjson.loads(raw)
            with open(cache_json, "wb") as f:
                f.write(orjson.dumps(data))
            if os.path.exists(cache_tar):
                os.remove(cache_tar)
                logger.info("Deleted archive: %s", cache_tar)
            anti_cheat_data = data or []
            logger.info("Loaded %d anti-cheat entries from archive", len(anti_cheat_data))
            callback(anti_cheat_data)
        except Exception as e:
            logger.error("Failed to extract WeAntiCheatYet archive: %s", e)
            callback([])

    if os.path.exists(cache_json) and (time.time() - os.path.getmtime(cache_json) < CACHE_DURATION):
        logger.info("Using cached WeAntiCheatYet JSON: %s", cache_json)
        try:
            with open(cache_json, "rb") as f:
                data = orjson.loads(f.read())
            # Validate JSON structure
            if not isinstance(data, list):
                logger.error("Invalid JSON format in %s (not a list), re-downloading", cache_json)
                raise ValueError("Invalid JSON structure")
            # Validate each anti-cheat entry
            for entry in data:
                if not isinstance(entry, dict) or "normalized_name" not in entry or "status" not in entry:
                    logger.error("Invalid anti-cheat entry in cached JSON %s, re-downloading", cache_json)
                    raise ValueError("Invalid anti-cheat entry structure")
            anti_cheat_data = data
            logger.info("Loaded %d anti-cheat entries from cache", len(anti_cheat_data))
            callback(anti_cheat_data)
        except Exception as e:
            logger.error("Failed to read or validate cached WeAntiCheatYet JSON %s: %s", cache_json, e)
            # Attempt to re-download if cache is invalid or corrupted
            app_list_url = (
                "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/anticheat_games.tar.xz"
            )
            downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)
    else:
        app_list_url = (
            "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/anticheat_games.tar.xz"
        )
        downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)

def build_weanticheatyet_index(anti_cheat_data):
    """
    Builds an index of anti-cheat data by normalized_name field.
    """
    anti_cheat_index = {}
    if not anti_cheat_data:
        return anti_cheat_index
    logger.info("Building WeAntiCheatYet data index")
    for entry in anti_cheat_data:
        normalized = entry["normalized_name"]
        anti_cheat_index[normalized] = entry
    return anti_cheat_index

def search_anticheat_status(candidate, anti_cheat_index):
    candidate_norm = normalize_name(candidate)
    logger.info("Searching for anti-cheat status for candidate: '%s' -> '%s'", candidate, candidate_norm)
    if candidate_norm in anti_cheat_index:
        status = anti_cheat_index[candidate_norm]["status"]
        logger.info("Found exact match: '%s', status: '%s'", candidate_norm, status)
        return status
    for name_norm, entry in anti_cheat_index.items():
        if candidate_norm in name_norm:
            ratio = len(candidate_norm) / len(name_norm)
            if ratio > 0.8:
                status = entry["status"]
                logger.info("Found partial match: candidate '%s' in '%s' (ratio: %.2f), status: '%s'", candidate_norm, name_norm, ratio, status)
                return status
    logger.info("No anti-cheat status found for candidate '%s'", candidate_norm)
    return ""

def get_weanticheatyet_status_async(game_name: str, callback: Callable[[str], None]):
    """
    Asynchronously retrieves WeAntiCheatYet status for a game by name.
    Calls the callback with the status string or empty string if not found.
    """
    def on_anticheat_data(anti_cheat_data: list):
        anti_cheat_index = build_weanticheatyet_index(anti_cheat_data)
        status = search_anticheat_status(game_name, anti_cheat_index)
        callback(status)

    load_weanticheatyet_data_async(on_anticheat_data)

def load_protondb_status(appid):
    """Loads cached ProtonDB data for a game by appid if not outdated."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            try:
                with open(cache_file, "rb") as f:
                    return orjson.loads(f.read())
            except Exception as e:
                logger.error("Failed to load ProtonDB cache for appid %s: %s", appid, e)
    return None

def save_protondb_status(appid, data):
    """Saves ProtonDB data for a game by appid to a cache file."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    try:
        with open(cache_file, "wb") as f:
            f.write(orjson.dumps(data))
    except Exception as e:
        logger.error("Failed to save ProtonDB cache for appid %s: %s", appid, e)

def get_protondb_tier_async(appid: int, callback: Callable[[str], None]):
    """
    Asynchronously fetches ProtonDB tier for an app.
    Calls the callback with the tier string or empty string if failed.
    """
    cached = load_protondb_status(appid)
    if cached is not None:
        callback(cached.get("tier", ""))
        return

    url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")

    def process_response(result: str | None):
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

    downloader.download_async(url, cache_file, timeout=5, callback=process_response)

def get_full_steam_game_info_async(appid: int, callback: Callable[[dict], None]):
    """
    Asynchronously retrieves full Steam game info, including WeAntiCheatYet status.
    Calls the callback with the game info dictionary.
    """
    def on_app_info(app_info: dict | None):
        if not app_info:
            callback({})
            return
        title = decode_text(app_info.get("name", ""))
        description = decode_text(app_info.get("short_description", ""))
        cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
        if not check_url_exists(cover):
            logger.info("Steam cover not found for %s, trying SGDB", title)
            alt_cover = fetch_sgdb_cover(title)
            if alt_cover:
                cover = alt_cover

        def on_protondb_tier(tier: str):
            def on_anticheat_status(anticheat_status: str):
                callback({
                    'description': description,
                    'controller_support': app_info.get('controller_support', ''),
                    'cover': cover,
                    'protondb_tier': tier,
                    'steam_game': "true",
                    'name': title,
                    'anticheat_status': anticheat_status
                })

            get_weanticheatyet_status_async(title, on_anticheat_status)

        get_protondb_tier_async(appid, on_protondb_tier)

    fetch_app_info_async(appid, on_app_info)

def get_steam_game_info_async(desktop_name: str, exec_line: str, callback: Callable[[dict], tuple[bool, str] | None]) -> None:
    """
    Asynchronously retrieves game info based on desktop name and exec line, including WeAntiCheatYet status for all games.
    Calls the callback with the game info dictionary.
    """
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

    def on_steam_apps(steam_apps: list):
        steam_apps_index = build_index(steam_apps)
        matching_app = None
        for candidate in candidates_ordered:
            if not candidate:
                continue
            matching_app = search_app(candidate, steam_apps_index)
            if matching_app:
                logger.info("Match found for candidate '%s': %s", candidate, matching_app.get("normalized_name"))
                break

        game_name = desktop_name or exe_name.capitalize()

        if not matching_app:
            cover = fetch_sgdb_cover(game_name) or ""
            logger.info("Using SGDB cover for non-Steam game '%s': %s", game_name, cover)

            def on_anticheat_status(anticheat_status: str):
                callback({
                    "appid": "",
                    "name": decode_text(game_name),
                    "description": "",
                    "cover": cover,
                    "controller_support": "",
                    "protondb_tier": "",
                    "steam_game": "false",
                    "anticheat_status": anticheat_status
                })

            get_weanticheatyet_status_async(game_name, on_anticheat_status)
            return

        appid = matching_app["appid"]
        def on_app_info(app_info: dict | None):
            if not app_info:
                def on_anticheat_status(anticheat_status: str):
                    callback({
                        "appid": "",
                        "name": decode_text(game_name),
                        "description": "",
                        "cover": "",
                        "controller_support": "",
                        "protondb_tier": "",
                        "steam_game": "false",
                        "anticheat_status": anticheat_status
                    })

                get_weanticheatyet_status_async(game_name, on_anticheat_status)
                return

            title = decode_text(app_info.get("name", game_name))
            description = decode_text(app_info.get("short_description", ""))
            cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
            if not check_url_exists(cover):
                logger.info("Steam cover not found for %s, trying SGDB", title)
                alt_cover = fetch_sgdb_cover(title)
                if alt_cover:
                    cover = alt_cover
            controller_support = app_info.get("controller_support", "")

            def on_protondb_tier(tier: str):
                def on_anticheat_status(anticheat_status: str):
                    callback({
                        "appid": appid,
                        "name": title,
                        "description": description,
                        "cover": cover,
                        "controller_support": controller_support,
                        "protondb_tier": tier,
                        "steam_game": "true",
                        "anticheat_status": anticheat_status
                    })

                get_weanticheatyet_status_async(title, on_anticheat_status)

            get_protondb_tier_async(appid, on_protondb_tier)

        fetch_app_info_async(appid, on_app_info)

    load_steam_apps_async(on_steam_apps)

_STEAM_APPS = None
_STEAM_APPS_INDEX = None
_STEAM_APPS_LOCK = threading.Lock()

def get_steam_apps_and_index_async(callback: Callable[[tuple[list, dict]], None]):
    """
    Asynchronously loads and caches Steam apps and their index.
    Calls the callback with (steam_apps, steam_apps_index).
    """
    global _STEAM_APPS, _STEAM_APPS_INDEX
    with _STEAM_APPS_LOCK:
        if _STEAM_APPS is not None and _STEAM_APPS_INDEX is not None:
            callback((_STEAM_APPS, _STEAM_APPS_INDEX))
            return

    def on_steam_apps(steam_apps: list):
        global _STEAM_APPS, _STEAM_APPS_INDEX
        with _STEAM_APPS_LOCK:
            _STEAM_APPS = steam_apps
            _STEAM_APPS_INDEX = build_index(steam_apps)
            callback((_STEAM_APPS, _STEAM_APPS_INDEX))

    load_steam_apps_async(on_steam_apps)

def enable_steam_cef() -> tuple[bool, str]:
    """
    Checks and enables Steam CEF remote debugging if necessary.

    Creates a .cef-enable-remote-debugging file in the Steam directory.
    Steam must be restarted after the file is first created.

    Returns a tuple:
    - (True, "already_enabled") if already enabled.
    - (True, "restart_needed") if just enabled and Steam restart is needed.
    - (False, "steam_not_found") if Steam directory is not found.
    """
    steam_home = get_steam_home()
    if not steam_home:
        return (False, "steam_not_found")

    cef_flag_file = steam_home / ".cef-enable-remote-debugging"
    logger.info(f"Checking CEF flag: {cef_flag_file}")

    if cef_flag_file.exists():
        logger.info("CEF Remote Debugging is already enabled")
        return (True, "already_enabled")
    else:
        try:
            os.makedirs(cef_flag_file.parent, exist_ok=True)
            cef_flag_file.touch()
            logger.info("Enabled CEF Remote Debugging. Steam restart required")
            return (True, "restart_needed")
        except Exception as e:
            logger.error(f"Failed to create CEF flag {cef_flag_file}: {e}")
            return (False, str(e))

def call_steam_api(js_cmd: str, *args) -> dict | None:
    """
    Executes a JavaScript function in the Steam context via CEF Remote Debugging.

    Args:
        js_cmd: Name of the JS function to call (e.g., 'createShortcut').
        *args: Arguments to pass to the JS function.

    Returns:
        Dictionary with the result or None if an error occurs.
    """
    status, message = enable_steam_cef()
    if not (status is True and message == "already_enabled"):
        if message == "restart_needed":
            logger.warning("Steam CEF API is available but requires Steam restart for full activation")
        elif message == "steam_not_found":
            logger.error("Could not find Steam directory to check CEF API")
        else:
            logger.error(f"Steam CEF API is unavailable or not ready: {message}")
        return None

    steam_debug_url = "http://localhost:8080/json"

    try:
        response = requests.get(steam_debug_url, timeout=2)
        response.raise_for_status()
        contexts = response.json()
        ws_url = next((ctx['webSocketDebuggerUrl'] for ctx in contexts if ctx['title'] == 'SharedJSContext'), None)
        if not ws_url:
            logger.warning("SharedJSContext not found. Is Steam running with -cef-enable-remote-debugging?")
            return None
    except Exception as e:
        logger.warning(f"Failed to connect to Steam CEF API at {steam_debug_url}. Is Steam running? {e}")
        return None

    js_code = """
        async function createShortcut(name, exe, dir, icon, args) {
            const id = await SteamClient.Apps.AddShortcut(name, exe, dir, args);
            console.log("Shortcut created with ID:", id);
            await SteamClient.Apps.SetShortcutName(id, name);
            if (icon)
                await SteamClient.Apps.SetShortcutIcon(id, icon);
            if (args)
                await SteamClient.Apps.SetAppLaunchOptions(id, args);
            return { id };
        };

        async function setGrid(id, i, ext, image) {
            await SteamClient.Apps.SetCustomArtworkForApp(id, image, ext, i);
            return true;
        };

        async function removeShortcut(id) {
            await SteamClient.Apps.RemoveShortcut(+id);
            return true;
        };
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=5)
        js_args = ", ".join(orjson.dumps(arg).decode('utf-8') for arg in args)
        expression = f"{js_code} {js_cmd}({js_args});"
        payload = {
            "id": random.randint(0, 32767),
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True
            }
        }

        ws.send(orjson.dumps(payload))
        response_str = ws.recv()
        ws.close()

        response_data = orjson.loads(response_str)
        if "error" in response_data:
            logger.error(f"JavaScript execution error in Steam: {response_data['error']['message']}")
            return None
        result = response_data.get('result', {}).get('result', {})
        if result.get('type') == 'object' and result.get('subtype') == 'error':
            logger.error(f"JavaScript execution error in Steam: {result.get('description')}")
            return None
        return result.get('value')
    except Exception as e:
        logger.error(f"WebSocket interaction error with Steam: {e}")
        return None

def add_to_steam(game_name: str, exec_line: str, cover_path: str) -> tuple[bool, str]:
    """
    Add a non-Steam game to Steam via shortcuts.vdf with PortProton tag,
    and download Steam Grid covers with correct sizes and names.
    """

    if not exec_line or not exec_line.strip():
        logger.error("Invalid exec_line: empty or whitespace")
        return (False, "Executable command is empty or invalid")

    # Parse exec_line to get the executable path
    try:
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            logger.error(f"Failed to parse exec_line: {exec_line}")
            return (False, "Failed to parse executable command: no valid tokens")

        if entry_exec_split[0] == "env" and len(entry_exec_split) >= 3:
            exe_path = entry_exec_split[2]
        elif entry_exec_split[0] == "flatpak" and len(entry_exec_split) >= 4:
            exe_path = entry_exec_split[3]
        else:
            exe_path = entry_exec_split[-1]
    except Exception as e:
        logger.error(f"Failed to parse exec_line: {exec_line}, error: {e}")
        return (False, f"Failed to parse executable command: {e}")

    if not os.path.exists(exe_path):
        logger.error(f"Executable not found: {exe_path}")
        return (False, f"Executable file not found: {exe_path}")

    portproton_dir = get_portproton_location()
    start_sh = get_portproton_start_command()
    if not portproton_dir or not start_sh:
        logger.error("PortProton directory not found")
        return (False, "PortProton directory not found")

    steam_scripts_dir = os.path.join(portproton_dir, "steam_scripts")
    os.makedirs(steam_scripts_dir, exist_ok=True)

    safe_game_name = re.sub(r'[<>:"/\\|?*]', '_', game_name.strip())
    script_path = os.path.join(steam_scripts_dir, f"{safe_game_name}.sh")

    if not os.path.exists(script_path):
        script_content = f"""#!/usr/bin/env bash
export LD_PRELOAD=
export START_FROM_STEAM=1
"{start_sh}" "{exe_path}" "$@"
"""
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            logger.info(f"Created launch script: {script_path}")
        except Exception as e:
            logger.error(f"Failed to create launch script {script_path}: {e}")
            return (False, f"Failed to create launch script: {e}")
    else:
        logger.info(f"Launch script already exists: {script_path}")

    generated_icon_path = os.path.join(portproton_dir, "data", "img", f"{safe_game_name}.png")
    try:
        img_dir = os.path.join(portproton_dir, "data", "img")
        os.makedirs(img_dir, exist_ok=True)

        if os.path.exists(generated_icon_path):
            logger.info(f"Reusing existing thumbnail: {generated_icon_path}")
        else:
            success = generate_thumbnail(exe_path, generated_icon_path, size=128, force_resize=True)
            if not success or not os.path.exists(generated_icon_path):
                logger.warning(f"Failed to generate thumbnail for {exe_path}")
                icon_path = ""
            else:
                logger.info(f"Generated thumbnail: {generated_icon_path}")
        icon_path = generated_icon_path
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for {exe_path}: {e}")
        icon_path = ""

    steam_home = get_steam_home()
    if not steam_home:
        logger.error("Steam home directory not found")
        return (False, "Steam directory not found")

    last_user = get_last_steam_user(steam_home)
    if not last_user or 'SteamID' not in last_user:
        logger.error("Failed to retrieve Steam user ID")
        return (False, "Failed to get Steam user ID")

    userdata_dir = steam_home / "userdata"
    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(unsigned_id)
    steam_shortcuts_path = user_dir / "config" / "shortcuts.vdf"
    grid_dir = user_dir / "config" / "grid"
    os.makedirs(grid_dir, exist_ok=True)

    appid = None
    was_api_used = False

    logger.info("Attempting to add shortcut via Steam CEF API")
    api_response = call_steam_api(
        "createShortcut",
        game_name,
        script_path,
        str(Path(script_path).parent),
        icon_path,
        ""
    )

    if api_response and isinstance(api_response, dict) and 'id' in api_response:
        appid = api_response['id']
        was_api_used = True
        logger.info(f"Shortcut successfully added via API. AppID: {appid}")
    else:
        logger.warning("Failed to add shortcut via API. Falling back to shortcuts.vdf")
        backup_path = f"{steam_shortcuts_path}.backup"
        if os.path.exists(steam_shortcuts_path):
            try:
                shutil.copy2(steam_shortcuts_path, backup_path)
                logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
            except Exception as e:
                logger.error(f"Failed to create backup of shortcuts.vdf: {e}")
                return (False, f"Failed to create backup of shortcuts.vdf: {e}")

        unique_string = f"{script_path}{game_name}"
        baseid = zlib.crc32(unique_string.encode('utf-8')) & 0xffffffff
        appid = baseid | 0x80000000
        if appid > 0x7FFFFFFF:
            aidvdf = appid - 0x100000000
        else:
            aidvdf = appid

        shortcut = {
            "appid": aidvdf,
            "AppName": game_name,
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
        logger.info(f"Shortcut entry to be written: {shortcut}")

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
                logger.warning(f"Failed to load existing shortcuts.vdf, starting fresh: {load_err}")
                shortcuts_data = {"shortcuts": {}}

            shortcuts = shortcuts_data.get("shortcuts", {})
            for _key, entry in shortcuts.items():
                if entry.get("AppName") == game_name and entry.get("Exe") == f'"{script_path}"':
                    logger.info(f"Game '{game_name}' already exists in Steam shortcuts")
                    return (False, f"Game '{game_name}' already exists in Steam")

            new_index = str(len(shortcuts))
            shortcuts[new_index] = shortcut

            with open(steam_shortcuts_path, 'wb') as f:
                vdf.binary_dump({"shortcuts": shortcuts}, f)
            logger.info(f"Game '{game_name}' successfully added to Steam with covers")
        except Exception as e:
            logger.error(f"Failed to update shortcuts.vdf: {e}")
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, steam_shortcuts_path)
                    logger.info("Restored shortcuts.vdf from backup due to update failure")
                except Exception as restore_err:
                    logger.error(f"Failed to restore shortcuts.vdf from backup: {restore_err}")
            appid = None

    if not appid:
        return (False, "Failed to create shortcut using any method")

    steam_appid = None

    def on_game_info(game_info: dict):
        nonlocal steam_appid
        steam_appid = game_info.get("appid")
        if not steam_appid or not isinstance(steam_appid, int):
            logger.info("No valid Steam appid found, skipping cover download")
            return
        logger.info(f"Found Steam AppID {steam_appid} for cover download")

        cover_types = [
            ("p.jpg", "library_600x900_2x.jpg"),
            ("_hero.jpg", "library_hero.jpg"),
            ("_logo.png", "logo.png"),
            (".jpg", "header.jpg")
        ]

        def on_cover_download(result_path: str | None, steam_name: str, index: int):
            try:
                if result_path and os.path.exists(result_path):
                    logger.info(f"Downloaded cover {steam_name} to {result_path}")
                    if was_api_used:
                        try:
                            with open(result_path, 'rb') as f:
                                img_b64 = base64.b64encode(f.read()).decode('utf-8')
                            logger.info(f"Applying cover type '{steam_name}' via API for AppID {appid}")
                            ext = Path(steam_name).suffix.lstrip('.')
                            call_steam_api("setGrid", appid, index, ext, img_b64)
                        except Exception as e:
                            logger.error(f"Failed to apply cover '{steam_name}' via API: {e}")
                else:
                    logger.warning(f"Failed to download cover {steam_name} for appid {steam_appid}")
            except Exception as e:
                logger.error(f"Failed to process cover {steam_name} for appid {steam_appid}: {e}")

        for i, (suffix, steam_name) in enumerate(cover_types):
            cover_file = os.path.join(grid_dir, f"{appid}{suffix}")
            cover_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_appid}/{steam_name}"
            downloader.download_async(
                cover_url,
                cover_file,
                timeout=5,
                callback=lambda result, index=i, name=steam_name: on_cover_download(result, name, index)
            )

    get_steam_game_info_async(game_name, exec_line, on_game_info)
    return (True, "Adding game to Steam, checking for covers...")

def remove_from_steam(game_name: str, exec_line: str) -> tuple[bool, str]:
    """
    Remove a non-Steam game from Steam by deleting its entry from shortcuts.vdf.
    """
    # Validate inputs
    if not game_name or not game_name.strip():
        logger.error("Invalid game_name: empty or whitespace")
        return (False, "Game name is empty or invalid")
    if not exec_line or not exec_line.strip():
        logger.error("Invalid exec_line: empty or whitespace")
        return (False, "Executable command is empty or invalid")

    # Get PortProton directory
    portproton_dir = get_portproton_location()
    if not portproton_dir:
        logger.error("PortProton directory not found")
        return (False, "PortProton directory not found")

    # Construct script path
    safe_game_name = re.sub(r'[<>:"/\\|?*]', '_', game_name.strip())
    script_path = os.path.join(portproton_dir, "steam_scripts", f"{safe_game_name}.sh")

    # Get Steam home directory
    steam_home = get_steam_home()
    if not steam_home:
        logger.error("Steam home directory not found")
        return (False, "Steam directory not found")

    # Get current Steam user ID
    last_user = get_last_steam_user(steam_home)
    if not last_user or 'SteamID' not in last_user:
        logger.error("Failed to retrieve Steam user ID")
        return (False, "Failed to get Steam user ID")
    userdata_dir = steam_home / "userdata"
    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(unsigned_id)

    # Construct path to shortcuts.vdf and grid directory
    steam_shortcuts_path = os.path.join(user_dir, "config", "shortcuts.vdf")
    grid_dir = os.path.join(user_dir, "config", "grid")

    # Check if shortcuts.vdf exists
    if not os.path.exists(steam_shortcuts_path):
        logger.info(f"shortcuts.vdf not found at {steam_shortcuts_path}")
        return (False, f"Game '{game_name}' not found in Steam")

    appid = None

    # Load and modify shortcuts.vdf
    try:
        if os.path.getsize(steam_shortcuts_path) > 0:
            with open(steam_shortcuts_path, 'rb') as f:
                shortcuts_data = vdf.binary_load(f)
        else:
            shortcuts_data = {"shortcuts": {}}
    except Exception as load_err:
        logger.error(f"Failed to load shortcuts.vdf: {load_err}")
        return (False, f"Failed to load shortcuts.vdf: {load_err}")

    shortcuts = shortcuts_data.get("shortcuts", {})
    new_shortcuts = {}
    index = 0

    # Filter out the matching shortcut
    for _key, entry in shortcuts.items():
        if entry.get("AppName") == game_name and entry.get("Exe") == f'"{script_path}"':
            appid = convert_steam_id(int(entry.get("appid")))
            logger.info(f"Found matching shortcut for '{game_name}' to remove")
            continue
        new_shortcuts[str(index)] = entry
        index += 1

    if not appid:
        logger.info(f"Game '{game_name}' not found in Steam shortcuts")
        return (False, f"Game '{game_name}' not found in Steam")

    api_response = call_steam_api("removeShortcut", appid)
    if api_response is not None: # API responded, even if response is empty
        logger.info(f"Shortcut for AppID {appid} successfully removed via API")
    else:
        logger.warning("Failed to remove shortcut via API. Falling back to editing shortcuts.vdf")

        # Create backup of shortcuts.vdf
        backup_path = f"{steam_shortcuts_path}.backup"
        try:
            shutil.copy2(steam_shortcuts_path, backup_path)
            logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup of shortcuts.vdf: {e}")
            return (False, f"Failed to create backup of shortcuts.vdf: {e}")

        # Save updated shortcuts.vdf
        try:
            with open(steam_shortcuts_path, 'wb') as f:
                vdf.binary_dump({"shortcuts": new_shortcuts}, f)
            logger.info(f"Successfully updated shortcuts.vdf, removed '{game_name}'")
        except Exception as e:
            logger.error(f"Failed to update shortcuts.vdf: {e}")
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, steam_shortcuts_path)
                    logger.info("Restored shortcuts.vdf from backup due to update failure")
                except Exception as restore_err:
                    logger.error(f"Failed to restore shortcuts.vdf from backup: {restore_err}")
            return (False, f"Failed to update shortcuts.vdf: {e}")

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
        else:
            logger.info(f"Cover file not found: {cover_file}")

    if os.path.exists(script_path):
        try:
            os.remove(script_path)
            logger.info(f"Deleted steam script: {script_path}")
        except Exception as e:
            logger.error(f"Failed to delete steam script {script_path}: {e}")
    else:
        logger.info(f"Steam script not found: {script_path}")

    logger.info(f"Game '{game_name}' successfully removed from Steam")
    return (True, f"Game '{game_name}' removed from Steam")

def is_game_in_steam(game_name: str) -> bool:
    steam_home = get_steam_home()
    if steam_home is None:
        logger.warning("Steam home directory not found")
        return False

    try:
        last_user = get_last_steam_user(steam_home)
        if not last_user or 'SteamID' not in last_user:
            logger.warning("No valid Steam user found")
            return False
        user_id = last_user['SteamID']
        unsigned_id = convert_steam_id(user_id)
        steam_shortcuts_path = os.path.join(str(steam_home), "userdata", str(unsigned_id), "config", "shortcuts.vdf")
        if not os.path.exists(steam_shortcuts_path):
            logger.warning(f"Shortcuts file not found at {steam_shortcuts_path}")
            return False

        shortcuts_data = safe_vdf_load(steam_shortcuts_path)
        shortcuts = shortcuts_data.get("shortcuts", {})
        for _key, entry in shortcuts.items():
            if entry.get("AppName") == game_name:
                return True
    except Exception as e:
        logger.error(f"Failed to check if game {game_name} is in Steam: {e}")
    return False
