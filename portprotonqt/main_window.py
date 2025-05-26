import os
import shlex
import shutil
import signal
import subprocess
import sys
import orjson
from pathlib import Path
import time

import portprotonqt.themes.standart.styles as default_styles
import psutil

from portprotonqt.dialogs import AddGameDialog
from portprotonqt.game_card import GameCard
from portprotonqt.custom_widgets import FlowLayout, ClickableLabel, AutoSizeButton, NavLabel
from portprotonqt.input_manager import InputManager
from portprotonqt.context_menu_manager import ContextMenuManager

from portprotonqt.image_utils import load_pixmap_async, round_corners, ImageCarousel
from portprotonqt.steam_api import get_steam_game_info_async, get_full_steam_game_info_async, get_steam_installed_games, get_weanticheatyet_status_async
from portprotonqt.theme_manager import ThemeManager, load_theme_screenshots, load_logo
from portprotonqt.time_utils import save_last_launch, get_last_launch, parse_playtime_file, format_playtime, get_last_launch_timestamp, format_last_launch
from portprotonqt.config_utils import (
    get_portproton_location, read_theme_from_config, save_theme_to_config, parse_desktop_entry, load_theme_metainfo, read_time_config, read_card_size, save_card_size,
    read_sort_method, read_display_filter, read_favorites, save_favorites, save_time_config, save_sort_method, save_display_filter, save_proxy_config, read_proxy_config,
    read_fullscreen_config, save_fullscreen_config, read_window_geometry, save_window_geometry, reset_config, clear_cache
)
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.downloader import Downloader

from PySide6.QtWidgets import (QLineEdit, QMainWindow, QStatusBar, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QStackedWidget, QComboBox, QScrollArea, QSlider,
                               QDialog, QFormLayout, QFrame, QGraphicsDropShadowEffect, QMessageBox, QGraphicsEffect, QGraphicsOpacityEffect, QApplication, QPushButton, QProgressBar, QCheckBox)
from PySide6.QtGui import QIcon, QPixmap, QColor, QDesktopServices
from PySide6.QtCore import Qt, QAbstractAnimation, QPropertyAnimation, QByteArray, QUrl, Signal, QTimer, Slot
from typing import cast
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = get_logger(__name__)

class MainWindow(QMainWindow):
    """Main window of PortProtonQT."""
    settings_saved = Signal()
    games_loaded = Signal(list)
    update_progress = Signal(int)  # Signal to update progress bar
    update_status_message = Signal(str, int)  # Signal to update status message

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.current_exec_line = None
        self.currentDetailPage = None
        self.current_play_button = None
        self.pending_games = []
        self.total_games = 0
        self.games_load_timer = QTimer(self)
        self.games_load_timer.setSingleShot(True)
        self.games_load_timer.timeout.connect(self.finalize_game_loading)
        self.games_loaded.connect(self.on_games_loaded)

        read_time_config()
        # Set LEGENDARY_CONFIG_PATH to ~/.cache/PortProtonQT/legendary
        self.legendary_config_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQT", "legendary_cache"
        )
        os.makedirs(self.legendary_config_path, exist_ok=True)
        os.environ["LEGENDARY_CONFIG_PATH"] = self.legendary_config_path

        self.legendary_path = os.path.join(self.legendary_config_path, "legendary")
        self.downloader = Downloader(max_workers=4)

        # Создаём менеджер тем и читаем, какая тема выбрана
        self.theme_manager = ThemeManager()
        selected_theme = read_theme_from_config()
        self.current_theme_name = selected_theme
        try:
            self.theme = self.theme_manager.apply_theme(selected_theme)
        except FileNotFoundError:
            logger.warning(f"Тема '{selected_theme}' не найдена, применяется стандартная тема 'standart'")
            self.theme = self.theme_manager.apply_theme("standart")
            self.current_theme_name = "standart"
            save_theme_to_config("standart")
        if not self.theme:
            self.theme = default_styles
        self.card_width = read_card_size()
        self.setWindowTitle("PortProtonQT")
        self.setMinimumSize(800, 600)

        self.games = []
        self.game_processes = []
        self.target_exe = None
        self.current_running_button = None
        self.portproton_location = get_portproton_location()

        self.context_menu_manager = ContextMenuManager(
            self,
            self.portproton_location,
            self.theme,
            self.loadGames,
            self.updateGameGrid
        )

        # Статус-бар
        self.setStatusBar(QStatusBar(self))
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.update_progress.connect(self.progress_bar.setValue)
        self.update_status_message.connect(self.statusBar().showMessage)

        # Центральный виджет и основной layout
        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QVBoxLayout(centralWidget)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        # 1. ШАПКА (HEADER)
        self.header = QWidget()
        self.header.setFixedHeight(80)
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        headerLayout = QVBoxLayout(self.header)
        headerLayout.setContentsMargins(0, 0, 0, 0)

        # Текст "PortProton" слева
        self.titleLabel = QLabel()
        pixmap = load_logo()
        if pixmap is None:
            width, height = self.theme.pixmapsScaledSize
            pixmap = QPixmap(width, height)
            pixmap.fill(QColor(0, 0, 0, 0))
        width, height = self.theme.pixmapsScaledSize
        scaled_pixmap = pixmap.scaled(width, height,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
        self.titleLabel.setPixmap(scaled_pixmap)
        self.titleLabel.setFixedSize(scaled_pixmap.size())
        self.titleLabel.setStyleSheet(self.theme.TITLE_LABEL_STYLE)
        headerLayout.addStretch()

        # 2. НАВИГАЦИЯ (КНОПКИ ВКЛАДОК)
        self.navWidget = QWidget()
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        navLayout = QHBoxLayout(self.navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(0)

        navLayout.addWidget(self.titleLabel)

        self.tabButtons = {}
        tabs = [
            _("Library"),
            _("Auto Install"),
            _("Emulators"),
            _("Wine Settings"),
            _("PortProton Settings"),
            _("Themes")
        ]
        for i, tabName in enumerate(tabs):
            btn = NavLabel(tabName)
            btn.setCheckable(True)
            btn.clicked.connect(lambda index=i: self.switchTab(index))
            btn.setStyleSheet(self.theme.NAV_BUTTON_STYLE)
            navLayout.addWidget(btn)
            self.tabButtons[i] = btn

        self.tabButtons[0].setChecked(True)
        mainLayout.addWidget(self.navWidget)

        # 3. QStackedWidget (ВКЛАДКИ)
        self.stackedWidget = QStackedWidget()
        mainLayout.addWidget(self.stackedWidget)

        # Создаём все вкладки
        self.createInstalledTab()    # вкладка 0
        self.createAutoInstallTab()  # вкладка 1
        self.createEmulatorsTab()    # вкладка 2
        self.createWineTab()         # вкладка 3
        self.createPortProtonTab()   # вкладка 4
        self.createThemeTab()        # вкладка 5

        self.restore_state()

        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
        self.setStyleSheet(self.theme.MESSAGE_BOX_STYLE)
        self.input_manager = InputManager(self)
        QTimer.singleShot(0, self.loadGames)

        if read_fullscreen_config():
            self.showFullScreen()
        else:
            width, height = read_window_geometry()
            if width > 0 and height > 0:
                self.resize(width, height)
            else:
                self.showNormal()

    @Slot(list)
    def on_games_loaded(self, games: list[tuple]):
        self.games = games
        favorites = read_favorites()
        sort_method = read_sort_method()

        # Sort by: favorites first, then descending playtime, then descending last launch
        if sort_method == "playtime":
            self.games.sort(key=lambda g: (0 if g[0] in favorites else 1, -g[11], -g[10]))

        # Sort by: favorites first, then alphabetically by game name
        elif sort_method == "alphabetical":
            self.games.sort(key=lambda g: (0 if g[0] in favorites else 1, g[0].lower()))

        # Sort by: favorites first, then leave the rest in their original order
        elif sort_method == "favorites":
            self.games.sort(key=lambda g: (0 if g[0] in favorites else 1))

        # Sort by: favorites first, then descending last launch, then descending playtime
        elif sort_method == "last_launch":
            self.games.sort(key=lambda g: (0 if g[0] in favorites else 1, -g[10], -g[11]))

        # Fallback: same as last_launch
        else:
            self.games.sort(key=lambda g: (0 if g[0] in favorites else 1, -g[10], -g[11]))

        self.updateGameGrid()
        self.progress_bar.setVisible(False)

    def loadGames(self):
        display_filter = read_display_filter()
        favorites = read_favorites()
        self.pending_games = []
        self.games = []
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        if display_filter == "steam":
            self._load_steam_games_async(lambda games: self.games_loaded.emit(games))
        elif display_filter == "portproton":
            self._load_portproton_games_async(lambda games: self.games_loaded.emit(games))
        elif display_filter == "epic":
            self._load_egs_games_async(lambda games: self.games_loaded.emit(games))
        elif display_filter == "favorites":
            def on_all_games(portproton_games, steam_games, epic_games):
                games = [game for game in portproton_games + steam_games + epic_games if game[0] in favorites]
                self.games_loaded.emit(games)
            self._load_portproton_games_async(
                lambda pg: self._load_steam_games_async(
                    lambda sg: self._load_egs_games_async(
                        lambda eg: on_all_games(pg, sg, eg)
                    )
                )
            )
        else:
            def on_all_games(portproton_games, steam_games, epic_games):
                seen = set()
                games = []
                for game in portproton_games + steam_games + epic_games:
                    name = game[0]
                    if name not in seen:
                        seen.add(name)
                        games.append(game)
                self.games_loaded.emit(games)
            self._load_portproton_games_async(
                lambda pg: self._load_steam_games_async(
                    lambda sg: self._load_egs_games_async(
                        lambda eg: on_all_games(pg, sg, eg)
                    )
                )
            )
        return []

    def _load_steam_games_async(self, callback: Callable[[list[tuple]], None]):
        steam_games = []
        installed_games = get_steam_installed_games()
        logger.info("Found %d installed Steam games: %s", len(installed_games), [g[0] for g in installed_games])
        if not installed_games:
            callback(steam_games)
            return
        self.total_games = len(installed_games)
        self.update_progress.emit(0)  # Initialize progress bar
        self.update_status_message.emit(_("Loading Steam games..."), 3000)
        processed_count = 0

        def on_game_info(info: dict, name, appid, last_played, playtime_seconds):
            nonlocal processed_count
            if not info:
                logger.warning("No info retrieved for game %s (appid %s)", name, appid)
                info = {
                    'description': '',
                    'cover': '',
                    'controller_support': '',
                    'protondb_tier': '',
                    'name': name,
                    'steam_game': 'true'
                }
            last_launch = format_last_launch(datetime.fromtimestamp(last_played)) if last_played else _("Never")
            steam_games.append((
                name,
                info.get('description', ''),
                info.get('cover', ''),
                appid,
                f"steam://rungameid/{appid}",
                info.get('controller_support', ''),
                last_launch,
                format_playtime(playtime_seconds),
                info.get('protondb_tier', ''),
                info.get("anticheat_status", ""),
                last_played,
                playtime_seconds,
                "true"
            ))
            processed_count += 1
            self.pending_games.append(None)
            self.update_progress.emit(len(self.pending_games))  # Update progress bar
            logger.info("Game %s processed, processed_count: %d/%d", name, processed_count, len(installed_games))
            if processed_count == len(installed_games):
                callback(steam_games)

        for name, appid, last_played, playtime_seconds in installed_games:
            logger.debug("Requesting info for game %s (appid %s)", name, appid)
            get_full_steam_game_info_async(appid, lambda info, n=name, a=appid, lp=last_played, pt=playtime_seconds: on_game_info(info, n, a, lp, pt))

    def _load_portproton_games_async(self, callback: Callable[[list[tuple]], None]):
        games = []
        if not self.portproton_location:
            callback(games)
            return
        desktop_files = [entry.path for entry in os.scandir(self.portproton_location)
                        if entry.name.endswith(".desktop")]
        if not desktop_files:
            callback(games)
            return
        self.total_games = len(desktop_files)
        self.update_progress.emit(0)  # Initialize progress bar
        self.update_status_message.emit(_("Loading PortProton games..."), 3000)
        def on_desktop_processed(result: tuple | None, games=games):
            if result:
                games.append(result)
            self.pending_games.append(None)
            self.update_progress.emit(len(self.pending_games))  # Update progress bar
            if len(self.pending_games) == len(desktop_files):
                callback(games)
        with ThreadPoolExecutor() as executor:
            for file_path in desktop_files:
                executor.submit(self._process_desktop_file_async, file_path, on_desktop_processed)

    def _process_desktop_file_async(self, file_path: str, callback: Callable[[tuple | None], None]):
        entry = parse_desktop_entry(file_path)
        if not entry:
            callback(None)
            return
        desktop_name = entry.get("Name", _("Unknown Game"))
        if desktop_name.lower() in ["portproton", "readme"]:
            callback(None)
            return
        exec_line = entry.get("Exec", "")
        game_exe = ""
        exe_name = ""
        playtime_seconds = 0
        formatted_playtime = ""

        if exec_line:
            parts = shlex.split(exec_line)
            game_exe = os.path.expanduser(parts[3] if len(parts) >= 4 else exec_line)

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        builtin_custom_folder = os.path.join(repo_root, "portprotonqt", "custom_data")
        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        user_custom_folder = os.path.join(xdg_data_home, "PortProtonQT", "custom_data")
        os.makedirs(user_custom_folder, exist_ok=True)

        builtin_cover = ""
        builtin_name = None
        builtin_desc = None
        user_cover = ""
        user_name = None
        user_desc = None

        if game_exe:
            exe_name = os.path.splitext(os.path.basename(game_exe))[0]
            builtin_game_folder = os.path.join(builtin_custom_folder, exe_name)
            user_game_folder = os.path.join(user_custom_folder, exe_name)
            os.makedirs(user_game_folder, exist_ok=True)

            builtin_files = set(os.listdir(builtin_game_folder)) if os.path.exists(builtin_game_folder) else set()
            for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                candidate = f"cover{ext}"
                if candidate in builtin_files:
                    builtin_cover = os.path.join(builtin_game_folder, candidate)
                    break

            builtin_metadata_file = os.path.join(builtin_game_folder, "metadata.txt")
            if os.path.exists(builtin_metadata_file):
                with open(builtin_metadata_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("name="):
                            builtin_name = line[len("name="):].strip()
                        elif line.startswith("description="):
                            builtin_desc = line[len("description="):].strip()

            user_files = set(os.listdir(user_game_folder)) if os.path.exists(user_game_folder) else set()
            for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                candidate = f"cover{ext}"
                if candidate in user_files:
                    user_cover = os.path.join(user_game_folder, candidate)
                    break

            user_metadata_file = os.path.join(user_game_folder, "metadata.txt")
            if os.path.exists(user_metadata_file):
                with open(user_metadata_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("name="):
                            user_name = line[len("name="):].strip()
                        elif line.startswith("description="):
                            user_desc = line[len("description="):].strip()

            if self.portproton_location:
                statistics_file = os.path.join(self.portproton_location, "data", "tmp", "statistics")
                try:
                    playtime_data = parse_playtime_file(statistics_file)
                    matching_key = next(
                        (key for key in playtime_data if os.path.basename(key).split('.')[0] == exe_name),
                        None
                    )
                    if matching_key:
                        playtime_seconds = playtime_data[matching_key]
                        formatted_playtime = format_playtime(playtime_seconds)
                except Exception as e:
                    print(f"Failed to parse playtime data: {e}")

        def on_steam_info(steam_info: dict):
            final_name = user_name or builtin_name or desktop_name
            final_desc = (user_desc if user_desc is not None else
                        builtin_desc if builtin_desc is not None else
                        steam_info.get("description", ""))
            final_cover = (user_cover if user_cover else
                        builtin_cover if builtin_cover else
                        steam_info.get("cover", "") or entry.get("Icon", ""))
            steam_game = "false"
            callback((
                final_name,
                final_desc,
                final_cover,
                steam_info.get("appid", ""),
                exec_line,
                steam_info.get("controller_support", ""),
                get_last_launch(exe_name) if exe_name else _("Never"),
                formatted_playtime,
                steam_info.get("protondb_tier", ""),
                steam_info.get("anticheat_status", ""),
                get_last_launch_timestamp(exe_name) if exe_name else 0,
                playtime_seconds,
                steam_game
            ))

        get_steam_game_info_async(desktop_name, exec_line, on_steam_info)

    def _load_egs_games_async(self, callback: Callable[[list[tuple]], None]):
            logger.debug("Starting to load Epic Games Store games")
            games: list[tuple] = []
            metadata_dir = Path(self.legendary_config_path) / "metadata"
            cache_dir = Path(self.legendary_config_path)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / "legendary_games.json"
            cache_ttl = 3600  # Cache TTL in seconds (e.g., 1 hour)

            # Ensure legendary binary is available
            self.legendary_path = os.path.join(self.legendary_config_path, "legendary")
            if not os.path.exists(self.legendary_path):
                logger.info("Legendary binary not found, downloading...")

                def on_legendary_downloaded(result):
                    if result:
                        logger.info("Legendary binary downloaded successfully")
                        # Make the binary executable
                        try:
                            os.chmod(self.legendary_path, 0o755)
                            logger.debug("Made legendary binary executable")
                        except Exception as e:
                            logger.error(f"Failed to make legendary binary executable: {e}")

                        # Continue with loading games
                        self._continue_loading_egs_games(callback, metadata_dir, cache_dir, cache_file, cache_ttl)
                    else:
                        logger.error("Failed to download legendary binary")
                        callback(games)

                self.downloader.download_legendary_binary(on_legendary_downloaded)
                return
            else:
                # Legendary binary exists, continue with loading games
                self._continue_loading_egs_games(callback, metadata_dir, cache_dir, cache_file, cache_ttl)

    def _continue_loading_egs_games(self, callback: Callable[[list[tuple]], None], metadata_dir, cache_dir, cache_file, cache_ttl):
        games: list[tuple] = []

        # Check if cache exists and is fresh, and metadata directory exists
        installed_games = None
        use_cache = False

        if cache_file.exists():
            try:
                cache_mtime = cache_file.stat().st_mtime
                if time.time() - cache_mtime < cache_ttl:
                    # Check if metadata directory exists and is not empty
                    if metadata_dir.exists() and any(metadata_dir.iterdir()):
                        logger.debug("Loading Epic Games Store games from cache: %s", cache_file)
                        with open(cache_file, "rb") as f:
                            installed_games = orjson.loads(f.read())
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

        # If cache is missing, invalid, or metadata directory is empty, fetch from legendary
        if not use_cache or installed_games is None:
            try:
                logger.info("Executing 'legendary list --json' to retrieve installed EGS games")
                result = subprocess.run(
                    [self.legendary_path, "list", "--json"],
                    capture_output=True,
                    text=False,
                    check=True
                )
                logger.debug("Parsing JSON output from legendary list command")
                installed_games = orjson.loads(result.stdout)
                logger.info("Found %d installed Epic Games Store games: %s",
                            len(installed_games),
                            [game.get("app_title", game.get("app_name", "")) for game in installed_games])
                # Save to cache
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
            except orjson.JSONDecodeError as e:
                logger.error("Failed to parse JSON output from legendary list: %s", str(e))
                callback(games)
                return
            except FileNotFoundError as e:
                logger.error("Legendary executable not found at path %s: %s", self.legendary_path, str(e))
                callback(games)
                return

        if not installed_games:
            logger.info("No installed Epic Games Store games found")
            callback(games)
            return

        pending_images = len(installed_games)
        self.total_games = len(installed_games)
        self.update_progress.emit(0)
        self.update_status_message.emit(_("Loading Epic Games Store games..."), 3000)

        # Изменяем подход: используем словарь для хранения результатов
        game_results: dict[int, tuple] = {}

        def process_game_metadata(game, index):
            nonlocal processed_count, pending_images
            app_name = game.get("app_name", "")
            title = game.get("app_title", app_name)
            logger.debug("Processing EGS game: %s (app_name: %s)", title, app_name)

            if game.get("is_dlc", False):
                logger.debug("Skipping DLC/add-on: %s (app_name: %s)", title, app_name)
                processed_count += 1
                pending_images -= 1
                self.pending_games.append(None)
                self.update_progress.emit(len(self.pending_games))
                if pending_images == 0:
                    # Собираем только валидные игры из словаря
                    final_games = [game_results[i] for i in sorted(game_results.keys())]
                    logger.info("All EGS games and images processed, invoking callback with %d games", len(final_games))
                    callback(final_games)
                return

            metadata_file = metadata_dir / f"{app_name}.json"
            try:
                logger.debug("Reading metadata file for %s: %s", app_name, metadata_file)
                with open(metadata_file, "rb") as f:  # Use binary mode for orjson
                    metadata = orjson.loads(f.read())
                logger.debug("Successfully parsed metadata JSON for %s", app_name)

                description = metadata.get("metadata", {}).get("description", "")
                cover_url = ""
                for img in metadata.get("metadata", {}).get("keyImages", []):
                    if img.get("type") in ["DieselGameBoxTall", "Thumbnail"]:
                        cover_url = img.get("url", "")
                        break
                logger.debug("Retrieved metadata for %s: description length=%d, cover_url=%s",
                            app_name, len(description), cover_url)
            except FileNotFoundError as e:
                logger.warning("Metadata file not found for EGS game %s: %s", app_name, str(e))
                description = ""
                cover_url = ""
            except orjson.JSONDecodeError as e:
                logger.warning("Failed to parse metadata JSON for %s: %s", app_name, str(e))
                description = ""
                cover_url = ""
            except Exception as e:
                logger.error("Unexpected error processing metadata for %s: %s", app_name, str(e))
                description = ""
                cover_url = ""

            # Define local_path based on load_pixmap_async cache path
            image_folder = os.path.join(os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "PortProtonQT", "images")
            local_path = os.path.join(image_folder, f"{app_name}.jpg") if cover_url else ""

            # Define default playtime and launch data
            playtime_seconds = 0
            last_played = 0
            last_launch = _("Never")
            formatted_playtime = ""

            # Optional: Attempt to load playtime data if available
            if self.portproton_location:
                statistics_file = os.path.join(self.portproton_location, "data", "tmp", "statistics")
                try:
                    playtime_data = parse_playtime_file(statistics_file)
                    matching_key = next(
                        (key for key in playtime_data if os.path.basename(key).split('.')[0] == app_name),
                        None
                    )
                    if matching_key:
                        playtime_seconds = playtime_data[matching_key]
                        formatted_playtime = format_playtime(playtime_seconds)
                        last_played = get_last_launch_timestamp(app_name)
                        last_launch = format_last_launch(datetime.fromtimestamp(last_played)) if last_played else _("Never")
                except Exception as e:
                    logger.error(f"Failed to parse playtime data for EGS game {app_name}: {e}")

            def on_cover_loaded(pixmap: QPixmap):
                nonlocal processed_count, pending_images
                logger.debug("Cover image loaded for %s: %s", app_name, local_path)

                def on_anticheat_status(status: str):
                    nonlocal processed_count, pending_images
                    # Сохраняем результат в словарь
                    game_results[index] = (
                        title,
                        description,
                        local_path if os.path.exists(local_path) else "",
                        app_name,
                        f"legendary:launch:{app_name}",
                        "",
                        last_launch,
                        formatted_playtime,
                        "",
                        status,
                        last_played,
                        playtime_seconds,
                        "epic"
                    )
                    processed_count += 1
                    pending_images -= 1
                    self.pending_games.append(None)
                    self.update_progress.emit(len(self.pending_games))
                    logger.info("Processed EGS game %s with cover %s and anticheat status '%s', progress: %d/%d",
                                title, local_path, status, processed_count, len(installed_games))
                    if pending_images == 0:
                        # Собираем только валидные игры из словаря
                        final_games = [game_results[i] for i in sorted(game_results.keys())]
                        logger.info("All EGS games and images processed, invoking callback with %d games", len(final_games))
                        callback(final_games)

                get_weanticheatyet_status_async(title, on_anticheat_status)

            logger.debug("Loading cover image for %s: %s", app_name, cover_url)
            load_pixmap_async(cover_url, 600, 900, on_cover_loaded, app_name=app_name)

        logger.debug("Starting ThreadPoolExecutor for processing %d EGS games", len(installed_games))
        processed_count = 0
        with ThreadPoolExecutor() as executor:
            for i, game in enumerate(installed_games):
                executor.submit(process_game_metadata, game, i)

    def finalize_game_loading(self):
        logger.info("Finalizing game loading, pending_games: %d", len(self.pending_games))
        if self.pending_games and all(x is None for x in self.pending_games):
            logger.info("All games processed, clearing pending_games")
            self.pending_games = []
            self.update_progress.emit(0)  # Hide progress bar
            self.progress_bar.setVisible(False)
            self.update_status_message.emit("", 0)  # Clear status message

    # ВКЛАДКИ
    def switchTab(self, index):
        """Устанавливает активную вкладку по индексу."""
        for i, btn in self.tabButtons.items():
            btn.setChecked(i == index)
        self.stackedWidget.setCurrentIndex(index)

    def createSearchWidget(self) -> tuple[QWidget, QLineEdit]:
        """Создаёт виджет добавить игру + поиск."""
        self.container = QWidget()
        self.container.setStyleSheet(self.theme.CONTAINER_STYLE)
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)

        self.GameLibraryTitle = QLabel(_("Game Library"))
        self.GameLibraryTitle.setStyleSheet(self.theme.INSTALLED_TAB_TITLE_STYLE)
        layout.addWidget(self.GameLibraryTitle)

        self.addGameButton = AutoSizeButton(_("Add Game"), icon=self.theme_manager.get_icon("addgame"))
        self.addGameButton.setStyleSheet(self.theme.ADDGAME_BACK_BUTTON_STYLE)
        self.addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(self.addGameButton, alignment=Qt.AlignmentFlag.AlignRight)

        self.searchEdit = QLineEdit()
        icon: QIcon = cast(QIcon, self.theme_manager.get_icon("search"))
        action_pos = cast(QLineEdit.ActionPosition, QLineEdit.ActionPosition.LeadingPosition)
        self.search_action = self.searchEdit.addAction(icon, action_pos)
        self.searchEdit.setMaximumWidth(200)
        self.searchEdit.setPlaceholderText(_("Find Games ..."))
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)

        layout.addWidget(self.searchEdit)
        return self.container, self.searchEdit

    def filterGames(self, text):
        """Фильтрует список игр по подстроке text."""
        text = text.strip().lower()
        if text == "":
            filtered = self.games
        else:
            filtered = [game for game in self.games if text in game[0].lower()]
        self.populateGamesGrid(filtered)

    def createInstalledTab(self):
        """Вкладка 'Game Library'."""
        self.gamesLibraryWidget = QWidget()
        self.gamesLibraryWidget.setStyleSheet(self.theme.LIBRARY_WIDGET_STYLE)
        layout = QVBoxLayout(self.gamesLibraryWidget)
        layout.setSpacing(15)

        searchWidget, self.searchEdit = self.createSearchWidget()
        self.searchEdit.textChanged.connect(self.filterGames)
        layout.addWidget(searchWidget)

        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet(self.theme.SCROLL_AREA_STYLE)

        self.gamesListWidget = QWidget()
        self.gamesListWidget.setStyleSheet(self.theme.LIST_WIDGET_STYLE)
        self.gamesListLayout = FlowLayout(self.gamesListWidget)
        self.gamesListWidget.setLayout(self.gamesListLayout)

        scrollArea.setWidget(self.gamesListWidget)
        layout.addWidget(scrollArea)

        # Слайдер для изменения размера карточек:
        sliderLayout = QHBoxLayout()
        sliderLayout.addStretch()  # сдвигаем ползунок вправо
        self.sizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.sizeSlider.setMinimum(200)
        self.sizeSlider.setMaximum(250)
        self.sizeSlider.setValue(self.card_width)
        self.sizeSlider.setTickInterval(10)
        self.sizeSlider.setFixedWidth(150)
        self.sizeSlider.setToolTip(f"{self.card_width} px")
        self.sizeSlider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        sliderLayout.addWidget(self.sizeSlider)
        layout.addLayout(sliderLayout)

        self.sliderDebounceTimer = QTimer(self)
        self.sliderDebounceTimer.setSingleShot(True)
        self.sliderDebounceTimer.setInterval(40)

        def on_slider_value_changed():
            self.setUpdatesEnabled(False)
            self.card_width = self.sizeSlider.value()
            self.sizeSlider.setToolTip(f"{self.card_width} px")
            self.updateGameGrid()  # обновляем карточки
            self.setUpdatesEnabled(True)
        self.sizeSlider.valueChanged.connect(lambda val: self.sliderDebounceTimer.start())
        self.sliderDebounceTimer.timeout.connect(on_slider_value_changed)

        def calculate_card_width():
                available_width = scrollArea.width() - 20  # Учитываем отступы scrollArea
                spacing = self.gamesListLayout._spacing  # Отступ между карточками (5 по умолчанию)
                target_cards_per_row = 6  # Целевое количество карточек в ряду
                # Вычисляем ширину карточки: (доступная ширина - отступы) / количество карточек
                calculated_width = (available_width - spacing * (target_cards_per_row - 1)) // target_cards_per_row
                # Ограничиваем ширину разумными значениями
                calculated_width = max(200, min(calculated_width, 250))
                if not self.sizeSlider.value() == self.card_width:  # Если слайдер не изменён вручную
                    self.card_width = calculated_width
                    self.sizeSlider.setValue(self.card_width)
                    self.sizeSlider.setToolTip(f"{self.card_width} px")
                    self.updateGameGrid()

        QTimer.singleShot(0, calculate_card_width)

        self.stackedWidget.addWidget(self.gamesLibraryWidget)

        # Первичная отрисовка карточек:
        self.updateGameGrid()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sliderDebounceTimer.start()

    def updateGameGrid(self):
        if not self.games:
            return
        self.clearLayout(self.gamesListLayout)
        card_width = self.card_width
        for game_data in self.games:
            card = GameCard(
                *game_data,
                select_callback=self.openGameDetailPage,
                theme=self.theme,
                card_width=card_width,
                context_menu_manager=self.context_menu_manager
            )
            # Connect context menu signals (unchanged)
            card.editShortcutRequested.connect(self.context_menu_manager.edit_game_shortcut)
            card.deleteGameRequested.connect(self.context_menu_manager.delete_game)
            card.addToMenuRequested.connect(self.context_menu_manager.add_to_menu)
            card.removeFromMenuRequested.connect(self.context_menu_manager.remove_from_menu)
            card.addToDesktopRequested.connect(self.context_menu_manager.add_to_desktop)
            card.removeFromDesktopRequested.connect(self.context_menu_manager.remove_from_desktop)
            card.addToSteamRequested.connect(self.context_menu_manager.add_to_steam)
            card.removeFromSteamRequested.connect(self.context_menu_manager.remove_from_steam)
            card.openGameFolderRequested.connect(self.context_menu_manager.open_game_folder)
            self.gamesListLayout.addWidget(card)
        self.gamesListWidget.updateGeometry()
        self.gamesListLayout.invalidate()
        self.gamesListWidget.update()

    def populateGamesGrid(self, games_list):
        self.clearLayout(self.gamesListLayout)
        for _idx, game_data in enumerate(games_list):
            card = GameCard(*game_data, select_callback=self.openGameDetailPage, theme=self.theme, card_width=self.card_width, context_menu_manager=self.context_menu_manager)
            # Connect context menu signals
            card.editShortcutRequested.connect(self.context_menu_manager.edit_game_shortcut)
            card.deleteGameRequested.connect(self.context_menu_manager.delete_game)
            card.addToMenuRequested.connect(self.context_menu_manager.add_to_menu)
            card.removeFromMenuRequested.connect(self.context_menu_manager.remove_from_menu)
            card.addToDesktopRequested.connect(self.context_menu_manager.add_to_desktop)
            card.removeFromDesktopRequested.connect(self.context_menu_manager.remove_from_desktop)
            card.addToSteamRequested.connect(self.context_menu_manager.add_to_steam)
            card.removeFromSteamRequested.connect(self.context_menu_manager.remove_from_steam)
            card.openGameFolderRequested.connect(self.context_menu_manager.open_game_folder)
            self.gamesListLayout.addWidget(card)

    def clearLayout(self, layout):
        """Удаляет все виджеты из layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".exe"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".exe"):
                self.openAddGameDialog(path)
                break

    def openAddGameDialog(self, exe_path=None):
        """Открывает диалоговое окно 'Add Game' с текущей темой."""
        dialog = AddGameDialog(self, self.theme)

        # Предзаполняем путь к .exe при drag-and-drop
        if exe_path:
            dialog.exeEdit.setText(exe_path)
            dialog.nameEdit.setText(os.path.splitext(os.path.basename(exe_path))[0])
            dialog.updatePreview()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.nameEdit.text().strip()
            exe_path = dialog.exeEdit.text().strip()
            user_cover = dialog.coverEdit.text().strip()

            if not name or not exe_path:
                return

            # Сохраняем .desktop файл
            desktop_entry, desktop_path = dialog.getDesktopEntryData()
            if desktop_entry and desktop_path:
                with open(desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                    os.chmod(desktop_path, 0o755)

                # Проверяем путь обложки, если он отличается от стандартной
                if os.path.isfile(user_cover):
                    exe_name = os.path.splitext(os.path.basename(exe_path))[0]
                    xdg_data_home = os.getenv("XDG_DATA_HOME",
                        os.path.join(os.path.expanduser("~"), ".local", "share"))
                    custom_folder = os.path.join(
                        xdg_data_home,
                        "PortProtonQT",
                        "custom_data",
                        exe_name
                    )
                    os.makedirs(custom_folder, exist_ok=True)

                    # Сохраняем пользовательскую обложку как cover.*
                    ext = os.path.splitext(user_cover)[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".bmp"]:
                        shutil.copyfile(user_cover, os.path.join(custom_folder, f"cover{ext}"))

            self.games = self.loadGames()
            self.updateGameGrid()


    def createAutoInstallTab(self):
        """Вкладка 'Auto Install'."""
        self.autoInstallWidget = QWidget()
        self.autoInstallWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.autoInstallWidget.setObjectName("otherPage")
        layout = QVBoxLayout(self.autoInstallWidget)
        layout.setContentsMargins(10, 18, 10, 10)

        self.autoInstallTitle = QLabel(_("Auto Install"))
        self.autoInstallTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.autoInstallTitle.setObjectName("tabTitle")
        layout.addWidget(self.autoInstallTitle)

        self.autoInstallContent = QLabel(_("Here you can configure automatic game installation..."))
        self.autoInstallContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.autoInstallContent.setObjectName("tabContent")
        layout.addWidget(self.autoInstallContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.autoInstallWidget)

    def createEmulatorsTab(self):
        """Вкладка 'Emulators'."""
        self.emulatorsWidget = QWidget()
        self.emulatorsWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.emulatorsWidget.setObjectName("otherPage")
        layout = QVBoxLayout(self.emulatorsWidget)
        layout.setContentsMargins(10, 18, 10, 10)

        self.emulatorsTitle = QLabel(_("Emulators"))
        self.emulatorsTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.emulatorsTitle.setObjectName("tabTitle")
        layout.addWidget(self.emulatorsTitle)

        self.emulatorsContent = QLabel(_("List of available emulators and their configuration..."))
        self.emulatorsContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.emulatorsContent.setObjectName("tabContent")
        layout.addWidget(self.emulatorsContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.emulatorsWidget)

    def createWineTab(self):
        """Вкладка 'Wine Settings'."""
        self.wineWidget = QWidget()
        self.wineWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.wineWidget.setObjectName("otherPage")
        layout = QVBoxLayout(self.wineWidget)
        layout.setContentsMargins(10, 18, 10, 10)

        self.wineTitle = QLabel(_("Wine Settings"))
        self.wineTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.wineTitle.setObjectName("tabTitle")
        layout.addWidget(self.wineTitle)

        self.wineContent = QLabel(_("Various Wine parameters and versions..."))
        self.wineContent.setStyleSheet(self.theme.CONTENT_STYLE)
        self.wineContent.setObjectName("tabContent")
        layout.addWidget(self.wineContent)
        layout.addStretch(1)

        self.stackedWidget.addWidget(self.wineWidget)

    def createPortProtonTab(self):
        """Вкладка 'PortProton Settings'."""
        self.portProtonWidget = QWidget()
        self.portProtonWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.portProtonWidget.setObjectName("otherPage")
        layout = QVBoxLayout(self.portProtonWidget)
        layout.setContentsMargins(10, 18, 10, 10)

        # Заголовок
        title = QLabel(_("PortProton Settings"))
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        title.setObjectName("tabTitle")
        title.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(title)

        # Подзаголовок/описание
        content = QLabel(_("Main PortProton parameters..."))
        content.setStyleSheet(self.theme.CONTENT_STYLE)
        content.setObjectName("tabContent")
        content.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(content)

        # Форма с настройками
        formLayout = QFormLayout()
        formLayout.setContentsMargins(0, 10, 0, 0)
        formLayout.setSpacing(10)

        # 1. Time detail_level
        self.timeDetailCombo = QComboBox()
        self.time_keys = ["detailed", "brief"]
        self.time_labels = [_("detailed"), _("brief")]
        self.timeDetailCombo.addItems(self.time_labels)
        self.timeDetailCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.timeDetailCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.timeDetailTitle = QLabel(_("Time Detail Level:"))
        self.timeDetailTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.timeDetailTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = read_time_config()
        try:
            idx = self.time_keys.index(current)
        except ValueError:
            idx = 0
        self.timeDetailCombo.setCurrentIndex(idx)
        formLayout.addRow(self.timeDetailTitle, self.timeDetailCombo)

        # 2. Games sort_method
        self.gamesSortCombo = QComboBox()
        self.sort_keys = ["last_launch", "playtime", "alphabetical", "favorites"]
        self.sort_labels = [_("last launch"), _("playtime"), _("alphabetical"), _("favorites")]
        self.gamesSortCombo.addItems(self.sort_labels)
        self.gamesSortCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamesSortCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamesSortTitle = QLabel(_("Games Sort Method:"))
        self.gamesSortTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.gamesSortTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = read_sort_method()
        try:
            idx = self.sort_keys.index(current)
        except ValueError:
            idx = 0
        self.gamesSortCombo.setCurrentIndex(idx)
        formLayout.addRow(self.gamesSortTitle, self.gamesSortCombo)

        # 3. Games display_filter
        self.filter_keys = ["all", "steam", "portproton", "favorites", "epic"]
        self.filter_labels = [_("all"), "steam", "portproton", _("favorites"), "epic games store"]
        self.gamesDisplayCombo = QComboBox()
        self.gamesDisplayCombo.addItems(self.filter_labels)
        self.gamesDisplayCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamesDisplayCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamesDisplayTitle = QLabel(_("Games Display Filter:"))
        self.gamesDisplayTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.gamesDisplayTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = read_display_filter()
        try:
            idx = self.filter_keys.index(current)
        except ValueError:
            idx = 0
        self.gamesDisplayCombo.setCurrentIndex(idx)
        formLayout.addRow(self.gamesDisplayTitle, self.gamesDisplayCombo)

        # 4. Proxy settings
        self.proxyUrlEdit = QLineEdit()
        self.proxyUrlEdit.setPlaceholderText(_("Proxy URL"))
        self.proxyUrlEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        self.proxyUrlEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyUrlTitle = QLabel(_("Proxy URL:"))
        self.proxyUrlTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.proxyUrlTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        proxy_cfg = read_proxy_config()
        if proxy_cfg.get("http", ""):
            self.proxyUrlEdit.setText(proxy_cfg["http"])
        formLayout.addRow(self.proxyUrlTitle, self.proxyUrlEdit)

        self.proxyUserEdit = QLineEdit()
        self.proxyUserEdit.setPlaceholderText(_("Proxy Username"))
        self.proxyUserEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        self.proxyUserEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyUserTitle = QLabel(_("Proxy Username:"))
        self.proxyUserTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.proxyUserTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        formLayout.addRow(self.proxyUserTitle, self.proxyUserEdit)

        self.proxyPasswordEdit = QLineEdit()
        self.proxyPasswordEdit.setPlaceholderText(_("Proxy Password"))
        self.proxyPasswordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxyPasswordEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        self.proxyPasswordEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyPasswordTitle = QLabel(_("Proxy Password:"))
        self.proxyPasswordTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.proxyPasswordTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        formLayout.addRow(self.proxyPasswordTitle, self.proxyPasswordEdit)

        # 5. Fullscreen setting for application
        self.fullscreenCheckBox = QCheckBox(_("Launch Application in Fullscreen"))
        #self.fullscreenCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.fullscreenCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fullscreenTitle = QLabel(_("Application Fullscreen Mode:"))
        self.fullscreenTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.fullscreenTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_fullscreen = read_fullscreen_config()
        self.fullscreenCheckBox.setChecked(current_fullscreen)
        formLayout.addRow(self.fullscreenTitle, self.fullscreenCheckBox)

        # 6. Legendary Authentication
        self.legendaryAuthButton = AutoSizeButton(
            _("Open Legendary Login"),
            icon=self.theme_manager.get_icon("login")
        )
        self.legendaryAuthButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.legendaryAuthButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.legendaryAuthButton.clicked.connect(self.openLegendaryLogin)
        self.legendaryAuthTitle = QLabel(_("Legendary Authentication:"))
        self.legendaryAuthTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.legendaryAuthTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        formLayout.addRow(self.legendaryAuthTitle, self.legendaryAuthButton)

        self.legendaryCodeEdit = QLineEdit()
        self.legendaryCodeEdit.setPlaceholderText(_("Enter Legendary Authorization Code"))
        self.legendaryCodeEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        self.legendaryCodeEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.legendaryCodeTitle = QLabel(_("Authorization Code:"))
        self.legendaryCodeTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.legendaryCodeTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        formLayout.addRow(self.legendaryCodeTitle, self.legendaryCodeEdit)

        self.submitCodeButton = AutoSizeButton(
            _("Submit Code"),
            icon=self.theme_manager.get_icon("save")
        )
        self.submitCodeButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.submitCodeButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.submitCodeButton.clicked.connect(self.submitLegendaryCode)
        formLayout.addRow(QLabel(""), self.submitCodeButton)

        layout.addLayout(formLayout)

        # Кнопки
        buttonsLayout = QHBoxLayout()
        buttonsLayout.setSpacing(10)

        # Кнопка сохранения настроек
        self.saveButton = AutoSizeButton(
            _("Save Settings"),
            icon=self.theme_manager.get_icon("save")
        )
        self.saveButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.saveButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.saveButton.clicked.connect(self.savePortProtonSettings)
        buttonsLayout.addWidget(self.saveButton)

        # Кнопка сброса настроек
        self.resetSettingsButton = AutoSizeButton(
            _("Reset Settings"),
            icon=self.theme_manager.get_icon("update")
        )
        self.resetSettingsButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.resetSettingsButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.resetSettingsButton.clicked.connect(self.resetSettings)
        buttonsLayout.addWidget(self.resetSettingsButton)

        # Кнопка очистки кэша
        self.clearCacheButton = AutoSizeButton(
            _("Clear Cache"),
            icon=self.theme_manager.get_icon("update")
        )
        self.clearCacheButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.clearCacheButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clearCacheButton.clicked.connect(self.clearCache)
        buttonsLayout.addWidget(self.clearCacheButton)

        layout.addLayout(buttonsLayout)
        layout.addStretch(1)
        self.stackedWidget.addWidget(self.portProtonWidget)

    def openLegendaryLogin(self):
        """Opens the Legendary login page in the default web browser."""
        login_url = "https://legendary.gl/epiclogin"
        try:
            QDesktopServices.openUrl(QUrl(login_url))
            self.statusBar().showMessage(_("Opened Legendary login page in browser"), 3000)
        except Exception as e:
            logger.error(f"Failed to open Legendary login page: {e}")
            self.statusBar().showMessage(_("Failed to open Legendary login page"), 3000)

    def submitLegendaryCode(self):
        """Submits the Legendary authorization code using the legendary CLI."""
        auth_code = self.legendaryCodeEdit.text().strip()
        if not auth_code:
            QMessageBox.warning(self, _("Error"), _("Please enter an authorization code"))
            return

        try:
            # Execute legendary auth command
            result = subprocess.run(
                [self.legendary_path, "auth", "--code", auth_code],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Legendary authentication successful: %s", result.stdout)
            self.statusBar().showMessage(_("Successfully authenticated with Legendary"), 3000)
            self.legendaryCodeEdit.clear()
            # Reload Epic Games Store games after successful authentication
            self.games = self.loadGames()
            self.updateGameGrid()
        except subprocess.CalledProcessError as e:
            logger.error("Legendary authentication failed: %s", e.stderr)
            self.statusBar().showMessage(_("Legendary authentication failed: {0}").format(e.stderr), 5000)
        except FileNotFoundError:
            logger.error("Legendary executable not found at %s", self.legendary_path)
            self.statusBar().showMessage(_("Legendary executable not found"), 5000)
        except Exception as e:
            logger.error("Unexpected error during Legendary authentication: %s", str(e))
            self.statusBar().showMessage(_("Unexpected error during authentication"), 5000)

    def resetSettings(self):
        """Сбрасывает настройки и перезапускает приложение."""
        reply = QMessageBox.question(
            self,
            _("Confirm Reset"),
            _("Are you sure you want to reset all settings? This action cannot be undone."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            reset_config()

            # Показываем сообщение
            self.statusBar().showMessage(_("Settings reset. Restarting..."), 3000)

            # Перезапускаем приложение
            QTimer.singleShot(1000, lambda: self.restart_application())

    def clearCache(self):
        """Очищает кэш."""
        reply = QMessageBox.question(
            self,
            _("Confirm Clear Cache"),
            _("Are you sure you want to clear the cache? This action cannot be undone."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_cache()

            # Показываем сообщение
            self.statusBar().showMessage(_("Cache cleared"), 3000)

    def savePortProtonSettings(self):
        """
        Сохраняет параметры конфигурации в конфигурационный файл,
        """
        time_idx = self.timeDetailCombo.currentIndex()
        time_key = self.time_keys[time_idx]
        save_time_config(time_key)

        sort_idx = self.gamesSortCombo.currentIndex()
        sort_key = self.sort_keys[sort_idx]
        save_sort_method(sort_key)

        filter_idx = self.gamesDisplayCombo.currentIndex()
        filter_key = self.filter_keys[filter_idx]
        save_display_filter(filter_key)

        # Сохранение proxy настроек
        proxy_url = self.proxyUrlEdit.text().strip()
        proxy_user = self.proxyUserEdit.text().strip()
        proxy_password = self.proxyPasswordEdit.text().strip()
        save_proxy_config(proxy_url, proxy_user, proxy_password)

        fullscreen = self.fullscreenCheckBox.isChecked()
        save_fullscreen_config(fullscreen)

        # Перезагружаем настройки
        read_time_config()
        self.games = self.loadGames()
        self.updateGameGrid()
        self.settings_saved.emit()

        if fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
            save_window_geometry(self.width(), self.height())

        self.statusBar().showMessage(_("Settings saved"), 3000)

    def createThemeTab(self):
        """Вкладка 'Themes'"""
        self.themeTabWidget = QWidget()
        self.themeTabWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.themeTabWidget.setObjectName("otherPage")
        mainLayout = QVBoxLayout(self.themeTabWidget)
        mainLayout.setContentsMargins(10, 14, 10, 10)
        mainLayout.setSpacing(10)

        # 1. Верхняя строка: Заголовок и список тем
        self.themeTabHeaderLayout = QHBoxLayout()

        self.themeTabTitleLabel = QLabel(_("Select Theme:"))
        self.themeTabTitleLabel.setObjectName("tabTitle")
        self.themeTabTitleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.themeTabHeaderLayout.addWidget(self.themeTabTitleLabel)

        self.themesCombo = QComboBox()
        self.themesCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.themesCombo.setObjectName("comboString")
        available_themes = self.theme_manager.get_available_themes()
        if self.current_theme_name in available_themes:
            available_themes.remove(self.current_theme_name)
            available_themes.insert(0, self.current_theme_name)
        self.themesCombo.addItems(available_themes)
        self.themeTabHeaderLayout.addWidget(self.themesCombo)
        self.themeTabHeaderLayout.addStretch(1)

        mainLayout.addLayout(self.themeTabHeaderLayout)

        # 2. Карусель скриншотов
        self.screenshotsCarousel = ImageCarousel([])
        self.screenshotsCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        mainLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Информация о теме
        self.themeInfoLayout = QVBoxLayout()
        self.themeInfoLayout.setSpacing(10)

        self.themeMetainfoLabel = QLabel()
        self.themeMetainfoLabel.setWordWrap(True)
        self.themeInfoLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = AutoSizeButton(_("Apply Theme"), icon=self.theme_manager.get_icon("update"))
        self.applyButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.applyButton.setObjectName("actionButton")
        self.themeInfoLayout.addWidget(self.applyButton)

        mainLayout.addLayout(self.themeInfoLayout)

        # Функция обновления превью
        def updateThemePreview(theme_name):
            meta = load_theme_metainfo(theme_name)
            link = meta.get("author_link", "")
            link_html = f'<a href="{link}">{link}</a>' if link else _("No link")
            unknown_author = _("Unknown")

            preview_text = (
                "<b>" + _("Name:") + "</b> " + meta.get('name', theme_name) + "<br>" +
                "<b>" + _("Description:") + "</b> " + meta.get('description', '') + "<br>" +
                "<b>" + _("Author:") + "</b> " + meta.get('author', unknown_author) + "<br>" +
                "<b>" + _("Link:") + "</b> " + link_html
            )
            self.themeMetainfoLabel.setText(preview_text)
            self.themeMetainfoLabel.setStyleSheet(self.theme.CONTENT_STYLE)
            self.themeMetainfoLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            screenshots = load_theme_screenshots(theme_name)
            if screenshots:
                self.screenshotsCarousel.update_images([
                    (pixmap, os.path.splitext(filename)[0])
                    for pixmap, filename in screenshots
                ])
                self.screenshotsCarousel.show()
            else:
                self.screenshotsCarousel.hide()

        updateThemePreview(self.current_theme_name)
        self.themesCombo.currentTextChanged.connect(updateThemePreview)

        # Логика применения темы
        def on_apply():
            selected_theme = self.themesCombo.currentText()
            if selected_theme:
                theme_module = self.theme_manager.apply_theme(selected_theme)
                if theme_module:
                    save_theme_to_config(selected_theme)
                    self.statusBar().showMessage(_("Theme '{0}' applied successfully").format(selected_theme), 3000)
                    xdg_data_home = os.getenv("XDG_DATA_HOME",
                                            os.path.join(os.path.expanduser("~"), ".local", "share"))
                    state_file = os.path.join(xdg_data_home, "PortProtonQT", "state.txt")
                    os.makedirs(os.path.dirname(state_file), exist_ok=True)
                    with open(state_file, "w", encoding="utf-8") as f:
                        f.write("theme_tab\n")
                    QTimer.singleShot(500, lambda: self.restart_application())
                else:
                    self.statusBar().showMessage(_("Error applying theme '{0}'").format(selected_theme), 3000)

        self.applyButton.clicked.connect(on_apply)

        # Добавляем виджет в stackedWidget
        self.stackedWidget.addWidget(self.themeTabWidget)

    def restart_application(self):
        """Перезапускает приложение."""
        if not self.isFullScreen():
            save_window_geometry(self.width(), self.height())
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def restore_state(self):
        """Восстанавливает состояние приложения после перезапуска."""
        xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
        state_file = os.path.join(xdg_cache_home, "PortProtonQT", "state.txt")
        if os.path.exists(state_file):
            with open(state_file, encoding="utf-8") as f:
                state = f.read().strip()
                if state == "theme_tab":
                    self.switchTab(5)
            os.remove(state_file)

    # ЛОГИКА ДЕТАЛЬНОЙ СТРАНИЦЫ ИГРЫ
    def getColorPalette_async(self, cover_path, num_colors=5, sample_step=10, callback=None):
        def on_pixmap(pixmap):
            if pixmap.isNull():
                if callback:
                    callback([QColor("#1a1a1a")] * num_colors)
                    return

            image = pixmap.toImage()
            width, height = image.width(), image.height()
            histogram = {}
            for x in range(0, width, sample_step):
                for y in range(0, height, sample_step):
                    color = image.pixelColor(x, y)
                    key = (color.red() // 32, color.green() // 32, color.blue() // 32)
                    if key in histogram:
                        histogram[key][0] += color.red()
                        histogram[key][1] += color.green()
                        histogram[key][2] += color.blue()
                        histogram[key][3] += 1
                    else:
                        histogram[key] = [color.red(), color.green(), color.blue(), 1]
            avg_colors = []
            for _unused, (r_sum, g_sum, b_sum, count) in histogram.items():
                avg_r = r_sum // count
                avg_g = g_sum // count
                avg_b = b_sum // count
                avg_colors.append((count, QColor(avg_r, avg_g, avg_b)))
            avg_colors.sort(key=lambda x: x[0], reverse=True)
            palette = [color for count, color in avg_colors[:num_colors]]
            if len(palette) < num_colors:
                palette += [palette[-1]] * (num_colors - len(palette))
            if callback:
                callback(palette)

        load_pixmap_async(cover_path, 180, 250, on_pixmap)

    def darkenColor(self, color, factor=200):
        return color.darker(factor)

    def openGameDetailPage(self, name, description, cover_path=None, appid="", exec_line="", controller_support="", last_launch="", formatted_playtime="", protondb_tier="", steam_game=""):
        detailPage = QWidget()
        self._animations = {}
        imageLabel = QLabel()
        imageLabel.setFixedSize(300, 400)

        if cover_path:
            def on_pixmap_ready(pixmap):
                rounded = round_corners(pixmap, 10)
                imageLabel.setPixmap(rounded)

                def on_palette_ready(palette):
                    dark_palette = [self.darkenColor(color, factor=200) for color in palette]
                    stops = ",\n".join(
                        [f"stop:{i/(len(dark_palette)-1):.2f} {dark_palette[i].name()}" for i in range(len(dark_palette))]
                    )
                    detailPage.setStyleSheet(self.theme.detail_page_style(stops))

                self.getColorPalette_async(cover_path, num_colors=5, callback=on_palette_ready)

            load_pixmap_async(cover_path, 300, 400, on_pixmap_ready)
        else:
            detailPage.setStyleSheet(self.theme.DETAIL_PAGE_NO_COVER_STYLE)

        mainLayout = QVBoxLayout(detailPage)
        mainLayout.setContentsMargins(30, 30, 30, 30)
        mainLayout.setSpacing(20)

        backButton = AutoSizeButton(_("Back"), icon=self.theme_manager.get_icon("back"))
        backButton.setFixedWidth(100)
        backButton.setStyleSheet(self.theme.ADDGAME_BACK_BUTTON_STYLE)
        backButton.clicked.connect(lambda: self.goBackDetailPage(detailPage))
        mainLayout.addWidget(backButton, alignment=Qt.AlignmentFlag.AlignLeft)

        contentFrame = QFrame()
        contentFrame.setStyleSheet(self.theme.DETAIL_CONTENT_FRAME_STYLE)
        contentFrameLayout = QHBoxLayout(contentFrame)
        contentFrameLayout.setContentsMargins(20, 20, 20, 20)
        contentFrameLayout.setSpacing(40)
        mainLayout.addWidget(contentFrame)

        # Обложка (слева)
        coverFrame = QFrame()
        coverFrame.setFixedSize(300, 400)
        coverFrame.setStyleSheet(self.theme.COVER_FRAME_STYLE)
        shadow = QGraphicsDropShadowEffect(coverFrame)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        coverFrame.setGraphicsEffect(shadow)
        coverLayout = QVBoxLayout(coverFrame)
        coverLayout.setContentsMargins(0, 0, 0, 0)

        coverLayout.addWidget(imageLabel)

        # Добавляем значок избранного поверх обложки в левом верхнем углу
        favoriteLabelCover = ClickableLabel(coverFrame)
        favoriteLabelCover.setFixedSize(*self.theme.favoriteLabelSize)
        favoriteLabelCover.setStyleSheet(self.theme.FAVORITE_LABEL_STYLE)
        favorites = read_favorites()
        if name in favorites:
            favoriteLabelCover.setText("★")
        else:
            favoriteLabelCover.setText("☆")
        favoriteLabelCover.clicked.connect(lambda: self.toggleFavoriteInDetailPage(name, favoriteLabelCover))
        favoriteLabelCover.move(8, 8)
        favoriteLabelCover.raise_()

        contentFrameLayout.addWidget(coverFrame)

        # Детали игры (справа)
        detailsWidget = QWidget()
        detailsWidget.setStyleSheet(self.theme.DETAILS_WIDGET_STYLE)
        detailsLayout = QVBoxLayout(detailsWidget)
        detailsLayout.setContentsMargins(20, 20, 20, 20)
        detailsLayout.setSpacing(15)

        titleLabel = QLabel(name)
        titleLabel.setStyleSheet(self.theme.DETAIL_PAGE_TITLE_STYLE)
        detailsLayout.addWidget(titleLabel)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(self.theme.DETAIL_PAGE_LINE_STYLE)
        detailsLayout.addWidget(line)

        descLabel = QLabel(description)
        descLabel.setWordWrap(True)
        descLabel.setStyleSheet(self.theme.DETAIL_PAGE_DESC_STYLE)
        detailsLayout.addWidget(descLabel)

        infoLayout = QHBoxLayout()
        infoLayout.setSpacing(10)
        lastLaunchTitle = QLabel(_("LAST LAUNCH"))
        lastLaunchTitle.setStyleSheet(self.theme.LAST_LAUNCH_TITLE_STYLE)
        lastLaunchValue = QLabel(last_launch)
        lastLaunchValue.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)
        playTimeTitle = QLabel(_("PLAY TIME"))
        playTimeTitle.setStyleSheet(self.theme.PLAY_TIME_TITLE_STYLE)
        playTimeValue = QLabel(formatted_playtime)
        playTimeValue.setStyleSheet(self.theme.PLAY_TIME_VALUE_STYLE)
        infoLayout.addWidget(lastLaunchTitle)
        infoLayout.addWidget(lastLaunchValue)
        infoLayout.addSpacing(30)
        infoLayout.addWidget(playTimeTitle)
        infoLayout.addWidget(playTimeValue)
        detailsLayout.addLayout(infoLayout)

        if controller_support:
            cs = controller_support.lower()
            translated_cs = ""
            if cs == "full":
                translated_cs = _("full")
            elif cs == "partial":
                translated_cs = _("partial")
            elif cs == "none":
                translated_cs = _("none")
            gamepadSupportLabel = QLabel(_("Gamepad Support: {0}").format(translated_cs))
            gamepadSupportLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gamepadSupportLabel.setStyleSheet(self.theme.GAMEPAD_SUPPORT_VALUE_STYLE)
            detailsLayout.addWidget(gamepadSupportLabel, alignment=Qt.AlignmentFlag.AlignCenter)

        detailsLayout.addStretch(1)

        # Определяем текущий идентификатор игры по exec_line для корректного отображения кнопки
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            return

        if entry_exec_split[0] == "env":
            file_to_check = entry_exec_split[2] if len(entry_exec_split) >= 3 else None
        elif entry_exec_split[0] == "flatpak":
            file_to_check = entry_exec_split[3] if len(entry_exec_split) >= 4 else None
        else:
            file_to_check = entry_exec_split[0]
        current_exe = os.path.basename(file_to_check) if file_to_check else None

        if self.target_exe is not None and current_exe == self.target_exe:
            playButton = AutoSizeButton(_("Stop"), icon=self.theme_manager.get_icon("stop"))
        else:
            playButton = AutoSizeButton(_("Play"), icon=self.theme_manager.get_icon("play"))

        playButton.setFixedSize(120, 40)
        playButton.setStyleSheet(self.theme.PLAY_BUTTON_STYLE)
        playButton.clicked.connect(lambda: self.toggleGame(exec_line, playButton))
        detailsLayout.addWidget(playButton, alignment=Qt.AlignmentFlag.AlignLeft)

        contentFrameLayout.addWidget(detailsWidget)
        mainLayout.addStretch()

        self.stackedWidget.addWidget(detailPage)
        self.stackedWidget.setCurrentWidget(detailPage)
        self.currentDetailPage = detailPage
        self.current_exec_line = exec_line
        self.current_play_button = playButton

        # Анимация
        opacityEffect = QGraphicsOpacityEffect(detailPage)
        detailPage.setGraphicsEffect(opacityEffect)
        animation = QPropertyAnimation(opacityEffect, QByteArray(b"opacity"))
        animation.setDuration(800)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._animations[detailPage] = animation
        animation.finished.connect(
            lambda: detailPage.setGraphicsEffect(cast(QGraphicsEffect, None))
        )

    def toggleFavoriteInDetailPage(self, game_name, label):
        favorites = read_favorites()
        if game_name in favorites:
            favorites.remove(game_name)
            label.setText("☆")
        else:
            favorites.append(game_name)
            label.setText("★")
        save_favorites(favorites)
        self.updateGameGrid()

    def activateFocusedWidget(self):
        """Activate the currently focused widget."""
        focused_widget = QApplication.focusWidget()
        if not focused_widget:
            return
        if isinstance(focused_widget, ClickableLabel):
            focused_widget.clicked.emit()
        elif isinstance(focused_widget, AutoSizeButton):
            focused_widget.click()
        elif isinstance(focused_widget, QPushButton):
            focused_widget.click()
        elif isinstance(focused_widget, NavLabel):
            focused_widget.clicked.emit()
        elif isinstance(focused_widget, ImageCarousel):
            if focused_widget.image_items:
                current_item = focused_widget.image_items[focused_widget.horizontalScrollBar().value() // 100]
                current_item.show_fullscreen()
        elif isinstance(focused_widget, QLineEdit):
            focused_widget.setFocus()
            focused_widget.selectAll()
        elif isinstance(focused_widget, QCheckBox):
            focused_widget.setChecked(not focused_widget.isChecked())
        elif isinstance(focused_widget, GameCard):
                    focused_widget.select_callback(
                        focused_widget.name,
                        focused_widget.description,
                        focused_widget.cover_path,
                        focused_widget.appid,
                        focused_widget.controller_support,
                        focused_widget.exec_line,
                        focused_widget.last_launch,
                        focused_widget.formatted_playtime,
                        focused_widget.protondb_tier,
                        focused_widget.steam_game
                    )

    def goBackDetailPage(self, page: QWidget | None) -> None:
        if page is None or page != self.stackedWidget.currentWidget():
            return
        self.stackedWidget.setCurrentIndex(0)
        self.stackedWidget.removeWidget(page)
        page.deleteLater()
        self.currentDetailPage = None
        self.current_exec_line = None

    def is_target_exe_running(self):
        """Проверяет, запущен ли процесс с именем self.target_exe через psutil."""
        if not self.target_exe:
            return False
        for proc in psutil.process_iter(attrs=["name"]):
            if proc.info["name"].lower() == self.target_exe.lower():
                return True
        return False

    def checkTargetExe(self):
        """
        Проверяет, запущена ли игра.
        Если процесс игры (target_exe) обнаружен – устанавливаем флаг и обновляем кнопку.
        Если игра завершилась – сбрасываем флаг, обновляем кнопку и останавливаем таймер.
        """
        target_running = self.is_target_exe_running()
        child_running = any(proc.poll() is None for proc in self.game_processes)

        if target_running:
            # Игра стартовала – устанавливаем флаг, обновляем кнопку на "Stop"
            self._gameLaunched = True
            if self.current_running_button is not None:
                self.current_running_button.setText(_("Stop"))
                #self._inhibit_screensaver()
        elif not child_running:
            # Игра завершилась – сбрасываем флаг, сбрасываем кнопку и останавливаем таймер
            self._gameLaunched = False
            self.resetPlayButton()
            #self._uninhibit_screensaver()
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None

    def resetPlayButton(self):
        """
        Сбрасывает кнопку запуска игры:
        меняет текст на "Играть", устанавливает иконку и сбрасывает переменные.
        Вызывается, когда игра завершилась (не по нажатию кнопки).
        """
        if self.current_running_button is not None:
            self.current_running_button.setText(_("Play"))
            icon = self.theme_manager.get_icon("play")
            if isinstance(icon, str):
                icon = QIcon(icon)  # Convert path to QIcon
            elif icon is None:
                icon = QIcon()  # Use empty QIcon as fallback
            self.current_running_button.setIcon(icon)
            self.current_running_button = None
        self.target_exe = None

    def toggleGame(self, exec_line, button=None):
        if exec_line.startswith("steam://"):
            url = QUrl(exec_line)
            QDesktopServices.openUrl(url)
            return

        entry_exec_split = shlex.split(exec_line)
        if entry_exec_split[0] == "env":
            if len(entry_exec_split) < 3:
                QMessageBox.warning(self, _("Error"), _("Invalid command format (native)"))
                return
            file_to_check = entry_exec_split[2]
        elif entry_exec_split[0] == "flatpak":
            if len(entry_exec_split) < 4:
                QMessageBox.warning(self, _("Error"), _("Invalid command format (flatpak)"))
                return
            file_to_check = entry_exec_split[3]
        else:
            file_to_check = entry_exec_split[0]
        if not os.path.exists(file_to_check):
            QMessageBox.warning(self, _("Error"), _("File not found: {0}").format(file_to_check))
            return
        current_exe = os.path.basename(file_to_check)

        if self.game_processes and self.target_exe is not None and self.target_exe != current_exe:
            QMessageBox.warning(self, _("Error"), _("Cannot launch game while another game is running"))
            return

        update_button = button if button is not None else self.current_play_button

        # Если игра уже запущена для этого exe – останавливаем её по нажатию кнопки
        if self.game_processes and self.target_exe == current_exe:
            for proc in self.game_processes:
                try:
                    parent = psutil.Process(proc.pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    psutil.wait_procs(children, timeout=5)
                    for child in children:
                        if child.is_running():
                            child.kill()
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except psutil.NoSuchProcess:
                    pass
            self.game_processes = []
            if update_button:
                update_button.setText(_("Play"))
                icon = self.theme_manager.get_icon("play")
                if isinstance(icon, str):
                    icon = QIcon(icon)
                elif icon is None:
                    icon = QIcon()
                update_button.setIcon(icon)
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None
            self.current_running_button = None
            self.target_exe = None
            self._gameLaunched = False
            #self._uninhibit_screensaver()
        else:
            # Сохраняем ссылку на кнопку для сброса после завершения игры
            self.current_running_button = update_button
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]
            env_vars = os.environ.copy()
            if entry_exec_split[0] == "env" and len(entry_exec_split) > 1 and 'data/scripts/start.sh' in entry_exec_split[1]:
                env_vars['START_FROM_STEAM'] = '1'
            elif entry_exec_split[0] == "flatpak":
                env_vars['START_FROM_STEAM'] = '1'
            process = subprocess.Popen(entry_exec_split, env=env_vars, shell=False, preexec_fn=os.setsid)
            self.game_processes.append(process)
            save_last_launch(exe_name, datetime.now())
            if update_button:
                update_button.setText(_("Launching"))
                icon = self.theme_manager.get_icon("stop")
                if isinstance(icon, str):
                    icon = QIcon(icon)
                elif icon is None:
                    icon = QIcon()
                update_button.setIcon(icon)

            self.checkProcessTimer = QTimer(self)
            self.checkProcessTimer.timeout.connect(self.checkTargetExe)
            self.checkProcessTimer.start(500)

    def closeEvent(self, event):
        for proc in self.game_processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass  # процесс уже завершился

        if not read_fullscreen_config():
            save_window_geometry(self.width(), self.height())

        save_card_size(self.card_width)
        event.accept()
