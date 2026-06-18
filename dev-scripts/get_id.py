#!/usr/bin/env python3

import os
import json
import asyncio
import aiohttp
import tarfile
import ssl

# Получаем ключи и данные из переменных окружения
STEAM_KEY = os.environ.get('STEAM_KEY')

# Флаги для включения/отключения источников
ENABLE_STEAM = os.environ.get('ENABLE_STEAM', 'true').lower() == 'true'
ENABLE_ANTICHEAT = os.environ.get('ENABLE_ANTICHEAT', 'true').lower() == 'true'
ENABLE_PPDB = os.environ.get('ENABLE_PPDB', 'true').lower() == 'true'
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'

# Конфигурация API
STEAM_BASE_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/?"
PPDB_RATINGS_URL = "https://ppdb.linux-gaming.ru/api/games/ratings?fields=id,name,overall_rating&has_reports=true"
CATEGORY_STEAM = "games"

# Отключаем предупреждения об SSL в дебаг-режиме
if DEBUG_MODE:
    print("DEBUG_MODE enabled: SSL verification is disabled (insecure, use for debugging only).")

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

def process_steam_apps(steam_apps):
    """
    Для каждого приложения из Steam добавляет ключ "normalized_name",
    содержащий нормализованное значение имени (поле "name"),
    и удаляет ненужные поля: "name", "last_modified", "price_change_number".
    """
    for app in steam_apps:
        original = app.get("name", "")
        if not app.get("normalized_name"):
            app["normalized_name"] = normalize_name(original)
        app.pop("name", None)
        app.pop("last_modified", None)
        app.pop("price_change_number", None)
    return steam_apps

async def get_app_list(session, last_appid, endpoint):
    """
    Получает часть списка приложений из API Steam.
    Если last_appid передан, добавляет его к URL для постраничной загрузки.
    """
    url = endpoint
    if last_appid:
        url = f"{url}&last_appid={last_appid}"
    async with session.get(url, verify_ssl=not DEBUG_MODE) as response:
        response.raise_for_status()
        return await response.json()

async def fetch_games_json(session):
    """
    Загружает JSON с данными из AreWeAntiCheatYet и извлекает normalized_name, status и slug.
    """
    url = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/HEAD/games.json"
    try:
        async with session.get(url, verify_ssl=not DEBUG_MODE) as response:
            response.raise_for_status()
            text = await response.text()
            data = json.loads(text)
            result = []
            for game in data:
                slug = game.get("slug") or game.get("id") or ""
                result.append({
                    "normalized_name": normalize_name(game["name"]),
                    "status": game["status"],
                    "slug": slug,
                })
            return result
    except Exception as error:
        print(f"Ошибка загрузки games.json: {error}")
        return []

async def fetch_ppdb_games(session):
    """
    Загружает JSON с данными PPDB и извлекает id, normalized_name и overall_rating.
    """
    try:
        async with session.get(PPDB_RATINGS_URL, verify_ssl=not DEBUG_MODE) as response:
            response.raise_for_status()
            data = await response.json()
            if isinstance(data, dict):
                data = next(
                    (
                        data[key]
                        for key in ("data", "results", "games", "items")
                        if isinstance(data.get(key), list)
                    ),
                    next((value for value in data.values() if isinstance(value, list)), []),
                )
            if not isinstance(data, list):
                print("Ошибка загрузки PPDB games ratings: неожиданный формат ответа")
                return []
            result = []
            for game in data:
                if not isinstance(game, dict):
                    continue
                result.append({
                    "id": game["id"],
                    "normalized_name": normalize_name(game["name"]),
                    "overall_rating": game.get("overall_rating"),
                })
            return result
    except Exception as error:
        print(f"Ошибка загрузки PPDB games ratings: {error}")
        return []

async def request_data():
    """
    Получает данные из Steam, AreWeAntiCheatYet и PPDB,
    обрабатывает их и сохраняет в JSON-файлы и tar.xz архивы.
    """
    output_json = []
    total_parsed = 0
    anticheat_games = []
    ppdb_games = []

    try:
        async with aiohttp.ClientSession() as session:
            # Загружаем данные Steam
            if ENABLE_STEAM:
                # Параметры запроса для Steam
                game_param = "&include_games=true"
                dlc_param = "&include_dlc=false"
                software_param = "&include_software=false"
                videos_param = "&include_videos=false"
                hardware_param = "&include_hardware=false"

                endpoint = (
                    f"{STEAM_BASE_URL}key={STEAM_KEY}"
                    f"{game_param}{dlc_param}{software_param}{videos_param}{hardware_param}"
                    f"&max_results=50000"
                )

                have_more_results = True
                last_appid_val = None
                while have_more_results:
                    app_list = await get_app_list(session, last_appid_val, endpoint)
                    apps = app_list['response']['apps']
                    apps = process_steam_apps(apps)
                    output_json.extend(apps)
                    total_parsed += len(apps)
                    have_more_results = app_list['response'].get('have_more_results', False)
                    last_appid_val = app_list['response'].get('last_appid')
                    print(f"Обработано {len(apps)} игр Steam, всего: {total_parsed}.")
            else:
                print("Пропущена загрузка данных Steam (ENABLE_STEAM=false).")

            # Загружаем данные AreWeAntiCheatYet
            if ENABLE_ANTICHEAT:
                anticheat_games = await fetch_games_json(session)
            else:
                print("Пропущена загрузка данных AreWeAntiCheatYet (ENABLE_ANTICHEAT=false).")

            # Загружаем данные PPDB
            if ENABLE_PPDB:
                ppdb_games = await fetch_ppdb_games(session)
            else:
                print("Пропущена загрузка данных PPDB (ENABLE_PPDB=false).")

    except Exception as error:
        print(f"Ошибка получения данных: {error}")
        return False

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Сохранение данных Steam
    if ENABLE_STEAM and output_json:
        output_json_full = os.path.join(data_dir, f"{CATEGORY_STEAM}_appid.json")
        output_json_min = os.path.join(data_dir, f"{CATEGORY_STEAM}_appid_min.json")
        with open(output_json_full, "w", encoding="utf-8") as f:
            json.dump(output_json, f, ensure_ascii=False, indent=2)
        with open(output_json_min, "w", encoding="utf-8") as f:
            json.dump(output_json, f, ensure_ascii=False, separators=(',',':'))

        # Упаковка минифицированного JSON Steam в tar.xz архив
        steam_archive_path = os.path.join(data_dir, f"{CATEGORY_STEAM}_appid.tar.xz")
        try:
            with tarfile.open(steam_archive_path, "w:xz", preset=9) as tar:
                tar.add(output_json_min, arcname=os.path.basename(output_json_min))
            print(f"Упаковано минифицированное JSON Steam в архив: {steam_archive_path}")
            os.remove(output_json_min)
        except Exception as e:
            print(f"Ошибка при упаковке архива Steam: {e}")
            return False

    # Сохранение данных AreWeAntiCheatYet
    if ENABLE_ANTICHEAT and anticheat_games:
        anticheat_json_full = os.path.join(data_dir, "anticheat_games.json")
        anticheat_json_min = os.path.join(data_dir, "anticheat_games_min.json")
        with open(anticheat_json_full, "w", encoding="utf-8") as f:
            json.dump(anticheat_games, f, ensure_ascii=False, indent=2)
        with open(anticheat_json_min, "w", encoding="utf-8") as f:
            json.dump(anticheat_games, f, ensure_ascii=False, separators=(',',':'))

        # Упаковка минифицированного JSON AreWeAntiCheatYet в tar.xz архив
        anticheat_archive_path = os.path.join(data_dir, "anticheat_games.tar.xz")
        try:
            with tarfile.open(anticheat_archive_path, "w:xz", preset=9) as tar:
                tar.add(anticheat_json_min, arcname=os.path.basename(anticheat_json_min))
            print(f"Упаковано минифицированное JSON AreWeAntiCheatYet в архив: {anticheat_archive_path}")
            os.remove(anticheat_json_min)
        except Exception as e:
            print(f"Ошибка при упаковке архива AreWeAntiCheatYet: {e}")
            return False

    # Сохранение данных PPDB
    if ENABLE_PPDB and ppdb_games:
        ppdb_json_full = os.path.join(data_dir, "ppdb_games.json")
        ppdb_json_min = os.path.join(data_dir, "ppdb_games_min.json")
        with open(ppdb_json_full, "w", encoding="utf-8") as f:
            json.dump(ppdb_games, f, ensure_ascii=False, indent=2)
        with open(ppdb_json_min, "w", encoding="utf-8") as f:
            json.dump(ppdb_games, f, ensure_ascii=False, separators=(',',':'))

        # Упаковка минифицированного JSON PPDB в tar.xz архив
        ppdb_archive_path = os.path.join(data_dir, "ppdb_games.tar.xz")
        try:
            with tarfile.open(ppdb_archive_path, "w:xz", preset=9) as tar:
                tar.add(ppdb_json_min, arcname=os.path.basename(ppdb_json_min))
            print(f"Упаковано минифицированное JSON PPDB в архив: {ppdb_archive_path}")
            os.remove(ppdb_json_min)
        except Exception as e:
            print(f"Ошибка при упаковке архива PPDB: {e}")
            return False

    return True

async def run():
    success = await request_data()
    if not success:
        exit(1)

if __name__ == "__main__":
    asyncio.run(run())
