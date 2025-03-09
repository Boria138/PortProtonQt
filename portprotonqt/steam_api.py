import os
import time
import shlex
import requests
import orjson
import subprocess
import requests
import re

def is_russian(text):
    """
    Проверяет, содержит ли текст русские буквы.
    """
    return bool(re.search("[а-яА-Я]", text))


def load_steam_apps(requests_session):
    """
    Загружает список приложений Steam с использованием кэширования (30 дней).
    """
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQT")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "steam_apps.json")
    cache_valid = False
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < 30 * 24 * 60 * 60:
            cache_valid = True

    if cache_valid:
        try:
            with open(cache_file, "rb") as f:
                steam_apps = orjson.loads(f.read())
            return steam_apps
        except Exception as e:
            print("Ошибка загрузки кэша:", e)

    app_list_url = "http://api.steampowered.com/ISteamApps/GetAppList/v2/"
    try:
        response = requests_session.get(app_list_url)
        if response.status_code == 200:
            data = response.json()
            steam_apps = data.get("applist", {}).get("apps", [])
            try:
                with open(cache_file, "wb") as f:
                    f.write(orjson.dumps(steam_apps))
            except Exception as e:
                print("Ошибка сохранения кэша:", e)
        else:
            steam_apps = []
    except Exception as e:
        print("Ошибка загрузки списка приложений Steam:", e)
        steam_apps = []
    return steam_apps

def build_index(steam_apps):
    """
    Строит индекс приложений для быстрого поиска по имени.
    """
    steam_apps_index = {}
    if not steam_apps:
        return steam_apps_index
    for app in steam_apps:
        name = app.get("name", "")
        if name:
            steam_apps_index[name.lower()] = app
    return steam_apps_index

def search_app(candidate, steam_apps_index):
    """
    Производит поиск приложения по имени:
      - сначала ищется точное совпадение,
      - затем поиск по подстроке.
    """
    candidate_lower = candidate.lower()
    if candidate_lower in steam_apps_index:
        return steam_apps_index[candidate_lower]
    for name_lower, app in steam_apps_index.items():
        if len(name_lower) < len(candidate_lower):
            continue
        if candidate_lower in name_lower:
            return app
    return None

def fetch_app_info(app_id, requests_session):
    """
    Получает подробную информацию об игре по appid.
    """
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=russian"
    try:
        response = requests_session.get(url)
        if response.status_code != 200:
            return None
        details = response.json().get(str(app_id), {})
        if not details.get("success"):
            return None
        return details.get("data", {})
    except Exception as e:
        print(f"Ошибка запроса данных для appid {app_id}: {e}")
        return None

def get_steam_game_info(desktop_name, exec_line, requests_session, steam_details_cache):
    """
    Определяет, есть ли информация об игре в Steam по различным вариантам имени.
    Если найдена, возвращает словарь с appid, названием, описанием и ссылкой на обложку.
    """
    try:
        parts = shlex.split(exec_line)
        game_exe = parts[3] if len(parts) >= 4 else exec_line
        folder_name = os.path.basename(os.path.dirname(game_exe)) if os.path.dirname(game_exe) else ""
        exe_name = os.path.splitext(os.path.basename(game_exe))[0]
        candidates = [desktop_name, folder_name, exe_name]

        steam_apps = load_steam_apps(requests_session)
        steam_apps_index = build_index(steam_apps)
        matching_app = None
        for candidate in candidates:
            if not candidate:
                continue
            matching_app = search_app(candidate, steam_apps_index)
            if matching_app:
                break

        if not matching_app:
            return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}

        appid = matching_app["appid"]
        if appid in steam_details_cache:
            app_info = steam_details_cache[appid]
        else:
            app_info = fetch_app_info(appid, requests_session)
            if not app_info:
                return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}
            fullgame_appid = app_info.get("fullgame", {}).get("appid")
            if fullgame_appid:
                if fullgame_appid in steam_details_cache:
                    app_info = steam_details_cache[fullgame_appid]
                    appid = fullgame_appid
                else:
                    fullgame_info = fetch_app_info(fullgame_appid, requests_session)
                    if fullgame_info:
                        app_info = fullgame_info
                        appid = fullgame_appid
                        steam_details_cache[fullgame_appid] = fullgame_info
            steam_details_cache[matching_app["appid"]] = app_info

        title = app_info.get("name", exe_name.capitalize())
        description = app_info.get("short_description", "")
        cover = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"

        if not is_russian(description):
            return {"appid": appid, "name": title, "description": "", "cover": cover}

        return {"appid": appid, "name": title, "description": description, "cover": cover}
    except Exception as e:
        print(f"Ошибка получения данных из Steam API: {e}")
        return {"appid": "", "name": exe_name.capitalize(), "description": "", "cover": ""}
