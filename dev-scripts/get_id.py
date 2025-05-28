#!/usr/bin/env python3

import os
import json
import asyncio
import aiohttp
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from epicstore_api import EpicGamesStoreAPI
from requests.exceptions import JSONDecodeError

# Получаем ключ Steam из переменной окружения
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

    keywords_to_remove = {"ultimate", "edition", "definitive", "complete", "remastered"}
    words = s.split()
    filtered_words = [word for word in words if word not in keywords_to_remove]
    return " ".join(filtered_words)

def process_steam_apps(steam_apps):
    """
    Для каждого приложения из Steam добавляет ключ 'normalized_name',
    содержащий нормализованное значение имени (поле 'name'),
    и удаляет ненужные поля: 'name', 'last_modified', 'price_change_number'.
    """
    for app in steam_apps:
        original = app.get("name", "")
        if not app.get("normalized_name"):
            app["normalized_name"] = normalize_name(original)
        app.pop("name", None)
        app.pop("last_modified", None)
        app.pop("price_change_number", None)
    return steam_apps

def fetch_all_epic_products_sync(
    api: EpicGamesStoreAPI,
    sort_by: str = 'releaseDate',
    sort_dir: str = 'DESC',
    page_size: int = 100,
    pause: float = 0.5,
) -> list:
    """
    Синхронно загружает все продукты из Epic Store постранично.
    """
    all_products = []
    start = 0

    while True:
        try:
            resp = api.fetch_store_games(
                count=page_size,
                start=start,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
        except JSONDecodeError:
            print("Получен неожиданный (не-JSON) ответ от Epic — выходим из цикла.")
            break
        except Exception as e:
            print(f"Ошибка запроса Epic: {e!r} — выходим из цикла.")
            break

        data = resp.get('data', {}).get('Catalog', {}).get('searchStore', {})
        items = data.get('elements') or []
        if not items:
            print("Новых продуктов Epic не найдено — все данные загружены.")
            break

        all_products.extend(items)
        start += page_size
        print(f"Загружено записей Epic: {len(all_products)}…")
        time.sleep(pause)

    return all_products

def extract_epic_titles_and_slugs(products: list) -> list:
    """
    Извлекает из каждого продукта Epic только title и чистый slug.
    """
    result = []
    for prod in products:
        title = prod.get('title') or prod.get('productName') or prod.get('titleText')
        raw_slug = prod.get('productSlug', '')
        clean_slug = raw_slug.split('/')[-1]
        result.append({
            'title': title,
            'slug': clean_slug
        })
    return result

async def fetch_epic_products():
    """
    Асинхронно вызывает синхронную функцию Epic Games API через пул потоков.
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        api = EpicGamesStoreAPI()
        products = await loop.run_in_executor(pool, fetch_all_epic_products_sync, api)
        return extract_epic_titles_and_slugs(products)

async def get_app_list(session, last_appid, endpoint):
    """
    Получает часть списка приложений из Steam API.
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
            text = await response.text()
            data = json.loads(text)
            return [{"normalized_name": normalize_name(game["name"]), "status": game["status"]} for game in data]
    except Exception as error:
        print(f"Ошибка загрузки games.json: {error}")
        return []

async def request_data():
    """
    Получает данные из Steam API, AreWeAntiCheatYet и Epic Games Store,
    обрабатывает их и сохраняет в JSON-файлы и архивы.
    """
    # Параметры запроса для Steam
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
    anticheat_games = []
    epic_products = []

    try:
        async with aiohttp.ClientSession() as session:
            # Загружаем данные Steam
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

            # Загружаем данные AreWeAntiCheatYet
            anticheat_games = await fetch_games_json(session)

            # Загружаем данные Epic Games
            epic_products = await fetch_epic_products()
            print(f"Всего записей Epic: {len(epic_products)}")

    except Exception as error:
        print(f"Ошибка получения данных: {error}")
        return False

    # Создаём директорию для данных
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Путь к JSON-файлам для Steam
    steam_json_full = os.path.join(data_dir, f"{category}_appid.json")
    steam_json_min = os.path.join(data_dir, f"{category}_appid_min.json")

    # Записываем полные данные Steam
    with open(steam_json_full, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)

    # Записываем минифицированные данные Steam
    with open(steam_json_min, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, separators=(',',':'))

    # Путь к JSON-файлам для AreWeAntiCheatYet
    anticheat_json_full = os.path.join(data_dir, "anticheat_games.json")
    anticheat_json_min = os.path.join(data_dir, "anticheat_games_min.json")

    # Записываем полные данные AreWeAntiCheatYet
    with open(anticheat_json_full, "w", encoding="utf-8") as f:
        json.dump(anticheat_games, f, ensure_ascii=False, indent=2)

    # Записываем минифицированные данные AreWeAntiCheatYet
    with open(anticheat_json_min, "w", encoding="utf-8") as f:
        json.dump(anticheat_games, f, ensure_ascii=False, separators=(',',':'))

    # Путь к JSON-файлам для Epic Games
    epic_json_full = os.path.join(data_dir, "egs_games.json")
    epic_json_min = os.path.join(data_dir, "egs_games_min.json")

    # Записываем полные данные Epic Games
    with open(epic_json_full, "w", encoding="utf-8") as f:
        json.dump(epic_products, f, ensure_ascii=False, indent=2)

    # Записываем минифицированные данные Epic Games
    with open(epic_json_min, "w", encoding="utf-8") as f:
        json.dump(epic_products, f, ensure_ascii=False, separators=(',',':'))

    # Упаковка минифицированных JSON в tar.xz архивы
    # Архив для Steam
    steam_archive_path = os.path.join(data_dir, f"{category}_appid.tar.xz")
    try:
        with tarfile.open(steam_archive_path, "w:xz", preset=9) as tar:
            tar.add(steam_json_min, arcname=os.path.basename(steam_json_min))
        print(f"Упаковано минифицированное JSON Steam в архив: {steam_archive_path}")
        os.remove(steam_json_min)
    except Exception as e:
        print(f"Ошибка при упаковке архива Steam: {e}")
        return False

    # Архив для AreWeAntiCheatYet
    anticheat_archive_path = os.path.join(data_dir, "anticheat_games.tar.xz")
    try:
        with tarfile.open(anticheat_archive_path, "w:xz", preset=9) as tar:
            tar.add(anticheat_json_min, arcname=os.path.basename(anticheat_json_min))
        print(f"Упаковано минифицированное JSON AreWeAntiCheatYet в архив: {anticheat_archive_path}")
        os.remove(anticheat_json_min)
    except Exception as e:
        print(f"Ошибка при упаковке архива AreWeAntiCheatYet: {e}")
        return False

    # Архив для Epic Games
    epic_archive_path = os.path.join(data_dir, "egs_games.tar.xz")
    try:
        with tarfile.open(epic_archive_path, "w:xz", preset=9) as tar:
            tar.add(epic_json_min, arcname=os.path.basename(epic_json_min))
        print(f"Упаковано минифицированное JSON Epic в архив: {epic_archive_path}")
        os.remove(epic_json_min)
    except Exception as e:
        print(f"Ошибка при упаковке архива Epic: {e}")
        return False

    return True

async def run():
    success = await request_data()
    if not success:
        exit(1)

if __name__ == "__main__":
    asyncio.run(run())
