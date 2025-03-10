import os
import time
import shlex
import subprocess
import orjson
import requests
import functools
import configparser

# Время жизни кэша – 30 дней (в секундах)
CACHE_DURATION = 30 * 24 * 60 * 60

def get_cache_dir():
    """Возвращает путь к каталогу кэша, создаёт его при необходимости."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQT")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

# Получаем метаданные из exe через exiftool
def get_exiftool_data(game_exe):
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
        print(f"Ошибка при запуске exiftool для {game_exe}: {e}")
        return {}

# Функция для загрузки списка приложений Steam с использованием кэша (30 дней)
def load_steam_apps(session):
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, "steam_apps.json")
    cache_valid = False
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_DURATION:
            cache_valid = True
    if cache_valid:
        try:
            with open(cache_file, "rb") as f:
                steam_apps = orjson.loads(f.read())
            return steam_apps
        except Exception as e:
            print("Ошибка загрузки кэша приложений:", e)
    app_list_url = "http://api.steampowered.com/ISteamApps/GetAppList/v2/"
    try:
        response = session.get(app_list_url)
        if response.status_code == 200:
            data = response.json()
            steam_apps = data.get("applist", {}).get("apps", [])
            try:
                with open(cache_file, "wb") as f:
                    f.write(orjson.dumps(steam_apps))
            except Exception as e:
                print("Ошибка сохранения кэша приложений:", e)
        else:
            steam_apps = []
    except Exception as e:
        print("Ошибка загрузки списка приложений Steam:", e)
        steam_apps = []
    return steam_apps

# Строим индекс приложений для быстрого поиска по имени (все имена приводятся к нижнему регистру)
def build_index(steam_apps):
    steam_apps_index = {}
    if not steam_apps:
        return steam_apps_index
    for app in steam_apps:
        name = app.get("name", "")
        if name:
            steam_apps_index[name.lower()] = app
    return steam_apps_index

# Поиск приложения по кандидату (точное совпадение или поиск подстроки)
def search_app(candidate, steam_apps_index):
    candidate_lower = candidate.lower()
    if candidate_lower in steam_apps_index:
        return steam_apps_index[candidate_lower]
    for name_lower, app in steam_apps_index.items():
        if len(name_lower) < len(candidate_lower):
            continue
        if candidate_lower in name_lower:
            return app
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
                print(f"Ошибка загрузки кэша для appid {app_id}: {e}")
    return None

def save_app_details(app_id, data):
    """Сохраняет данные по appid в файл кэша."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"steam_app_{app_id}.json")
    try:
        with open(cache_file, "wb") as f:
            f.write(orjson.dumps(data))
    except Exception as e:
        print(f"Ошибка сохранения кэша для appid {app_id}: {e}")

# Кэширование запроса к Steam API: результаты сохраняются в памяти (до 256 вариантов) и на диск
@functools.lru_cache(maxsize=256)
def fetch_app_info_cached(app_id, session_url):
    """
    Функция обращается к Steam API для получения подробной информации по appid.
    Сначала проверяется наличие файлового кэша, затем выполняется запрос.
    """
    # Проверяем файловый кэш
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
        # Сохраняем данные в файловый кэш
        save_app_details(app_id, app_data)
        return app_data
    except Exception as e:
        print(f"Ошибка запроса данных для appid {app_id}: {e}")
        return None

# Основная функция для получения информации об игре
def get_steam_game_info(desktop_name, exec_line, session):
    try:
        parts = shlex.split(exec_line)
        game_exe = parts[3] if len(parts) >= 4 else exec_line
    except Exception as e:
        print("Ошибка разбора exec_line:", e)
        game_exe = exec_line
    exe_name = os.path.splitext(os.path.basename(game_exe))[0]

    candidates = []
    # Получаем метаданные через exiftool
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

    # Убираем дубликаты с учётом регистра
    seen = set()
    candidates_ordered = []
    for cand in candidates:
        lower = cand.lower()
        if lower not in seen:
            seen.add(lower)
            candidates_ordered.append(cand)

    steam_apps = load_steam_apps(session)
    steam_apps_index = build_index(steam_apps)
    matching_app = None
    for candidate in candidates_ordered:
        if not candidate:
            continue
        matching_app = search_app(candidate, steam_apps_index)
        if matching_app:
            break

    if not matching_app:
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
    return {
        "appid": appid,
        "name": title,
        "description": description,
        "cover": cover,
        "controller_support": controller_support
    }
