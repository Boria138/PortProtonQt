#!/usr/bin/env python

import os
import json
import asyncio
import aiohttp

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
    содержащий нормализованное значение имени (поле "name").
    """
    for app in steam_apps:
        name = app.get("name", "")
        if not app.get("normalized_name"):
            app["normalized_name"] = normalize_name(name)
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

async def request_data():
    """
    Получает данные списка приложений для категории "games" до тех пор,
    пока не закончатся результаты, обрабатывает данные для добавления нормализованных имён
    и записывает итоговый результат в JSON-файл.
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
        have_more_results = True
        last_appid_val = None
        async with aiohttp.ClientSession() as session:
            while have_more_results:
                app_list = await get_app_list(session, last_appid_val, endpoint)
                apps = app_list['response']['apps']
                # Обрабатываем приложения для добавления нормализованных имён.
                apps = process_steam_apps(apps)
                output_json.extend(apps)
                total_parsed += len(apps)
                have_more_results = app_list['response'].get('have_more_results', False)
                last_appid_val = app_list['response'].get('last_appid')

                print(f"Обработано {len(apps)} игр, всего: {total_parsed}.")
    except Exception as error:
        print(f"Ошибка получения данных для {category}: {error}")
        return

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path_formatted = os.path.join(data_dir, f"{category}_appid.json")
    with open(output_path_formatted, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)

    output_path_min = os.path.join(data_dir, f"{category}_appid_min.json")
    with open(output_path_min, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, separators=(',',':'))


async def run():
    await request_data()

if __name__ == "__main__":
    asyncio.run(run())
