import os
import tarfile
import orjson
import requests
import urllib.parse
import time
import glob
import re
import hashlib
from collections.abc import Callable
from PySide6.QtCore import QThread, Signal
from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger
from portprotonqt.config_utils import get_portproton_location

logger = get_logger(__name__)
CACHE_DURATION = 30 * 24 * 60 * 60  # 30 days in seconds
AUTOINSTALL_CACHE_DURATION = 3600  # 1 hour for autoinstall cache

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
        self._autoinstall_cache = None  # New: In-memory cache

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
        """Download only autoinstall cover image (PNG only, no metadata)."""
        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        autoinstall_root = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", "autoinstall")
        user_game_folder = os.path.join(autoinstall_root, exe_name)

        if not os.path.isdir(user_game_folder):
            try:
                os.mkdir(user_game_folder)
            except FileExistsError:
                pass

        cover_url = f"{self.base_url}/{exe_name}/cover.png"
        local_cover_path = os.path.join(user_game_folder, "cover.png")

        def on_cover_downloaded(local_path: str | None):
            if local_path:
                logger.info(f"Async autoinstall cover downloaded for {exe_name}: {local_path}")
            else:
                logger.debug(f"No autoinstall cover downloaded for {exe_name}")
            if callback:
                callback(local_path)

        if self._check_file_exists(cover_url, timeout):
            self.downloader.download_async(
                cover_url,
                local_cover_path,
                timeout=timeout,
                callback=on_cover_downloaded
            )
        else:
            logger.debug(f"No autoinstall cover found for {exe_name}")
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
                    if stripped.startswith("#"):
                        continue
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

    def _compute_scripts_signature(self, auto_dir: str) -> str:
        """Compute a hash-based signature of the autoinstall scripts to detect changes."""
        if not os.path.exists(auto_dir):
            return ""
        scripts = sorted(glob.glob(os.path.join(auto_dir, "*")))
        # Simple hash: concatenate sorted filenames and hash
        filenames_str = "".join(sorted([os.path.basename(s) for s in scripts]))
        return hashlib.md5(filenames_str.encode()).hexdigest()

    def _load_autoinstall_cache(self):
        """Load cached autoinstall games if fresh and scripts unchanged."""
        if self._autoinstall_cache is not None:
            return self._autoinstall_cache
        cache_dir = get_cache_dir()
        cache_file = os.path.join(cache_dir, "autoinstall_games_cache.json")
        if os.path.exists(cache_file):
            try:
                mod_time = os.path.getmtime(cache_file)
                if time.time() - mod_time < AUTOINSTALL_CACHE_DURATION:
                    with open(cache_file, "rb") as f:
                        data = orjson.loads(f.read())
                        # Check signature
                        cached_signature = data.get("scripts_signature", "")
                        current_signature = self._compute_scripts_signature(
                            os.path.join(self.portproton_location or "", "data", "scripts", "pw_autoinstall")
                        )
                        if cached_signature != current_signature:
                            logger.info("Scripts signature mismatch; invalidating cache")
                            return None
                        self._autoinstall_cache = data["games"]
                        logger.info(f"Loaded {len(self._autoinstall_cache)} cached autoinstall games")
                        return self._autoinstall_cache
            except Exception as e:
                logger.error(f"Failed to load autoinstall cache: {e}")
        return None

    def _save_autoinstall_cache(self, games):
        """Save parsed autoinstall games to cache with scripts signature."""
        try:
            cache_dir = get_cache_dir()
            cache_file = os.path.join(cache_dir, "autoinstall_games_cache.json")
            auto_dir = os.path.join(self.portproton_location or "", "data", "scripts", "pw_autoinstall")
            scripts_signature = self._compute_scripts_signature(auto_dir)
            data = {"games": games, "scripts_signature": scripts_signature, "timestamp": time.time()}
            with open(cache_file, "wb") as f:
                f.write(orjson.dumps(data))
            logger.debug(f"Saved {len(games)} autoinstall games to cache with signature {scripts_signature}")
        except Exception as e:
            logger.error(f"Failed to save autoinstall cache: {e}")

    def start_autoinstall_games_load(self, callback: Callable[[list[tuple]], None]) -> QThread | None:
        """Start loading auto-install games in a background thread. Returns the thread for management."""
        # Check cache first (sync, fast)
        cached_games = self._load_autoinstall_cache()
        if cached_games is not None:
            # Emit via callback immediately if cached
            QThread.msleep(0)  # Yield to Qt event loop
            callback(cached_games)
            return None  # No thread needed

        # No cache: Start background thread
        class AutoinstallWorker(QThread):
            finished = Signal(list)
            api: "PortProtonAPI"
            portproton_location: str | None

            def run(self):
                games = []
                auto_dir = os.path.join(
                    self.portproton_location or "", "data", "scripts", "pw_autoinstall"
                ) if self.portproton_location else ""
                if not os.path.exists(auto_dir):
                    self.finished.emit(games)
                    return

                scripts = sorted(glob.glob(os.path.join(auto_dir, "*")))
                if not scripts:
                    self.finished.emit(games)
                    return

                xdg_data_home = os.getenv(
                    "XDG_DATA_HOME",
                    os.path.join(os.path.expanduser("~"), ".local", "share"),
                )
                base_autoinstall_dir = os.path.join(
                    xdg_data_home, "PortProtonQt", "custom_data", "autoinstall"
                )
                os.makedirs(base_autoinstall_dir, exist_ok=True)

                for script_path in scripts:
                    display_name, exe_name = self.api.parse_autoinstall_script(script_path)
                    script_name = os.path.splitext(os.path.basename(script_path))[0]

                    if not (display_name and exe_name):
                        continue

                    exe_name = os.path.splitext(exe_name)[0]
                    user_game_folder = os.path.join(base_autoinstall_dir, exe_name)
                    os.makedirs(user_game_folder, exist_ok=True)

                    # Find cover
                    cover_path = ""
                    user_files = (
                        set(os.listdir(user_game_folder))
                        if os.path.exists(user_game_folder)
                        else set()
                    )
                    for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                        candidate = f"cover{ext}"
                        if candidate in user_files:
                            cover_path = os.path.join(user_game_folder, candidate)
                            break

                    if not cover_path:
                        logger.debug(f"No local cover found for autoinstall {exe_name}")

                    game_tuple = (
                        display_name, "", cover_path, "", f"autoinstall:{script_name}",
                        "", "Never", "0h 0m", "", "", 0, 0, "autoinstall", exe_name
                    )
                    games.append(game_tuple)

                self.api._save_autoinstall_cache(games)
                self.api._autoinstall_cache = games
                self.finished.emit(games)

        worker = AutoinstallWorker()
        worker.api = self
        worker.portproton_location = self.portproton_location
        worker.finished.connect(lambda games: callback(games))
        worker.start()
        logger.info("Started background load of autoinstall games")
        return worker

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
