import functools
import os
import shlex
import subprocess
import time
import html

import orjson
import vdf

from pathlib import Path
from portprotonqt.logger import get_logger
from portprotonqt.localization import get_steam_language
from portprotonqt.downloader import Downloader

downloader = Downloader()

logger = get_logger(__name__)

# Время жизни кэша – 30 дней (можно вынести в настройки)
CACHE_DURATION = 30 * 24 * 60 * 60

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

def get_last_steam_user(steam_home):
    """Возвращает данные последнего пользователя Steam из loginusers.vdf."""
    loginusers_path = steam_home / "config/loginusers.vdf"
    if not loginusers_path.exists():
        logger.error("Файл loginusers.vdf не найден")
        return None
    with open(loginusers_path, encoding='utf-8') as f:
        data = vdf.load(f)
    users = data.get('users', {})
    for user_id, user_info in users.items():
        if user_info.get('MostRecent') == '1':
            return {'SteamID': int(user_id)}
    logger.info("Не найден пользователь с MostRecent=1")
    return None

def convert_steam_id(steam_id: int) -> int:
    """
    Преобразует знаковое 32-битное целое число в беззнаковое 32-битное целое число.
    Использует побитовое И с 0xFFFFFFFF, что корректно обрабатывает отрицательные значения.
    """
    return steam_id & 0xFFFFFFFF

def get_steam_libs(steam_dir):
    libs = set()
    libs_vdf = steam_dir / "steamapps/libraryfolders.vdf"
    with open(libs_vdf, encoding='utf-8') as f:
        data = vdf.load(f)['libraryfolders']
        for k in data:
            if k.isdigit() and (path := Path(data[k]['path'])):
                libs.add(path)
    libs.add(steam_dir)
    return libs

def get_playtime_data(steam_home):
    """Возвращает данные о времени игры для последнего пользователя."""
    play_data = {}
    userdata_dir = steam_home / "userdata"
    if not userdata_dir.exists():
        return play_data
    last_user = get_last_steam_user(steam_home)
    if not last_user:
        logger.info("Не удалось определить последнего пользователя Steam")
        return play_data
    user_id = last_user['SteamID']
    convert_user_id = convert_steam_id(user_id)
    user_dir = userdata_dir / str(convert_user_id)
    if not user_dir.exists():
        logger.info(f"Директория пользователя {convert_user_id} не найдена")
        return play_data
    localconfig = user_dir / "config/localconfig.vdf"
    if not localconfig.exists():
        logger.info(f"Файл localconfig.vdf не найден для пользователя {convert_user_id}")
        return play_data
    with open(localconfig, encoding='utf-8') as f:
        data = vdf.load(f)['UserLocalConfigStore']
        apps = data.get('Software', {}).get('Valve', {}).get('Steam', {}).get('apps', {})
        for appid_str, info in apps.items():
            appid = int(appid_str)
            last_played = int(info.get('LastPlayed', 0))
            playtime = int(info.get('Playtime', 0))
            play_data[appid] = (last_played, playtime)
    return play_data

def get_steam_installed_games():
    """Возвращает список установленных Steam игр в формате:
    (name, appid, last_played_timestamp, playtime_seconds)"""
    games = []
    steam_home = _get_steam_home()
    if not steam_home:
        return games
    play_data = get_playtime_data(steam_home)
    for lib in get_steam_libs(steam_home):
        steamapps = lib / "steamapps"
        if not steamapps.exists():
            continue
        for manifest in steamapps.glob("appmanifest_*.acf"):
            with open(manifest, encoding='utf-8') as f:
                app = vdf.load(f)['AppState']
            appid = int(app.get('appid', 0))
            game_name = app.get('name', f"Unknown ({appid})")
            lower_name = game_name.lower()
            if ("proton" in lower_name or
                "steamworks" in lower_name or
                "steam linux runtime" in lower_name):
                continue
            last_played, playtime = play_data.get(appid, (0, 0))
            games.append((
                game_name,
                appid,
                last_played,
                playtime * 60  # Конвертируем минуты в секунды
            ))
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

def load_steam_apps():
    """
    Загружает список приложений Steam с использованием кэша (30 дней).
    """
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, "steam_apps.json")
    steam_apps = []
    cache_valid = False

    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            cache_valid = True

    if cache_valid:
        with open(cache_file, "rb") as f:
            steam_apps = orjson.loads(f.read())
        logger.info("Загружен кэш Steam приложений с %d записями", len(steam_apps))
        return steam_apps

    app_list_url = "https://raw.githubusercontent.com/BlackSnaker/PortProtonQt/refs/heads/main/data/games_appid_min.json"
    try:
        result = downloader.download_parallel(app_list_url, cache_file, timeout=5)
        if result:
            with open(result, "rb") as f:
                data = orjson.loads(f.read())
            if isinstance(data, dict):
                steam_apps = data.get("applist", {}).get("apps", [])
            else:
                steam_apps = data
            logger.info("Кэш Steam приложений сохранён с %d записями", len(steam_apps))
        else:
            steam_apps = []
    except Exception as e:
        logger.error("Ошибка загрузки списка Steam приложений: %s", e)
        steam_apps = []

    return steam_apps

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

@functools.lru_cache(maxsize=256)
def fetch_app_info_cached(app_id):
    """
    Получает подробную информацию об игре через Steam API
    Если данные уже сохранены локально (и кэш валиден), возвращает их.
    В противном случае загружает JSON-ответ по URL, сохраняет его в кэш и возвращает данные.
    """
    cached = load_app_details(app_id)
    if cached is not None:
        return cached

    lang = get_steam_language()
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l={lang}"

    # Определяем путь для сохранения кэшированного ответа
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")

    # Загружаем данные через Downloader
    result = downloader.download(url, cache_file, timeout=5)
    if not result:
        return None

    try:
        with open(result, "rb") as f:
            data = orjson.loads(f.read())
    except Exception as e:
        logger.error("Ошибка при чтении загруженной информации об игре: %s", e)
        return None

    details = data.get(str(app_id), {})
    if not details.get("success"):
        return None

    app_data = details.get("data", {})
    save_app_details(app_id, app_data)
    return app_data

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
    """Сохраняет данные ProtonDB для игры по appid в файл кеша."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")
    try:
        with open(cache_file, "wb") as f:
            f.write(orjson.dumps(data))
    except Exception as e:
        logger.error("Ошибка сохранения кеша ProtonDB для appid %s: %s", appid, e)

@functools.lru_cache(maxsize=256)
def get_protondb_tier(appid):
    """
    Получает статус ProtonDB для приложения.
    Сначала пытается загрузить данные из кеша, затем обращается к API ProtonDB
    и сохраняет результат в кеш.
    """
    cached = load_protondb_status(appid)
    if cached is not None:
        return cached.get("tier", "")

    url = f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"

    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"protondb_{appid}.json")

    result = downloader.download(url, cache_file, timeout=5)
    if not result:
        logger.info("Не удалось загрузить данные ProtonDB для appid %s", appid)
        return ""

    try:
        with open(result, "rb") as f:
            data = orjson.loads(f.read())
        tier = data.get("tier", "")
        save_protondb_status(appid, data)
        return tier
    except Exception as e:
        logger.info("Не удалось обработать данные ProtonDB для appid %s, ошибка: %s", appid, e)
        return ""

# Глобальные переменные для кэширования Steam-приложений и их индекса
_STEAM_APPS = None
_STEAM_APPS_INDEX = None

def get_steam_apps_and_index():
    """
    Загружает и кэширует список приложений Steam и построенный индекс.
    """
    global _STEAM_APPS, _STEAM_APPS_INDEX
    if _STEAM_APPS is None or _STEAM_APPS_INDEX is None:
        _STEAM_APPS = load_steam_apps()
        _STEAM_APPS_INDEX = build_index(_STEAM_APPS)
    return _STEAM_APPS, _STEAM_APPS_INDEX

def get_full_steam_game_info(appid):
    """Возвращает полную информацию об игре через Steam API"""
    app_info = fetch_app_info_cached(appid)
    if not app_info:
        return {}
    title = decode_text(app_info.get("name", ""))
    description = decode_text(app_info.get("short_description", ""))
    cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
    return {
        'description': description,
        'controller_support': app_info.get('controller_support', ''),
        'cover': cover,
        'protondb_tier': get_protondb_tier(appid),
        "steam_game": "true",
        "name": title
    }

def get_steam_game_info(desktop_name, exec_line):
    """
    Определяет информацию об игре по exec_line, используя метаданные файла,
    формируя список кандидатов, отбрасывая недопустимые, затем удаляя дубликаты,
    сортируя и выполняя поиск по списку Steam-приложений.
    """
    parts = shlex.split(exec_line)
    game_exe = parts[-1] if parts else exec_line

    # Если это bat-файл, открываем его и ищем путь к .exe
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
                logger.error("Ошибка при обработке bat файла %s: %s", game_exe, e)
        else:
            logger.error("Файл bat не найден: %s", game_exe)

    if not game_exe.lower().endswith('.exe'):
        logger.error("Получен некорректный путь к исполняемому файлу: %s. Ожидается .exe", game_exe)
        meta_data = {}
    else:
        meta_data = get_exiftool_data(game_exe)

    exe_name = os.path.splitext(os.path.basename(game_exe))[0]
    folder_path = os.path.dirname(game_exe)
    folder_name = os.path.basename(folder_path)
    if folder_name.lower() in ['bin', 'binaries']:
        folder_path = os.path.dirname(folder_path)
        folder_name = os.path.basename(folder_path)
    logger.info("Имя папки игры: '%s'", folder_name)
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
    logger.info("Исходные кандидаты: %s", candidates)
    candidates = filter_candidates(candidates)
    candidates = remove_duplicates(candidates)
    candidates_ordered = sorted(candidates, key=lambda s: len(s.split()), reverse=True)
    logger.info("Кандидаты после сортировки: %s", candidates_ordered)
    _, steam_apps_index = get_steam_apps_and_index()
    matching_app = None
    for candidate in candidates_ordered:
        if not candidate:
            continue
        matching_app = search_app(candidate, steam_apps_index)
        if matching_app:
            logger.info("Совпадение найдено для кандидата '%s': %s", candidate, matching_app.get("name"))
            break
    if not matching_app:
        return {
            "appid": "",
            "name": decode_text(f"{exe_name.capitalize()}"),
            "description": "",
            "cover": "",
            "controller_support": "",
            "protondb_tier": "",
            "steam_game": "false"
        }
    appid = matching_app["appid"]
    app_info = fetch_app_info_cached(appid)
    if not app_info:
        return {
            "appid": "",
            "name": decode_text(f"{exe_name.capitalize()}"),
            "description": "",
            "cover": "",
            "controller_support": "",
            "protondb_tier": "",
            "steam_game": "false"
        }
    title = decode_text(app_info.get("name", exe_name.capitalize()))
    description = decode_text(app_info.get("short_description", ""))
    cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
    controller_support = app_info.get("controller_support", "")
    protondb_tier = get_protondb_tier(appid)
    return {
        "appid": appid,
        "name": title,
        "description": description,
        "cover": cover,
        "controller_support": controller_support,
        "protondb_tier": protondb_tier,
        "steam_game": "false"
    }
