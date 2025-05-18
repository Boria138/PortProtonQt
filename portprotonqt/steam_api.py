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
from portprotonqt.config_utils import get_portproton_location
from collections.abc import Callable
import re
import shutil
import hashlib

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
    Декодирует HTML-сущности в строке.
    Например, "&amp;quot;" преобразуется в '"'.
    Остальные символы и HTML-теги остаются без изменений.
    """
    return html.unescape(text)

def get_cache_dir():
    """Возвращает путь к каталогу кэша, создаёт его при необходимости."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQT")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

STEAM_DATA_DIRS = (
    "~/.local/share/Steam",
    "~/snap/steam/common/.local/share/Steam",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
)

def _get_steam_home():
    """Возвращает путь к директории Steam, используя список возможных директорий."""
    for dir_path in STEAM_DATA_DIRS:
        expanded_path = Path(os.path.expanduser(dir_path))
        if expanded_path.exists():
            return expanded_path
    return None

def get_last_steam_user(steam_home: Path) -> dict | None:
    """Возвращает данные последнего пользователя Steam из loginusers.vdf."""
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
                logger.error(f"Неверный формат SteamID: {user_id}")
                return None
    logger.info("Не найден пользователь с MostRecent=1")
    return None

def convert_steam_id(steam_id: int) -> int:
    """
    Преобразует знаковое 32-битное целое число в беззнаковое 32-битное целое число.
    Использует побитовое И с 0xFFFFFFFF, что корректно обрабатывает отрицательные значения.
    """
    return steam_id & 0xFFFFFFFF

def get_steam_libs(steam_dir: Path) -> set[Path]:
    """Возвращает набор директорий Steam libraryfolders."""
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
    """Возвращает данные о времени игры для последнего пользователя."""
    play_data: dict[int, tuple[int, int]] = {}
    if steam_home is None:
        steam_home = _get_steam_home()
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
        logger.info("Не удалось определить последнего пользователя Steam")
        return play_data

    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(unsigned_id)
    if not user_dir.exists():
        logger.info(f"Директория пользователя {unsigned_id} не найдена")
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
            logger.warning(f"Некорректные данные playtime для app {appid_str}")
    return play_data

def get_steam_installed_games() -> list[tuple[str, int, int, int]]:
    """Возвращает список установленных Steam игр в формате (name, appid, last_played, playtime_sec)."""
    games: list[tuple[str, int, int, int]] = []
    steam_home = _get_steam_home()
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
    Приведение строки к нормальному виду:
      - перевод в нижний регистр,
      - удаление символов ™ и ®,
      - замена разделителей (-, :, ,) на пробел,
      - удаление лишних пробелов,
      - удаление суффиксов 'bin' или 'app' в конце строки,
      - удаление ключевых слов типа 'ultimate', 'edition' и т.п.
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
    Проверяет, содержит ли кандидат запрещённые подстроки:
      - win32
      - win64
      - gamelauncher
    Для проверки дополнительно используется строка без пробелов.
    Возвращает True, если кандидат допустим, иначе False.
    """
    normalized_candidate = normalize_name(candidate)
    normalized_no_space = normalized_candidate.replace(" ", "")
    forbidden = ["win32", "win64", "gamelauncher"]
    for token in forbidden:
        if token in normalized_no_space:
            return False
    return True

def filter_candidates(candidates):
    """
    Фильтрует список кандидатов, отбрасывая недопустимые.
    """
    valid = []
    dropped = []
    for cand in candidates:
        if cand.strip() and is_valid_candidate(cand):
            valid.append(cand)
        else:
            dropped.append(cand)
    if dropped:
        logger.info("Отбрасываю кандидатов: %s", dropped)
    return valid

def remove_duplicates(candidates):
    """
    Удаляет дубликаты из списка, сохраняя порядок.
    """
    return list(dict.fromkeys(candidates))

@functools.lru_cache(maxsize=256)
def get_exiftool_data(game_exe):
    """Получает метаданные через exiftool"""
    try:
        proc = subprocess.run(
            ["exiftool", "-j", game_exe],
            capture_output=True,
            text=True,
            check=False
        )
        if proc.returncode != 0:
            logger.error(f"exiftool error for {game_exe}: {proc.stderr.strip()}")
            return {}
        meta_data_list = orjson.loads(proc.stdout.encode("utf-8"))
        return meta_data_list[0] if meta_data_list else {}
    except Exception as e:
        return {}

def load_steam_apps_async(callback: Callable[[list], None]):
    """
    Asynchronously loads the list of Steam applications, using cache if available.
    Calls the callback with the list of apps.
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
                logger.info("Archive %s deleted after extraction", cache_tar)
            steam_apps = data.get("applist", {}).get("apps", []) if isinstance(data, dict) else data or []
            logger.info("Loaded %d apps from archive", len(steam_apps))
            callback(steam_apps)
        except Exception as e:
            logger.error("Error extracting Steam apps archive: %s", e)
            callback([])

    if os.path.exists(cache_json) and (time.time() - os.path.getmtime(cache_json) < CACHE_DURATION):
        logger.info("Using cached Steam apps JSON: %s", cache_json)
        try:
            with open(cache_json, "rb") as f:
                data = orjson.loads(f.read())
            steam_apps = data.get("applist", {}).get("apps", []) if isinstance(data, dict) else data or []
            logger.info("Loaded %d apps from cache", len(steam_apps))
            callback(steam_apps)
        except Exception as e:
            logger.error("Error reading cached JSON: %s", e)
            callback([])
    else:
        app_list_url = (
            "https://raw.githubusercontent.com/Boria138/PortProtonQt/"
            "refs/heads/main/data/games_appid.tar.xz"
        )
        downloader.download_async(app_list_url, cache_tar, timeout=5, callback=process_tar)

def build_index(steam_apps):
    """
    Строит индекс приложений по полю normalized_name.
    """
    steam_apps_index = {}
    if not steam_apps:
        return steam_apps_index
    logger.info("Построение индекса Steam приложений:")
    for app in steam_apps:
        normalized = app["normalized_name"]
        steam_apps_index[normalized] = app
    return steam_apps_index

def search_app(candidate, steam_apps_index):
    """
    Ищет приложение по кандидату: сначала пытается точное совпадение, затем ищет подстроку.
    """
    candidate_norm = normalize_name(candidate)
    logger.info("Поиск приложения для кандидата: '%s' -> '%s'", candidate, candidate_norm)
    if candidate_norm in steam_apps_index:
        logger.info("    Найдено точное совпадение: '%s'", candidate_norm)
        return steam_apps_index[candidate_norm]
    for name_norm, app in steam_apps_index.items():
        if candidate_norm in name_norm:
            ratio = len(candidate_norm) / len(name_norm)
            if ratio > 0.8:
                logger.info("    Найдено частичное совпадение: кандидат '%s' в '%s' (ratio: %.2f)",
                            candidate_norm, name_norm, ratio)
                return app
    logger.info("    Приложение для кандидата '%s' не найдено", candidate_norm)
    return None

def load_app_details(app_id):
    """Загружает кэшированные данные для игры по appid, если они не устарели."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            with open(cache_file, "rb") as f:
                return orjson.loads(f.read())
    return None

def save_app_details(app_id, data):
    """Сохраняет данные по appid в файл кэша."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    with open(cache_file, "wb") as f:
        f.write(orjson.dumps(data))

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
            logger.error("Error processing Steam app info for appid %s: %s", app_id, e)
            callback(None)

    downloader.download_async(url, cache_file, timeout=5, callback=process_response)

def load_protondb_status(appid):
    """Загружает закешированные данные ProtonDB для игры по appid, если они не устарели."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            try:
                with open(cache_file, "rb") as f:
                    return orjson.loads(f.read())
            except Exception as e:
                logger.error("Ошибка загрузки кеша ProtonDB для appid %s: %s", appid, e)
    return None

def save_protondb_status(appid, data):
    """Сохраняет данные ProtonDB для игры по appid в файл кэша."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    try:
        with open(cache_file, "wb") as f:
            f.write(orjson.dumps(data))
    except Exception as e:
        logger.error("Ошибка сохранения кеша ProtonDB для appid %s: %s", appid, e)

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
    Asynchronously retrieves full Steam game info.
    Calls the callback with the game info dictionary.
    """
    def on_app_info(app_info: dict | None):
        if not app_info:
            callback({})
            return
        title = decode_text(app_info.get("name", ""))
        description = decode_text(app_info.get("short_description", ""))
        cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"

        def on_protondb_tier(tier: str):
            callback({
                'description': description,
                'controller_support': app_info.get('controller_support', ''),
                'cover': cover,
                'protondb_tier': tier,
                'steam_game': "true",
                'name': title
            })

        get_protondb_tier_async(appid, on_protondb_tier)

    fetch_app_info_async(appid, on_app_info)

def get_steam_game_info_async(desktop_name: str, exec_line: str, callback: Callable[[dict], tuple[bool, str] | None]) -> None:
    """
    Asynchronously retrieves Steam game info based on desktop name and exec line.
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
                logger.error("Error processing bat file %s: %s", game_exe, e)
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
        if not matching_app:
            callback({
                "appid": "",
                "name": decode_text(f"{exe_name.capitalize()}"),
                "description": "",
                "cover": "",
                "controller_support": "",
                "protondb_tier": "",
                "steam_game": "false"
            })
            return

        appid = matching_app["appid"]
        def on_app_info(app_info: dict | None):
            if not app_info:
                callback({
                    "appid": "",
                    "name": decode_text(f"{exe_name.capitalize()}"),
                    "description": "",
                    "cover": "",
                    "controller_support": "",
                    "protondb_tier": "",
                    "steam_game": "false"
                })
                return
            title = decode_text(app_info.get("name", exe_name.capitalize()))
            description = decode_text(app_info.get("short_description", ""))
            cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
            controller_support = app_info.get("controller_support", "")

            def on_protondb_tier(tier: str):
                callback({
                    "appid": appid,
                    "name": title,
                    "description": description,
                    "cover": cover,
                    "controller_support": controller_support,
                    "protondb_tier": tier,
                    "steam_game": "false"
                })

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
    if not portproton_dir:
        logger.error("PortProton directory not found")
        return (False, "PortProton directory not found")

    steam_scripts_dir = os.path.join(portproton_dir, "steam_scripts")
    os.makedirs(steam_scripts_dir, exist_ok=True)

    safe_game_name = re.sub(r'[<>:"/\\|?*]', '_', game_name.strip())
    script_path = os.path.join(steam_scripts_dir, f"{safe_game_name}.sh")
    start_sh_path = os.path.join(portproton_dir, "data", "scripts", "start.sh")

    if not os.path.exists(start_sh_path):
        logger.error(f"start.sh not found at {start_sh_path}")
        return (False, f"start.sh not found at {start_sh_path}")

    if not os.path.exists(script_path):
        script_content = f"""#!/usr/bin/env bash
export LD_PRELOAD=
export START_FROM_STEAM=1
"{start_sh_path}" "{exe_path}" "$@"
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
                logger.warning(f"generate_thumbnail failed to create icon for {exe_path}")
                icon_path = ""
            else:
                logger.info(f"Generated thumbnail: {generated_icon_path}")
        icon_path = generated_icon_path
    except Exception as e:
        logger.error(f"Error generating thumbnail for {exe_path}: {e}")
        icon_path = ""

    steam_home = _get_steam_home()
    if not steam_home:
        logger.error("Steam home directory not found")
        return (False, "Steam directory not found.")

    last_user = get_last_steam_user(steam_home)
    if not last_user or 'SteamID' not in last_user:
        logger.error("Failed to retrieve Steam user ID")
        return (False, "Failed to get Steam user ID.")

    userdata_dir = steam_home / "userdata"
    user_id = last_user['SteamID']
    unsigned_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(unsigned_id)
    steam_shortcuts_path = user_dir / "config" / "shortcuts.vdf"
    grid_dir = user_dir / "config" / "grid"
    os.makedirs(grid_dir, exist_ok=True)

    backup_path = f"{steam_shortcuts_path}.backup"
    if os.path.exists(steam_shortcuts_path):
        try:
            shutil.copy2(steam_shortcuts_path, backup_path)
            logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup of shortcuts.vdf: {e}")
            return (False, f"Failed to create backup of shortcuts.vdf: {e}")

    unique_string = f"{game_name}:{script_path}"
    generated_appid = int(hashlib.md5(unique_string.encode('utf-8')).hexdigest()[:8], 16) & 0x7FFFFFFF

    real_appid = None
    downloaded_count = 0
    total_covers = 4  # количество обложек

    download_lock = threading.Lock()

    def on_cover_download(cover_file: str, cover_type: str):
        nonlocal downloaded_count
        try:
            if cover_file and os.path.exists(cover_file):
                logger.info(f"Downloaded cover {cover_type} to {cover_file}")
            else:
                logger.warning(f"Failed to download cover {cover_type} for appid {real_appid}")
        except Exception as e:
            logger.error(f"Error processing cover {cover_type} for appid {real_appid}: {e}")
        with download_lock:
            downloaded_count += 1
            if downloaded_count == total_covers:
                finalize_shortcut()

    def finalize_shortcut():
        tags_dict = {'0': 'PortProton'}
        shortcut = {
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
            "tags": tags_dict
        }

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
        except Exception as e:
            logger.error(f"Failed to update shortcuts.vdf: {e}")
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, steam_shortcuts_path)
                    logger.info("Restored shortcuts.vdf from backup due to update failure")
                except Exception as restore_err:
                    logger.error(f"Failed to restore shortcuts.vdf from backup: {restore_err}")
            return (False, f"Failed to update shortcuts.vdf: {e}")

        logger.info(f"Game '{game_name}' successfully added to Steam with covers")
        return (True, f"Game '{game_name}' added to Steam with covers")

    def on_game_info(game_info: dict):
        nonlocal real_appid
        real_appid = game_info.get("appid")
        if not real_appid or not isinstance(real_appid, int):
            logger.info("No valid Steam appid found, skipping cover download")
            return finalize_shortcut()

        # Обложки и имена, соответствующие bash-скрипту и твоим размерам
        cover_types = [
            ("", "library_600x900_2x.jpg"),  # базовый, сохранится как AppId.jpg
            ("p", "library_hero.jpg"),       # сохранится как AppIdp.jpg
            ("_hero", "hero_capsule.jpg"),   # AppId_hero.jpg
            ("_logo", "logo.png")            # AppId_logo.png
        ]

        for suffix, cover_type in cover_types:
            if suffix == "p":
                cover_file = os.path.join(grid_dir, f"{generated_appid}p.jpg")
            elif suffix == "_logo":
                cover_file = os.path.join(grid_dir, f"{generated_appid}_logo.png")
            else:
                cover_file = os.path.join(grid_dir, f"{generated_appid}{suffix}.jpg")

            cover_url = f"https://steamcdn-a.akamaihd.net/steam/apps/{real_appid}/{cover_type}"
            downloader.download_async(
                cover_url,
                cover_file,
                timeout=5,
                callback=lambda result, cfile=cover_file, ctype=cover_type: on_cover_download(cfile, ctype)
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
    steam_home = _get_steam_home()
    if not steam_home:
        logger.error("Steam home directory not found")
        return (False, "Steam directory not found.")

    # Get current Steam user ID
    last_user = get_last_steam_user(steam_home)
    if not last_user or 'SteamID' not in last_user:
        logger.error("Failed to retrieve Steam user ID")
        return (False, "Failed to get Steam user ID.")
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

    # Generate appid for identifying cover files
    unique_string = f"{game_name}:{script_path}"
    generated_appid = int(hashlib.md5(unique_string.encode('utf-8')).hexdigest()[:8], 16) & 0x7FFFFFFF

    # Create backup of shortcuts.vdf
    backup_path = f"{steam_shortcuts_path}.backup"
    try:
        shutil.copy2(steam_shortcuts_path, backup_path)
        logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup of shortcuts.vdf: {e}")
        return (False, f"Failed to create backup of shortcuts.vdf: {e}")

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
    found = False
    new_shortcuts = {}
    index = 0

    # Filter out the matching shortcut
    for _key, entry in shortcuts.items():
        if entry.get("AppName") == game_name and entry.get("Exe") == f'"{script_path}"':
            found = True
            logger.info(f"Found matching shortcut for '{game_name}' to remove")
            continue
        new_shortcuts[str(index)] = entry
        index += 1

    if not found:
        logger.info(f"Game '{game_name}' not found in Steam shortcuts")
        return (False, f"Game '{game_name}' not found in Steam")

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
        os.path.join(grid_dir, f"{generated_appid}.jpg"),
        os.path.join(grid_dir, f"{generated_appid}_hero.jpg"),
        os.path.join(grid_dir, f"{generated_appid}_logo.png")
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

    logger.info(f"Game '{game_name}' successfully removed from Steam")
    return (True, f"Game '{game_name}' removed from Steam")

def is_game_in_steam(game_name: str) -> bool:
    steam_home = _get_steam_home()
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
        logger.error(f"Error checking if game {game_name} is in Steam: {e}")
    return False
