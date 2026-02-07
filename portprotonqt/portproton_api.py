import os
import orjson
import requests
import urllib.parse
import time
import glob
import re
import hashlib
from collections.abc import Callable
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger
from portprotonqt.config_utils import get_portproton_location

logger = get_logger(__name__)
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


def extract_exe_name(exec_line: str) -> str:
    """Extract executable name from exec_line.

    Handles various exec_line formats:
    - Full command: 'env VAR=val /path/to/script /path/to/game.exe' -> 'game.exe'
    - Autoinstall: 'autoinstall:script_name' -> ''
    - Simple path: '/path/to/game.exe' -> 'game.exe'

    Returns:
        Executable name with .exe extension, or empty string if not found
    """
    import shlex

    if not exec_line:
        return ""

    # Handle autoinstall scripts - they don't have a direct exe
    if exec_line.startswith("autoinstall:"):
        return ""

    try:
        parts = shlex.split(exec_line)

        # Search for the last part ending with .exe
        # In PortProton format, the game exe is always the last argument
        for part in reversed(parts):
            if part.lower().endswith(".exe"):
                game_exe = os.path.expanduser(part)
                return os.path.basename(game_exe)

        return ""
    except (ValueError, IndexError):
        return ""

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
        self.downloader = downloader or Downloader(max_workers=4)
        self.xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        self.custom_data_dir = os.path.join(self.xdg_data_home, "PortProtonQt", "custom_data")
        os.makedirs(self.custom_data_dir, exist_ok=True)
        self.portproton_location = get_portproton_location()
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.builtin_custom_folder = os.path.join(self.repo_root, "custom_data")
        self._autoinstall_cache = None  # In-memory cache

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

        # Check if metadata already exists locally before attempting download
        local_metadata_path = os.path.join(game_dir, "metadata.txt")
        if os.path.exists(local_metadata_path):
            logger.debug(f"Metadata already exists locally for {exe_name}: {local_metadata_path}")
            results["metadata"] = local_metadata_path
        elif self._check_file_exists(metadata_url, timeout):
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

        if self._check_file_exists(metadata_url, timeout):
            self.downloader.download_async(
                metadata_url,
                local_metadata_path,
                timeout=timeout,
                callback=on_metadata_downloaded
            )
        else:
            logger.debug(f"No autoinstall metadata found for {exe_name}")
            if callback:
                callback(None)

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

            import re
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
                    # Add timeout protection for file operations
                    start_time = time.time()
                    with open(cache_file, "rb") as f:
                        data = orjson.loads(f.read())
                        # Check signature
                        cached_signature = data.get("scripts_signature", "")
                        current_signature = self._compute_scripts_signature(
                            os.path.join(self.portproton_location or "", "data", "scripts", "pw_autoinstall")
                        )
                        # Check for timeout during signature computation
                        if time.time() - start_time > 3:  # 3 second timeout
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
        class AutoinstallWorker(QThread):
            finished = Signal(list)
            api: "PortProtonAPI"
            portproton_location: str | None

            def run(self):
                import time
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

                    # Try to get the description from metadata file
                    description = ""
                    # Look for metadata in the expected location
                    try:
                        import locale
                        current_locale = locale.getlocale()[0] or 'en'
                    except (AttributeError, IndexError, TypeError):
                        current_locale = 'en'
                    lang_code = 'ru' if current_locale and 'ru' in current_locale.lower() else 'en'

                    # Try to read description from downloaded metadata
                    metadata_description = self.api.get_autoinstall_description(exe_name, lang_code)
                    if metadata_description:
                        description = metadata_description

                    game_tuple = (
                        display_name, description, cover_path, "", f"autoinstall:{script_name}",
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
            exe_path = self.ask_user_for_exe_location("the game executable")
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
                    import shutil
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


    def ask_user_for_exe_location(self, exe_name: str) -> str | None:
        """Ask the user for the location of the .exe file.

        Args:
            exe_name: Name of the executable to find

        Returns:
            Path to the .exe file if provided by user, None otherwise
        """
        # Import FileExplorer as requested
        from PySide6.QtWidgets import QApplication
        from portprotonqt.dialogs import FileExplorer

        # Check if we're running in GUI mode
        app = QApplication.instance()
        if app is not None:
            # Use FileExplorer which is adapted for gamepad control
            import queue
            result_queue = queue.Queue()

            def on_file_selected(file_path):
                result_queue.put(file_path)

            # Create and configure FileExplorer
            from portprotonqt.dialogs import FileExplorer
            file_explorer = FileExplorer(
                file_filter=".exe",
                initial_path=os.path.expanduser("~")
            )
            file_explorer.setWindowTitle(f"Select {exe_name} file for PPDB download")

            # Connect the file selection signal
            file_explorer.file_signal.file_selected.connect(on_file_selected)

            # Show the dialog
            file_explorer.exec()

            # Get the selected file from the queue
            try:
                selected_file = result_queue.get(timeout=0.1)  # Small timeout to get result
                if selected_file and os.path.exists(selected_file) and selected_file.lower().endswith('.exe'):
                    logger.info(f"User selected .exe file: {selected_file}")
                    return selected_file
                else:
                    logger.info("No valid .exe file selected by user")
                    return None
            except queue.Empty:
                logger.info("No file selected in FileExplorer")
                return None
        else:
            logger.info("No GUI application instance available for FileExplorer")
            return None
