import os
import subprocess
import requests
import urllib.parse
import time
import glob
import re
import hashlib
import queue
import shutil
import locale
from collections.abc import Callable
from typing import Any
from PySide6.QtCore import QThread, Signal, QUrl, QObject, Qt, SignalInstance
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
from portprotonqt.downloader import Downloader, get_requests_session
from portprotonqt.logger import get_logger
from portprotonqt.config import (
    extract_exec_target_path,
    get_portproton_location,
    get_portproton_scripts_path,
    get_portproton_start_command,
)
from portprotonqt.localization import _
from portprotonqt.dialogs import FileExplorer
from portprotonqt.config.cache import CacheManager
from portprotonqt.image_utils import COVER_IMAGE_EXTENSIONS

logger = get_logger(__name__)
AUTOINSTALL_CACHE_DURATION = 3600  # 1 hour for autoinstall cache
HEAD_FAILURE_RETRY_DELAY = 60  # 1 minute cooldown for failed HEAD checks
HEAD_CACHE_DURATION = 24 * 60 * 60
HEAD_CACHE_NAME = "head_cache"
HEAD_CACHE_OLD_PATTERN = "head_*.json"


def _create_bootstrap_file_explorer_parent() -> tuple[QObject | None, Any]:
    """Create a minimal parent with InputManager before MainWindow exists."""
    parent = QApplication.activeWindow()
    if parent is not None:
        return parent, None

    try:
        from portprotonqt.input_manager import InputManager
        from portprotonqt.port_data_path_selector import _BootstrapInputHost
    except ImportError as e:
        logger.warning("Cannot initialize gamepad support for PPDB file dialog: %s", e)
        return None, None

    input_host = _BootstrapInputHost()
    input_manager = InputManager(input_host)
    input_host.input_manager = input_manager
    return input_host, input_manager


def normalize_name(s):
    """
    Normalize string:
    - convert to lowercase,
    - remove ™ and ® symbols,
    - replace separators (-, :, ,) with space,
    - remove extra spaces,
    - remove 'bin' or 'app' suffixes at end of string,
    - remove keywords like 'ultimate', 'edition', etc.
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


def extract_exe_name(exec_line: str) -> str:
    """Extract executable name from exec_line.

    Handles various exec_line formats:
    - Full command: 'env VAR=val /path/to/script /path/to/game.exe' -> 'game.exe'
    - Autoinstall: 'autoinstall:script_name' -> ''
    - Simple path: '/path/to/game.exe' -> 'game.exe'

    Returns:
        Executable name with .exe extension, or empty string if not found
    """

    if not exec_line:
        return ""

    # Handle autoinstall scripts - they don't have a direct exe
    if exec_line.startswith("autoinstall:"):
        return ""

    game_exe = extract_exec_target_path(exec_line)
    if game_exe and game_exe.lower().endswith(".exe"):
        return os.path.basename(game_exe)
    return ""


class PortProtonAPI:
    """API to fetch game assets (cover, metadata) and forum topics from the PortProtonQt repository."""
    def __init__(self, downloader: Downloader | None = None):
        self.base_url = "https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt-Custom-Metadata/raw/branch/main"
        self.downloader = downloader or Downloader(max_workers=4)
        self.xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        self.custom_data_dir = os.path.join(self.xdg_data_home, "PortProtonQt", "custom_data")
        os.makedirs(self.custom_data_dir, exist_ok=True)
        self.portproton_location = get_portproton_location()
        self._autoinstall_cache = None  # In-memory cache
        self._head_positive_cache: set[str] = set()
        self._head_negative_cache: set[str] = set()
        self._head_failure_cache: dict[str, float] = {}
        self._head_disk_cache_cleaned = False
        self._pending_asset_notifier: QObject | None = None
        self._pending_asset_batch_thread: QThread | None = None

    def _get_game_dir(self, exe_name: str) -> str:
        game_dir = os.path.join(self.custom_data_dir, exe_name)
        os.makedirs(game_dir, exist_ok=True)
        return game_dir

    def _load_head_cache_entry(self, cache_manager: CacheManager, cache_key: str) -> bool | None:
        cached = cache_manager.load_json(HEAD_CACHE_NAME)
        if not isinstance(cached, dict):
            return None
        entry = cached.get(cache_key)
        if not isinstance(entry, dict):
            return None
        timestamp = entry.get("timestamp")
        if not isinstance(timestamp, int | float):
            return None
        if time.time() - timestamp > HEAD_CACHE_DURATION:
            return None
        return entry.get("exists") is True

    def _save_head_cache_entry(self, cache_manager: CacheManager, cache_key: str, exists: bool) -> None:
        cached = cache_manager.load_json(HEAD_CACHE_NAME)
        if not isinstance(cached, dict):
            cached = {}
        cached[cache_key] = {"exists": exists, "timestamp": time.time()}
        cache_manager.save_json(HEAD_CACHE_NAME, cached)
        self._remove_old_head_cache_files(cache_manager)

    def _remove_old_head_cache_files(self, cache_manager: CacheManager) -> None:
        if self._head_disk_cache_cleaned:
            return
        for cache_file in cache_manager.cache_dir.glob(HEAD_CACHE_OLD_PATTERN):
            try:
                cache_file.unlink()
            except OSError as e:
                logger.debug("Failed to remove old HEAD cache %s: %s", cache_file, e)
        self._head_disk_cache_cleaned = True

    def _check_file_exists(self, url: str, timeout: int = 5) -> bool:
        if url in self._head_negative_cache:
            return False
        if url in self._head_positive_cache:
            return True
        last_failed_check = self._head_failure_cache.get(url)
        if last_failed_check and (time.time() - last_failed_check) < HEAD_FAILURE_RETRY_DELAY:
            return False

        cache_manager = CacheManager()
        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
        cached_exists = self._load_head_cache_entry(cache_manager, cache_key)
        if cached_exists is not None:
            return cached_exists

        try:
            session = get_requests_session()
            response = session.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 404:
                self._head_negative_cache.add(url)
                self._head_positive_cache.discard(url)
                self._head_failure_cache.pop(url, None)
                self._save_head_cache_entry(cache_manager, cache_key, False)
                return False
            response.raise_for_status()
            if response.status_code == 200:
                self._head_positive_cache.add(url)
                self._head_failure_cache.pop(url, None)
                self._save_head_cache_entry(cache_manager, cache_key, True)
                return True
            return False
        except requests.RequestException as e:
            logger.debug(f"Failed to check file at {url}: {e}")
            self._head_failure_cache[url] = time.time()
            return False

    def download_game_assets_async(self, exe_name: str, timeout: int = 5, callback: Callable[[dict[str, str | None]], None] | None = None) -> None:
        game_dir = self._get_game_dir(exe_name)
        cover_extensions = [".png"]
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

        metadata_found = False
        local_metadata_path = os.path.join(game_dir, "metadata.txt")
        if os.path.exists(local_metadata_path):
            logger.debug(f"Metadata already exists locally for {exe_name}: {local_metadata_path}")
            results["metadata"] = local_metadata_path
            metadata_found = True
        elif self._check_file_exists(metadata_url, timeout):
            metadata_found = True
            pending_downloads += 1
            self.downloader.download_async(
                metadata_url,
                local_metadata_path,
                timeout=timeout,
                callback=on_metadata_downloaded
            )

        if not metadata_found:
            logger.debug(f"No metadata found for {exe_name}, skipping cover checks")
            if callback:
                callback(results)
            return

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

        local_cover_path = os.path.join(user_game_folder, "cover.png")

        # Check if the cover already exists locally before attempting download
        if os.path.exists(local_cover_path):
            logger.debug(f"Async autoinstall cover already exists locally for {exe_name}: {local_cover_path}")
            if callback:
                callback(local_cover_path)
            return

        cover_url = f"{self.base_url}/{exe_name}/cover.png"

        def on_cover_downloaded(local_path: str | None):
            if local_path:
                logger.info(f"Async autoinstall cover downloaded for {exe_name}: {local_path}")
            else:
                logger.debug(f"No autoinstall cover downloaded for {exe_name}")
            if callback:
                callback(local_path)

        self.downloader.download_async(
            cover_url,
            local_cover_path,
            timeout=timeout,
            callback=on_cover_downloaded
        )

    def download_autoinstall_metadata_async(self, exe_name: str, timeout: int = 5, callback: Callable[[str | None], None] | None = None) -> None:
        """Download autoinstall metadata.txt file."""
        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        autoinstall_root = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", "autoinstall")
        user_game_folder = os.path.join(autoinstall_root, exe_name)

        if not os.path.isdir(user_game_folder):
            try:
                os.makedirs(user_game_folder, exist_ok=True)
            except FileExistsError:
                pass

        local_metadata_path = os.path.join(user_game_folder, "metadata.txt")

        # Check if the file already exists locally before attempting download
        if os.path.exists(local_metadata_path):
            logger.debug(f"Async autoinstall metadata already exists locally for {exe_name}: {local_metadata_path}")
            if callback:
                callback(local_metadata_path)
            return

        metadata_url = f"{self.base_url}/{exe_name}/metadata.txt"

        def on_metadata_downloaded(local_path: str | None):
            if local_path:
                logger.info(f"Async autoinstall metadata downloaded for {exe_name}: {local_path}")
            else:
                logger.debug(f"No autoinstall metadata downloaded for {exe_name}")
            if callback:
                callback(local_path)

        self.downloader.download_async(
            metadata_url,
            local_metadata_path,
            timeout=timeout,
            callback=on_metadata_downloaded
        )

    def download_autoinstall_assets_batch_async(
        self,
        exe_names: list[str],
        timeout: int = 5,
        cover_callback: Callable[[str, str | None], None] | None = None,
        metadata_callback: Callable[[str, str | None], None] | None = None
    ) -> None:
        """Download covers and metadata for multiple autoinstall games in parallel.

        Args:
            exe_names: List of executable names to download assets for
            timeout: Request timeout in seconds
            cover_callback: Callback(exe_name, local_path) for cover downloads
            metadata_callback: Callback(exe_name, local_path) for metadata downloads
        """
        xdg_data_home = os.getenv(
            "XDG_DATA_HOME",
            os.path.join(os.path.expanduser("~"), ".local", "share"),
        )
        autoinstall_root = os.path.join(
            xdg_data_home, "PortProtonQt", "custom_data", "autoinstall"
        )

        class AssetNotifier(QObject):
            cover_ready = Signal(str, object)
            metadata_ready = Signal(str, object)

        notifier = AssetNotifier()
        if cover_callback:
            notifier.cover_ready.connect(cover_callback, Qt.ConnectionType.DirectConnection)
        if metadata_callback:
            notifier.metadata_ready.connect(metadata_callback, Qt.ConnectionType.DirectConnection)
        self._pending_asset_notifier = notifier

        pending_tasks: list[tuple[str, str, SignalInstance, str, str]] = []

        for exe_name in exe_names:
            user_game_folder = os.path.join(autoinstall_root, exe_name)
            try:
                os.makedirs(user_game_folder, exist_ok=True)
            except FileExistsError:
                pass

            local_cover_path = os.path.join(user_game_folder, "cover.png")
            local_metadata_path = os.path.join(user_game_folder, "metadata.txt")

            cover_exists = os.path.exists(local_cover_path)
            metadata_exists = os.path.exists(local_metadata_path)

            if cover_exists:
                logger.debug(f"Batch cover already exists for {exe_name}: {local_cover_path}")
                notifier.cover_ready.emit(exe_name, local_cover_path)
            else:
                cover_url = f"{self.base_url}/{exe_name}/cover.png"
                pending_tasks.append((cover_url, local_cover_path, notifier.cover_ready, exe_name, "cover"))

            if metadata_exists:
                logger.debug(f"Batch metadata already exists for {exe_name}: {local_metadata_path}")
                notifier.metadata_ready.emit(exe_name, local_metadata_path)
            else:
                metadata_url = f"{self.base_url}/{exe_name}/metadata.txt"
                pending_tasks.append((metadata_url, local_metadata_path, notifier.metadata_ready, exe_name, "metadata"))

        if not pending_tasks:
            return

        pending_tasks_by_url = {task[0]: task for task in pending_tasks}

        class BatchDownloadWorker(QThread):
            item_ready = Signal(str, object)
            finished = Signal()
            downloader: Downloader
            urls: list[str]
            local_paths: list[str]
            timeout: int

            def run(self):
                self.downloader.download_parallel(
                    self.urls,
                    self.local_paths,
                    timeout=self.timeout,
                    on_result=lambda url, result: self.item_ready.emit(url, result),
                )
                self.finished.emit()

        worker = BatchDownloadWorker()
        worker.downloader = self.downloader
        worker.urls = [task[0] for task in pending_tasks]
        worker.local_paths = [task[1] for task in pending_tasks]
        worker.timeout = timeout

        def on_item_ready(url: str, result: str | None):
            task = pending_tasks_by_url.get(url)
            if task is None:
                return
            _url, _local_path, signal, exe_name, asset_type = task
            if result:
                logger.info(f"{asset_type.capitalize()} downloaded for {exe_name}: {result}")
            else:
                logger.debug(f"No {asset_type} found for {exe_name}")
            signal.emit(exe_name, result)

        def on_batch_finished():
            self._pending_asset_batch_thread = None

        worker.item_ready.connect(on_item_ready)
        worker.finished.connect(on_batch_finished)
        worker.finished.connect(worker.deleteLater)
        self._pending_asset_batch_thread = worker
        worker.start()

    def get_autoinstall_description(self, exe_name: str, lang_code: str = "en") -> str | None:
        """Read description from downloaded metadata.txt file for autoinstall game.

        Args:
            exe_name: The executable name/script name
            lang_code: Language code ("en" or "ru" for description)

        Returns:
            Description string or None if not found
        """
        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        autoinstall_root = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", "autoinstall")
        metadata_path = os.path.join(autoinstall_root, exe_name, "metadata.txt")

        if not os.path.exists(metadata_path):
            return None

        try:
            with open(metadata_path, encoding='utf-8') as f:
                content = f.read()

            # Parse the metadata content to extract description
            # Format: description_en=... or description_ru=...
            if lang_code == "ru":
                pattern = r'^description_ru=(.*)$'
            else:
                pattern = r'^description_en=(.*)$'

            match = re.search(pattern, content, re.MULTILINE)
            if match:
                description = match.group(1).strip()
                # Handle potential quoted strings
                if description.startswith('"') and description.endswith('"'):
                    description = description[1:-1]
                return description
            else:
                # Try fallback to the other language if the requested one is not found
                fallback_lang = "ru" if lang_code == "en" else "en"
                fallback_pattern = rf'^description_{fallback_lang}=(.*)$'
                fallback_match = re.search(fallback_pattern, content, re.MULTILINE)
                if fallback_match:
                    description = fallback_match.group(1).strip()
                    if description.startswith('"') and description.endswith('"'):
                        description = description[1:-1]
                    return description
        except Exception as e:
            logger.error(f"Error reading metadata for {exe_name}: {e}")

        return None

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
                    if "PW_EXE_FILE" in stripped and "=" in stripped:
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
        cache_manager = CacheManager()
        if cache_manager.exists("autoinstall_games_cache"):
            try:
                data = cache_manager.load_json("autoinstall_games_cache")
                if data:
                    mod_time = cache_manager.get_file_age("autoinstall_games_cache")
                    if mod_time is not None and mod_time < AUTOINSTALL_CACHE_DURATION:
                        start_time = time.time()
                        cached_signature = data.get("scripts_signature", "")
                        scripts_path = get_portproton_scripts_path()
                        auto_dir = os.path.join(scripts_path, "pw_autoinstall") if scripts_path else ""
                        current_signature = self._compute_scripts_signature(auto_dir)
                        if time.time() - start_time > 3:
                            logger.warning("Cache loading took too long, skipping cache")
                            return None
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
            cache_manager = CacheManager()
            scripts_path = get_portproton_scripts_path()
            auto_dir = os.path.join(scripts_path, "pw_autoinstall") if scripts_path else ""
            scripts_signature = self._compute_scripts_signature(auto_dir)
            data = {"games": games, "scripts_signature": scripts_signature, "timestamp": time.time()}
            cache_manager.save_json("autoinstall_games_cache", data)
            logger.debug(f"Saved {len(games)} autoinstall games to cache with signature {scripts_signature}")
        except Exception as e:
            logger.error(f"Failed to save autoinstall cache: {e}")

    def start_autoinstall_games_load(self, callback: Callable[[list[tuple]], None]) -> QThread | None:
        """Start loading auto-install games in a background thread. Returns the thread for management."""
        class AutoinstallWorker(QThread):
            finished = Signal(list)
            api: "PortProtonAPI"
            portproton_location: str | None

            def run(self):
                # Check cache in this background thread, not in main thread
                start_time = time.time()
                cached_games = self.api._load_autoinstall_cache()
                # If cache loading took too long (>2 seconds), skip cache and load directly
                if time.time() - start_time > 2:
                    logger.warning("Cache loading took too long, proceeding without cache")
                    cached_games = None

                if cached_games is not None:
                    self.finished.emit(cached_games)
                    return

                # No cache: Load games from scratch
                games = []
                scripts_path = get_portproton_scripts_path()
                if not scripts_path:
                    logger.info("PortProton scripts path is not resolved for autoinstall games")
                    self.finished.emit(games)
                    return

                auto_dir = os.path.join(scripts_path, "pw_autoinstall")
                if not os.path.exists(auto_dir):
                    logger.info("PortProton autoinstall scripts directory not found: %s", auto_dir)
                    self.finished.emit(games)
                    return

                scripts = sorted(glob.glob(os.path.join(auto_dir, "*")))
                if not scripts:
                    logger.info("PortProton autoinstall scripts not found in: %s", auto_dir)
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
                    for ext in COVER_IMAGE_EXTENSIONS:
                        candidate = f"cover{ext}"
                        if candidate in user_files:
                            cover_path = os.path.join(user_game_folder, candidate)
                            break

                    if not cover_path:
                        logger.debug(f"No local cover found for autoinstall {exe_name}")

                    # Try to get the description from metadata file
                    description = ""
                    # Look for metadata in the expected location
                    try:
                        current_locale = locale.getlocale()[0] or 'en'
                    except (AttributeError, IndexError, TypeError):
                        current_locale = 'en'
                    lang_code = 'ru' if current_locale and 'ru' in current_locale.lower() else 'en'

                    # Try to read description from downloaded metadata
                    metadata_description = self.api.get_autoinstall_description(exe_name, lang_code)
                    if metadata_description:
                        description = metadata_description

                    game_tuple = (
                        display_name, description, cover_path, "",
                        "", f"autoinstall:{script_name}", "Never", "0h 0m", "", "", 0, 0, "autoinstall", exe_name
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

    def get_ppdb_url(self, game_name: str, exe_name: str) -> str:
        """Get the PPDB URL for a given game.

        Makes an API call to ppdb.linux-gaming.ru to look up the game by exe name.
        If the returned name matches the game name, returns the direct URL.
        Otherwise returns a search URL to avoid false positives (e.g., launcher.exe matches many games).

        Args:
            game_name: Display name of the game
            exe_name: Executable name (with or without .exe extension)

        Returns:
            Full URL to the PPDB page or search page
        """
        base_url = "https://ppdb.linux-gaming.ru"

        # Ensure exe_name has .exe extension
        if not exe_name.lower().endswith(".exe"):
            exe_name = f"{exe_name}.exe"

        api_url = f"{base_url}/api/lookup/exe/{urllib.parse.quote(exe_name)}"

        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                api_name = data.get("name", "")
                api_url_result = data.get("url", "")

                # Compare normalized names to avoid false positives
                if api_name and api_url_result:
                    normalized_game = normalize_name(game_name)
                    normalized_api = normalize_name(api_name)

                    if normalized_game == normalized_api:
                        logger.debug("PPDB exact match for %s: %s", game_name, api_url_result)
                        return api_url_result

                    logger.debug(
                        "PPDB name mismatch for %s (exe: %s): API returned '%s', redirecting to search",
                        game_name, exe_name, api_name
                    )
        except requests.RequestException as e:
            logger.debug("PPDB API request failed for %s: %s", exe_name, e)
        except (ValueError, KeyError) as e:
            logger.debug("PPDB API response parsing failed for %s: %s", exe_name, e)

        # Fallback to search URL
        encoded_name = urllib.parse.quote(game_name)
        return f"{base_url}/browse?search={encoded_name}"

    def open_ppdb_page(self, game_name: str, exec_line: str) -> None:
        """Open the PPDB page for a game in the default browser.

        Args:
            game_name: Display name of the game
            exec_line: Exec line from which to extract the exe name
        """
        exe_name = extract_exe_name(exec_line)
        url = self.get_ppdb_url(game_name, exe_name)
        QDesktopServices.openUrl(QUrl(url))

    def download_ppdb_from_url(self, download_url: str) -> bool:
        """Download PPDB file from the given URL and place it next to the selected .exe file.

        Args:
            download_url: The full URL to download the PPDB file from

        Returns:
            True if download was successful, False otherwise
        """
        try:
            # Get the .exe file path directly from FileExplorer
            exe_path = self.ask_user_for_exe_location()
            if not exe_path:
                logger.error("User did not provide .exe file location")
                return False

            # Determine the destination directory for the PPDB file (next to the .exe file)
            exe_dir = os.path.dirname(exe_path)

            # Generate the PPDB filename based on the .exe filename
            exe_basename = os.path.basename(exe_path)
            if exe_basename.lower().endswith('.exe'):
                ppdb_filename = f"{os.path.splitext(exe_basename)[0]}.ppdb"
            else:
                ppdb_filename = f"{exe_basename}.ppdb"

            destination_path = os.path.join(exe_dir, ppdb_filename)

            logger.info(f"Downloading PPDB from {download_url} to {destination_path}")

            # Use the existing downloader synchronously
            try:
                # Download to a temporary file first
                temp_path = destination_path + ".tmp"
                response = requests.get(download_url, timeout=30)
                if response.status_code == 200:
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)

                    # Move the file to its final location
                    shutil.move(temp_path, destination_path)
                    logger.info(f"Successfully downloaded PPDB to {destination_path}")

                    return True
                else:
                    logger.error(f"Failed to download PPDB: HTTP {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Error during download: {e}")
                # Clean up temp file if it exists
                if os.path.exists(destination_path + ".tmp"):
                    os.remove(destination_path + ".tmp")
                return False

        except requests.RequestException as e:
            logger.error(f"Request error downloading PPDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Error downloading PPDB: {e}")
            return False


    def ask_user_for_exe_location(self) -> str | None:
        """Ask the user for the location of the .exe file.

        Returns:
            Path to the .exe file if provided by user, None otherwise
        """
        # Check if we're running in GUI mode
        app = QApplication.instance()
        if app is None:
            logger.info("No GUI application instance available for FileExplorer")
            return None

        result_queue = queue.Queue()
        parent, bootstrap_input_manager = _create_bootstrap_file_explorer_parent()

        def on_file_selected(file_path):
            result_queue.put(file_path)

        file_explorer = FileExplorer(
            parent=parent,
            file_filter=".exe",
            initial_path=os.path.expanduser("~")
        )
        file_explorer.setWindowTitle(_("Select file for PPDB download"))
        file_explorer.file_signal.file_selected.connect(on_file_selected)

        try:
            file_explorer.exec()
        finally:
            if bootstrap_input_manager:
                bootstrap_input_manager.cleanup()
            if parent and bootstrap_input_manager:
                parent.deleteLater()

        try:
            selected_file = result_queue.get(timeout=0.1)  # Small timeout to get result
            if selected_file and os.path.exists(selected_file) and selected_file.lower().endswith('.exe'):
                logger.info(f"User selected .exe file: {selected_file}")
                return selected_file
            logger.info("No valid .exe file selected by user")
            return None
        except queue.Empty:
            logger.info("No file selected in FileExplorer")
            return None




def get_user_conf_setting(variable_name):
    """
    Gets the value of a specific variable from user.conf.

    Args:
        variable_name: Name of the variable to get

    Returns:
        Value of the variable or None if not set
    """

    start_cmd = get_portproton_start_command()
    if not start_cmd:
        logger.error("Could not determine PortProton start command")
        return None
    try:
        result = subprocess.run(
            start_cmd + ["cli", "--get-user-conf", variable_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning("Failed to get user.conf value for %s: %s", variable_name, e)
        return None

    if result.returncode != 0:
        logger.debug("PortProton CLI returned %s for --get-user-conf %s", result.returncode, variable_name)
        return None

    clean_lines = []
    for line in result.stdout.splitlines():
        stripped_line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line).strip()
        if not stripped_line:
            continue
        if any(char in stripped_line for char in "█░▄▀╔╗╚╝║"):
            continue
        if re.match(r'^\[?[0-9;]*m?\s*(Info|Warning|Error|OK):', stripped_line):
            continue
        if "must use subscript when assigning associative array" in stripped_line:
            continue
        if " '" in stripped_line and stripped_line.endswith("'"):
            line_start, quoted_path = stripped_line.rsplit(" '", 1)
            if line_start and quoted_path.startswith("/"):
                continue
        clean_lines.append(stripped_line)

    if not clean_lines:
        return None

    return clean_lines[-1]


def set_user_conf_setting(variable_name, value):
    """
    Sets or deletes a specific variable in user.conf via PortProton CLI.

    Args:
        variable_name: Name of the variable to set or delete
        value: Value to set, or None/empty to delete the variable
    """
    start_cmd = get_portproton_start_command()
    if not start_cmd:
        logger.error("Could not determine PortProton start command")
        return False

    if value is None or value == "":
        cli_args = ["cli", "--delete-user-conf", variable_name]
    else:
        cli_args = ["cli", "--set-user-conf", variable_name, str(value)]

    try:
        result = subprocess.run(
            start_cmd + cli_args,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning("Failed to update user.conf value for %s: %s", variable_name, e)
        return False

    if result.returncode != 0:
        logger.warning(
            "PortProton CLI failed for %s (code %s): %s",
            variable_name,
            result.returncode,
            result.stderr.strip(),
        )
        return False

    return True
