"""Cache management for Steam API module."""

import glob
import os
import subprocess
import tarfile
import threading
import time
from collections.abc import Callable
from typing import Any

import orjson

from portprotonqt.logger import get_logger
from portprotonqt.downloader import Downloader
from portprotonqt.steam_api.utils import get_cache_dir, normalize_name

logger = get_logger(__name__)
downloader = Downloader()

CACHE_DURATION = 30 * 24 * 60 * 60

_EXIFTOOL_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_MAX_ENTRIES = 64
_CACHE_TTL = 300


def get_exiftool_data(game_exe: str) -> dict:
    """Retrieve metadata using exiftool with TTL-based caching."""
    current_time = time.time()

    if len(_EXIFTOOL_CACHE) > _CACHE_MAX_ENTRIES // 2:
        expired_keys = [
            key for key, (data, timestamp) in _EXIFTOOL_CACHE.items()
            if current_time - timestamp > _CACHE_TTL
        ]
        for key in expired_keys:
            del _EXIFTOOL_CACHE[key]

    if game_exe in _EXIFTOOL_CACHE:
        data, timestamp = _EXIFTOOL_CACHE[game_exe]
        if current_time - timestamp <= _CACHE_TTL:
            return data
        else:
            del _EXIFTOOL_CACHE[game_exe]

    try:
        proc = subprocess.run(
            ["exiftool", "-j", game_exe],
            capture_output=True,
            text=True,
            check=False,
            timeout=10
        )
        if proc.returncode != 0:
            logger.error(f"exiftool failed for {game_exe}: {proc.stderr.strip()}")
            return {}
        meta_data_list = orjson.loads(proc.stdout.encode("utf-8"))
        result = meta_data_list[0] if meta_data_list else {}

        if result and len(_EXIFTOOL_CACHE) < _CACHE_MAX_ENTRIES:
            _EXIFTOOL_CACHE[game_exe] = (result, current_time)

        return result
    except subprocess.TimeoutExpired:
        logger.error(f"exiftool timed out for {game_exe}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in get_exiftool_data for {game_exe}: {e}")
        return {}


def delete_cached_app_files(cache_dir: str, pattern: str) -> None:
    """Delete cached files matching the given pattern."""
    try:
        for file_path in glob.glob(os.path.join(cache_dir, pattern)):
            os.remove(file_path)
            logger.info(f"Deleted cached file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to delete cached files matching {pattern}: {e}")


def load_app_details(app_id: int) -> dict | None:
    """Load cached game data by appid if not outdated."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            with open(cache_file, "rb") as f:
                return orjson.loads(f.read())
    return None


def save_app_details(app_id: int, data: dict) -> None:
    """Save appid data to a cache file."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    with open(cache_file, "wb") as f:
        f.write(orjson.dumps(data))


class CacheManager:
    """Generic cache manager with thread safety."""

    def __init__(self, name: str):
        self._cache: dict[str, Any] = {
            'data': None,
            'index': None,
            'timestamp': 0
        }
        self._lock = threading.RLock()
        self._name = name
        self._loading = False
        self._pending_callbacks: list[Callable] = []

    def get_data_and_index_async(
        self,
        load_func: Callable[[Callable[[list], None]], None],
        build_index_func: Callable[[list], dict],
        callback: Callable[[tuple[list | None, dict | None]], None],
        cache_duration: float = CACHE_DURATION
    ) -> None:
        """Asynchronously load and cache data with index."""
        current_time = time.time()

        with self._lock:
            if (self._cache['data'] is not None and
                self._cache['index'] is not None and
                current_time - self._cache['timestamp'] < cache_duration):
                callback((self._cache['data'], self._cache['index']))
                return

            if self._loading:
                self._pending_callbacks.append(callback)
                return

            self._loading = True
            self._pending_callbacks = []

        def on_data(data: list) -> None:
            current_time = time.time()
            with self._lock:
                if data:
                    self._cache['data'] = data
                    self._cache['index'] = build_index_func(data)
                    self._cache['timestamp'] = current_time
                    cached_data = (self._cache['data'], self._cache['index'])
                else:
                    self._cache['data'] = None
                    self._cache['index'] = None
                    self._cache['timestamp'] = 0
                    cached_data = (None, None)

                self._loading = False
                pending_callbacks = self._pending_callbacks
                self._pending_callbacks = []

            callback(cached_data)
            for pending_callback in pending_callbacks:
                pending_callback(cached_data)

        load_func(on_data)

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache = {
                'data': None,
                'index': None,
                'timestamp': 0
            }
        logger.info("Cleared %s cache", self._name)


def load_steam_apps_async(callback: Callable[[list], None]) -> None:
    """Asynchronously load Steam applications, using cache if available."""
    cache_dir = get_cache_dir()
    cache_tar = os.path.join(cache_dir, "games_appid.tar.xz")
    cache_json = os.path.join(cache_dir, "steam_apps.json")

    def process_tar(result: str | None) -> None:
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
            if not isinstance(data, list):
                logger.error("Invalid JSON format in %s (not a list), re-downloading", cache_json)
                raise ValueError("Invalid JSON structure")
            for app in data:
                if not isinstance(app, dict) or "appid" not in app or "normalized_name" not in app:
                    logger.error("Invalid app entry in cached JSON %s, re-downloading", cache_json)
                    raise ValueError("Invalid app entry structure")
            callback(data)
        except Exception as e:
            logger.error("Failed to read or validate cached JSON %s: %s", cache_json, e)
            app_list_url = (
                "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/games_appid.tar.xz"
            )
            delete_cached_app_files(cache_dir, "steam_app_*.json")
            downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)
    else:
        app_list_url = (
            "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/games_appid.tar.xz"
        )
        delete_cached_app_files(cache_dir, "steam_app_*.json")
        downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)


def build_index(steam_apps: list) -> dict:
    """Build index of applications by normalized_name field."""
    steam_apps_index: dict[str, dict] = {}
    if not steam_apps:
        return steam_apps_index
    logger.info("Building Steam apps index")
    for app in steam_apps:
        normalized = app.get("normalized_name", "")
        if normalized:
            steam_apps_index[normalized] = app
    return steam_apps_index


def search_app(candidate: str, steam_apps_index: dict) -> dict | None:
    """Search for application by candidate: exact match first, then partial."""
    candidate_norm = normalize_name(candidate)

    if candidate_norm in steam_apps_index:
        return steam_apps_index[candidate_norm]

    for name_norm, app in steam_apps_index.items():
        if candidate_norm in name_norm:
            ratio = len(candidate_norm) / len(name_norm)
            if ratio > 0.8:
                return app

    return None


def load_weanticheatyet_data_async(callback: Callable[[list], None]) -> None:
    """Asynchronously load WeAntiCheatYet data, using cache if available."""
    cache_dir = get_cache_dir()
    cache_tar = os.path.join(cache_dir, "anticheat_games.tar.xz")
    cache_json = os.path.join(cache_dir, "anticheat_games.json")

    def process_tar(result: str | None) -> None:
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
            if not isinstance(data, list):
                logger.error("Invalid JSON format in %s (not a list), re-downloading", cache_json)
                raise ValueError("Invalid JSON structure")
            for entry in data:
                if not isinstance(entry, dict) or "normalized_name" not in entry or "status" not in entry:
                    logger.error("Invalid anti-cheat entry in cached JSON %s, re-downloading", cache_json)
                    raise ValueError("Invalid anti-cheat entry structure")
            callback(data)
        except Exception as e:
            logger.error("Failed to read or validate cached WeAntiCheatYet JSON %s: %s", cache_json, e)
            app_list_url = (
                "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/anticheat_games.tar.xz"
            )
            downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)
    else:
        app_list_url = (
            "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/anticheat_games.tar.xz"
        )
        downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)


def build_weanticheatyet_index(anti_cheat_data: list) -> dict:
    """Build index of anti-cheat data by normalized_name field."""
    anti_cheat_index: dict[str, dict] = {}
    if not anti_cheat_data:
        return anti_cheat_index
    logger.info("Building WeAntiCheatYet data index")
    for entry in anti_cheat_data:
        normalized = entry.get("normalized_name", "")
        if normalized:
            anti_cheat_index[normalized] = entry
    return anti_cheat_index


def load_protondb_status(appid: int) -> dict | None:
    """Load cached ProtonDB data for a game by appid if not outdated."""
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


def save_protondb_status(appid: int, data: dict) -> None:
    """Save ProtonDB data for a game by appid to a cache file."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    try:
        with open(cache_file, "wb") as f:
            f.write(orjson.dumps(data))
    except Exception as e:
        logger.error("Failed to save ProtonDB cache for appid %s: %s", appid, e)


def search_anticheat_status(candidate: str, anti_cheat_index: dict) -> str:
    """Search for anti-cheat status by candidate: exact match first, then partial."""
    if not candidate:
        return ""
    candidate_norm = normalize_name(candidate)

    if candidate_norm in anti_cheat_index:
        status = anti_cheat_index[candidate_norm]["status"]
        return status

    for name_norm, entry in anti_cheat_index.items():
        if candidate_norm in name_norm:
            ratio = len(candidate_norm) / len(name_norm)
            if ratio > 0.8:
                status = entry["status"]
                return status

    return ""
