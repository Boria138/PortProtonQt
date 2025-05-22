#!/usr/bin/env python3

import os
import json
import asyncio
import aiohttp
import tarfile


# Получаем ключ Steam из переменной окружения.
key = os.environ.get('STEAM_KEY')
base_url = "https://api.steampowered.com/IStoreService/GetAppList/v1/?"
category = "games"

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

    # Удаляем служебные слова, которые не должны влиять на сопоставление
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
        # Удаляем ненужные поля
        app.pop("name", None)
        app.pop("last_modified", None)
        app.pop("price_change_number", None)
    return steam_apps


async def get_app_list(session, last_appid, endpoint):
    """
    Получает часть списка приложений из API.
    Если last_appid передан, добавляет его к URL для постраничной загрузки.
    """
    url = endpoint
    if last_appid:
        url = f"{url}&last_appid={last_appid}"
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


async def fetch_games_json(session):
    """
    Загружает JSON с данными из AreWeAntiCheatYet и извлекает поля normalized_name и status.
    """
    url = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/HEAD/games.json"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            # Извлекаем только поля normalized_name и status
            return [{"normalized_name": normalize_name(game["name"]), "status": game["status"]} for game in data]
    except Exception as error:
        print(f"Ошибка загрузки games.json: {error}")
        return []


async def request_data():
    """
    Получает данные списка приложений для категории "games" до тех пор,
    пока не закончатся результаты, обрабатывает данные для добавления
    нормализованных имён и записывает итоговый результат в JSON-файл.
    Отдельно загружает games.json и сохраняет его в отдельный JSON-файл.
    """
    # Параметры запроса для игр.
    game_param = "&include_games=true"
    dlc_param = "&include_dlc=false"
    software_param = "&include_software=false"
    videos_param = "&include_videos=false"
    hardware_param = "&include_hardware=false"

    endpoint = (
        f"{base_url}key={key}"
        f"{game_param}{dlc_param}{software_param}{videos_param}{hardware_param}"
        f"&max_results=50000"
    )

    output_json = []
    total_parsed = 0

    try:
        async with aiohttp.ClientSession() as session:
            # Загружаем данные Steam
            have_more_results = True
            last_appid_val = None
            while have_more_results:
                app_list = await get_app_list(session, last_appid_val, endpoint)
                apps = app_list['response']['apps']
                # Обрабатываем приложения для добавления нормализованных имён
                apps = process_steam_apps(apps)
                output_json.extend(apps)
                total_parsed += len(apps)
                have_more_results = app_list['response'].get('have_more_results', False)
                last_appid_val = app_list['response'].get('last_appid')

                print(f"Обработано {len(apps)} игр, всего: {total_parsed}.")

            # Загружаем и сохраняем games.json отдельно
            anticheat_games = await fetch_games_json(session)

    except Exception as error:
        print(f"Ошибка получения данных для {category}: {error}")
        return False

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Путь к JSON-файлам для Steam
    output_json_full = os.path.join(data_dir, f"{category}_appid.json")
    output_json_min = os.path.join(data_dir, f"{category}_appid_min.json")

    # Записываем полные данные Steam с отступами
    with open(output_json_full, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)

    # Записываем минимизированные данные Steam
    with open(output_json_min, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, separators=(',',':'))

    # Путь к JSON-файлам для AreWeAntiCheatYet
    anticheat_json_full = os.path.join(data_dir, "anticheat_games.json")
    anticheat_json_min = os.path.join(data_dir, "anticheat_games_min.json")

    # Записываем полные данные AreWeAntiCheatYet с отступами
    with open(anticheat_json_full, "w", encoding="utf-8") as f:
        json.dump(anticheat_games, f, ensure_ascii=False, indent=2)

    # Записываем минимизированные данные AreWeAntiCheatYet
    with open(anticheat_json_min, "w", encoding="utf-8") as f:
        json.dump(anticheat_games, f, ensure_ascii=False, separators=(',',':'))

    # Упаковка только минифицированных JSON в tar.xz архивы с максимальным сжатием
    # Архив для Steam
    steam_archive_path = os.path.join(data_dir, f"{category}_appid.tar.xz")
    try:
        with tarfile.open(steam_archive_path, "w:xz", preset=9) as tar:
            tar.add(output_json_min, arcname=os.path.basename(output_json_min))
        print(f"Упаковано минифицированное JSON Steam в архив: {steam_archive_path}")
        # Удаляем исходный минифицированный файл после упаковки
        os.remove(output_json_min)
    except Exception as e:
        print(f"Ошибка при упаковке архива Steam: {e}")
        return False

    # Архив для AreWeAntiCheatYet
    anticheat_archive_path = os.path.join(data_dir, "anticheat_games.tar.xz")
    try:
        with tarfile.open(anticheat_archive_path, "w:xz", preset=9) as tar:
            tar.add(anticheat_json_min, arcname=os.path.basename(anticheat_json_min))
        print(f"Упаковано минифицированное JSON AreWeAntiCheatYet в архив: {anticheat_archive_path}")
        # Удаляем исходный минифицированный файл после упаковки
        os.remove(anticheat_json_min)
    except Exception as e:
        print(f"Ошибка при упаковке архива AreWeAntiCheatYet: {e}")
        return False

    return True


async def run():
    success = await request_data()
    if not success:
        exit(1)


if __name__ == "__main__":
    asyncio.run(run())
