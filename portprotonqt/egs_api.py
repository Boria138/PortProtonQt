import re
import requests
import requests.exceptions
import threading
import orjson
from pathlib import Path
import time
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from portprotonqt.localization import get_egs_language, _
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import load_pixmap_async
from PySide6.QtGui import QPixmap

logger = get_logger(__name__)

def get_cache_dir() -> Path:
    """Returns the path to the cache directory, creating it if necessary."""
    xdg_cache_home = os.getenv(
        "XDG_CACHE_HOME",
        os.path.join(os.path.expanduser("~"), ".cache")
    )
    cache_dir = Path(xdg_cache_home) / "PortProtonQT"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_egs_game_description_async(
    app_name: str,
    callback: Callable[[str], None],
    namespace: str | None = None,
    cache_ttl: int = 3600
) -> None:
    """
    Asynchronously fetches the game description from the Epic Games Store API.
    Prioritizes GraphQL API with namespace for slug and description.
    Falls back to legacy API if GraphQL provides a slug but no description.
    Caches results in ~/.cache/PortProtonQT/egs_app_{app_name}.json.
    Handles DNS resolution failures gracefully.
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / f"egs_app_{app_name.lower().replace(':', '_').replace(' ', '_')}.json"

    # Check cache
    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                content = f.read()
            cached_entry = orjson.loads(content)
            if not isinstance(cached_entry, dict):
                logger.warning(
                    "Invalid cache format in %s: expected dict, got %s",
                    cache_file,
                    type(cached_entry)
                )
                cache_file.unlink(missing_ok=True)
            else:
                cached_time = cached_entry.get("timestamp", 0)
                if time.time() - cached_time < cache_ttl:
                    description = cached_entry.get("description", "")
                    logger.debug(
                        "Using cached description for %s: %s",
                        app_name,
                        (description[:100] + "...") if len(description) > 100 else description
                    )
                    callback(description)
                    return
        except orjson.JSONDecodeError as e:
            logger.warning(
                "Failed to parse description cache for %s: %s",
                app_name,
                str(e)
            )
            cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(
                "Unexpected error reading description cache for %s: %s",
                app_name,
                str(e)
            )
            cache_file.unlink(missing_ok=True)

    lang = get_egs_language()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) EpicGamesLauncher"
    }

    def slug_from_title(title: str) -> str:
        """Derives a slug from the game title, preserving numbers and handling special characters."""
        # Keep letters, numbers, and spaces; replace spaces with hyphens
        cleaned = re.sub(r'[^a-z0-9 ]', '', title.lower()).strip()
        return re.sub(r'\s+', '-', cleaned)

    def get_product_slug(namespace: str) -> str:
        """Fetches the product slug using the namespace via GraphQL."""
        search_query = {
            "query": """
                query {
                    Catalog {
                        catalogNs(namespace: $namespace) {
                            mappings(pageType: "productHome") {
                                pageSlug
                                pageType
                            }
                        }
                    }
                }
            """,
            "variables": {"namespace": namespace}
        }
        try:
            response = requests.post(
                "https://launcher.store.epicgames.com/graphql",
                json=search_query,
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            data = orjson.loads(response.content)
            mappings = data.get("data", {}).get("Catalog", {}).get("catalogNs", {}).get("mappings", [])
            for mapping in mappings:
                if mapping.get("pageType") == "productHome":
                    return mapping.get("pageSlug", "")
            logger.warning("No productHome slug found for namespace %s", namespace)
            return ""
        except requests.RequestException as e:
            logger.warning("Failed to fetch product slug for namespace %s: %s", namespace, str(e))
            return ""
        except orjson.JSONDecodeError:
            logger.warning("Invalid JSON response for namespace %s", namespace)
            return ""

    def fetch_legacy_description(url: str) -> str:
        """Fetches description from the legacy API, handling DNS failures."""
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = orjson.loads(response.content)
            if not isinstance(data, dict):
                logger.warning("Invalid JSON structure for %s in legacy API: %s", app_name, type(data))
                return ""
            pages = data.get("pages", [])
            if pages:
                for page in pages:
                    if page.get("type") == "productHome":
                        return page.get("data", {}).get("about", {}).get("shortDescription", "")
                return pages[0].get("data", {}).get("about", {}).get("shortDescription", "")
            return ""
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.info("Legacy API returned 404 for %s", app_name)
            else:
                logger.warning("HTTP error in legacy API for %s: %s", app_name, str(e))
            return ""
        except requests.exceptions.ConnectionError as e:
            logger.error("DNS resolution failed for legacy API %s: %s", url, str(e))
            return ""
        except requests.RequestException as e:
            logger.warning("Failed to fetch legacy API for %s: %s", app_name, str(e))
            return ""
        except orjson.JSONDecodeError:
            logger.warning("Invalid JSON response for %s in legacy API", app_name)
            return ""

    def fetch_graphql_description(namespace: str | None, locale: str) -> tuple[str, str]:
        """Fetches description and slug from GraphQL API using namespace or title."""
        if namespace:
            search_query = {
                "query": """
                    query {
                        Product {
                            sandbox(sandboxId: $namespace) {
                                configuration {
                                    ... on StoreConfiguration {
                                        configs {
                                            shortDescription
                                        }
                                    }
                                }
                            }
                            catalogNs {
                                mappings(pageType: "productHome") {
                                    pageSlug
                                    pageType
                                }
                            }
                        }
                    }
                """,
                "variables": {"namespace": namespace}
            }
            url = "https://launcher.store.epicgames.com/graphql"
        else:
            search_query = {
                "query": """
                    query search($keywords: String!, $locale: String) {
                        Catalog {
                            searchStore(keywords: $keywords, locale: $locale) {
                                elements { title namespace productSlug description }
                            }
                        }
                    }
                """,
                "variables": {"keywords": app_name, "locale": locale}
            }
            url = "https://graphql.epicgames.com/graphql"

        try:
            response = requests.post(url, json=search_query, headers=headers, timeout=5)
            response.raise_for_status()
            data = orjson.loads(response.content)
            if namespace:
                configs = data.get("data", {}).get("Product", {}).get("sandbox", {}).get("configuration", [{}])[0].get("configs", {})
                description = configs.get("shortDescription", "")
                mappings = data.get("data", {}).get("Product", {}).get("catalogNs", {}).get("mappings", [])
                slug = next((m.get("pageSlug", "") for m in mappings if m.get("pageType") == "productHome"), "")
                return description, slug
            else:
                elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
                for element in elements:
                    if (isinstance(element, dict) and
                        element.get("title", "").lower() == app_name.lower() and
                        element.get("productSlug") and
                        not any(substring in element.get("title", "").lower()
                                for substring in ["bundle", "pack", "edition", "dlc", "upgrade", "chapter", "набор", "пак", "дополнение"])):
                        return element.get("description", ""), element.get("productSlug", "")
                return "", ""
        except requests.RequestException as e:
            logger.warning("Failed to fetch GraphQL data for %s with locale %s: %s", app_name, locale, str(e))
            return "", ""
        except orjson.JSONDecodeError:
            logger.warning("Invalid JSON response for %s with locale %s", app_name, locale)
            return "", ""

    def fetch_description():
        description = ""
        product_slug = ""

        # Step 1: Try GraphQL with namespace to get description and slug
        if namespace:
            description, product_slug = fetch_graphql_description(namespace, lang)
            if description:
                logger.debug("Fetched description from GraphQL for %s: %s", app_name, (description[:100] + "...") if len(description) > 100 else description)

        # Step 2: If no description or no namespace, try legacy API with slug
        if not description:
            if not product_slug:
                product_slug = slug_from_title(app_name)
            legacy_url = f"https://store-content.ak.epicgames.com/api/{lang}/content/products/{product_slug}"
            try:
                description = fetch_legacy_description(legacy_url)
                if description:
                    logger.debug("Fetched description from legacy API for %s: %s", app_name, (description[:100] + "...") if len(description) > 100 else description)
            except requests.exceptions.ConnectionError:
                logger.error("Skipping legacy API due to DNS resolution failure for %s", app_name)

        # Step 3: If still no description and no namespace, try GraphQL with title
        if not description and not namespace:
            description, _ = fetch_graphql_description(None, lang)
            if description:
                logger.debug("Fetched description from GraphQL title search for %s: %s", app_name, (description[:100] + "...") if len(description) > 100 else description)

        # Step 4: If no description found, log and return empty
        if not description:
            logger.warning("No valid description found for %s", app_name)

        # Save to cache
        cache_entry = {"description": description, "timestamp": time.time()}
        try:
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, "wb") as f:
                f.write(orjson.dumps(cache_entry))
            temp_file.replace(cache_file)
            logger.debug("Saved description to cache for %s", app_name)
        except Exception as e:
            logger.error("Failed to save description cache for %s: %s", app_name, str(e))

        callback(description)

    thread = threading.Thread(target=fetch_description, daemon=True)
    thread.start()
def run_legendary_list_async(legendary_path: str, callback: Callable[[list | None], None]):
    """
    Асинхронно выполняет команду 'legendary list --json' и возвращает результат через callback.
    """
    def execute_command():
        process = None
        try:
            process = subprocess.Popen(
                [legendary_path, "list", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
            stdout, stderr = process.communicate(timeout=30)
            if process.returncode != 0:
                logger.error("Legendary list command failed: %s", stderr.decode('utf-8', errors='replace'))
                callback(None)
                return
            try:
                result = orjson.loads(stdout)
                if not isinstance(result, list):
                    logger.error("Invalid legendary output format: expected list, got %s", type(result))
                    callback(None)
                    return
                callback(result)
            except orjson.JSONDecodeError as e:
                logger.error("Failed to parse JSON output from legendary list: %s", str(e))
                callback(None)
        except subprocess.TimeoutExpired:
            logger.error("Legendary list command timed out")
            if process:
                process.kill()
            callback(None)
        except FileNotFoundError:
            logger.error("Legendary executable not found at %s", legendary_path)
            callback(None)
        except Exception as e:
            logger.error("Unexpected error executing legendary list: %s", str(e))
            callback(None)

    threading.Thread(target=execute_command, daemon=True).start()

def load_egs_games_async(legendary_path: str, callback: Callable[[list[tuple]], None], downloader, update_progress: Callable[[int], None], update_status_message: Callable[[str, int], None]):
    """
    Асинхронно загружает Epic Games Store игры с использованием legendary CLI.
    """
    logger.debug("Starting to load Epic Games Store games")
    games: list[tuple] = []
    cache_dir = Path(os.path.dirname(legendary_path))
    metadata_dir = cache_dir / "metadata"
    cache_file = cache_dir / "legendary_games.json"
    cache_ttl = 3600  # Cache TTL in seconds (1 hour)

    if not os.path.exists(legendary_path):
        logger.info("Legendary binary not found, downloading...")
        def on_legendary_downloaded(result):
            if result:
                logger.info("Legendary binary downloaded successfully")
                try:
                    os.chmod(legendary_path, 0o755)
                except Exception as e:
                    logger.error(f"Failed to make legendary binary executable: {e}")
                    callback(games)  # Return empty games list on failure
                    return
                _continue_loading_egs_games(legendary_path, callback, metadata_dir, cache_dir, cache_file, cache_ttl, update_progress, update_status_message)
            else:
                logger.error("Failed to download legendary binary")
                callback(games)  # Return empty games list on failure
        try:
            downloader.download_legendary_binary(on_legendary_downloaded)
        except Exception as e:
            logger.error(f"Error initiating legendary binary download: {e}")
            callback(games)
        return
    else:
        _continue_loading_egs_games(legendary_path, callback, metadata_dir, cache_dir, cache_file, cache_ttl, update_progress, update_status_message)

def _continue_loading_egs_games(legendary_path: str, callback: Callable[[list[tuple]], None], metadata_dir: Path, cache_dir: Path, cache_file: Path, cache_ttl: int, update_progress: Callable[[int], None], update_status_message: Callable[[str, int], None]):
    """
    Продолжает процесс загрузки EGS игр, либо из кэша, либо через legendary CLI.
    """
    games: list[tuple] = []
    cache_dir.mkdir(parents=True, exist_ok=True)

    def process_games(installed_games: list | None):
        if installed_games is None:
            logger.info("No installed Epic Games Store games found")
            callback(games)
            return

        # Сохраняем в кэш
        try:
            with open(cache_file, "wb") as f:
                f.write(orjson.dumps(installed_games))
            logger.debug("Saved Epic Games Store games to cache: %s", cache_file)
        except Exception as e:
            logger.error("Failed to save cache: %s", str(e))

        # Фильтруем игры
        valid_games = [game for game in installed_games if isinstance(game, dict) and game.get("app_name") and not game.get("is_dlc", False)]
        if len(valid_games) != len(installed_games):
            logger.warning("Filtered out %d invalid game records", len(installed_games) - len(valid_games))

        if not valid_games:
            logger.info("No valid Epic Games Store games found after filtering")
            callback(games)
            return

        pending_images = len(valid_games)
        total_games = len(valid_games)
        update_progress(0)
        update_status_message(_("Loading Epic Games Store games..."), 3000)

        game_results: dict[int, tuple] = {}
        results_lock = threading.Lock()

        def process_game_metadata(game, index):
            nonlocal pending_images
            app_name = game.get("app_name", "")
            title = game.get("app_title", app_name)
            if not app_name:
                with results_lock:
                    pending_images -= 1
                    update_progress(total_games - pending_images)
                    if pending_images == 0:
                        final_games = [game_results[i] for i in sorted(game_results.keys())]
                        callback(final_games)
                return

            metadata_file = metadata_dir / f"{app_name}.json"
            cover_url = ""
            try:
                with open(metadata_file, "rb") as f:
                    metadata = orjson.loads(f.read())
                key_images = metadata.get("metadata", {}).get("keyImages", [])
                for img in key_images:
                    if isinstance(img, dict) and img.get("type") in ["DieselGameBoxTall", "Thumbnail"]:
                        cover_url = img.get("url", "")
                        break
            except Exception as e:
                logger.warning("Error processing metadata for %s: %s", app_name, str(e))

            image_folder = os.path.join(os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "PortProtonQT", "images")
            local_path = os.path.join(image_folder, f"{app_name}.jpg") if cover_url else ""

            def on_description_fetched(api_description: str):
                final_description = api_description or _("No description available")

                def on_cover_loaded(pixmap: QPixmap):
                    from portprotonqt.steam_api import get_weanticheatyet_status_async
                    def on_anticheat_status(status: str):
                        nonlocal pending_images
                        with results_lock:
                            game_results[index] = (
                                title,
                                final_description,
                                local_path if os.path.exists(local_path) else "",
                                app_name,
                                f"legendary:launch:{app_name}",
                                "",
                                _("Never"),
                                "",
                                "",
                                status or "",
                                0,
                                0,
                                "epic"
                            )
                            pending_images -= 1
                            update_progress(total_games - pending_images)
                            if pending_images == 0:
                                final_games = [game_results[i] for i in sorted(game_results.keys())]
                                callback(final_games)

                    get_weanticheatyet_status_async(title, on_anticheat_status)

                load_pixmap_async(cover_url, 600, 900, on_cover_loaded, app_name=app_name)

            get_egs_game_description_async(title, on_description_fetched)

        max_workers = min(4, len(valid_games))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i, game in enumerate(valid_games):
                executor.submit(process_game_metadata, game, i)

    # Проверяем кэш
    use_cache = False
    if cache_file.exists():
        try:
            cache_mtime = cache_file.stat().st_mtime
            if time.time() - cache_mtime < cache_ttl and metadata_dir.exists() and any(metadata_dir.iterdir()):
                logger.debug("Loading Epic Games Store games from cache: %s", cache_file)
                with open(cache_file, "rb") as f:
                    installed_games = orjson.loads(f.read())
                if not isinstance(installed_games, list):
                    logger.warning("Invalid cache format: expected list, got %s", type(installed_games))
                else:
                    use_cache = True
                    process_games(installed_games)
        except Exception as e:
            logger.error("Error reading cache: %s", str(e))

    if not use_cache:
        logger.info("Fetching Epic Games Store games using legendary list")
        run_legendary_list_async(legendary_path, process_games)
