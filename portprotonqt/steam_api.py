import os
import time
import shlex
import subprocess
import orjson
import requests
import functools
import configparser
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Время жизни кэша – 30 дней (в секундах)
CACHE_DURATION = 30 * 24 * 60 * 60

def get_cache_dir():
    """Возвращает путь к каталогу кэша, создаёт его при необходимости."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQT")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def normalize_name(s):
    """
    Нормализует строку:
      - приводит к нижнему регистру,
      - удаляет символы торговых марок,
      - заменяет разделители (-, :, ,) на пробел,
      - убирает лишние пробелы,
      - если строка оканчивается на 'bin' или 'app', удаляет этот суффикс.
    """
    s_original = s
    s = s.lower()
    for ch in ["™", "®"]:
        s = s.replace(ch, "")
    for ch in ["-", ":", ","]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    for suffix in ["bin", "app"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    return s

def is_valid_candidate(candidate):
    """
    Возвращает False, если кандидат содержит запрещённые подстроки:
      - win32
      - win64
      - win 64 shipping
      - gamelauncher
    Нормализуем кандидата перед проверкой.
    """
    normalized_candidate = candidate.lower().replace("-", " ")
    normalized_candidate = " ".join(normalized_candidate.split())
    forbidden = ["win32", "win64", "win 64 shipping", "gamelauncher"]
    for token in forbidden:
        if token in normalized_candidate:
            logger.debug("Отбрасываю кандидата '%s' (нормализовано: '%s') из-за '%s'",
                         candidate, normalized_candidate, token)
            return False
    return True

@functools.lru_cache(maxsize=128)
def get_exiftool_data(game_exe):
    """Получает метаданные из exe через exiftool."""
    try:
        proc = subprocess.run(
            ["exiftool", "-j", game_exe],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        meta_data_list = orjson.loads(proc.stdout.encode("utf-8"))
        return meta_data_list[0] if meta_data_list else {}
    except Exception as e:
        return {}

def process_steam_apps(steam_apps):
    """
    Для каждого приложения из Steam добавляет ключ "normalized_name",
    содержащий нормализованное значение имени (поле "name").
    """
    for app in steam_apps:
        name = app.get("name", "")
        if not app.get("normalized_name"):
            app["normalized_name"] = normalize_name(name)
    return steam_apps

def load_steam_apps(session):
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
        try:
            with open(cache_file, "rb") as f:
                steam_apps = orjson.loads(f.read())
            steam_apps = process_steam_apps(steam_apps)
            logger.debug("Загружен кэш Steam приложений с %d записями", len(steam_apps))
            return steam_apps
        except Exception as e:
            logger.error("Ошибка загрузки кэша приложений: %s", e)
    app_list_url = "http://api.steampowered.com/ISteamApps/GetAppList/v2/"
    try:
        response = session.get(app_list_url)
        if response.status_code == 200:
            data = response.json()
            steam_apps = data.get("applist", {}).get("apps", [])
            steam_apps = process_steam_apps(steam_apps)
            try:
                with open(cache_file, "wb") as f:
                    f.write(orjson.dumps(steam_apps))
                logger.debug("Кэш Steam приложений сохранён с %d записями", len(steam_apps))
            except Exception as e:
                logger.error("Ошибка сохранения кэша приложений: %s", e)
        else:
            steam_apps = []
    except Exception as e:
        logger.error("Ошибка загрузки списка приложений Steam: %s", e)
        steam_apps = []
    return steam_apps

def load_index_cache(steam_apps):
    """
    Загружает кэшированный индекс приложений из файла, если он актуален.
    Если кэша нет или он просрочен, строит индекс из steam_apps и сохраняет его.
    """
    cache_dir = get_cache_dir()
    index_file = os.path.join(cache_dir, "steam_apps_index.json")
    index = {}
    if os.path.exists(index_file):
        if time.time() - os.path.getmtime(index_file) < CACHE_DURATION:
            try:
                with open(index_file, "rb") as f:
                    index = orjson.loads(f.read())
                logger.debug("Загружен кэш индекса Steam приложений с %d записями", len(index))
                return index
            except Exception as e:
                logger.error("Ошибка загрузки кэша индекса: %s", e)
    # Если кэша нет или он просрочен, строим индекс заново
    for app in steam_apps:
        normalized = app.get("normalized_name")
        if normalized:
            index[normalized] = app
    try:
        with open(index_file, "wb") as f:
            f.write(orjson.dumps(index))
        logger.debug("Сохранён кэш индекса Steam приложений с %d записями", len(index))
    except Exception as e:
        logger.error("Ошибка сохранения кэша индекса: %s", e)
    return index

def search_app(candidate, steam_apps_index):
    """
    Ищет приложение по кандидату (точное совпадение или поиск подстроки).
    """
    candidate_norm = normalize_name(candidate)
    logger.debug("Поиск приложения для кандидата: '%s' -> '%s'", candidate, candidate_norm)
    if candidate_norm in steam_apps_index:
        logger.debug("Найдено точное совпадение: '%s'", candidate_norm)
        return steam_apps_index[candidate_norm]
    if " " in candidate_norm:
        for name_norm, app in steam_apps_index.items():
            if candidate_norm in name_norm:
                logger.debug("Найдено частичное совпадение: '%s' в '%s'", candidate_norm, name_norm)
                return app
    logger.debug("Приложение для кандидата '%s' не найдено", candidate_norm)
    return None

def load_app_details(app_id):
    """Пытается загрузить кэшированные данные для игры по appid из файла."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            try:
                with open(cache_file, "rb") as f:
                    return orjson.loads(f.read())
            except Exception as e:
                logger.error("Ошибка загрузки кэша для appid %s: %s", app_id, e)
    return None

def save_app_details(app_id, data):
    """Сохраняет данные по appid в файл кэша."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    try:
        with open(cache_file, "wb") as f:
            f.write(orjson.dumps(data))
    except Exception as e:
        logger.error("Ошибка сохранения кэша для appid %s: %s", app_id, e)

@functools.lru_cache(maxsize=256)
def fetch_app_info_cached(app_id, session_url):
    """
    Обращается к Steam API для получения подробной информации по appid.
    Сначала проверяется файловый кэш, затем выполняется запрос.
    """
    cached = load_app_details(app_id)
    if cached is not None:
        return cached
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=russian"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None
        data = response.json()
        details = data.get(str(app_id), {})
        if not details.get("success"):
            return None
        app_data = details.get("data", {})
        save_app_details(app_id, app_data)
        return app_data
    except Exception as e:
        logger.error("Ошибка запроса данных для appid %s: %s", app_id, e)
        return None

def get_steam_game_info(desktop_name, exec_line, session):
    """
    Получает информацию об игре из Steam, используя список приложений.
    """
    try:
        parts = shlex.split(exec_line)
        game_exe = parts[3] if len(parts) >= 4 else exec_line
    except Exception as e:
        logger.error("Ошибка разбора exec_line: %s", e)
        game_exe = exec_line
    exe_name = os.path.splitext(os.path.basename(game_exe))[0]

    folder_path = os.path.dirname(game_exe)
    folder_name = os.path.basename(folder_path)
    if folder_name.lower() in ['bin', 'binaries']:
        folder_path = os.path.dirname(folder_path)
        folder_name = os.path.basename(folder_path)
    logger.debug("Имя папки игры: '%s'", folder_name)

    candidates = []
    meta_data = get_exiftool_data(game_exe)
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

    logger.debug("Исходные кандидаты: %s", candidates)
    candidates = [cand for cand in candidates if is_valid_candidate(cand)]
    logger.debug("Кандидаты после фильтрации: %s", candidates)
    candidates_ordered = sorted(candidates, key=lambda s: len(s.split()), reverse=True)
    logger.debug("Кандидаты после сортировки: %s", candidates_ordered)

    steam_apps = load_steam_apps(session)
    steam_apps_index = load_index_cache(steam_apps)
    matching_app = None
    for candidate in candidates_ordered:
        if not candidate:
            continue
        matching_app = search_app(candidate, steam_apps_index)
        if matching_app:
            logger.debug("Совпадение найдено для '%s': %s", candidate, matching_app.get("name"))
            break

    if not matching_app:
        logger.debug("Совпадений не найдено")
        return {
            "appid": "",
            "name": exe_name.capitalize(),
            "description": "",
            "cover": "",
            "controller_support": ""
        }

    appid = matching_app["appid"]
    app_info = fetch_app_info_cached(appid, f"{appid}_russian")
    if not app_info:
        logger.debug("Нет данных для appid %s", appid)
        return {
            "appid": "",
            "name": exe_name.capitalize(),
            "description": "",
            "cover": "",
            "controller_support": ""
        }

    fullgame_appid = app_info.get("fullgame", {}).get("appid")
    if fullgame_appid:
        fullgame_info = fetch_app_info_cached(fullgame_appid, f"{fullgame_appid}_russian")
        if fullgame_info:
            app_info = fullgame_info
            appid = fullgame_appid

    title = app_info.get("name", exe_name.capitalize())
    description = app_info.get("short_description", "")
    cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
    controller_support = app_info.get("controller_support", "")
    logger.debug("Информация об игре: appid=%s, name='%s'", appid, title)
    return {
        "appid": appid,
        "name": title,
        "description": description,
        "cover": cover,
        "controller_support": controller_support
    }

def load_cached_anticheat_json():
    """
    Загружает JSON с данными AreWeAntiCheatYet из кэша, если он актуален,
    иначе – запрашивает с GitHub и сохраняет в кэш.
    """
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, "areweanticheatyet.json")
    use_cache = False
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            use_cache = True
    if use_cache:
        try:
            with open(cache_file, "rb") as f:
                data = orjson.loads(f.read())
            logger.debug("Загружен кэш AreWeAntiCheatYet с %d записями", len(data))
            return data
        except Exception as e:
            logger.error("Ошибка загрузки кэша AreWeAntiCheatYet: %s", e)
    url = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logger.error("Ошибка загрузки JSON AreWeAntiCheatYet: %s", response.status_code)
            return []
        data = response.json()
        try:
            with open(cache_file, "wb") as f:
                f.write(orjson.dumps(data))
            logger.debug("Сохранён кэш AreWeAntiCheatYet с %d записями", len(data))
        except Exception as e:
            logger.error("Ошибка сохранения кэша AreWeAntiCheatYet: %s", e)
        return data
    except Exception as e:
        logger.error("Ошибка запроса JSON AreWeAntiCheatYet: %s", e)
        return []

def get_anticheat_status(appid, game_name=None):
    """
    Получает исключительно статус античита из кэшированного JSON AreWeAntiCheatYet.
    Если в записи есть storeIds.steam, сравнивает с appid.
    Если нет – ищет по нормализованному названию (game_name).
    """
    games = load_cached_anticheat_json()
    normalized_game_name = normalize_name(game_name) if game_name else ""
    for game in games:
        store_ids = game.get("storeIds", {})
        steam_id = store_ids.get("steam")
        if steam_id:
            if str(steam_id) == str(appid):
                logger.debug("Найдена запись античита для appid %s", appid)
                return game
        else:
            slug = normalize_name(game.get("slug", ""))
            name_norm = normalize_name(game.get("name", ""))
            if normalized_game_name and (slug == normalized_game_name or name_norm == normalized_game_name):
                logger.debug("Найдена запись античита по названию '%s'", game_name)
                return game
    logger.debug("Запись античита для appid %s (или игры '%s') не найдена", appid, game_name)
    return {}
