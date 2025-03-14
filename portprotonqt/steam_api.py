import functools
import logging
import os
import shlex
import subprocess
import time

import orjson
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Время жизни кэша – 30 дней (можно вынести в настройки)
CACHE_DURATION = 30 * 24 * 60 * 60

def get_cache_dir():
    """Возвращает путь к каталогу кэша, создаёт его при необходимости."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQT")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def normalize_name(s):
    """
    Приведение строки к нормальному виду:
      - перевод в нижний регистр,
      - удаление символов ™ и ®,
      - замена разделителей (-, :, ,) на пробел,
      - удаление лишних пробелов,
      - удаление суффиксов 'bin' или 'app' в конце строки.
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
    return s

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
    Выводит список отсеянных кандидатов и возвращает список допустимых.
    """
    valid = []
    dropped = []
    for cand in candidates:
        if is_valid_candidate(cand):
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
    """Получает метаданные через exiftool."""
    try:
        proc = subprocess.run(
            ["exiftool", "-j", game_exe],
            capture_output=True,
            text=True,
            check=True
        )
        meta_data_list = orjson.loads(proc.stdout.encode("utf-8"))
        return meta_data_list[0] if meta_data_list else {}
    except Exception:
        return {}

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
            logger.info("Загружен кэш Steam приложений с %d записями", len(steam_apps))
            return steam_apps
        except Exception as e:
            logger.error("Ошибка загрузки кэша приложений: %s", e)
    app_list_url = "https://raw.githubusercontent.com/BlackSnaker/PortProtonQt/refs/heads/main/data/games_appid_min.json"
    try:
        response = session.get(app_list_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                steam_apps = data.get("applist", {}).get("apps", [])
            else:
                steam_apps = data
            try:
                with open(cache_file, "wb") as f:
                    f.write(orjson.dumps(steam_apps))
                logger.info("Кэш Steam приложений сохранён с %d записями", len(steam_apps))
            except Exception as e:
                logger.error("Ошибка сохранения кэша приложений: %s", e)
        else:
            steam_apps = []
    except Exception as e:
        logger.error("Ошибка загрузки списка приложений Steam: %s", e)
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
                logger.info("    Найдено частичное совпадение с достаточной схожестью: кандидат '%s' в '%s' (ratio: %.2f)",
                            candidate_norm, name_norm, ratio)
                return app
            else:
                logger.info("    Частичное совпадение, но соотношение длин недостаточно: кандидат '%s' в '%s' (ratio: %.2f)",
                            candidate_norm, name_norm, ratio)
    logger.info("    Приложение для кандидата '%s' не найдено", candidate_norm)
    return None

def load_app_details(app_id):
    """Загружает кэшированные данные для игры по appid, если они не устарели."""
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
def fetch_app_info_cached(app_id):
    """
    Получает подробную информацию об игре через Steam API с использованием кэша.
    """
    cached = load_app_details(app_id)
    if cached is not None:
        return cached
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=russian"
    try:
        response = requests.get(url, timeout=5)
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

# Глобальные переменные для кэширования Steam-приложений и их индекса
_STEAM_APPS = None
_STEAM_APPS_INDEX = None

def get_steam_apps_and_index(session):
    """
    Загружает и кэширует список приложений Steam и построенный индекс.
    """
    global _STEAM_APPS, _STEAM_APPS_INDEX
    if _STEAM_APPS is None or _STEAM_APPS_INDEX is None:
        _STEAM_APPS = load_steam_apps(session)
        _STEAM_APPS_INDEX = build_index(_STEAM_APPS)
    return _STEAM_APPS, _STEAM_APPS_INDEX

def get_steam_game_info(desktop_name, exec_line, session):
    """
    Определяет информацию об игре по exec_line, используя метаданные файла,
    формируя список кандидатов, отбрасывая недопустимые, затем удаляя дубликаты,
    сортируя и выполняя поиск по списку Steam-приложений.
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
    logger.info("Имя папки игры: '%s'", folder_name)

    # Формирование списка кандидатов
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

    logger.info("Исходные кандидаты: %s", candidates)

    # Сначала отбрасываем недопустимые кандидаты
    candidates = filter_candidates(candidates)
    # Затем удаляем дубликаты, сохраняя порядок
    candidates = remove_duplicates(candidates)
    logger.info("Кандидаты после фильтрации и удаления дублей: %s", candidates)

    # Сортируем кандидатов по количеству слов (от большего к меньшему)
    candidates_ordered = sorted(candidates, key=lambda s: len(s.split()), reverse=True)
    logger.info("Кандидаты после сортировки: %s", candidates_ordered)

    # Используем глобальное кэширование Steam-приложений и их индекса
    _, steam_apps_index = get_steam_apps_and_index(session)
    matching_app = None
    for candidate in candidates_ordered:
        if not candidate:
            continue
        matching_app = search_app(candidate, steam_apps_index)
        if matching_app:
            logger.info("Совпадение найдено для кандидата '%s': %s", candidate, matching_app.get("name"))
            break

    if not matching_app:
        logger.info("Не найдено ни одного совпадения для кандидатов")
        return {
            "appid": "",
            "name": exe_name.capitalize(),
            "description": "",
            "cover": "",
            "controller_support": ""
        }

    appid = matching_app["appid"]
    app_info = fetch_app_info_cached(appid)
    if not app_info:
        logger.info("Не удалось получить информацию для appid %s", appid)
        return {
            "appid": "",
            "name": exe_name.capitalize(),
            "description": "",
            "cover": "",
            "controller_support": ""
        }

    title = app_info.get("name", exe_name.capitalize())
    description = app_info.get("short_description", "")
    cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
    controller_support = app_info.get("controller_support", "")
    logger.info("Итоговая информация об игре: appid=%s, name='%s'", appid, title)
    return {
        "appid": appid,
        "name": title,
        "description": description,
        "cover": cover,
        "controller_support": controller_support
    }
