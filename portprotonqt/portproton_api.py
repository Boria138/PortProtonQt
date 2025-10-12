import os
import tarfile
import orjson
import requests
import urllib.parse
import time
import glob
import re
from collections.abc import Callable
from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger
from portprotonqt.config_utils import get_portproton_location

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
        self.portproton_location = get_portproton_location()
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.builtin_custom_folder = os.path.join(self.repo_root, "custom_data")
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

    def download_autoinstall_cover_async(self, exe_name: str, timeout: int = 5, callback: Callable[[str | None], None] | None = None) -> None:
        """Download only autoinstall cover image (no metadata)."""
        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        user_game_folder = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", "autoinstall", exe_name)
        os.makedirs(user_game_folder, exist_ok=True)

        cover_extensions = [".png", ".jpg", ".jpeg", ".bmp"]
        results: str | None = None
        pending_downloads = 0

        def on_cover_downloaded(local_path: str | None, ext: str):
            nonlocal pending_downloads, results
            if local_path:
                logger.info(f"Async autoinstall cover downloaded for {exe_name}: {local_path}")
                results = local_path
            else:
                logger.debug(f"No autoinstall cover downloaded for {exe_name} with extension {ext}")
            pending_downloads -= 1
            if pending_downloads == 0 and callback:
                callback(results)

        for ext in cover_extensions:
            cover_url = f"{self.base_url}/{exe_name}/cover{ext}"
            if self._check_file_exists(cover_url, timeout):
                local_cover_path = os.path.join(user_game_folder, f"cover{ext}")
                pending_downloads += 1
                self.downloader.download_async(
                    cover_url,
                    local_cover_path,
                    timeout=timeout,
                    callback=lambda path, ext=ext: on_cover_downloaded(path, ext)
                )
                break

        if pending_downloads == 0:
            logger.debug(f"No autoinstall covers found for {exe_name}")
            if callback:
                callback(None)

    def parse_autoinstall_script(self, file_path: str) -> tuple[str | None, str | None]:
        """Extract display_name from # name comment and exe_name from autoinstall bash script."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Skip emulators
            if re.search(r'#\s*type\s*:\s*emulators', content, re.IGNORECASE):
                return None, None

            display_name = None
            exe_name = None

            # Extract display_name from "# name:" comment
            name_match = re.search(r'#\s*name\s*:\s*(.+)', content, re.IGNORECASE)
            if name_match:
                display_name = name_match.group(1).strip()

            # --- pw_create_unique_exe ---
            pw_match = re.search(r'pw_create_unique_exe(?:\s+["\']([^"\']+)["\'])?', content)
            if pw_match:
                arg = pw_match.group(1)
                if arg:
                    exe_name = arg.strip()
                    if not exe_name.lower().endswith(".exe"):
                        exe_name += ".exe"
                else:
                    export_match = re.search(
                        r'export\s+PORTWINE_CREATE_SHORTCUT_NAME\s*=\s*["\']([^"\']+)["\']',
                        content, re.IGNORECASE)
                    if export_match:
                        exe_name = f"{export_match.group(1).strip()}.exe"

            else:
                portwine_match = None
                for line in content.splitlines():
                    stripped = line.strip()
                    # Игнорируем закомментированные строки
                    if stripped.startswith("#"):
                        continue
                    # Ищем portwine_exe только в активных строках
                    if "portwine_exe" in stripped and "=" in stripped:
                        portwine_match = stripped
                        break

                if portwine_match:
                    exe_expr = portwine_match.split("=", 1)[1].strip().strip("'\" ")
                    exe_candidates = re.findall(r'[-\w\s/\\\.]+\.exe', exe_expr)
                    if exe_candidates:
                        exe_name = os.path.basename(exe_candidates[-1].strip())


            # Fallback
            if not display_name and exe_name:
                display_name = exe_name

            return display_name, exe_name

        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None, None

    def get_autoinstall_games_async(self, callback: Callable[[list[tuple]], None]) -> None:
        """Load auto-install games with user/builtin covers and async autoinstall cover download."""
        games = []
        auto_dir = os.path.join(self.portproton_location, "data", "scripts", "pw_autoinstall")
        if not os.path.exists(auto_dir):
            callback(games)
            return

        scripts = sorted(glob.glob(os.path.join(auto_dir, "*")))
        if not scripts:
            callback(games)
            return

        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        base_autoinstall_dir = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", "autoinstall")
        os.makedirs(base_autoinstall_dir, exist_ok=True)

        for script_path in scripts:
            display_name, exe_name = self.parse_autoinstall_script(script_path)
            script_name = os.path.splitext(os.path.basename(script_path))[0]

            if not (display_name and exe_name):
                continue

            exe_name = os.path.splitext(exe_name)[0]  # Без .exe
            user_game_folder = os.path.join(base_autoinstall_dir, exe_name)
            os.makedirs(user_game_folder, exist_ok=True)

            # Поиск обложки
            cover_path = ""
            user_files = set(os.listdir(user_game_folder)) if os.path.exists(user_game_folder) else set()
            for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                candidate = f"cover{ext}"
                if candidate in user_files:
                    cover_path = os.path.join(user_game_folder, candidate)
                    break

            # Если обложки нет — пытаемся скачать
            if not cover_path:
                logger.debug(f"No local cover found for autoinstall {exe_name}, trying to download...")
                def on_cover_downloaded(path):
                    if path:
                        logger.info(f"Downloaded autoinstall cover for {exe_name}: {path}")
                self.download_autoinstall_cover_async(exe_name, timeout=5, callback=on_cover_downloaded)

            # Формируем кортеж игры
            game_tuple = (
                display_name,  # name
                "",  # description
                cover_path,  # cover
                "",  # appid
                f"autoinstall:{script_name}",  # exec_line
                "",  # controller_support
                "Never",  # last_launch
                "0h 0m",  # formatted_playtime
                "",  # protondb_tier
                "",  # anticheat_status
                0,  # last_played
                0,  # playtime_seconds
                "autoinstall"  # game_source
            )
            games.append(game_tuple)

        callback(games)

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
