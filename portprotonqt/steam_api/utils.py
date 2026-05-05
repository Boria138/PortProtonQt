"""Utility functions for Steam API module."""

import os
from pathlib import Path

import vdf

from portprotonqt.logger import get_logger
from portprotonqt.image_utils import COVER_IMAGE_EXTENSIONS

logger = get_logger(__name__)

STEAM_DATA_DIRS = (
    "~/.local/share/Steam",
    "~/snap/steam/common/.local/share/Steam",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
)


def safe_vdf_load(path: str | Path) -> dict:
    """Load VDF file, trying binary format first, then text."""
    path = str(path)
    # Check first byte to determine format
    try:
        with open(path, "rb") as f:
            first_byte = f.read(1)
            if not first_byte:
                return {}
    except Exception:
        return {}

    # Binary VDF starts with 0x00 or 0x01, text VDF starts with ASCII
    if first_byte in (b"\x00", b"\x01"):
        try:
            with open(path, "rb") as f:
                return vdf.binary_load(f)
        except Exception as e:
            logger.debug("Failed to load binary VDF %s: %s", path, e)
            return {}
    else:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return vdf.load(f)
        except Exception as e:
            logger.debug("Failed to load text VDF %s: %s", path, e)
            return {}


def decode_text(text: str) -> str:
    """Decode HTML entities in a string."""
    import html
    return html.unescape(text)


def get_steam_home() -> Path | None:
    """Return path to Steam directory."""
    for dir_path in STEAM_DATA_DIRS:
        expanded_path = Path(os.path.expanduser(dir_path))
        if expanded_path.exists():
            return expanded_path
    return None


def get_local_steam_cover(appid: int | str, prefer_exact: bool = True) -> str:
    """Return local Steam library cover path for appid."""
    steam_home = get_steam_home()
    if steam_home is None:
        return ""

    appid_str = str(appid).strip()
    if not appid_str:
        return ""

    librarycache = steam_home / "appcache" / "librarycache"
    if not librarycache.exists():
        return ""

    exact_paths = (
        librarycache / appid_str / "library_600x900.jpg",
        librarycache / f"{appid_str}_library_600x900.jpg",
    )
    for cover_path in exact_paths:
        if cover_path.is_file():
            return str(cover_path)

    capsule_paths = (
        librarycache / appid_str / "library_capsule.jpg",
        librarycache / appid_str / "library_capsule.png",
        librarycache / f"{appid_str}_library_capsule.jpg",
        librarycache / f"{appid_str}_library_capsule.png",
    )
    for cover_path in capsule_paths:
        if cover_path.is_file():
            return str(cover_path)

    if prefer_exact:
        return ""

    for suffix in (ext.removeprefix(".") for ext in COVER_IMAGE_EXTENSIONS):
        patterns = (
            f"{appid_str}/library_600x900*.{suffix}",
            f"{appid_str}/library_capsule*.{suffix}",
            f"{appid_str}/*/library_600x900*.{suffix}",
            f"{appid_str}/*/library_capsule*.{suffix}",
            f"{appid_str}/*.{suffix}",
            f"{appid_str}_library_600x900*.{suffix}",
            f"{appid_str}_library_capsule*.{suffix}",
            f"{appid_str}_*.{suffix}",
        )
        for pattern in patterns:
            for cover_path in sorted(librarycache.glob(pattern)):
                if cover_path.is_file():
                    return str(cover_path)

    return ""


def get_steam_compat_tool(appid: int) -> str | None:
    """Return compatibility tool name for given Steam appid."""
    steam_home = get_steam_home()
    if steam_home is None or not steam_home.exists():
        return None

    config_vdf = steam_home / "config" / "config.vdf"
    if not config_vdf.exists():
        return None

    data = safe_vdf_load(config_vdf)
    compat_tools = data.get('InstallConfigStore', {}).get('Software', {}).get('Valve', {}).get('Steam', {}).get('CompatToolMapping', {})

    appid_str = str(appid)
    if appid_str in compat_tools:
        tool_info = compat_tools[appid_str]
        if isinstance(tool_info, dict):
            return tool_info.get('name')

    return None


def get_last_steam_user(steam_home: Path) -> dict | None:
    """Return data for last Steam user from loginusers.vdf."""
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
    """Convert signed 32-bit integer to unsigned 32-bit integer."""
    return steam_id & 0xFFFFFFFF


def get_steam_libs(steam_dir: Path) -> set[Path]:
    """Return set of Steam library folders."""
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
    """Return playtime data for last user."""
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

    last_user = get_last_steam_user(steam_home)
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
    """Return list of installed Steam games (name, appid, last_played, playtime_sec)."""
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


def normalize_name(s: str) -> str:
    """Normalize string: lowercase, remove symbols, replace separators."""
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


def is_valid_candidate(candidate: str) -> bool:
    """Check if candidate string is valid for use as game name."""
    normalized_candidate = normalize_name(candidate)
    if normalized_candidate == "game":
        return False
    normalized_no_space = normalized_candidate.replace(" ", "")
    forbidden = ["win32", "win64", "gamelauncher"]
    for token in forbidden:
        if token in normalized_no_space:
            return False
    return True


def filter_candidates(candidates: list[str]) -> list[str]:
    """Filter candidates, discarding invalid ones."""
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


def remove_duplicates(candidates: list[str]) -> list[str]:
    """Remove duplicates from list while preserving order."""
    return list(dict.fromkeys(candidates))
