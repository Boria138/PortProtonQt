#!/usr/bin/env python3

import os
import json
import asyncio
import aiohttp
import tarfile
import ssl

# Получаем ключи и данные из переменных окружения
STEAM_KEY = os.environ.get('STEAM_KEY')
LINUX_GAMING_API_KEY = os.environ.get('LINUX_GAMING_API_KEY')
LINUX_GAMING_API_USERNAME = os.environ.get('LINUX_GAMING_API_USERNAME')

# Флаги для включения/отключения источников
ENABLE_STEAM = os.environ.get('ENABLE_STEAM', 'true').lower() == 'true'
ENABLE_ANTICHEAT = os.environ.get('ENABLE_ANTICHEAT', 'true').lower() == 'true'
ENABLE_LINUX_GAMING = os.environ.get('ENABLE_LINUX_GAMING', 'true').lower() == 'true'
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'

# Конфигурация API
STEAM_BASE_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/?"
LINUX_GAMING_BASE_URL = "https://linux-gaming.ru"
CATEGORY_STEAM = "games"
CATEGORY_LINUX_GAMING = "ppdb"
LINUX_GAMING_HEADERS = {
    "Api-Key": LINUX_GAMING_API_KEY,
    "Api-Username": LINUX_GAMING_API_USERNAME
}

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
    Загружает JSON с данными из AreWeAntiCheatYet и извлекает поля normalized_name и status.
    """
    url = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/HEAD/games.json"
    try:
        async with session.get(url, verify_ssl=not DEBUG_MODE) as response:
            response.raise_for_status()
            text = await response.text()
            data = json.loads(text)
            return [{"normalized_name": normalize_name(game["name"]), "status": game["status"]} for game in data]
    except Exception as error:
        print(f"Ошибка загрузки games.json: {error}")
        return []

async def get_linux_gaming_topics(session, category_slug):
    page = 0
    all_topics = []
    max_pages = 100

    while page < max_pages:
        # Пробуем несколько вариантов URL
        urls_to_try = [
            f"{LINUX_GAMING_BASE_URL}/c/{category_slug}/5/l/latest.json",  # с id категории
            f"{LINUX_GAMING_BASE_URL}/c/{category_slug}/l/latest.json",     # только slug
            f"{LINUX_GAMING_BASE_URL}/c/5/l/latest.json",                  # только id
            f"{LINUX_GAMING_BASE_URL}/latest.json"                         # все темы
        ]

        success = False
        data = None

        for url in urls_to_try:
            try:
                # Добавляем параметры пагинации
                params = {
                    'page': page,
                    'order': 'default'
                }

                async with session.get(url, headers=LINUX_GAMING_HEADERS,
                                     params=params, verify_ssl=not DEBUG_MODE) as response:
                    if response.status == 429:
                        print(f"Слишком много запросов на странице {page}, ожидание...")
                        await asyncio.sleep(5)
                        continue

                    if response.status == 404:
                        if DEBUG_MODE:
                            print(f"URL не найден: {url}")
                        continue

                    response.raise_for_status()
                    data = await response.json()

                    # Проверяем структуру ответа
                    topic_list = data.get("topic_list", {})
                    topics = topic_list.get("topics", [])

                    if not topics:
                        if page == 0:
                            if DEBUG_MODE:
                                print(f"Нет тем в URL: {url}")
                            continue
                        else:
                            print(f"Страница {page} пуста, завершаем пагинацию.")
                            return all_topics

                    if DEBUG_MODE and page == 0:
                        print(f"Успешно подключились к URL: {url}")

                    success = True
                    break

            except Exception as e:
                if DEBUG_MODE:
                    print(f"Ошибка с URL {url}: {e}")
                continue

        if not success:
            print(f"Не удалось загрузить страницу {page}")
            break

        # Обрабатываем темы (этот блок должен быть внутри основного цикла)
        try:
            topic_list = data.get("topic_list", {})
            topics = topic_list.get("topics", [])

            page_topics_added = 0
            for topic in topics:
                slug = topic["slug"]

                # Пропускаем тему описания категории
                if slug is None or slug == "opisanie-kategorii-portprotondb":
                    if DEBUG_MODE:
                        print(f"Пропущена тема описания категории")
                    continue

                normalized_title = normalize_name(topic["title"])

                # Добавляем только валидные темы
                all_topics.append({
                    "normalized_title": normalized_title,
                    "slug": slug,
                })
                page_topics_added += 1

                if DEBUG_MODE and page_topics_added <= 3:  # Показываем первые 3 темы
                    print(f"Добавлена тема: {normalized_title} (slug: {slug}")

            print(f"Обработано {len(topics)} тем на странице {page}, добавлено: {page_topics_added}, всего: {len(all_topics)}.")

            # Проверяем, есть ли еще страницы
            more_topics_url = topic_list.get("more_topics_url")
            if not more_topics_url:
                print("Больше тем нет, завершаем пагинацию.")
                break

            page += 1

            # Добавляем небольшую задержку между запросами
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"Ошибка при обработке тем на странице {page}: {e}")
            break

    if not all_topics:
        print("Предупреждение: не удалось получить ни одной темы из linux-gaming.ru.")
    else:
        print(f"Всего получено {len(all_topics)} тем из категории {category_slug}")

    return all_topics


async def request_data():
    """
    Получает данные из Steam, AreWeAntiCheatYet и linux-gaming.ru,
    обрабатывает их и сохраняет в JSON-файлы и tar.xz архивы.
    """
    output_json = []
    total_parsed = 0
    linux_gaming_topics = []
    anticheat_games = []

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

            # Загружаем данные linux-gaming.ru
            if ENABLE_LINUX_GAMING:
                if LINUX_GAMING_API_KEY and LINUX_GAMING_API_USERNAME:
                    linux_gaming_topics = await get_linux_gaming_topics(session, CATEGORY_LINUX_GAMING)
                else:
                    print("Предупреждение: LINUX_GAMING_API_KEY или LINUX_GAMING_API_USERNAME не установлены.")
            else:
                print("Пропущена загрузка данных linux-gaming.ru (ENABLE_LINUX_GAMING=false).")

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

    # Сохранение данных linux-gaming.ru
    if ENABLE_LINUX_GAMING and linux_gaming_topics:
        linux_gaming_json_full = os.path.join(data_dir, "linux_gaming_topics.json")
        linux_gaming_json_min = os.path.join(data_dir, "linux_gaming_topics_min.json")
        with open(linux_gaming_json_full, "w", encoding="utf-8") as f:
            json.dump(linux_gaming_topics, f, ensure_ascii=False, indent=2)
        with open(linux_gaming_json_min, "w", encoding="utf-8") as f:
            json.dump(linux_gaming_topics, f, ensure_ascii=False, separators=(',',':'))

        # Упаковка минифицированного JSON linux-gaming.ru в tar.xz архив
        linux_gaming_archive_path = os.path.join(data_dir, "linux_gaming_topics.tar.xz")
        try:
            with tarfile.open(linux_gaming_archive_path, "w:xz", preset=9) as tar:
                tar.add(linux_gaming_json_min, arcname=os.path.basename(linux_gaming_json_min))
            print(f"Упаковано минифицированное JSON linux-gaming.ru в архив: {linux_gaming_archive_path}")
            os.remove(linux_gaming_json_min)
        except Exception as e:
            print(f"Ошибка при упаковке архива linux-gaming.ru: {e}")
            return False

    return True

async def run():
    success = await request_data()
    if not success:
        exit(1)

if __name__ == "__main__":
    asyncio.run(run())
