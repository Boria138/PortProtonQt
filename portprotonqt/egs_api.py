import requests
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
    cache_ttl: int = 3600
) -> None:
    """
    Asynchronously fetches the game description from the Epic Games Store API.
    Uses per-app cache files named egs_app_{app_name}.json in ~/.cache/PortProtonQT.
    Checks the cache first; if the description is cached and not expired, returns it.
    Takes the description from data.about.shortDescription[2] if available (len >= 3), else [0].
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / f"egs_app_{app_name.lower().replace(':', '_').replace(' ', '_')}.json"

    # Initialize content to avoid unbound variable
    content = b""
    # Load existing cache
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
            logger.debug(
                "Cache file content (first 100 chars): %s",
                content[:100].decode('utf-8', errors='replace')
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
    slug = app_name.lower().replace(":", "").replace(" ", "-")
    url = f"https://store-content.ak.epicgames.com/api/{lang}/content/products/{slug}"

    def fetch_description():
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = orjson.loads(response.content)

            if not isinstance(data, dict):
                logger.warning("Invalid JSON structure for %s: %s", app_name, type(data))
                callback("")
                return

            descriptions = (
                data.get("pages", [{}])[0]
                    .get("data", {})
                    .get("about", {})
                    .get("shortDescription", [])
            )

            description = ""
            if isinstance(descriptions, list) and descriptions:
                try:
                    description = (
                        descriptions[2]
                        if len(descriptions) >= 3
                        else descriptions[0]
                    ) or ""
                except (IndexError, TypeError):
                    logger.warning(
                        "Error accessing description index for %s", app_name
                    )
                    description = ""
            elif isinstance(descriptions, str):
                description = descriptions
            else:
                logger.warning(
                    "Unexpected shortDescription format for %s: %s",
                    app_name,
                    type(descriptions)
                )

            logger.debug(
                "Fetched EGS description for %s: %s",
                app_name,
                (description[:100] + "...") if len(description) > 100 else description
            )

            cache_entry = {"description": description, "timestamp": time.time()}
            try:
                temp_file = cache_file.with_suffix('.tmp')
                with open(temp_file, "wb") as f:
                    f.write(orjson.dumps(cache_entry))
                temp_file.replace(cache_file)
                logger.debug(
                    "Saved description to cache for %s", app_name
                )
            except Exception as e:
                logger.error(
                    "Failed to save description cache for %s: %s",
                    app_name,
                    str(e)
                )
            callback(description)
        except requests.RequestException as e:
            logger.warning(
                "Failed to fetch EGS description for %s: %s",
                app_name,
                str(e)
            )
            callback("")
        except orjson.JSONDecodeError:
            logger.warning(
                "Invalid JSON response for %s", app_name
            )
            callback("")
        except Exception as e:
            logger.error(
                "Unexpected error fetching EGS description for %s: %s",
                app_name,
                str(e)
            )
            callback("")

    thread = threading.Thread(
        target=fetch_description,
        daemon=True
    )
    thread.start()

def load_egs_games_async(legendary_path: str, callback: Callable[[list[tuple]], None], downloader, update_progress: Callable[[int], None], update_status_message: Callable[[str, int], None]):
    """
    Asynchronously loads Epic Games Store games using the legendary CLI.
    Caches the game list to avoid repeated calls to legendary list.
    """
    logger.debug("Starting to load Epic Games Store games")
    games: list[tuple] = []
    cache_dir = Path(os.path.dirname(legendary_path))
    metadata_dir = cache_dir / "metadata"
    cache_file = cache_dir / "legendary_games.json"
    cache_ttl = 3600  # Cache TTL in seconds (1 hour)

    # Ensure legendary binary is available
    if not os.path.exists(legendary_path):
        logger.info("Legendary binary not found, downloading...")

        def on_legendary_downloaded(result):
            if result:
                logger.info("Legendary binary downloaded successfully")
                try:
                    os.chmod(legendary_path, 0o755)
                    logger.debug("Made legendary binary executable")
                except Exception as e:
                    logger.error(f"Failed to make legendary binary executable: {e}")
                _continue_loading_egs_games(legendary_path, callback, metadata_dir, cache_dir, cache_file, cache_ttl, update_progress, update_status_message)
            else:
                logger.error("Failed to download legendary binary")
                callback(games)

        downloader.download_legendary_binary(on_legendary_downloaded)
        return
    else:
        _continue_loading_egs_games(legendary_path, callback, metadata_dir, cache_dir, cache_file, cache_ttl, update_progress, update_status_message)

def _continue_loading_egs_games(legendary_path: str, callback: Callable[[list[tuple]], None], metadata_dir: Path, cache_dir: Path, cache_file: Path, cache_ttl: int, update_progress: Callable[[int], None], update_status_message: Callable[[str, int], None]):
    """
    Continues the process of loading EGS games, either from cache or by querying the legendary CLI.
    """
    games: list[tuple] = []
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if cache exists and is fresh, and metadata directory exists
    installed_games = None
    use_cache = False

    if cache_file.exists():
        try:
            cache_mtime = cache_file.stat().st_mtime
            if time.time() - cache_mtime < cache_ttl:
                if metadata_dir.exists() and any(metadata_dir.iterdir()):
                    logger.debug("Loading Epic Games Store games from cache: %s", cache_file)
                    with open(cache_file, "rb") as f:
                        installed_games = orjson.loads(f.read())

                    # Verify loaded data is a list
                    if not isinstance(installed_games, list):
                        logger.warning("Invalid cache format: expected list, got %s", type(installed_games))
                        installed_games = None
                    else:
                        logger.info("Loaded %d games from cache", len(installed_games))
                        use_cache = True
                else:
                    logger.warning("Metadata directory is missing or empty, ignoring cache and fetching fresh data")
            else:
                logger.debug("Cache is expired, fetching fresh data")
        except orjson.JSONDecodeError as e:
            logger.warning("Failed to parse cached JSON: %s", str(e))
        except Exception as e:
            logger.error("Unexpected error reading cache: %s", str(e))

    if not use_cache or installed_games is None:
        try:
            logger.info("Executing 'legendary list --json' to retrieve installed EGS games")
            result = subprocess.run(
                [legendary_path, "list", "--json"],
                capture_output=True,
                text=False,
                check=True,
                timeout=30
            )
            logger.debug("Parsing JSON output from legendary list command")
            installed_games = orjson.loads(result.stdout)

            # Verify data is a list
            if not isinstance(installed_games, list):
                logger.error("Invalid legendary output format: expected list, got %s", type(installed_games))
                callback(games)
                return

            logger.info("Found %d installed Epic Games Store games: %s",
                        len(installed_games),
                        [game.get("app_title", game.get("app_name", "")) for game in installed_games if isinstance(game, dict)])
            try:
                with open(cache_file, "wb") as f:
                    f.write(orjson.dumps(installed_games))
                logger.debug("Saved Epic Games Store games to cache: %s", cache_file)
            except Exception as e:
                logger.error("Failed to save cache: %s", str(e))
        except subprocess.CalledProcessError as e:
            logger.error("Failed to execute legendary list command: %s", str(e))
            callback(games)
            return
        except subprocess.TimeoutExpired as e:
            logger.error("Legendary list command timed out: %s", str(e))
            callback(games)
            return
        except orjson.JSONDecodeError as e:
            logger.error("Failed to parse JSON output from legendary list: %s", str(e))
            callback(games)
            return
        except FileNotFoundError as e:
            logger.error("Legendary executable not found at path %s: %s", legendary_path, str(e))
            callback(games)
            return

    if not installed_games:
        logger.info("No installed Epic Games Store games found")
        callback(games)
        return

    # Filter out invalid game entries
    valid_games = [game for game in installed_games if isinstance(game, dict) and game.get("app_name")]
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

        # Validate game data
        if not isinstance(game, dict):
            logger.warning("Invalid game data at index %d: expected dict, got %s", index, type(game))
            with results_lock:
                pending_images -= 1
                update_progress(total_games - pending_images)
                if pending_images == 0:
                    final_games = [game_results[i] for i in sorted(game_results.keys())]
                    logger.info("All EGS games and images processed, invoking callback with %d games", len(final_games))
                    callback(final_games)
            return

        app_name = game.get("app_name", "")
        title = game.get("app_title", app_name)

        if not app_name:
            logger.warning("Game at index %d has no app_name, skipping", index)
            with results_lock:
                pending_images -= 1
                update_progress(total_games - pending_images)
                if pending_images == 0:
                    final_games = [game_results[i] for i in sorted(game_results.keys())]
                    logger.info("All EGS games and images processed, invoking callback with %d games", len(final_games))
                    callback(final_games)
            return

        logger.debug("Processing EGS game: %s (app_name: %s)", title, app_name)

        if game.get("is_dlc", False):
            logger.debug("Skipping DLC/add-on: %s (app_name: %s)", title, app_name)
            with results_lock:
                pending_images -= 1
                update_progress(total_games - pending_images)
                if pending_images == 0:
                    final_games = [game_results[i] for i in sorted(game_results.keys())]
                    logger.info("All EGS games and images processed, invoking callback with %d games", len(final_games))
                    callback(final_games)
            return

        metadata_file = metadata_dir / f"{app_name}.json"
        try:
            logger.debug("Reading metadata file for %s: %s", app_name, metadata_file)
            with open(metadata_file, "rb") as f:
                metadata = orjson.loads(f.read())
            logger.debug("Successfully parsed metadata JSON for %s", app_name)

            cover_url = ""
            try:
                key_images = metadata.get("metadata", {}).get("keyImages", [])
                if isinstance(key_images, list):
                    for img in key_images:
                        if isinstance(img, dict) and img.get("type") in ["DieselGameBoxTall", "Thumbnail"]:
                            cover_url = img.get("url", "") or ""
                            break
            except (AttributeError, TypeError):
                cover_url = ""

            logger.debug("Retrieved metadata for %s: cover_url=%s", app_name, cover_url)
        except FileNotFoundError as e:
            logger.warning("Metadata file not found for EGS game %s: %s", app_name, str(e))
            cover_url = ""
        except orjson.JSONDecodeError as e:
            logger.warning("Failed to parse metadata JSON for %s: %s", app_name, str(e))
            cover_url = ""
        except Exception as e:
            logger.error("Unexpected error processing metadata for %s: %s", app_name, str(e))
            cover_url = ""

        image_folder = os.path.join(os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "PortProtonQT", "images")
        local_path = os.path.join(image_folder, f"{app_name}.jpg") if cover_url else ""

        playtime_seconds = 0
        last_played = 0
        last_launch = _("Never")
        formatted_playtime = ""

        def on_description_fetched(api_description: str):
            final_description = api_description or _("No description available")
            logger.debug("Final description for %s: %s", title, final_description[:100])

            def on_cover_loaded(pixmap: QPixmap):
                logger.debug("Cover image loaded for %s: %s", app_name, local_path)

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
                            last_launch,
                            formatted_playtime,
                            "",
                            status or "",
                            last_played,
                            playtime_seconds,
                            "epic"
                        )
                        pending_images -= 1
                        update_progress(total_games - pending_images)
                        logger.info("Processed EGS game %s with cover %s and anticheat status '%s', progress: %d/%d",
                                    title, local_path, status, total_games - pending_images, total_games)
                        if pending_images == 0:
                            final_games = [game_results[i] for i in sorted(game_results.keys())]
                            logger.info("All EGS games and images processed, invoking callback with %d games", len(final_games))
                            callback(final_games)

                from portprotonqt.steam_api import get_weanticheatyet_status_async
                get_weanticheatyet_status_async(title, on_anticheat_status)

            load_pixmap_async(cover_url, 600, 900, on_cover_loaded, app_name=app_name)

        # Request description from cache or API
        get_egs_game_description_async(title, on_description_fetched)

    logger.debug("Starting ThreadPoolExecutor for processing %d EGS games", len(valid_games))
    max_workers = min(10, len(valid_games))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        try:
            futures = []
            for i, game in enumerate(valid_games):
                future = executor.submit(process_game_metadata, game, i)
                futures.append(future)

            for future in futures:
                try:
                    future.result(timeout=30)
                except Exception as e:
                    logger.error("Error processing game metadata: %s", str(e))
        except Exception as e:
            logger.error("Error in ThreadPoolExecutor: %s", str(e))
