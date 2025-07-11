import os
import tarfile
import orjson
import requests
import urllib.parse
import time
from collections.abc import Callable
from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
CACHE_DURATION = 30 * 24 * 60 * 60  # 30 days in seconds

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

def get_cache_dir():
    """Return the cache directory path, creating it if necessary."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQt")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

class PortProtonAPI:
    """API to fetch game assets (cover, metadata) and forum topics from the PortProtonQt repository."""
    def __init__(self, downloader: Downloader | None = None):
        self.base_url = "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/portprotonqt/custom_data"
        self.topics_url = "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/data/linux_gaming_topics.tar.xz"
        self.downloader = downloader or Downloader(max_workers=4)
        self.xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        self.custom_data_dir = os.path.join(self.xdg_data_home, "PortProtonQt", "custom_data")
        os.makedirs(self.custom_data_dir, exist_ok=True)
        self._topics_data = None

    def _get_game_dir(self, exe_name: str) -> str:
        game_dir = os.path.join(self.custom_data_dir, exe_name)
        os.makedirs(game_dir, exist_ok=True)
        return game_dir

    def _check_file_exists(self, url: str, timeout: int = 5) -> bool:
        try:
            response = requests.head(url, timeout=timeout)
            response.raise_for_status()
            return response.status_code == 200
        except requests.RequestException as e:
            logger.debug(f"Failed to check file at {url}: {e}")
            return False

    def download_game_assets(self, exe_name: str, timeout: int = 5) -> dict[str, str | None]:
        game_dir = self._get_game_dir(exe_name)
        results: dict[str, str | None] = {"cover": None, "metadata": None}
        cover_extensions = [".png", ".jpg", ".jpeg", ".bmp"]
        cover_url_base = f"{self.base_url}/{exe_name}/cover"
        metadata_url = f"{self.base_url}/{exe_name}/metadata.txt"

        for ext in cover_extensions:
            cover_url = f"{cover_url_base}{ext}"
            if self._check_file_exists(cover_url, timeout):
                local_cover_path = os.path.join(game_dir, f"cover{ext}")
                result = self.downloader.download(cover_url, local_cover_path, timeout=timeout)
                if result:
                    results["cover"] = result
                    logger.info(f"Downloaded cover for {exe_name} to {result}")
                    break
                else:
                    logger.error(f"Failed to download cover for {exe_name} from {cover_url}")
            else:
                logger.debug(f"No cover found for {exe_name} with extension {ext}")

        if self._check_file_exists(metadata_url, timeout):
            local_metadata_path = os.path.join(game_dir, "metadata.txt")
            result = self.downloader.download(metadata_url, local_metadata_path, timeout=timeout)
            if result:
                results["metadata"] = result
                logger.info(f"Downloaded metadata for {exe_name} to {result}")
            else:
                logger.error(f"Failed to download metadata for {exe_name} from {metadata_url}")
        else:
            logger.debug(f"No metadata found for {exe_name}")

        return results

    def download_game_assets_async(self, exe_name: str, timeout: int = 5, callback: Callable[[dict[str, str | None]], None] | None = None) -> None:
        game_dir = self._get_game_dir(exe_name)
        cover_extensions = [".png", ".jpg", ".jpeg", ".bmp"]
        cover_url_base = f"{self.base_url}/{exe_name}/cover"
        metadata_url = f"{self.base_url}/{exe_name}/metadata.txt"

        results: dict[str, str | None] = {"cover": None, "metadata": None}
        pending_downloads = 0

        def on_cover_downloaded(local_path: str | None, ext: str):
            nonlocal pending_downloads
            if local_path:
                logger.info(f"Async cover downloaded for {exe_name}: {local_path}")
                results["cover"] = local_path
            else:
                logger.debug(f"No cover downloaded for {exe_name} with extension {ext}")
            pending_downloads -= 1
            check_completion()

        def on_metadata_downloaded(local_path: str | None):
            nonlocal pending_downloads
            if local_path:
                logger.info(f"Async metadata downloaded for {exe_name}: {local_path}")
                results["metadata"] = local_path
            else:
                logger.debug(f"No metadata downloaded for {exe_name}")
            pending_downloads -= 1
            check_completion()

        def check_completion():
            if pending_downloads == 0 and callback:
                callback(results)

        for ext in cover_extensions:
            cover_url = f"{cover_url_base}{ext}"
            if self._check_file_exists(cover_url, timeout):
                local_cover_path = os.path.join(game_dir, f"cover{ext}")
                pending_downloads += 1
                self.downloader.download_async(
                    cover_url,
                    local_cover_path,
                    timeout=timeout,
                    callback=lambda path, ext=ext: on_cover_downloaded(path, ext)
                )
                break

        if self._check_file_exists(metadata_url, timeout):
            local_metadata_path = os.path.join(game_dir, "metadata.txt")
            pending_downloads += 1
            self.downloader.download_async(
                metadata_url,
                local_metadata_path,
                timeout=timeout,
                callback=on_metadata_downloaded
            )

        if pending_downloads == 0:
            logger.debug(f"No assets found for {exe_name}")
            if callback:
                callback(results)

    def _load_topics_data(self):
        """Load and cache linux_gaming_topics_min.json from the archive."""
        if self._topics_data is not None:
            return self._topics_data

        cache_dir = get_cache_dir()
        cache_tar = os.path.join(cache_dir, "linux_gaming_topics.tar.xz")
        cache_json = os.path.join(cache_dir, "linux_gaming_topics_min.json")

        if os.path.exists(cache_json) and (time.time() - os.path.getmtime(cache_json) < CACHE_DURATION):
            logger.info("Using cached topics JSON: %s", cache_json)
            try:
                with open(cache_json, "rb") as f:
                    self._topics_data = orjson.loads(f.read())
                logger.debug("Loaded %d topics from cache", len(self._topics_data))
                return self._topics_data
            except Exception as e:
                logger.error("Error reading cached topics JSON: %s", e)
                self._topics_data = []

        def process_tar(result: str | None):
            if not result or not os.path.exists(result):
                logger.error("Failed to download topics archive")
                self._topics_data = []
                return
            try:
                with tarfile.open(result, mode="r:xz") as tar:
                    member = next((m for m in tar.getmembers() if m.name == "linux_gaming_topics_min.json"), None)
                    if member is None:
                        raise RuntimeError("linux_gaming_topics_min.json not found in archive")
                    fobj = tar.extractfile(member)
                    if fobj is None:
                        raise RuntimeError("Failed to extract linux_gaming_topics_min.json from archive")
                    raw = fobj.read()
                    fobj.close()
                    self._topics_data = orjson.loads(raw)
                    with open(cache_json, "wb") as f:
                        f.write(orjson.dumps(self._topics_data))
                    if os.path.exists(cache_tar):
                        os.remove(cache_tar)
                        logger.info("Archive %s deleted after extraction", cache_tar)
                    logger.info("Loaded %d topics from archive", len(self._topics_data))
            except Exception as e:
                logger.error("Error processing topics archive: %s", e)
                self._topics_data = []

        self.downloader.download_async(self.topics_url, cache_tar, timeout=5, callback=process_tar)
        # Wait for async download to complete if called synchronously
        while self._topics_data is None:
            time.sleep(0.1)
        return self._topics_data

    def get_forum_topic_slug(self, game_name: str) -> str:
        """Get the forum topic slug or search URL for a given game name."""
        topics = self._load_topics_data()
        normalized_name = normalize_name(game_name)
        for topic in topics:
            if topic["normalized_title"] == normalized_name:
                return topic["slug"]
        logger.debug("No forum topic found for game: %s, redirecting to search", game_name)
        encoded_name = urllib.parse.quote(f"#ppdb {game_name}")
        return f"search?q={encoded_name}"
