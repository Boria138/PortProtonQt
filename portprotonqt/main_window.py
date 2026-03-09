import os
import shlex
import shutil
import signal
import subprocess
import psutil
import re
from portprotonqt.logger import get_logger
from portprotonqt.dialogs import AddGameDialog, FileExplorer, WinetricksDialog, ExeSettingsDialog
from portprotonqt.game_card import GameCard
from portprotonqt.animations import DetailPageAnimations
from portprotonqt.custom_widgets import ClickableLabel, AutoSizeButton, NavLabel, FlowLayout
from portprotonqt.detail_pages import DetailPageManager
from portprotonqt.portproton_api import PortProtonAPI, get_user_conf_setting, set_user_conf_setting
from portprotonqt.debug_utils import get_gpu_list
from portprotonqt.input_manager import InputManager, MainWindowProtocol
from portprotonqt.context_menu_manager import ContextMenuManager, CustomLineEdit
from portprotonqt.system_overlay import SystemOverlay
from portprotonqt.input_manager import GamepadType

from portprotonqt.image_utils import load_pixmap_async, ImageCarousel
from portprotonqt.steam_api import get_steam_game_info_async, get_full_steam_game_info_async, get_steam_installed_games
from portprotonqt.egs_api import load_egs_games_async, get_egs_executable
from portprotonqt.theme_manager import ThemeManager, load_theme_screenshots
from portprotonqt.time_utils import save_last_launch, get_last_launch, parse_playtime_file, format_playtime, get_last_launch_timestamp, format_last_launch
from portprotonqt.config_utils import (
    get_portproton_location, read_theme_from_config, save_theme_to_config, parse_desktop_entry,
    load_theme_metainfo, read_time_config, read_card_size, save_card_size, read_sort_method,
    read_display_filter, read_favorites, save_time_config, save_sort_method,
    save_display_filter, save_proxy_config, read_proxy_config, read_fullscreen_config,
    save_fullscreen_config, read_window_geometry, save_window_geometry, reset_config,
    clear_cache, read_auto_fullscreen_gamepad, save_auto_fullscreen_gamepad, read_rumble_config, save_rumble_config, read_gamepad_type, save_gamepad_type, read_minimize_to_tray, save_minimize_to_tray,
    read_auto_card_size, save_auto_card_size, get_portproton_start_command, read_hide_autoinstall_tab, save_hide_autoinstall_tab
)

from portprotonqt.tray_manager import restart_application_with_muvm
from portprotonqt.version_utils import version_sort_key
from portprotonqt.localization import _, get_egs_language, read_metadata_translations
from portprotonqt.downloader import Downloader
from portprotonqt.tray_manager import TrayManager
from portprotonqt.game_library_manager import GameLibraryManager
from portprotonqt.virtual_keyboard import VirtualKeyboard
from portprotonqt.dialogs.proton_manager import show_proton_manager
from portprotonqt.config_utils import find_game_by_exe, create_desktop_file

from PySide6.QtWidgets import (QLineEdit, QMainWindow, QStatusBar, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QStackedWidget, QComboBox,
                               QDialog, QFormLayout, QMessageBox, QApplication, QPushButton, QProgressBar, QCheckBox, QSizePolicy, QGridLayout, QScrollArea, QScroller, QSlider, QFrame)
from PySide6.QtCore import Qt, QAbstractAnimation, QUrl, Signal, QTimer, Slot, QProcess, QFileSystemWatcher
from PySide6.QtGui import QIcon, QPixmap, QColor, QDesktopServices
from typing import cast
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = get_logger(__name__)

class MainWindow(QMainWindow):
    games_loaded = Signal(list)
    update_progress = Signal(int)
    update_status_message = Signal(str, int)

    def __init__(self, app_name: str, version: str, launch_exe: str | None = None, resolution: tuple[int, int] | None = None):
        super().__init__()
        self.theme_manager = ThemeManager()
        selected_theme = read_theme_from_config()
        self.current_theme_name = selected_theme
        # Apply theme but defer heavy font loading
        self.theme = self.theme_manager.apply_theme(selected_theme)
        self.tray_manager = TrayManager(self, app_name, self.current_theme_name)
        self.card_width = read_card_size()
        self.auto_card_width = read_auto_card_size()
        self.setWindowTitle(f"{app_name} {version}")
        self.setMinimumSize(800, 600)
        self._pending_resolution = resolution  # Store resolution for later application

        self.games = []
        self.game_processes = []
        self.target_exe = None
        self.current_running_button = None
        self.portproton_location = get_portproton_location()
        self.start_sh = get_portproton_start_command()
        self.launch_exe = launch_exe  # Store launch_exe path

        self.game_library_manager = GameLibraryManager(self, self.theme, None)

        # Initialize detail page manager
        self.detail_page_manager = DetailPageManager(self)

        self.context_menu_manager = ContextMenuManager(
            self,
            self.portproton_location,
            self.theme,
            self.game_library_manager
        )

        self.game_library_manager.context_menu_manager = self.context_menu_manager

        QApplication.setStyle("Fusion")
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
        self.setAcceptDrops(True)
        self.current_exec_line = None
        self.currentDetailPage = None
        self.current_play_button = None
        self.current_focused_card: GameCard | None = None
        self.current_hovered_card: GameCard | None = None
        self.pending_games = []
        self.total_games = 0
        self.games_load_timer = QTimer(self)
        self.games_load_timer.setSingleShot(True)
        self.games_load_timer.timeout.connect(self.finalize_game_loading)
        self.games_loaded.connect(self.on_games_loaded)
        self.current_add_game_dialog = None

        self.settingsDebounceTimer = QTimer(self)
        self.settingsDebounceTimer.setSingleShot(True)
        self.settingsDebounceTimer.setInterval(300)
        self.settingsDebounceTimer.timeout.connect(self.applySettingsDelayed)

        # Initialize file system watcher for dist and prefixes directories
        self.fs_watcher = QFileSystemWatcher(self)
        self.fs_watcher.directoryChanged.connect(self.on_directory_changed)

        read_time_config()

        # Start watching dist and prefixes directories if they exist
        QTimer.singleShot(0, self.start_watching_directories)  # Delay to ensure portproton_location is set
        self.legendary_config_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache"
        )
        os.makedirs(self.legendary_config_path, exist_ok=True)
        os.environ["LEGENDARY_CONFIG_PATH"] = self.legendary_config_path

        self.legendary_path = os.path.join(self.legendary_config_path, "legendary")
        self.downloader = Downloader(max_workers=4)
        self.portproton_api = PortProtonAPI(self.downloader)

        # Status bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setStyleSheet(self.theme.STATUS_BAR_STYLE)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.update_progress.connect(self.progress_bar.setValue)
        self.update_status_message.connect(self.statusBar().showMessage)

        # Show immediate startup progress to indicate the app is loading
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate initially
        self.progress_bar.setValue(0)  # Reset value
        self.update_status_message.emit(_("Starting PortProton..."), 0)
        QApplication.processEvents()  # Process to show progress bar immediately

        self.installing = False
        self.install_process = None
        self.install_monitor_timer = None

        # Wine download monitoring during game launch
        self.wine_download_timer = None
        self.wine_download_percent = 0.0
        self.wine_download_seen = False

        # Central widget and main layout
        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QVBoxLayout(centralWidget)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        # 1. HEADER
        self.header = QWidget()
        self.header.setFixedHeight(80)
        self.header.setStyleSheet(self.theme.MAIN_WINDOW_HEADER_STYLE)
        headerLayout = QVBoxLayout(self.header)
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.addStretch()

        self.input_manager = InputManager(cast(MainWindowProtocol, self))
        self.input_manager.button_event.connect(self.updateControlHints)
        self.input_manager.dpad_moved.connect(self.updateControlHints)

        # 2. NAVIGATION (TAB BUTTONS)
        self.navWidget = QWidget()
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        navLayout = QHBoxLayout(self.navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(10)

         # Left navigation button (key_left or button_lb)
        self.leftNavButton = QLabel()
        self.leftNavButton.setFixedSize(32, 32)
        self.leftNavButton.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navLayout.addWidget(self.leftNavButton)

        # Tabs
        self.tabButtons = {}
        tabs = [
            _("Library"),
            _("Auto Install"),
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

        # Right navigation button (key_right or button_rb)
        self.rightNavButton = QLabel()
        self.rightNavButton.setFixedSize(32, 32)
        self.rightNavButton.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navLayout.addWidget(self.rightNavButton)

        # Initial update of navigation buttons based on input device
        self.updateNavButtons()

        mainLayout.addWidget(self.navWidget)

        # 3. QStackedWidget (TABS)
        self.stackedWidget = QStackedWidget()
        mainLayout.addWidget(self.stackedWidget)

        self.createInstalledTab()

        # Always create auto-install tab but set visibility based on settings
        self.createAutoInstallTab()
        self.auto_install_tab_index = 1  # Auto Install tab is always at index 1

        # Set visibility based on settings
        hide_autoinstall = read_hide_autoinstall_tab()
        if hide_autoinstall:
            # Hide the tab button and page
            if hasattr(self, 'tabButtons') and self.auto_install_tab_index in self.tabButtons:
                tab_button = self.tabButtons[self.auto_install_tab_index]
                tab_button.setVisible(False)

            if hasattr(self, 'stackedWidget'):
                auto_install_page = self.stackedWidget.widget(self.auto_install_tab_index)
                if auto_install_page:
                    auto_install_page.setVisible(False)

        self.createWineTab()
        self.createPortProtonTab()
        self.createThemeTab()

        self.controlHintsWidget = self.createControlHintsWidget()
        mainLayout.addWidget(self.controlHintsWidget)

        self.updateControlHints()

        self.restore_state()

        self.keyboard = VirtualKeyboard(self, self.theme)

        self.detail_animations = DetailPageAnimations(self, self.theme)
        self._animations = {}

        if read_fullscreen_config():
            self.showFullScreen()
        elif self._pending_resolution:
            # Apply resolution from command line
            self.resize(self._pending_resolution[0], self._pending_resolution[1])
            self.showNormal()
        else:
            width, height = read_window_geometry()
            if width > 0 and height > 0:
                self.resize(width, height)
            else:
                self.showNormal()

        # Process events to ensure UI is responsive before starting heavy operations
        QApplication.processEvents()

        # Delay game loading until after the UI is fully displayed to prevent blocking
        # Use a longer delay to ensure window is fully rendered and responsive
        # Use a custom event processing approach to make sure UI stays responsive
        QTimer.singleShot(500, self.loadGames)  # Reduced delay but ensure UI gets event processing

    def on_slider_released(self) -> None:
        """Delegate to game library manager."""
        if hasattr(self, 'game_library_manager'):
            self.game_library_manager.on_slider_released()

    def on_directory_changed(self, path: str):
        """Handle directory change events for dist and prefixes directories."""
        if not self.portproton_location:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        prefixes_path = os.path.join(self.portproton_location, "data", "prefixes")

        if path == dist_path:
            # Wine/Proton directory changed, refresh wine combo
            QTimer.singleShot(100, self.refresh_wine_combo)  # Small delay to allow file operations to complete
        elif path == prefixes_path:
            # Prefixes directory changed, refresh prefix combo
            QTimer.singleShot(100, self.refresh_prefix_combo)  # Small delay to allow file operations to complete

    def start_watching_directories(self):
        """Start watching dist and prefixes directories for changes."""
        if not self.portproton_location:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        prefixes_path = os.path.join(self.portproton_location, "data", "prefixes")

        # Create directories if they don't exist
        os.makedirs(dist_path, exist_ok=True)
        os.makedirs(prefixes_path, exist_ok=True)

        # Add dist directory to watcher
        self.fs_watcher.addPath(dist_path)

        # Add prefixes directory to watcher
        self.fs_watcher.addPath(prefixes_path)

    def get_button_icon(self, action: str, gtype: GamepadType) -> str:
        """Get the icon name for a specific action and gamepad type."""
        mappings = {
            'confirm': {
                GamepadType.XBOX: "xbox_a",
                GamepadType.PLAYSTATION: "ps_cross",
            },
            'back': {
                GamepadType.XBOX: "xbox_b",
                GamepadType.PLAYSTATION: "ps_circle",
            },
            'add_game': {
                GamepadType.XBOX: "xbox_x",
                GamepadType.PLAYSTATION: "ps_triangle",
            },
            'context_menu': {
                GamepadType.XBOX: "xbox_start",
                GamepadType.PLAYSTATION: "ps_options",
            },
            'menu': {
                GamepadType.XBOX: "xbox_view",  # Select button on Xbox
                GamepadType.PLAYSTATION: "ps_share",
            },
            'search': {
                GamepadType.XBOX: "xbox_y",
                GamepadType.PLAYSTATION: "ps_square",
            },
            'prev_dir': {
                GamepadType.XBOX: "xbox_y",
                GamepadType.PLAYSTATION: "ps_square",
            },
            'guide_select': {
                GamepadType.XBOX: "xbox_xbox",  # Xbox Guide button
                GamepadType.PLAYSTATION: "ps_ps",  # PS button
            },
        }
        return mappings.get(action, {}).get(gtype, "placeholder")

    def get_nav_icon(self, direction: str, gtype: GamepadType) -> str:
        """Get the icon name for navigation direction and gamepad type."""
        if direction == 'left':
            action = 'prev_tab'
        else:
            action = 'next_tab'
        mappings = {
            'prev_tab': {
                GamepadType.XBOX: "xbox_lb",
                GamepadType.PLAYSTATION: "ps_l1",
            },
            'next_tab': {
                GamepadType.XBOX: "xbox_rb",
                GamepadType.PLAYSTATION: "ps_r1",
            },
        }
        return mappings.get(action, {}).get(gtype, "placeholder")

    def createControlHintsWidget(self) -> QWidget:
        from portprotonqt.localization import _
        """Creates a widget displaying control hints for gamepad and keyboard."""
        logger.debug("Creating control hints widget")
        hintsWidget = QWidget()
        hintsWidget.setStyleSheet(self.theme.STATUS_BAR_STYLE)

        hintsLayout = QHBoxLayout(hintsWidget)
        hintsLayout.setContentsMargins(10, 0, 10, 0)
        hintsLayout.setSpacing(20)

        gamepad_actions = [
            ("confirm", _("Select")),
            ("back", _("Back")),
            ("add_game", _("Add Game")),
            ("context_menu", _("Menu")),
            ("menu", _("Fullscreen")),
            ("search", _("Search")),
            ("guide_select", _("Refresh Grid")),
            ("mouse_emulation", _("Mouse Emulation")),
        ]

        keyboard_hints = [
            ("key_enter", _("Select")),
            ("key_backspace", _("Back")),
            ("key_e", _("Add Game")),
            ("key_context", _("Menu")),
            ("key_f11", _("Fullscreen")),
            ("key_f5", _("Refresh Grid")),
        ]

        self.hintsLabels = []

        def makeHint(icon_name: str, action_text: str, is_gamepad: bool, action: str | None = None,):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 5, 0, 0)
            layout.setSpacing(6)

            # button icon
            icon_label = QLabel()
            icon_label.setFixedSize(26, 26)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap()
            for candidate in (
                self.theme_manager.get_theme_image(icon_name, self.current_theme_name),
                self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
            ):
                if candidate is not None and pixmap.load(str(candidate)):
                    break

            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(
                    26, 26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))

            layout.addWidget(icon_label)

            # action text
            text_label = QLabel(action_text)
            text_label.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)
            text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(text_label)

            if is_gamepad:
                container.setVisible(False)
                self.hintsLabels.append((container, icon_label, action))  # Store action for dynamic update
            else:
                container.setVisible(True)
                self.hintsLabels.append((container, icon_label, None))  # Keyboard, no action

            hintsLayout.addWidget(container)

        # Special function to create combination hint for Guide+Select or Guide+Start
        def makeCombinationHint(action_text: str, action: str | None = None):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 5, 0, 0)
            layout.setSpacing(6)

            # First icon (Guide button)
            guide_icon = QLabel()
            guide_icon.setFixedSize(26, 26)
            guide_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap()
            for candidate in (
                self.theme_manager.get_theme_image("xbox_xbox", self.current_theme_name),  # Xbox Guide
                self.theme_manager.get_theme_image("ps_ps", self.current_theme_name),  # PS Button
                self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
            ):
                if candidate is not None and pixmap.load(str(candidate)):
                    break

            if not pixmap.isNull():
                guide_icon.setPixmap(pixmap.scaled(
                    26, 26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))

            layout.addWidget(guide_icon)

            # Plus sign between icons
            plus_icon = QLabel()
            plus_icon.setFixedSize(26, 26)
            plus_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            plus_pixmap = QPixmap()
            for candidate in (
                self.theme_manager.get_theme_image("key_+", self.current_theme_name),
                self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
            ):
                if candidate is not None and plus_pixmap.load(str(candidate)):
                    break

            if not plus_pixmap.isNull():
                plus_icon.setPixmap(plus_pixmap.scaled(
                    26, 26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))

            layout.addWidget(plus_icon)

            # Second icon (Select button for guide_select, Start button for mouse_emulation)
            select_icon = QLabel()
            select_icon.setFixedSize(26, 26)
            select_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Determine which icon to use based on action
            if action == "mouse_emulation":  # Guide+Start combination for mouse emulation
                pixmap2 = QPixmap()
                for candidate in (
                    self.theme_manager.get_theme_image("xbox_start", self.current_theme_name),  # Xbox Start
                    self.theme_manager.get_theme_image("ps_options", self.current_theme_name),  # PS Options
                    self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                ):
                    if candidate is not None and pixmap2.load(str(candidate)):
                        break
            else:  # Default to Select for guide_select
                pixmap2 = QPixmap()
                for candidate in (
                    self.theme_manager.get_theme_image("xbox_view", self.current_theme_name),  # Xbox Select
                    self.theme_manager.get_theme_image("ps_share", self.current_theme_name),  # PS Share
                    self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                ):
                    if candidate is not None and pixmap2.load(str(candidate)):
                        break

            if not pixmap2.isNull():
                select_icon.setPixmap(pixmap2.scaled(
                    26, 26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))

            layout.addWidget(select_icon)

            # action text
            text_label = QLabel(action_text)
            text_label.setStyleSheet(self.theme.LAST_LAUNCH_VALUE_STYLE)
            text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(text_label)

            # For gamepad combination hints
            container.setVisible(False)
            self.hintsLabels.append((container, [guide_icon, plus_icon, select_icon], action))  # Store all three elements for dynamic update

            hintsLayout.addWidget(container)

        # Create gamepad hints
        for action, text in gamepad_actions:
            if action in ("guide_select", "mouse_emulation"):
                # For the Guide+Select or Guide+Start combination, create a special combination hint
                makeCombinationHint(text, action)
            else:
                makeHint("placeholder", text, True, action)  # Initial placeholder

        # Create keyboard hints
        for icon, text in keyboard_hints:
            makeHint(icon, text, False)

        hintsLayout.addStretch()
        return hintsWidget

    def updateNavButtons(self, *args) -> None:
        """Updates navigation buttons based on gamepad connection status and type."""
        is_gamepad_connected = self.input_manager.gamepad is not None
        gtype = self.input_manager.gamepad_type
        logger.debug("Updating nav buttons, gamepad connected: %s, type: %s", is_gamepad_connected, gtype.value)

        # Left navigation button
        left_pix = QPixmap()
        if is_gamepad_connected:
            left_icon_name = self.get_nav_icon('left', gtype)
        else:
            left_icon_name = "key_left"
        left_icon = self.theme_manager.get_theme_image(left_icon_name, self.current_theme_name)
        if left_icon:
            left_pix.load(str(left_icon))
        if not left_pix.isNull():
            self.leftNavButton.setPixmap(left_pix.scaled(
                32, 32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        self.leftNavButton.setVisible(True)  # Always visible, icon changes

        # Right navigation button
        right_pix = QPixmap()
        if is_gamepad_connected:
            right_icon_name = self.get_nav_icon('right', gtype)
        else:
            right_icon_name = "key_right"
        right_icon = self.theme_manager.get_theme_image(right_icon_name, self.current_theme_name)
        if right_icon:
            right_pix.load(str(right_icon))
        if not right_pix.isNull():
            self.rightNavButton.setPixmap(right_pix.scaled(
                32, 32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        self.rightNavButton.setVisible(True)  # Always visible, icon changes

    def updateControlHints(self, *args) -> None:
        """Updates control hints based on gamepad connection status and type."""
        is_gamepad_connected = self.input_manager.gamepad is not None
        gtype = self.input_manager.gamepad_type
        logger.debug("Updating control hints, gamepad connected: %s, type: %s", is_gamepad_connected, gtype.value)

        gamepad_actions = ['confirm', 'back', 'add_game', 'context_menu', 'menu', 'search', 'guide_select', 'mouse_emulation']

        for container, icon_element, action in self.hintsLabels:
            if action in gamepad_actions:  # Gamepad hint
                if is_gamepad_connected:
                    container.setVisible(True)
                    # Check if this is a combination hint (array of icons) or single icon hint
                    if isinstance(icon_element, list) and len(icon_element) == 3 and action in ("guide_select", "mouse_emulation"):
                        # This is a combination hint for Guide+Select or Guide+Start (mouse emulation)
                        guide_icon, plus_icon, select_icon = icon_element

                        # Determine guide icon based on gamepad type
                        if gtype == GamepadType.XBOX:
                            guide_icon_name = "xbox_xbox"  # Xbox Guide button
                        elif gtype == GamepadType.PLAYSTATION:
                            guide_icon_name = "ps_ps"  # PS Button
                        else:
                            guide_icon_name = "xbox_xbox"  # Default to Xbox guide

                        # Load Guide icon
                        guide_pixmap = QPixmap()
                        for candidate in (
                            self.theme_manager.get_theme_image(guide_icon_name, self.current_theme_name),
                            self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                        ):
                            if candidate is not None and guide_pixmap.load(str(candidate)):
                                break

                        if not guide_pixmap.isNull():
                            guide_icon.setPixmap(guide_pixmap.scaled(
                                26, 26,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))

                        # Load Plus icon
                        plus_pixmap = QPixmap()
                        for candidate in (
                            self.theme_manager.get_theme_image("key_+", self.current_theme_name),
                            self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                        ):
                            if candidate is not None and plus_pixmap.load(str(candidate)):
                                break

                        if not plus_pixmap.isNull():
                            plus_icon.setPixmap(plus_pixmap.scaled(
                                26, 26,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))

                        # Determine second icon based on gamepad type and action
                        select_icon_name = "xbox_view"  # Default to Xbox Select
                        if action == "guide_select":  # Guide+Select combination
                            if gtype == GamepadType.XBOX:
                                select_icon_name = "xbox_view"  # Xbox Select button
                            elif gtype == GamepadType.PLAYSTATION:
                                select_icon_name = "ps_share"  # PS Share button
                        elif action == "mouse_emulation":  # Guide+Start combination
                            if gtype == GamepadType.XBOX:
                                select_icon_name = "xbox_start"  # Xbox Start button
                            elif gtype == GamepadType.PLAYSTATION:
                                select_icon_name = "ps_options"  # PS Options button
                            else:
                                select_icon_name = "xbox_start"  # Default to Xbox Start

                        # Load second icon
                        select_pixmap = QPixmap()
                        for candidate in (
                            self.theme_manager.get_theme_image(select_icon_name, self.current_theme_name),
                            self.theme_manager.get_theme_image("placeholder", self.current_theme_name),
                        ):
                            if candidate is not None and select_pixmap.load(str(candidate)):
                                break

                        if not select_pixmap.isNull():
                            select_icon.setPixmap(select_pixmap.scaled(
                                26, 26,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))
                    else:
                        # This is a regular single-icon hint
                        # Verify that icon_element is not a list before assigning
                        if isinstance(icon_element, list):
                            # This shouldn't happen based on current logic, but added for safety
                            logger.warning(f"Unexpected list found for single-icon hint with action: {action}")
                            continue  # Skip this iteration to prevent error
                        icon_label = icon_element
                        # Update icon based on type
                        icon_name = self.get_button_icon(action, gtype)
                        icon_path = self.theme_manager.get_theme_image(icon_name, self.current_theme_name)
                        pixmap = QPixmap()
                        if icon_path:
                            pixmap.load(str(icon_path))
                        if not pixmap.isNull():
                            icon_label.setPixmap(pixmap.scaled(
                                26, 26,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))
                        else:
                            # Fallback to placeholder
                            placeholder = self.theme_manager.get_theme_image("placeholder", self.current_theme_name)
                            if placeholder:
                                pixmap.load(str(placeholder))
                                icon_label.setPixmap(pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    container.setVisible(False)
            else:  # Keyboard hint
                container.setVisible(not is_gamepad_connected)

        # Update navigation buttons
        self.updateNavButtons()

    def launch_autoinstall(self, script_name: str):
        """Launch auto-install script."""
        if self.installing:
            QMessageBox.warning(self, _("Warning"), _("Installation already in progress."))
            return
        self.installing = True
        self.seen_progress = False
        self.current_percent = 0.0
        start_sh = self.start_sh
        if not start_sh:
            self.installing = False
            return
        cmd = start_sh + ["cli", "--autoinstall", script_name]
        self.install_process = QProcess(self)
        self.install_process.finished.connect(self.on_install_finished)
        self.install_process.errorOccurred.connect(self.on_install_error)
        self.install_process.start(cmd[0], cmd[1:])
        if not self.install_process.waitForStarted(5000):
            self.installing = False
            QMessageBox.warning(self, _("Error"), _("Failed to start installation."))
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.update_status_message.emit(_("Processed {} installation...").format(script_name), 0)
        self.install_monitor_timer = QTimer(self)
        self.install_monitor_timer.timeout.connect(self.monitor_install_progress)
        self.install_monitor_timer.start(2000)  # Start monitoring after 2s

    def _parse_process_log_progress(self) -> float | None:
        """Parse progress percentage from /tmp/PortProton_$USER/process.log.

        Returns:
            float | None: Progress percentage (0.0-100.0) if found, None otherwise.
        """
        user = os.getenv('USER', 'unknown')
        log_file = f"/tmp/PortProton_{user}/process.log"
        if not os.path.exists(log_file):
            return None
        try:
            with open(log_file, encoding='utf-8') as f:
                content = f.read()
            matches = re.findall(r'([0-9]*\.?[0-9]+)%', content)
            if matches:
                percent = float(matches[-1])
                return percent
        except Exception as e:
            logger.error(f"Error parsing process log: {e}")
        return None

    def monitor_install_progress(self):
        """Monitor /tmp/PortProton_$USER/process.log for progress."""
        percent = self._parse_process_log_progress()
        if percent is None:
            return
        try:
            if percent > 0:
                self.seen_progress = True
                self.current_percent = percent
            elif self.seen_progress and percent == 0:
                self.current_percent = 100.0
                if self.install_monitor_timer is not None:
                    self.install_monitor_timer.stop()
            # Update progress bar to determinate if not already
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setFormat("%p")  # Show percentage
            self.progress_bar.setValue(int(self.current_percent))
            if self.current_percent >= 100:
                if self.install_monitor_timer is not None:
                    self.install_monitor_timer.stop()
        except ValueError:
            pass  # Ignore invalid floats

    @Slot(int, int)
    def on_install_finished(self, exit_code: int, exit_status: int):
        """Handle installation finish."""
        self.installing = False
        if self.install_monitor_timer is not None:
            self.install_monitor_timer.stop()
            self.install_monitor_timer.deleteLater()
            self.install_monitor_timer = None
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        if exit_code == 0:
            self.update_status_message.emit(_("Installation completed successfully."), 5000)

            desktop_dir = self.portproton_location or ""
            new_desktops = [e.path for e in os.scandir(desktop_dir) if e.name.endswith(".desktop")]
            if new_desktops:
                latest = max(new_desktops, key=os.path.getmtime)
                self._process_desktop_file_async(
                    latest,
                    lambda result: (
                        self.game_library_manager.add_game_incremental(result)
                        if result else None
                    )
                )

        else:
            self.update_status_message.emit(_("Installation failed."), 5000)
            QMessageBox.warning(self, _("Error"), f"Installation failed (code: {exit_code}).")

        self.progress_bar.setVisible(False)
        if self.install_process:
            self.install_process.deleteLater()
            self.install_process = None

    def on_install_error(self, error: QProcess.ProcessError):
        """Handle installation error."""
        self.installing = False
        if self.install_monitor_timer is not None:
            self.install_monitor_timer.stop()
            self.install_monitor_timer.deleteLater()
            self.install_monitor_timer = None
        self.update_status_message.emit(_("Installation error."), 5000)
        QMessageBox.warning(self, _("Error"), f"Process error: {error}")
        self.progress_bar.setVisible(False)

    @Slot(list)
    def on_games_loaded(self, games: list[tuple]):
        self.games = games
        self.game_library_manager.set_games(games)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)  # Reset to determinate state for next use
        self.progress_bar.setValue(0)

        # Clear the refresh in progress flag
        if hasattr(self, '_refresh_in_progress'):
            self._refresh_in_progress = False

        # Re-enable the refresh button if it exists
        if hasattr(self, 'refreshButton'):
            self.refreshButton.setEnabled(True)
            self.refreshButton.setText(_("Refresh Grid"))
            self.update_status_message.emit(_("Game library refreshed"), 3000)

    def loadGames(self):
        # Skip loading library if launching a specific exe
        if self.launch_exe:
            # Hide progress bar and status message when skipping library load
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.statusBar().clearMessage()
            return

        display_filter = read_display_filter()
        favorites = read_favorites()
        self.pending_games = []
        self.games = []

        # Show initial progress bar immediately
        self.progress_bar.setRange(0, 100)  # Set to determinate range
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Process events to keep UI responsive
        QApplication.processEvents()

        def start_loading():
            # Make sure progress bar is still visible
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # Allow UI to update

            if display_filter == "steam":
                self._load_steam_games_async(lambda games: self.games_loaded.emit(games))
            elif display_filter == "portproton":
                self._load_portproton_games_async(lambda games: self.games_loaded.emit(games))
            elif display_filter == "epic":
                load_egs_games_async(
                    self.legendary_path,
                    lambda games: self.games_loaded.emit(games),
                    self.downloader,
                    self.update_progress.emit,
                    self.update_status_message.emit
                )
            elif display_filter == "favorites":
                def on_all_games_favorites(portproton_games, steam_games, epic_games):
                    games = [game for game in portproton_games + steam_games + epic_games if game[0] in favorites]
                    self.games_loaded.emit(games)

                # Load games from different sources in parallel to prevent blocking
                results = {'portproton': [], 'steam': [], 'epic': []}
                completed = {'portproton': False, 'steam': False, 'epic': False}

                def check_completion():
                    if all(completed.values()):
                        QApplication.processEvents()  # Keep UI responsive
                        on_all_games_favorites(results['portproton'], results['steam'], results['epic'])

                def portproton_callback(games):
                    results['portproton'] = games
                    completed['portproton'] = True
                    QApplication.processEvents()  # Keep UI responsive
                    check_completion()

                def steam_callback(games):
                    results['steam'] = games
                    completed['steam'] = True
                    QApplication.processEvents()  # Keep UI responsive
                    check_completion()

                def epic_callback(games):
                    results['epic'] = games
                    completed['epic'] = True
                    QApplication.processEvents()  # Keep UI responsive
                    check_completion()

                self._load_portproton_games_async(portproton_callback)
                self._load_steam_games_async(steam_callback)
                load_egs_games_async(
                    self.legendary_path,
                    epic_callback,
                    self.downloader,
                    self.update_progress.emit,
                    self.update_status_message.emit
                )
            else:
                # For 'all' filter - load games from different sources in parallel to prevent blocking
                results = {'portproton': [], 'steam': [], 'epic': []}
                completed = {'portproton': False, 'steam': False, 'epic': False}

                def on_all_games():
                    seen = set()
                    games = []
                    for game in results['portproton'] + results['steam'] + results['epic']:
                        # Unique key: name + exec_line
                        key = (game[0], game[4])
                        if key not in seen:
                            seen.add(key)
                            games.append(game)
                    QApplication.processEvents()  # Keep UI responsive
                    self.games_loaded.emit(games)

                def check_completion():
                    if all(completed.values()):
                        QApplication.processEvents()  # Keep UI responsive
                        on_all_games()

                def portproton_callback(games):
                    results['portproton'] = games
                    completed['portproton'] = True
                    QApplication.processEvents()  # Keep UI responsive
                    check_completion()

                def steam_callback(games):
                    results['steam'] = games
                    completed['steam'] = True
                    QApplication.processEvents()  # Keep UI responsive
                    check_completion()

                def epic_callback(games):
                    results['epic'] = games
                    completed['epic'] = True
                    QApplication.processEvents()  # Keep UI responsive
                    check_completion()

                # Load all sources in parallel
                self._load_portproton_games_async(portproton_callback)
                self._load_steam_games_async(steam_callback)
                load_egs_games_async(
                    self.legendary_path,
                    epic_callback,
                    self.downloader,
                    self.update_progress.emit,
                    self.update_status_message.emit
                )

        # Run loading immediately to show status without delay
        start_loading()

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
                    'game_source': 'steam'
                }
            last_launch = format_last_launch(datetime.fromtimestamp(last_played)) if last_played else _("Never")
            steam_games.append((
                name,
                info.get('description', ''),
                info.get('cover', ''),
                appid,
                info.get('controller_support', ''),
                f"steam://rungameid/{appid}",
                last_launch,
                format_playtime(playtime_seconds),
                info.get('protondb_tier', ''),
                info.get("anticheat_status", ""),
                last_played,
                playtime_seconds,
                "steam"
            ))
            processed_count += 1
            self.pending_games.append(None)
            self.update_progress.emit(len(self.pending_games))  # Update progress bar
            if processed_count == len(installed_games):
                callback(steam_games)

        for name, appid, last_played, playtime_seconds in installed_games:
            get_full_steam_game_info_async(appid, lambda info, n=name, a=appid, lp=last_played, pt=playtime_seconds: on_game_info(info, n, a, lp, pt), fallback_name=name)

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
        processed_count = 0
        def on_desktop_processed(result: tuple | None, games=games):
            nonlocal processed_count
            if result:
                games.append(result)
            self.pending_games.append(None)
            self.update_progress.emit(len(self.pending_games))  # Update progress bar
            processed_count += 1
            if processed_count == len(desktop_files):
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
        user_custom_folder = os.path.join(xdg_data_home, "PortProtonQt", "custom_data")
        os.makedirs(user_custom_folder, exist_ok=True)

        builtin_cover = ""
        user_cover = ""
        user_game_folder = ""
        builtin_game_folder = ""

        if game_exe:
            exe_name = os.path.splitext(os.path.basename(game_exe))[0]
            builtin_game_folder = os.path.join(builtin_custom_folder, exe_name)
            user_game_folder = os.path.join(user_custom_folder, exe_name)
            os.makedirs(user_game_folder, exist_ok=True)

            # Check if local game folder is empty and download assets if it is
            if not os.listdir(user_game_folder):
                logger.debug(f"Local folder for {exe_name} is empty, checking repository")
                def on_assets_downloaded(results):
                    nonlocal user_cover
                    if results["cover"]:
                        user_cover = results["cover"]
                        logger.info(f"Downloaded assets for {exe_name}: {results}")
                    if results["metadata"]:
                        logger.info(f"Downloaded metadata for {exe_name}: {results['metadata']}")
                self.portproton_api.download_game_assets_async(exe_name, timeout=5, callback=on_assets_downloaded)

            # Read cover
            builtin_files = set(os.listdir(builtin_game_folder)) if os.path.exists(builtin_game_folder) else set()
            for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                candidate = f"cover{ext}"
                if candidate in builtin_files:
                    builtin_cover = os.path.join(builtin_game_folder, candidate)
                    break

            user_files = set(os.listdir(user_game_folder)) if os.path.exists(user_game_folder) else set()
            for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                candidate = f"cover{ext}"
                if candidate in user_files:
                    user_cover = os.path.join(user_game_folder, candidate)
                    break

            # Read statistics
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
                    logger.error(f"Failed to parse playtime data: {e}")

        def on_steam_info(steam_info: dict):
            # Get current language
            language_code = get_egs_language()

            # Read translations from metadata.txt
            user_metadata_file = os.path.join(user_game_folder, "metadata.txt")
            builtin_metadata_file = os.path.join(builtin_game_folder, "metadata.txt")

            # Try user translations first
            translations = {'name': desktop_name, 'description': ''}
            if os.path.exists(user_metadata_file):
                translations = read_metadata_translations(user_metadata_file, language_code)
            elif os.path.exists(builtin_metadata_file):
                translations = read_metadata_translations(builtin_metadata_file, language_code)

            final_name = translations['name']
            final_desc = translations['description'] or steam_info.get("description", "")
            final_cover = (user_cover if user_cover else
                        builtin_cover if builtin_cover else
                        steam_info.get("cover", "") or entry.get("Icon", ""))

            callback((
                final_name,
                final_desc,
                final_cover,
                steam_info.get("appid", ""),
                steam_info.get("controller_support", ""),
                exec_line,
                get_last_launch(exe_name) if exe_name else _("Never"),
                formatted_playtime,
                steam_info.get("protondb_tier", ""),
                steam_info.get("anticheat_status", ""),
                get_last_launch_timestamp(exe_name) if exe_name else 0,
                playtime_seconds,
                "portproton"
            ))

        get_steam_game_info_async(desktop_name, exec_line, on_steam_info)

    def finalize_game_loading(self):
        logger.info("Finalizing game loading, pending_games: %d", len(self.pending_games))
        if self.pending_games and all(x is None for x in self.pending_games):
            logger.info("All games processed, clearing pending_games")
            self.pending_games = []
            self.update_progress.emit(0)  # Hide progress bar
            self.progress_bar.setVisible(False)
            self.update_status_message.emit("", 0)  # Clear status message

    # TABS
    def switchTab(self, index):
        """Set active tab by index."""
        # Check if the requested tab index is valid, exists, and is visible
        if (hasattr(self, 'tabButtons') and
            index in self.tabButtons and
            self.tabButtons[index].isVisible()):

            # Only allow switching to existing and visible tabs
            for i, btn in self.tabButtons.items():
                btn.setChecked(i == index)
            self.stackedWidget.setCurrentIndex(index)
            if index == self.auto_install_tab_index:
                self._start_autoinstall_load()
        else:
            # If trying to switch to a non-existent or hidden tab (like auto-install when it's hidden),
            # find the first visible tab to switch to
            visible_tab_found = False
            if hasattr(self, 'tabButtons'):
                for i, btn in self.tabButtons.items():
                    if btn.isVisible():
                        for j, other_btn in self.tabButtons.items():
                            other_btn.setChecked(j == i)
                        self.stackedWidget.setCurrentIndex(i)
                        visible_tab_found = True
                        break

            # If no visible tab found (shouldn't happen), default to the first tab
            if not visible_tab_found and hasattr(self, 'tabButtons') and 0 in self.tabButtons:
                for i, btn in self.tabButtons.items():
                    btn.setChecked(i == 0)
                self.stackedWidget.setCurrentIndex(0)

        if hasattr(self, "game_library_manager"):
            mgr = self.game_library_manager
            if mgr.gamesListWidget and mgr.gamesListLayout:
                games_layout = mgr.gamesListLayout
                games_widget = mgr.gamesListWidget
                # Update layout updates to be more compatible with PySide 6.10.1
                QTimer.singleShot(0, lambda: games_layout.invalidate())
                QTimer.singleShot(10, lambda: games_widget.adjustSize())
                QTimer.singleShot(15, lambda: games_widget.updateGeometry())
        if hasattr(self, "autoInstallContainer") and hasattr(self, "autoInstallContainerLayout"):
            auto_layout = self.autoInstallContainerLayout
            auto_widget = self.autoInstallContainer
            # Update layout updates to be more compatible with PySide 6.10.1
            QTimer.singleShot(0, lambda: auto_layout.invalidate())
            QTimer.singleShot(10, lambda: auto_widget.adjustSize())
            QTimer.singleShot(15, lambda: auto_widget.updateGeometry())


    def openSystemOverlay(self):
        """Opens the system overlay dialog."""
        overlay = SystemOverlay(self, self.theme)
        overlay.exec()

    def createSearchWidget(self) -> tuple[QWidget, CustomLineEdit]:
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
        self.addGameButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(self.addGameButton)

        # Refresh button
        self.refreshButton = AutoSizeButton(_("Refresh Grid"), icon=self.theme_manager.get_icon("update"))
        self.refreshButton.setStyleSheet(self.theme.ADDGAME_BACK_BUTTON_STYLE)
        self.refreshButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refreshButton.clicked.connect(self.refreshGames)
        layout.addWidget(self.refreshButton)

        layout.addStretch()  # Add stretch to push search to the right

        self.searchEdit = CustomLineEdit(self, theme=self.theme)
        icon: QIcon = cast(QIcon, self.theme_manager.get_icon("search"))
        action_pos = cast(QLineEdit.ActionPosition, QLineEdit.ActionPosition.LeadingPosition)
        self.searchEdit.addAction(icon, action_pos)
        self.searchEdit.setMaximumWidth(200)
        self.searchEdit.setPlaceholderText(_("Find Games ..."))
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)

        self.searchEdit.textChanged.connect(self.startSearchDebounce)
        self.searchDebounceTimer = QTimer(self)
        self.searchDebounceTimer.setSingleShot(True)
        self.searchDebounceTimer.setInterval(150)  # Reduced debounce time for better responsiveness
        self.searchDebounceTimer.timeout.connect(self.on_search_changed)

        layout.addWidget(self.searchEdit)
        return self.container, self.searchEdit

    def refreshGames(self):
        """Refresh the game grid by reloading all games without restarting the application."""
        # Prevent multiple refreshes at once
        if hasattr(self, '_refresh_in_progress') and self._refresh_in_progress:
            # If refresh is already in progress, just update the status
            self.update_status_message.emit(_("A refresh is already in progress..."), 3000)
            return

        # Mark that a refresh is in progress
        self._refresh_in_progress = True

        # Clear the search field to ensure all games are shown after refresh
        self.searchEdit.clear()

        # Disable the refresh button during refresh to prevent multiple clicks
        self.refreshButton.setEnabled(False)
        self.refreshButton.setText(_("Refreshing..."))

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.update_status_message.emit(_("Refreshing game library..."), 0)

        # Clear the game card cache and layout to force reload of custom data
        if hasattr(self, 'game_library_manager') and self.game_library_manager:
            # Clear the cache to ensure custom data is reloaded
            self.game_library_manager.game_card_cache.clear()
            self.game_library_manager.pending_images.clear()
            # Clear search indices to rebuild with fresh data
            if hasattr(self.game_library_manager, '_build_search_indices'):
                # Mark for full rebuild of search indices
                self.game_library_manager.dirty = True  # Force full update

            # Also clear the layout to ensure old widgets are removed
            if (hasattr(self.game_library_manager, 'gamesListLayout') and
                self.game_library_manager.gamesListLayout and
                hasattr(self.game_library_manager, 'gamesListWidget') and
                self.game_library_manager.gamesListWidget):
                # Remove all widgets from the layout
                self.game_library_manager.clear_layout(self.game_library_manager.gamesListLayout)

                # Force layout update to ensure UI changes are visible
                self.game_library_manager.gamesListWidget.updateGeometry()
                if hasattr(self.game_library_manager, 'gamesListLayout'):
                    self.game_library_manager.gamesListLayout.update()

        # Reload games using the existing loadGames functionality
        # Use a small delay to allow UI to update before starting the refresh
        QTimer.singleShot(50, lambda: self.loadGames())

    def on_search_text_changed(self, text: str):
        """Search text change handler with debounce."""
        self.searchDebounceTimer.stop()
        self.searchDebounceTimer.start()

    @Slot()
    def on_search_changed(self):
        """Triggers filtering with delay."""
        if hasattr(self, 'game_library_manager'):
            self.game_library_manager.filter_games_delayed()

    def startSearchDebounce(self, text):
        self.searchDebounceTimer.start()

    def createInstalledTab(self):
        self.gamesLibraryWidget = self.game_library_manager.create_games_library_widget()
        self.stackedWidget.addWidget(self.gamesLibraryWidget)
        self.gamesListWidget = self.game_library_manager.gamesListWidget
        self.game_library_manager.update_game_grid()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_animations') and self._animations:
            for widget, animation in list(self._animations.items()):
                try:
                    if animation.state() == QAbstractAnimation.State.Running:
                        animation.stop()
                        widget.setWindowOpacity(1.0)
                        del self._animations[widget]
                except RuntimeError:
                    del self._animations[widget]
        if not hasattr(self, '_last_width'):
            self._last_width = self.width()
        if abs(self.width() - self._last_width) > 10:
            self._last_width = self.width()


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
        if self.current_add_game_dialog is not None and self.current_add_game_dialog.isVisible():
            self.current_add_game_dialog.activateWindow()
            self.current_add_game_dialog.raise_()
            return

        dialog = AddGameDialog(self, self.theme)
        dialog.setFocus(Qt.FocusReason.OtherFocusReason)
        self.current_add_game_dialog = dialog

        if exe_path:
            dialog.exeEdit.setText(exe_path)
            dialog.nameEdit.setText(os.path.splitext(os.path.basename(exe_path))[0])
            dialog.updatePreview()

        def on_dialog_finished():
            self.current_add_game_dialog = None

        dialog.finished.connect(on_dialog_finished)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.nameEdit.text().strip()
            exe_path = dialog.exeEdit.text().strip()
            user_cover = dialog.coverEdit.text().strip()

            if not name or not exe_path:
                return

            desktop_entry, desktop_path = dialog.getDesktopEntryData()
            if desktop_entry and desktop_path:
                with open(desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                    os.chmod(desktop_path, 0o755)

                exe_name = os.path.splitext(os.path.basename(exe_path))[0]
                xdg_data_home = os.getenv("XDG_DATA_HOME",
                    os.path.join(os.path.expanduser("~"), ".local", "share"))
                custom_folder = os.path.join(
                    xdg_data_home,
                    "PortProtonQt",
                    "custom_data",
                    exe_name
                )
                os.makedirs(custom_folder, exist_ok=True)

                # Handle user cover copy
                cover_path = None
                if user_cover:
                    ext = os.path.splitext(user_cover)[1].lower()
                    if os.path.isfile(user_cover) and ext in [".png", ".jpg", ".jpeg", ".bmp"]:
                        copied_cover = os.path.join(custom_folder, f"cover{ext}")
                        shutil.copyfile(user_cover, copied_cover)
                        cover_path = copied_cover

                # Parse .desktop (adapt from _process_desktop_file_async)
                entry = parse_desktop_entry(desktop_path)
                if not entry:
                    return
                description = entry.get("Comment", "")
                exec_line = entry.get("Exec", exe_path)

                # Builtin custom folder (adapt path)
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                builtin_custom_folder = os.path.join(repo_root, "portprotonqt", "custom_data")
                builtin_game_folder = os.path.join(builtin_custom_folder, exe_name)
                builtin_cover = ""
                if os.path.exists(builtin_game_folder):
                    builtin_files = set(os.listdir(builtin_game_folder))
                    for ext in [".jpg", ".png", ".jpeg", ".bmp"]:
                        candidate = f"cover{ext}"
                        if candidate in builtin_files:
                            builtin_cover = os.path.join(builtin_game_folder, candidate)
                            break

                # User cover fallback
                user_cover_path = cover_path  # Already set if user provided

                # Statistics (playtime, last launch - defaults for new)
                playtime_seconds = 0
                formatted_playtime = format_playtime(playtime_seconds)
                last_played_timestamp = 0
                last_launch = _("Never")

                # Language for translations
                language_code = get_egs_language()

                # Read translations from metadata.txt
                user_metadata_file = os.path.join(custom_folder, "metadata.txt")
                builtin_metadata_file = os.path.join(builtin_game_folder, "metadata.txt")

                translations = {'name': name, 'description': description}
                if os.path.exists(user_metadata_file):
                    translations = read_metadata_translations(user_metadata_file, language_code)
                elif os.path.exists(builtin_metadata_file):
                    translations = read_metadata_translations(builtin_metadata_file, language_code)

                final_name = translations['name']
                final_desc = translations['description']

                def on_steam_info(steam_info: dict):
                    nonlocal final_name, final_desc
                    # Adapt final_cover logic from _process_desktop_file_async
                    final_cover = (user_cover_path if user_cover_path else
                                builtin_cover if builtin_cover else
                                steam_info.get("cover", "") or entry.get("Icon", ""))

                    # Use Steam description as fallback if no translation
                    steam_desc = steam_info.get("description", "")
                    if steam_desc and steam_desc != final_desc:
                        final_desc = steam_desc

                    # Use Steam name as fallback if better
                    steam_name = steam_info.get("name", "")
                    if steam_name and steam_name != final_name:
                        final_name = steam_name

                    # Build full game_data tuple with all Steam data
                    game_data = (
                        final_name,
                        final_desc,
                        final_cover,
                        steam_info.get("appid", ""),
                        steam_info.get("controller_support", ""),
                        exec_line,
                        last_launch,
                        formatted_playtime,
                        steam_info.get("protondb_tier", ""),
                        steam_info.get("anticheat_status", ""),
                        last_played_timestamp,
                        playtime_seconds,
                        "portproton"
                    )

                    # Incremental add
                    self.game_library_manager.add_game_incremental(game_data)

                    # Status message
                    msg = _("Added '{name}'").format(name=final_name)
                    self.statusBar().showMessage(msg, 3000)

                    # Trigger visible images load
                    QTimer.singleShot(200, self.game_library_manager.load_visible_images)

                from portprotonqt.steam_api import get_steam_game_info_async
                get_steam_game_info_async(final_name, exec_line, on_steam_info)

    def createAutoInstallTab(self):
        autoInstallPage = QWidget()
        autoInstallPage.setStyleSheet(self.theme.LIBRARY_WIDGET_STYLE)
        autoInstallLayout = QVBoxLayout(autoInstallPage)
        autoInstallLayout.setSpacing(15)

        # Top panel with title and search
        headerWidget = QWidget()
        headerLayout = QHBoxLayout(headerWidget)
        headerLayout.setContentsMargins(0, 10, 0, 10)
        headerLayout.setSpacing(10)

        # Title
        titleLabel = QLabel(_("Auto Install"))
        titleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        titleLabel.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        headerLayout.addWidget(titleLabel)

        headerLayout.addStretch()

        # Search line
        self.autoInstallSearchLineEdit = CustomLineEdit(self, theme=self.theme)
        icon: QIcon = cast(QIcon, self.theme_manager.get_icon("search"))
        action_pos = QLineEdit.ActionPosition.LeadingPosition
        self.autoInstallSearchLineEdit.addAction(icon, action_pos)
        self.autoInstallSearchLineEdit.setMaximumWidth(200)
        self.autoInstallSearchLineEdit.setPlaceholderText(_("Find Games ..."))
        self.autoInstallSearchLineEdit.setClearButtonEnabled(True)
        self.autoInstallSearchLineEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)
        self.autoInstallSearchLineEdit.textChanged.connect(self.filterAutoInstallGames)
        headerLayout.addWidget(self.autoInstallSearchLineEdit)

        autoInstallLayout.addWidget(headerWidget)

        # Scroll
        self.autoInstallScrollArea = QScrollArea()
        self.autoInstallScrollArea.setWidgetResizable(True)
        self.autoInstallScrollArea.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        QScroller.grabGesture(self.autoInstallScrollArea.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        self.autoInstallContainer = QWidget()
        self.autoInstallContainerLayout = FlowLayout(self.autoInstallContainer)
        self.autoInstallContainer.setLayout(self.autoInstallContainerLayout)
        self.autoInstallScrollArea.setWidget(self.autoInstallContainer)

        autoInstallLayout.addWidget(self.autoInstallScrollArea)

        # Slider for card size
        sliderLayout = QHBoxLayout()
        sliderLayout.setSpacing(0)
        sliderLayout.setContentsMargins(0, 0, 0, 0)
        sliderLayout.addStretch()

        self.auto_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.auto_size_slider.setMinimum(200)
        self.auto_size_slider.setMaximum(250)
        self.auto_size_slider.setValue(self.auto_card_width)
        self.auto_size_slider.setTickInterval(10)
        self.auto_size_slider.setFixedWidth(150)
        self.auto_size_slider.setToolTip(f"{self.auto_card_width} px")
        self.auto_size_slider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        self.auto_size_slider.sliderReleased.connect(self.on_auto_slider_released)
        sliderLayout.addWidget(self.auto_size_slider)

        autoInstallLayout.addLayout(sliderLayout)

        # Store cards
        self.autoInstallGameCards = {}
        self.allAutoInstallCards = []
        self.autoInstallLoaded = False
        self.autoInstallLoading = False

        # Load games
        def on_autoinstall_games_loaded(games: list[tuple]):
            self.autoInstallLoaded = True
            self.autoInstallLoading = False

            # Clear
            while self.autoInstallContainerLayout.count():
                child = self.autoInstallContainerLayout.takeAt(0)
                if child:
                    widget = child.widget()
                    if widget:
                        widget.deleteLater()

            self.autoInstallGameCards.clear()
            self.allAutoInstallCards.clear()

            if not games:
                return

            # Callback for opening autoinstall detail page
            def select_callback(game_data: dict):
                exec_line = game_data.get("exec_line", "")
                if not exec_line or not exec_line.startswith("autoinstall:"):
                    logger.warning(f"Invalid exec_line for autoinstall: {exec_line}")
                    return
                game_data["game_source"] = "portproton"
                self.detail_page_manager.openAutoInstallDetailPage(game_data)

            # Create cards
            for game_tuple in games:
                name = game_tuple[0]
                description = game_tuple[1]
                cover_path = game_tuple[2]
                appid = game_tuple[3]
                controller_support = game_tuple[4]
                exec_line = game_tuple[5]
                game_source = game_tuple[12]
                exe_name = game_tuple[13]

                card = GameCard(
                    name, description, cover_path, appid, controller_support,
                    exec_line, None, None, None,
                    None, None, None, game_source,
                    select_callback=select_callback,
                    theme=self.theme,
                    card_width=self.auto_card_width,
                    parent=self.autoInstallContainer,
                )

                # Hide badges and favorite button
                if hasattr(card, 'steamLabel'):
                    card.steamLabel.setVisible(False)
                if hasattr(card, 'egsLabel'):
                    card.egsLabel.setVisible(False)
                if hasattr(card, 'portprotonLabel'):
                    card.portprotonLabel.setVisible(False)
                if hasattr(card, 'protondbLabel'):
                    card.protondbLabel.setVisible(False)
                if hasattr(card, 'anticheatLabel'):
                    card.anticheatLabel.setVisible(False)
                if hasattr(card, 'favoriteLabel'):
                    card.favoriteLabel.setVisible(False)

                self.autoInstallGameCards[exe_name] = card
                self.allAutoInstallCards.append(card)
                self.autoInstallContainerLayout.addWidget(card)

            # Load missing covers and metadata in batch
            exe_names_to_load = [game_tuple[13] for game_tuple in games]

            def batch_cover_callback(exe_name, local_path):
                if local_path and exe_name in self.autoInstallGameCards:
                    card = self.autoInstallGameCards[exe_name]
                    card.cover_path = local_path
                    load_pixmap_async(local_path, self.auto_card_width, int(self.auto_card_width * 1.5), card.on_cover_loaded)

            def batch_metadata_callback(exe_name, local_path):
                logger.debug(f"Metadata callback called for {exe_name}: {local_path}")
                if local_path and os.path.exists(local_path):
                    try:
                        self._update_card_name_from_metadata(exe_name, local_path)
                        logger.info(f"Updated metadata for {exe_name}")
                    except Exception as e:
                        logger.error(f"Error updating card metadata for {exe_name}: {e}")

            if exe_names_to_load:
                self.portproton_api.download_autoinstall_assets_batch_async(
                    exe_names_to_load,
                    timeout=5,
                    cover_callback=batch_cover_callback,
                    metadata_callback=batch_metadata_callback
                )

            self.autoInstallContainer.updateGeometry()
            self.autoInstallScrollArea.updateGeometry()
            self.filterAutoInstallGames()

        self._on_autoinstall_games_loaded = on_autoinstall_games_loaded

        self.stackedWidget.addWidget(autoInstallPage)

    def _start_autoinstall_load(self) -> None:
        if self.autoInstallLoaded or self.autoInstallLoading:
            return
        if not hasattr(self, "_on_autoinstall_games_loaded"):
            return
        self.autoInstallLoading = True
        self.autoInstallLoadThread = self.portproton_api.start_autoinstall_games_load(
            self._on_autoinstall_games_loaded
        )
        if self.autoInstallLoadThread:
            def on_thread_finished():
                self.autoInstallLoadThread = None  # Release reference
            self.autoInstallLoadThread.finished.connect(on_thread_finished)

    def on_auto_slider_released(self):
        """Handles auto-install slider release to update card size."""
        if hasattr(self, 'auto_size_slider') and self.auto_size_slider:
            self.auto_card_width = self.auto_size_slider.value()
            self.auto_size_slider.setToolTip(f"{self.auto_card_width} px")
            save_auto_card_size(self.auto_card_width)
            for card in self.allAutoInstallCards:
                card.update_card_size(self.auto_card_width)
            self.autoInstallContainerLayout.invalidate()
            self.autoInstallContainer.updateGeometry()
            self.autoInstallScrollArea.updateGeometry()

    def filterAutoInstallGames(self):
        """Filter auto install game cards based on search text."""
        search_text = self.autoInstallSearchLineEdit.text().lower().strip()

        for card in self.allAutoInstallCards:
            if search_text in card.name.lower():
                card.setVisible(True)
            else:
                card.setVisible(False)

        # Re-layout the container
        self.autoInstallContainerLayout.invalidate()
        self.autoInstallContainer.updateGeometry()
        self.autoInstallScrollArea.updateGeometry()

    def createWineTab(self):
        """Wine Settings tab."""
        self.wineWidget = QWidget()
        self.wineWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        layout = QVBoxLayout(self.wineWidget)
        layout.setContentsMargins(10, 18, 10, 10)

        self.wineTitle = QLabel(_("Wine Settings"))
        self.wineTitle.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.wineTitle.setObjectName("tabTitle")
        layout.addWidget(self.wineTitle)

        if self.portproton_location is None:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        prefixes_path = os.path.join(self.portproton_location, "data", "prefixes")

        if not os.path.exists(dist_path):
            return

        formLayout = QFormLayout()
        formLayout.setContentsMargins(0, 10, 0, 0)
        formLayout.setSpacing(10)
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.wine_versions = sorted([d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))], key=version_sort_key)
        self.wineCombo = QComboBox()
        self.wineCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.wineCombo.addItems(self.wine_versions)
        self.wineCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.wineCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.wineTitleLabel = QLabel(_("WINE/Proton:"))
        self.wineTitleLabel.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.wineTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if self.wine_versions:
            self.wineCombo.setCurrentIndex(0)
        formLayout.addRow(self.wineTitleLabel, self.wineCombo)

        self.prefixes = sorted([d for d in os.listdir(prefixes_path) if os.path.isdir(os.path.join(prefixes_path, d))], key=version_sort_key) if os.path.exists(prefixes_path) else []
        self.prefixCombo = QComboBox()
        self.prefixCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.prefixCombo.addItems(self.prefixes)
        self.prefixCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.prefixCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.prefixTitleLabel = QLabel(_("Prefix:"))
        self.prefixTitleLabel.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.prefixTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if self.prefixes:
            self.prefixCombo.setCurrentIndex(0)
        formLayout.addRow(self.prefixTitleLabel, self.prefixCombo)

        layout.addLayout(formLayout)

        # --- Wine Tools ---
        tools_grid = QGridLayout()
        tools_grid.setSpacing(6)

        tools = [
            ("--winecfg", _("Wine Configuration")),
            ("--winereg", _("Registry Editor")),
            ("--winefile", _("File Explorer")),
            ("--winecmd", _("Command Prompt")),
            ("--wine_uninstaller", _("Uninstaller")),
        ]

        for i, (tool_cmd, tool_name) in enumerate(tools):
            row = i // 3
            col = i % 3
            btn = AutoSizeButton(tool_name, update_size=False)
            btn.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.clicked.connect(lambda checked, t=tool_cmd: self.launch_generic_tool(t))
            tools_grid.addWidget(btn, row, col)

        for col in range(3):
            tools_grid.setColumnStretch(col, 1)

        layout.addLayout(tools_grid)

        # --- Additional Tools ---
        additional_grid = QGridLayout()
        additional_grid.setSpacing(6)

        additional_buttons = [
            ("Winetricks", self.open_winetricks),
            (_("Create Prefix Backup"), self.create_prefix_backup),
            (_("Load Prefix Backup"), self.load_prefix_backup),
            (_("Delete Prefix"), self.delete_prefix),
            (_("Clear Prefix"), self.clear_prefix),
            (_("Manage WINE versions"), self.show_proton_manager),
        ]

        for i, (text, callback) in enumerate(additional_buttons):
            row = i // 3
            col = i % 3
            btn = AutoSizeButton(text, update_size=False)
            btn.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if callback:
                btn.clicked.connect(callback)
            additional_grid.addWidget(btn, row, col)

        for col in range(3):
            additional_grid.setColumnStretch(col, 1)

        layout.addLayout(additional_grid)
        tools_grid.setContentsMargins(10, 4, 10, 0)
        additional_grid.setContentsMargins(10, 6, 10, 0)
        layout.addStretch(1)

        self.wine_progress_bar = QProgressBar(self.wineWidget)
        self.wine_progress_bar.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        self.wine_progress_bar.setMaximumWidth(200)
        self.wine_progress_bar.setTextVisible(True)
        self.wine_progress_bar.setVisible(False)
        self.wine_progress_bar.setRange(0, 0)

        wine_progress_layout = QHBoxLayout()
        wine_progress_layout.addStretch(1)
        wine_progress_layout.addWidget(self.wine_progress_bar)
        layout.addLayout(wine_progress_layout)

        self.stackedWidget.addWidget(self.wineWidget)

    def launch_generic_tool(self, cli_arg):
        wine = self.wineCombo.currentText()
        prefix = self.prefixCombo.currentText()
        if not wine or not prefix:
            return
        if not self.portproton_location or not self.start_sh:
            return
        start_sh = self.start_sh
        cmd = start_sh + ["cli", cli_arg, wine, prefix]

        # Show progress bar before launch
        self.wine_progress_bar.setVisible(True)
        self.update_status_message.emit(_("Launching tool..."), 0)

        proc = QProcess(self)
        proc.finished.connect(lambda exitCode: self._on_wine_tool_finished(exitCode, cli_arg))
        proc.errorOccurred.connect(lambda error: self._on_wine_tool_error(error, cli_arg))
        proc.start(cmd[0], cmd[1:])

        if not proc.waitForStarted(5000):
            self.wine_progress_bar.setVisible(False)
            self.update_status_message.emit("", 0)
            QMessageBox.warning(self, _("Error"), _("Failed to start process."))
            return

        self._start_wine_process_monitor(cli_arg)

    def _start_wine_process_monitor(self, cli_arg):
        """Start timer for Wine utility launch monitoring."""
        self.wine_monitor_timer = QTimer(self)
        self.wine_monitor_timer.setInterval(500)
        self.wine_monitor_timer.timeout.connect(lambda: self._check_wine_process(cli_arg))
        self.wine_monitor_timer.start()

    def _check_wine_process(self, cli_arg):
        """Check if target .exe process started."""
        exe_map = {
            "--winecfg": "winecfg.exe",
            "--winereg": "regedit.exe",
            "--winefile": "winefile.exe",
            "--winecmd": "cmd.exe",
            "--wine_uninstaller": "uninstaller.exe",
        }
        target_exe = exe_map.get(cli_arg, "")
        if not target_exe:
            return

        # Check processes via psutil
        for proc in psutil.process_iter(attrs=["name"]):
            if proc.info["name"].lower() == target_exe.lower():
                # Process started - hide progress bar and stop monitoring
                self.wine_progress_bar.setVisible(False)
                self.update_status_message.emit("", 0)
                if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
                    self.wine_monitor_timer.stop()
                    self.wine_monitor_timer.deleteLater()
                    self.wine_monitor_timer = None
                logger.info(f"Wine tool {target_exe} started successfully")
                return

    def _on_wine_tool_finished(self, exitCode, cli_arg):
        """Handle Wine utility completion."""
        self.wine_progress_bar.setVisible(False)
        self.update_status_message.emit("", 0)
        # Stop monitoring if active
        if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
            self.wine_monitor_timer.stop()
            self.wine_monitor_timer.deleteLater()
            self.wine_monitor_timer = None
        if exitCode == 0:
            logger.info(f"Wine tool {cli_arg} finished successfully")
        else:
            logger.warning(f"Wine tool {cli_arg} finished with exit code {exitCode}")

    def _on_wine_tool_error(self, error, cli_arg):
        """Handle Wine utility launch error."""
        self.wine_progress_bar.setVisible(False)
        self.update_status_message.emit("", 0)
        # Stop monitoring if active
        if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
            self.wine_monitor_timer.stop()
            self.wine_monitor_timer.deleteLater()
            self.wine_monitor_timer = None
        logger.error(f"Wine tool {cli_arg} error: {error}")
        QMessageBox.warning(self, _("Error"), f"Failed to launch tool: {error}")

    def show_proton_manager(self):
        """Shows the Proton/WINE manager for downloading other WINE versions"""
        show_proton_manager(self, self.portproton_location, input_manager=self.input_manager)

    def clear_prefix(self):
        """Clear prefix"""
        selected_prefix = self.prefixCombo.currentText()
        selected_wine = self.wineCombo.currentText()

        if not selected_prefix or not selected_wine:
            return
        if not self.portproton_location or not self.start_sh:
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Confirm Clear"))
        msg_box.setText(_("Are you sure you want to clear prefix '{}'?").format(selected_prefix))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return

        start_sh = self.start_sh

        self.wine_progress_bar.setVisible(True)
        self.update_status_message.emit(_("Clearing prefix..."), 0)

        self.clear_process = QProcess(self)
        self.clear_process.finished.connect(lambda exitCode: self._on_clear_prefix_finished(exitCode))
        self.clear_process.errorOccurred.connect(lambda error: self._on_clear_prefix_error(error))
        cmd = start_sh + ["cli", "--clear_pfx", selected_wine, selected_prefix]
        self.clear_process.start(cmd[0], cmd[1:])

        if not self.clear_process.waitForStarted(5000):
            self.wine_progress_bar.setVisible(False)
            self.update_status_message.emit("", 0)
            QMessageBox.warning(self, _("Error"), _("Failed to start prefix clear process."))
            return

    def _on_clear_prefix_finished(self, exitCode):
        self.wine_progress_bar.setVisible(False)
        self.update_status_message.emit("", 0)
        if exitCode == 0:
            QMessageBox.information(self, _("Success"), _("Prefix cleared successfully."))
        else:
            QMessageBox.warning(self, _("Error"), _("Prefix clear failed with exit code {}.").format(exitCode))

    def _on_clear_prefix_error(self, error):
        self.wine_progress_bar.setVisible(False)
        self.update_status_message.emit("", 0)
        QMessageBox.warning(self, _("Error"), _("Failed to run clear prefix command: {}").format(error))

    def create_prefix_backup(self):
        selected_prefix = self.prefixCombo.currentText()
        if not selected_prefix:
            return
        file_explorer = FileExplorer(self, directory_only=True)
        file_explorer.file_signal.file_selected.connect(lambda path: self._perform_backup(path, selected_prefix))
        file_explorer.exec()

    def _perform_backup(self, backup_dir, prefix_name):
        os.makedirs(backup_dir, exist_ok=True)
        if not self.portproton_location or not self.start_sh:
            return
        start_sh = self.start_sh
        self.backup_process = QProcess(self)
        self.backup_process.finished.connect(lambda exitCode: self._on_backup_finished(exitCode))
        cmd = start_sh + ["--backup-prefix", prefix_name, backup_dir]
        self.backup_process.start(cmd[0], cmd[1:])
        if not self.backup_process.waitForStarted():
            QMessageBox.warning(self, _("Error"), _("Failed to start backup process."))

    def load_prefix_backup(self):
        file_explorer = FileExplorer(self, file_filter='.ppack')
        file_explorer.file_signal.file_selected.connect(self._perform_restore)
        file_explorer.exec()

    def _perform_restore(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return
        if not self.portproton_location or not self.start_sh:
            return
        start_sh = self.start_sh
        self.restore_process = QProcess(self)
        self.restore_process.finished.connect(lambda exitCode: self._on_restore_finished(exitCode))
        cmd = start_sh + ["--restore-prefix", file_path]
        self.restore_process.start(cmd[0], cmd[1:])
        if not self.restore_process.waitForStarted():
            QMessageBox.warning(self, _("Error"), _("Failed to start restore process."))

    def _on_backup_finished(self, exitCode):
        if exitCode == 0:
            QMessageBox.information(self, _("Success"), _("Prefix backup completed."))
        else:
            QMessageBox.warning(self, _("Error"), _("Prefix backup failed."))

    def _on_restore_finished(self, exitCode):
        if exitCode == 0:
            QMessageBox.information(self, _("Success"), _("Prefix restore completed."))
        else:
            QMessageBox.warning(self, _("Error"), _("Prefix restore failed."))

    def delete_prefix(self):
        selected_prefix = self.prefixCombo.currentText()
        if not self.portproton_location:
            return

        if not selected_prefix:
            return

        prefix_path = os.path.join(self.portproton_location, "data", "prefixes", selected_prefix)
        if not os.path.exists(prefix_path):
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Confirm Deletion"))
        msg_box.setText(_("Are you sure you want to delete prefix '{}'?").format(selected_prefix))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(prefix_path)
                QMessageBox.information(self, _("Success"), _("Prefix '{}' deleted.").format(selected_prefix))
            except Exception as e:
                QMessageBox.warning(self, _("Error"), _("Failed to delete prefix: {}").format(str(e)))

    def refresh_wine_combo(self):
        """Refresh the wine combo box after deletion."""
        if not self.portproton_location:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        if not os.path.exists(dist_path):
            return

        # Update the wine versions list with sorting
        self.wine_versions = sorted([d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))], key=version_sort_key)
        self.wineCombo.clear()
        self.wineCombo.addItems(self.wine_versions)

    def refresh_prefix_combo(self):
        """Refresh the prefix combo box when prefixes directory changes."""
        if not self.portproton_location:
            return

        prefixes_path = os.path.join(self.portproton_location, "data", "prefixes")
        if not os.path.exists(prefixes_path):
            return

        # Update the prefixes list with sorting
        self.prefixes = sorted([d for d in os.listdir(prefixes_path) if os.path.isdir(os.path.join(prefixes_path, d))], key=version_sort_key)
        self.prefixCombo.clear()
        self.prefixCombo.addItems(self.prefixes)

    def open_winetricks(self):
        """Open the Winetricks dialog for the selected prefix and wine."""
        selected_prefix = self.prefixCombo.currentText()
        if not selected_prefix:
            return

        selected_wine = self.wineCombo.currentText()
        if not selected_wine:
            return

        assert self.portproton_location is not None
        prefix_path = os.path.join(self.portproton_location, "data", "prefixes", selected_prefix)
        wine_path = os.path.join(self.portproton_location, "data", "dist", selected_wine, "bin", "wine")

        # Open Winetricks dialog
        dialog = WinetricksDialog(self, self.theme, prefix_path, wine_path)
        dialog.exec()

    def createPortProtonTab(self):
        """PortProton Settings tab."""
        self.portProtonWidget = QWidget()
        self.portProtonWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.portProtonWidget.setObjectName("otherPage")
        layout = QVBoxLayout(self.portProtonWidget)
        layout.setContentsMargins(10, 18, 10, 10)

        # Title
        title = QLabel(_("PortProton Settings"))
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        title.setObjectName("tabTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(title)

        # --- New: Scroll Area for settings ---
        self.settingsScrollArea = QScrollArea()
        self.settingsScrollArea.setWidgetResizable(True)
        self.settingsScrollArea.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settingsScrollArea.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        self.settingsScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        # Disable horizontal scroll
        self.settingsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        QScroller.grabGesture(self.settingsScrollArea.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        scrollWidget = QWidget()
        scrollWidget.setStyleSheet("background: transparent;")
        scrollLayout = QVBoxLayout(scrollWidget)
        scrollLayout.setContentsMargins(0, 0, 0, 0)
        scrollLayout.setSpacing(10)  # Uniform spacing between sections

        # Helper to create styled sections
        def create_section(title_text):
            section_frame = QFrame()
            section_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            section_frame.setStyleSheet(self.theme.SETTINGS_FRAME_STYLE)
            section_layout = QVBoxLayout(section_frame)
            section_layout.setContentsMargins(15, 15, 15, 15)
            section_layout.setSpacing(10)

            section_title = QLabel(title_text)
            section_title.setStyleSheet(self.theme.SETTINGS_FRAME_TITLE_STYLE)
            section_layout.addWidget(section_title)

            section_form = QFormLayout()
            section_form.setSpacing(10)
            section_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            section_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            section_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            section_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            section_form.setHorizontalSpacing(15)
            section_form.setVerticalSpacing(10)
            section_layout.addLayout(section_form)
            return section_frame, section_form

        # 1. Library Settings Section
        genFrame, genForm = create_section(_("Library Settings"))
        genForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(genFrame)

        self.timeDetailCombo = QComboBox()
        self.timeDetailCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.time_keys = ["detailed", "brief"]
        self.time_labels = [_("Detailed"), _("Brief")]
        self.timeDetailCombo.addItems(self.time_labels)
        self.timeDetailCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.timeDetailCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.timeDetailTitle = QLabel(_("Time Detail Level:"))
        self.timeDetailTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.timeDetailTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.timeDetailTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = read_time_config()
        try:
            idx = self.time_keys.index(current)
        except ValueError:
            idx = 0
        self.timeDetailCombo.setCurrentIndex(idx)
        genForm.addRow(self.timeDetailTitle, self.timeDetailCombo)

        self.gamesSortCombo = QComboBox()
        self.gamesSortCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sort_keys = ["last_launch", "playtime", "alphabetical"]
        self.sort_labels = [_("Last launch"), _("Playtime"), _("Alphabetical")]
        self.gamesSortCombo.addItems(self.sort_labels)
        self.gamesSortCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamesSortCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamesSortTitle = QLabel(_("Games Sort Method:"))
        self.gamesSortTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.gamesSortTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.gamesSortTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = read_sort_method()
        try:
            idx = self.sort_keys.index(current)
        except ValueError:
            idx = 0
        self.gamesSortCombo.setCurrentIndex(idx)
        genForm.addRow(self.gamesSortTitle, self.gamesSortCombo)

        self.filter_keys = ["all", "steam", "portproton", "favorites", "epic"]
        self.filter_labels = [_("All"), "Steam", "PortProton", _("Favorites"), "Epic Games Store"]
        self.gamesDisplayCombo = QComboBox()
        self.gamesDisplayCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.gamesDisplayCombo.addItems(self.filter_labels)
        self.gamesDisplayCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamesDisplayCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamesDisplayTitle = QLabel(_("Games Display Filter:"))
        self.gamesDisplayTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.gamesDisplayTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.gamesDisplayTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = read_display_filter()
        try:
            idx = self.filter_keys.index(current)
        except ValueError:
            idx = 0
        self.gamesDisplayCombo.setCurrentIndex(idx)
        genForm.addRow(self.gamesDisplayTitle, self.gamesDisplayCombo)

        # 2. Interface Settings Section
        uiFrame, uiForm = create_section(_("Interface Settings"))
        uiForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(uiFrame)

        self.fullscreenCheckBox = QCheckBox()  # Removed text
        self.fullscreenCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.fullscreenCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fullscreenTitle = QLabel(_("Launch Application in Fullscreen"))
        self.fullscreenTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.fullscreenTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.fullscreenTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_fullscreen = read_fullscreen_config()
        self.fullscreenCheckBox.setChecked(current_fullscreen)
        fullscreen_layout = QHBoxLayout()
        fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        fullscreen_layout.addWidget(self.fullscreenCheckBox)
        fullscreen_layout.addWidget(self.fullscreenTitle)
        fullscreen_layout.addStretch()
        uiForm.addRow(fullscreen_layout)

        self.minimizeToTrayCheckBox = QCheckBox()  # Removed text
        self.minimizeToTrayCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.minimizeToTrayCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.minimizeToTrayTitle = QLabel(_("Minimize to tray on close"))
        self.minimizeToTrayTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.minimizeToTrayTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.minimizeToTrayTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_minimize_to_tray = read_minimize_to_tray()
        self.minimizeToTrayCheckBox.setChecked(current_minimize_to_tray)
        self.minimizeToTrayCheckBox.toggled.connect(lambda checked: save_minimize_to_tray(checked))
        minimize_layout = QHBoxLayout()
        minimize_layout.setContentsMargins(0, 0, 0, 0)
        minimize_layout.addWidget(self.minimizeToTrayCheckBox)
        minimize_layout.addWidget(self.minimizeToTrayTitle)
        minimize_layout.addStretch()
        uiForm.addRow(minimize_layout)

        self.hideAutoInstallTabCheckBox = QCheckBox()  # Removed text
        self.hideAutoInstallTabCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.hideAutoInstallTabCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hideAutoInstallTabTitle = QLabel(_("Hide Auto-Install Tab"))
        self.hideAutoInstallTabTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.hideAutoInstallTabTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.hideAutoInstallTabTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_hide_autoinstall = read_hide_autoinstall_tab()
        self.hideAutoInstallTabCheckBox.setChecked(current_hide_autoinstall)
        self.hideAutoInstallTabCheckBox.toggled.connect(lambda checked: save_hide_autoinstall_tab(checked))
        hide_autoinstall_layout = QHBoxLayout()
        hide_autoinstall_layout.setContentsMargins(0, 0, 0, 0)
        hide_autoinstall_layout.addWidget(self.hideAutoInstallTabCheckBox)
        hide_autoinstall_layout.addWidget(self.hideAutoInstallTabTitle)
        hide_autoinstall_layout.addStretch()
        uiForm.addRow(hide_autoinstall_layout)

        # 3. Gamepad Settings Section
        padFrame, padForm = create_section(_("Gamepad Settings"))
        padForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(padFrame)

        self.gamepadTypeCombo = QComboBox()
        self.gamepadTypeCombo.addItems(["Xbox", "PlayStation"])
        self.gamepadTypeCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamepadTypeCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamepadTypeTitle = QLabel(_("Gamepad Type:"))
        self.gamepadTypeTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.gamepadTypeTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.gamepadTypeTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_type_str = read_gamepad_type()
        if current_type_str == "playstation":
            self.gamepadTypeCombo.setCurrentText("PlayStation")
        else:
            self.gamepadTypeCombo.setCurrentText("Xbox")
        padForm.addRow(self.gamepadTypeTitle, self.gamepadTypeCombo)

        self.autoFullscreenGamepadCheckBox = QCheckBox()  # Removed text
        self.autoFullscreenGamepadCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.autoFullscreenGamepadCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.autoFullscreenGamepadTitle = QLabel(_("Auto Fullscreen on Gamepad connected"))
        self.autoFullscreenGamepadTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.autoFullscreenGamepadTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.autoFullscreenGamepadTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_auto_fullscreen = read_auto_fullscreen_gamepad()
        self.autoFullscreenGamepadCheckBox.setChecked(current_auto_fullscreen)
        auto_fullscreen_layout = QHBoxLayout()
        auto_fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        auto_fullscreen_layout.addWidget(self.autoFullscreenGamepadCheckBox)
        auto_fullscreen_layout.addWidget(self.autoFullscreenGamepadTitle)
        auto_fullscreen_layout.addStretch()
        padForm.addRow(auto_fullscreen_layout)

        self.gamepadRumbleCheckBox = QCheckBox()  # Removed text
        self.gamepadRumbleCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamepadRumbleCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.gamepadRumbleTitle = QLabel(_("Gamepad haptic feedback"))
        self.gamepadRumbleTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.gamepadRumbleTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.gamepadRumbleTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_rumble_state = read_rumble_config()
        self.gamepadRumbleCheckBox.setChecked(current_rumble_state)
        rumble_layout = QHBoxLayout()
        rumble_layout.setContentsMargins(0, 0, 0, 0)
        rumble_layout.addWidget(self.gamepadRumbleCheckBox)
        rumble_layout.addWidget(self.gamepadRumbleTitle)
        rumble_layout.addStretch()
        padForm.addRow(rumble_layout)

        # 4. Hardware Settings Section
        hwFrame, hwForm = create_section(_("Hardware Settings"))
        hwForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(hwFrame)

        gpu_list = get_gpu_list()
        filtered_gpu_list = [gpu for gpu in gpu_list if 'llvmpipe' not in gpu.lower()]
        if filtered_gpu_list:
            self.gpuCombo = QComboBox()
            self.gpuCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.gpuCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.gpuCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
            self.gpuCombo.addItems(filtered_gpu_list)
            current_gpu = get_user_conf_setting('PW_GPU_USE')
            if current_gpu and current_gpu in filtered_gpu_list:
                self.gpuCombo.setCurrentText(current_gpu)
            elif current_gpu:
                if current_gpu not in filtered_gpu_list:
                    self.gpuCombo.addItem(current_gpu)
                self.gpuCombo.setCurrentText(current_gpu)
            else:
                self.gpuCombo.setCurrentIndex(0)
            self.gpuTitle = QLabel(_("GPU to use:"))
            self.gpuTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.gpuTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
            self.gpuTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            hwForm.addRow(self.gpuTitle, self.gpuCombo)
        else:
            hwForm.addRow(QLabel(_("No GPUs found")), QLabel(""))

        # 5. Proxy Settings Section
        proxyFrame, proxyForm = create_section(_("Proxy Settings"))
        proxyForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(proxyFrame)

        self.proxyUrlEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyUrlEdit.setPlaceholderText(_("Proxy URL"))
        self.proxyUrlEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.proxyUrlEdit.setStyleSheet(self.theme.SETTINGS_LINE_EDIT_STYLE)
        self.proxyUrlEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyUrlTitle = QLabel(_("Proxy URL:"))
        self.proxyUrlTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.proxyUrlTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.proxyUrlTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        proxy_cfg = read_proxy_config()
        if proxy_cfg.get("http", ""):
            self.proxyUrlEdit.setText(proxy_cfg["http"])
        proxyForm.addRow(self.proxyUrlTitle, self.proxyUrlEdit)

        self.proxyUserEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyUserEdit.setPlaceholderText(_("Proxy Username"))
        self.proxyUserEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.proxyUserEdit.setStyleSheet(self.theme.SETTINGS_LINE_EDIT_STYLE)
        self.proxyUserEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyUserTitle = QLabel(_("Proxy Username:"))
        self.proxyUserTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.proxyUserTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.proxyUserTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        proxyForm.addRow(self.proxyUserTitle, self.proxyUserEdit)

        self.proxyPasswordEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyPasswordEdit.setPlaceholderText(_("Proxy Password"))
        self.proxyPasswordEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.proxyPasswordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxyPasswordEdit.setStyleSheet(self.theme.SETTINGS_LINE_EDIT_STYLE)
        self.proxyPasswordEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyPasswordTitle = QLabel(_("Proxy Password:"))
        self.proxyPasswordTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.proxyPasswordTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.proxyPasswordTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        proxyForm.addRow(self.proxyPasswordTitle, self.proxyPasswordEdit)

        scrollLayout.addStretch(1)
        self.settingsScrollArea.setWidget(scrollWidget)
        layout.addWidget(self.settingsScrollArea)

        # Buttons (outside scroll area, always visible)
        buttonsLayout = QHBoxLayout()
        buttonsLayout.setSpacing(10)

        self.saveButton = AutoSizeButton(_("Save Settings"), icon=self.theme_manager.get_icon("save"))
        self.saveButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.saveButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.saveButton.clicked.connect(self.savePortProtonSettings)
        buttonsLayout.addWidget(self.saveButton)

        self.resetSettingsButton = AutoSizeButton(_("Reset Settings"), icon=self.theme_manager.get_icon("update"))
        self.resetSettingsButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.resetSettingsButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.resetSettingsButton.clicked.connect(self.resetSettings)
        buttonsLayout.addWidget(self.resetSettingsButton)

        self.clearCacheButton = AutoSizeButton(_("Clear Cache"), icon=self.theme_manager.get_icon("update"))
        self.clearCacheButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.clearCacheButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clearCacheButton.clicked.connect(self.clearCache)
        buttonsLayout.addWidget(self.clearCacheButton)

        layout.addLayout(buttonsLayout)
        self.stackedWidget.addWidget(self.portProtonWidget)

    # def openLegendaryLogin(self):
    #     """Opens the Legendary login page in the default web browser."""
    #     login_url = "https://legendary.gl/epiclogin"
    #     try:
    #         QDesktopServices.openUrl(QUrl(login_url))
    #         self.statusBar().showMessage(_("Opened Legendary login page in browser"), 3000)
    #     except Exception as e:
    #         logger.error(f"Failed to open Legendary login page: {e}")
    #         self.statusBar().showMessage(_("Failed to open Legendary login page"), 3000)
    #
    # def submitLegendaryCode(self):
    #     """Submits the Legendary authorization code using the legendary CLI."""
    #     auth_code = self.legendaryCodeEdit.text().strip()
    #     if not auth_code:
    #         QMessageBox.warning(self, _("Error"), _("Please enter an authorization code"))
    #         return
    #
    #     try:
    #         # Execute legendary auth command
    #         result = subprocess.run(
    #             [self.legendary_path, "auth", "--code", auth_code],
    #             capture_output=True,
    #             text=True,
    #             check=True
    #         )
    #         logger.info("Legendary authentication successful: %s", result.stdout)
    #         self.statusBar().showMessage(_("Successfully authenticated with Legendary"), 3000)
    #         self.legendaryCodeEdit.clear()
    #         # Reload Epic Games Store games after successful authentication
    #         self.games = self.loadGames()
    #         self.updateGameGrid()
    #     except subprocess.CalledProcessError as e:
    #         logger.error("Legendary authentication failed: %s", e.stderr)
    #         self.statusBar().showMessage(_("Legendary authentication failed: {0}").format(e.stderr), 5000)
    #     except FileNotFoundError:
    #         logger.error("Legendary executable not found at %s", self.legendary_path)
    #         self.statusBar().showMessage(_("Legendary executable not found"), 5000)
    #     except Exception as e:
    #         logger.error("Unexpected error during Legendary authentication: %s", str(e))
    #         self.statusBar().showMessage(_("Unexpected error during authentication"), 5000)

    def resetSettings(self):
        """Reset settings and restart application."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Confirm Reset"))
        msg_box.setText(_("Are you sure you want to reset all settings? This action cannot be undone."))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            reset_config()

            # Show message
            self.statusBar().showMessage(_("Settings reset. Restarting..."), 3000)

            # Restart application
            QTimer.singleShot(1000, lambda: self.restart_application())

    def clearCache(self):
        """Clear cache."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Confirm Clear Cache"))
        msg_box.setText(_("Are you sure you want to clear the cache? This action cannot be undone."))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            clear_cache()

            # Show message
            self.statusBar().showMessage(_("Cache cleared"), 3000)

    def applySettingsDelayed(self):
        read_time_config()
        self.games = []
        self.loadGames()
        display_filter = read_display_filter()
        for card in self.game_library_manager.game_card_cache.values():
            card.update_badge_visibility(display_filter)

    def savePortProtonSettings(self):
        time_idx = self.timeDetailCombo.currentIndex()
        time_key = self.time_keys[time_idx]
        save_time_config(time_key)

        sort_idx = self.gamesSortCombo.currentIndex()
        sort_key = self.sort_keys[sort_idx]
        save_sort_method(sort_key)

        filter_idx = self.gamesDisplayCombo.currentIndex()
        filter_key = self.filter_keys[filter_idx]
        save_display_filter(filter_key)

        proxy_url = self.proxyUrlEdit.text().strip()
        proxy_user = self.proxyUserEdit.text().strip()
        proxy_password = self.proxyPasswordEdit.text().strip()
        save_proxy_config(proxy_url, proxy_user, proxy_password)

        fullscreen = self.fullscreenCheckBox.isChecked()
        save_fullscreen_config(fullscreen)

        auto_fullscreen_gamepad = self.autoFullscreenGamepadCheckBox.isChecked()
        save_auto_fullscreen_gamepad(auto_fullscreen_gamepad)

        rumble_enabled = self.gamepadRumbleCheckBox.isChecked()
        save_rumble_config(rumble_enabled)

        # Save GPU selection to user.conf (only if the combo box exists)
        if hasattr(self, 'gpuCombo'):
            selected_gpu = self.gpuCombo.currentText()
            set_user_conf_setting('PW_GPU_USE', selected_gpu)

        # Get hide auto-install tab setting
        hide_autoinstall = self.hideAutoInstallTabCheckBox.isChecked()

        gamepad_type_text = self.gamepadTypeCombo.currentText()
        gpad_type = "playstation" if gamepad_type_text == "PlayStation" else "xbox"
        save_gamepad_type(gpad_type)

        if hasattr(self, 'input_manager'):
            if gpad_type == "playstation":
                self.input_manager.gamepad_type = GamepadType.PLAYSTATION
            elif gpad_type == "xbox":
                self.input_manager.gamepad_type = GamepadType.XBOX
            else:
                self.input_manager.gamepad_type = GamepadType.UNKNOWN
            self.updateControlHints()
            # Update virtual keyboard icons
            if hasattr(self, 'keyboard'):
                self.keyboard.update_keyboard()

        for card in self.game_library_manager.game_card_cache.values():
            card.update_badge_visibility(filter_key)

        if self.currentDetailPage and self.current_exec_line:
            current_game = next((game for game in self.games if game[5] == self.current_exec_line), None)
            if current_game:
                self.stackedWidget.removeWidget(self.currentDetailPage)
                self.currentDetailPage.deleteLater()
                self.currentDetailPage = None
                game_data = {
                    "name": current_game[0],
                    "description": current_game[1],
                    "cover_path": current_game[2],
                    "appid": current_game[3],
                    "controller_support": current_game[4],
                    "exec_line": current_game[5],
                    "last_launch": current_game[6],
                    "formatted_playtime": current_game[7],
                    "protondb_tier": current_game[8],
                    "anticheat_status": current_game[9],
                    "game_source": current_game[12],
                }
                self.detail_page_manager.openGameDetailPage(game_data)

        self.settingsDebounceTimer.start()

        gamepad_connected = self.input_manager.find_gamepad() is not None
        if fullscreen or (auto_fullscreen_gamepad and gamepad_connected):
            self.showFullScreen()

        # Apply the hide auto-install tab setting
        if hide_autoinstall:  # Hide the tab
            # Find the auto-install tab button and hide it
            if hasattr(self, 'tabButtons') and self.auto_install_tab_index in self.tabButtons:
                tab_button = self.tabButtons[self.auto_install_tab_index]
                tab_button.setVisible(False)

                # If currently on the hidden tab, switch to the first tab
                if self.stackedWidget.currentIndex() == self.auto_install_tab_index:
                    self.switchTab(0)  # Switch to Library tab

            # Hide the stacked widget page too
            if hasattr(self, 'stackedWidget'):
                auto_install_page = self.stackedWidget.widget(self.auto_install_tab_index)
                if auto_install_page:
                    auto_install_page.setVisible(False)

            # Stop any ongoing auto-install loading if present
            if hasattr(self, 'autoInstallLoadThread') and self.autoInstallLoadThread:
                self.autoInstallLoadThread.requestInterruption()
                self.autoInstallLoadThread.wait(5000)  # Wait up to 5 seconds for thread to finish
                self.autoInstallLoadThread = None
        else:  # Show the tab
            # Make sure the tab button is visible
            if hasattr(self, 'tabButtons') and self.auto_install_tab_index in self.tabButtons:
                tab_button = self.tabButtons[self.auto_install_tab_index]
                tab_button.setVisible(True)

            # Make sure the stacked widget page is visible
            if hasattr(self, 'stackedWidget'):
                auto_install_page = self.stackedWidget.widget(self.auto_install_tab_index)
                if auto_install_page:
                    auto_install_page.setVisible(True)

        # Save the hide auto-install tab setting to config
        save_hide_autoinstall_tab(hide_autoinstall)

        self.statusBar().showMessage(_("Settings saved"), 3000)

    def createThemeTab(self):
        """Themes tab"""
        self.themeTabWidget = QWidget()
        self.themeTabWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        self.themeTabWidget.setObjectName("otherPage")
        mainLayout = QVBoxLayout(self.themeTabWidget)
        mainLayout.setContentsMargins(10, 14, 10, 10)
        mainLayout.setSpacing(10)

        # 1. Top line: Title and theme list
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

        # 2. Screenshots carousel
        self.screenshotsCarousel = ImageCarousel([])
        self.screenshotsCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        mainLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Theme info
        self.themeInfoLayout = QVBoxLayout()
        self.themeInfoLayout.setSpacing(10)

        self.themeMetainfoLabel = QLabel()
        self.themeMetainfoLabel.setWordWrap(True)
        self.themeInfoLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = AutoSizeButton(_("Apply Theme"), icon=self.theme_manager.get_icon("apply"))
        self.applyButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.applyButton.setObjectName("actionButton")
        self.themeInfoLayout.addWidget(self.applyButton)

        mainLayout.addLayout(self.themeInfoLayout)

        # Preview update function
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
                    (pixmap, caption)
                    for pixmap, caption in screenshots
                ])
                self.screenshotsCarousel.show()
            else:
                self.screenshotsCarousel.hide()

        updateThemePreview(self.current_theme_name)
        self.themesCombo.currentTextChanged.connect(updateThemePreview)

        # Theme apply logic
        def on_apply():
            selected_theme = self.themesCombo.currentText()
            if selected_theme:
                theme_module = self.theme_manager.apply_theme(selected_theme)
                if theme_module:
                    save_theme_to_config(selected_theme)
                    self.statusBar().showMessage(_("Theme '{0}' applied successfully").format(selected_theme), 3000)
                    xdg_data_home = os.getenv("XDG_DATA_HOME",
                                            os.path.join(os.path.expanduser("~"), ".local", "share"))
                    state_file = os.path.join(xdg_data_home, "PortProtonQt", "state.txt")
                    os.makedirs(os.path.dirname(state_file), exist_ok=True)
                    try:
                        with open(state_file, "w", encoding="utf-8") as f:
                            f.write("theme_tab\n")
                        logger.info(f"State saved to {state_file}")
                        QTimer.singleShot(500, lambda: self.restart_application())
                    except Exception as e:
                        logger.error(f"Failed to save state to {state_file}: {e}")
                else:
                    self.statusBar().showMessage(_("Error applying theme '{0}'").format(selected_theme), 3000)

        self.applyButton.clicked.connect(on_apply)

        # Add widget to stackedWidget
        self.stackedWidget.addWidget(self.themeTabWidget)

    def restart_application(self):
        """Restart application."""
        if not self.isFullScreen():
            save_window_geometry(self.width(), self.height())
        restart_application_with_muvm()

    def restore_state(self):
        """Restore application state after restart."""
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        state_file = os.path.join(xdg_data_home, "PortProtonQt", "state.txt")
        logger.info(f"Checking for state file: {state_file}")
        if os.path.exists(state_file):
            try:
                with open(state_file, encoding="utf-8") as f:
                    state = f.read().strip()
                    logger.info(f"State file contents: '{state}'")
                    if state == "theme_tab":
                        logger.info("Restoring to theme tab (index 5)")
                        if self.stackedWidget.count() > 5:
                            self.switchTab(5)
                        else:
                            logger.warning("Theme tab (index 5) not available yet")
                    else:
                        logger.warning(f"Unexpected state value: '{state}'")
                os.remove(state_file)
                logger.info(f"State file {state_file} removed")
            except Exception as e:
                logger.error(f"Failed to read or process state file {state_file}: {e}")
        else:
            logger.info(f"State file {state_file} does not exist")

    # GAME DETAIL PAGE LOGIC
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

    def getColorPalette_from_pixmap(self, pixmap, num_colors=5, sample_step=10, callback=None):
        """Extract color palette from a QPixmap directly."""
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

    def darkenColor(self, color, factor=200):
        return color.darker(factor)

    def open_exe_settings(self, exe_path, appid=None):
        """Open the ExeSettingsDialog for the given executable."""
        if not exe_path or not os.path.exists(exe_path):
            QMessageBox.warning(self, _("Error"), _("Executable not found: {0}").format(exe_path))
            return
        dialog = ExeSettingsDialog(self, self.theme, exe_path, appid=appid)
        dialog.exec()

    def openGameDetailPage(self, game_data: dict) -> None:
        """Open game detail page."""
        self.detail_page_manager.openGameDetailPage(game_data)

    def handle_launch_exe(self, exe_path: str) -> None:
        """Handle launching an exe file from CLI.

        If the game exists in the library, open its detail page.
        If not, add it to the library and then open the detail page.

        Args:
            exe_path: Full path to the executable file
        """
        import configparser

        # Normalize the exe path
        exe_path = os.path.abspath(exe_path)

        # Check if the game already exists in the library
        existing_entry = find_game_by_exe(exe_path)

        if existing_entry:
            # Game exists - open detail page
            game_name = existing_entry.get("Name", _("Unknown Game"))
            icon_path = existing_entry.get("Icon", "")
            exec_line = existing_entry.get("Exec", "")

            # Get Steam game info asynchronously to fetch appid, cover, etc.
            def on_steam_info(steam_info: dict):
                game_data = {
                    "name": game_name,
                    "description": steam_info.get("description", ""),
                    "cover_path": steam_info.get("cover", icon_path),
                    "appid": steam_info.get("appid", ""),
                    "controller_support": steam_info.get("controller_support", ""),
                    "exec_line": exec_line,
                    "last_launch": _("Never"),
                    "formatted_playtime": "0:00",
                    "protondb_tier": steam_info.get("protondb_tier", ""),
                    "anticheat_status": steam_info.get("anticheat_status", ""),
                    "game_source": "portproton",
                }
                # Open detail page for the newly added game
                self.openGameDetailPage(game_data)

            get_steam_game_info_async(game_name, exec_line, on_steam_info)
        else:
            # Skip desktop file creation for games in steamapps/common
            if "steamapps/common" in exe_path:
                game_name_from_exe = os.path.splitext(os.path.basename(exe_path))[0]
                logger.info("Game in steamapps/common, skipping desktop file creation: %s", game_name_from_exe)

                def on_steam_info_skip(steam_info: dict):
                    game_data = {
                        "name": game_name_from_exe,
                        "description": steam_info.get("description", ""),
                        "cover_path": steam_info.get("cover", ""),
                        "appid": steam_info.get("appid", ""),
                        "controller_support": steam_info.get("controller_support", ""),
                        "exec_line": exe_path,
                        "last_launch": _("Never"),
                        "formatted_playtime": "0:00",
                        "protondb_tier": steam_info.get("protondb_tier", ""),
                        "anticheat_status": steam_info.get("anticheat_status", ""),
                        "game_source": "portproton",
                    }
                    self.openGameDetailPage(game_data)

                get_steam_game_info_async(game_name_from_exe, exe_path, on_steam_info_skip)
                return

            # Game not found - create desktop entry and open detail page
            result = create_desktop_file(exe_path)

            if not result:
                logger.error(f"Failed to create desktop file for {exe_path}")
                return

            desktop_entry, desktop_path = result

            # Write the desktop file
            try:
                with open(desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                logger.info(f"Created desktop file: {desktop_path}")

                # Make it executable
                os.chmod(desktop_path, 0o644)

                # Parse the entry to get game data
                entry = configparser.ConfigParser(interpolation=None)
                entry.read(desktop_path, encoding="utf-8")

                if "Desktop Entry" not in entry:
                    logger.error(f"Invalid desktop file: {desktop_path}")
                    return

                desktop_section = entry["Desktop Entry"]

                game_name = desktop_section.get("Name", os.path.splitext(os.path.basename(exe_path))[0])
                exec_line = desktop_section.get("Exec", "")
                icon_path = desktop_section.get("Icon", "")

                # Get Steam game info asynchronously to fetch appid, cover, etc.
                def on_steam_info(steam_info: dict):
                    game_data = {
                        "name": game_name,
                        "description": steam_info.get("description", ""),
                        "cover_path": steam_info.get("cover", icon_path),
                        "appid": steam_info.get("appid", ""),
                        "controller_support": steam_info.get("controller_support", ""),
                        "exec_line": exec_line,
                        "last_launch": _("Never"),
                        "formatted_playtime": "0:00",
                        "protondb_tier": steam_info.get("protondb_tier", ""),
                        "anticheat_status": steam_info.get("anticheat_status", ""),
                        "game_source": "portproton",
                    }
                    # Open detail page for the newly added game
                    self.openGameDetailPage(game_data)

                get_steam_game_info_async(game_name, exec_line, on_steam_info)

            except Exception as e:
                logger.error(f"Error creating desktop file: {e}")


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
            game_data = {
                "name": focused_widget.name,
                "description": focused_widget.description,
                "cover_path": focused_widget.cover_path,
                "appid": focused_widget.appid,
                "controller_support": focused_widget.controller_support,
                "exec_line": focused_widget.exec_line,
                "last_launch": focused_widget.last_launch,
                "formatted_playtime": focused_widget.formatted_playtime,
                "protondb_tier": focused_widget.protondb_tier,
                "game_source": focused_widget.game_source,
            }
            focused_widget.select_callback(game_data)
        parent = focused_widget.parent()
        while parent:
            if isinstance(parent, FileExplorer):
                parent.select_item()
                break
            parent = parent.parent()


    def is_target_exe_running(self):
        """Check if process named self.target_exe is running via psutil."""
        if not self.target_exe:
            return False
        for proc in psutil.process_iter(attrs=["name"]):
            if proc.info["name"].lower() == self.target_exe.lower():
                return True
        return False

    def checkTargetExe(self):
        """
        Check if game is running.
        If game process (target_exe) detected - set flag and update button.
        If game completed - reset flag, update button and stop timer.
        """
        target_running = self.is_target_exe_running()
        child_running = any(proc.poll() is None for proc in self.game_processes)

        # Check Wine download progress first
        wine_downloading = self.monitor_wine_download_progress()

        if wine_downloading:
            # Wine is downloading - update button with progress
            if self.current_running_button is not None:
                try:
                    self.current_running_button.setText(_("Downloading Wine... {0}%").format(int(self.wine_download_percent)))
                    icon = self.theme_manager.get_icon("save")
                    if isinstance(icon, str):
                        icon = QIcon(icon)
                    elif icon is None:
                        icon = QIcon()
                    self.current_running_button.setIcon(icon)
                except RuntimeError:
                    pass
        elif target_running:
            # Game started - set flag, update button to "Stop"
            if self.current_running_button is not None:
                try:
                    self.current_running_button.setText(_("Stop"))
                except RuntimeError:
                    self.current_running_button = None
                #self._inhibit_screensaver()
        elif not child_running:
            # Game completed - reset flag, reset button and stop timer
            self.resetPlayButton()
            #self._uninhibit_screensaver()
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None

    def monitor_wine_download_progress(self) -> bool:
        """Monitor /tmp/PortProton_$USER/process.log for Wine download progress.

        Returns:
            bool: True if Wine download is in progress, False otherwise.
        """
        percent = self._parse_process_log_progress()
        if percent is None:
            return False
        try:
            logger.debug(f"Wine download progress: {percent}%")
            if percent > 0:
                self.wine_download_seen = True
                self.wine_download_percent = percent
                return True
            elif self.wine_download_seen and percent == 0:
                # Download completed
                self.wine_download_percent = 100.0
                if self.wine_download_timer is not None:
                    self.wine_download_timer.stop()
                return False
        except ValueError as e:
            logger.debug(f"Invalid percent value: {e}")
        return False

    def resetPlayButton(self):
        """
        Reset game launch button:
        change text to "Play", set icon and reset variables.
        Called when game completed (not by button press).
        """
        if self.current_running_button is not None:
            try:
                self.current_running_button.setText(_("Play"))
                icon = self.theme_manager.get_icon("play")
                if isinstance(icon, str):
                    icon = QIcon(icon)  # Convert path to QIcon
                elif icon is None:
                    icon = QIcon()  # Use empty QIcon as fallback
                self.current_running_button.setIcon(icon)
            except RuntimeError:
                pass
            self.current_running_button = None
        self.target_exe = None
        # Reset Wine download monitoring
        self.wine_download_seen = False
        self.wine_download_percent = 0.0

    def toggleGame(self, exec_line, button=None):
        # Handle Steam games
        if exec_line.startswith("steam://"):
            url = QUrl(exec_line)
            QDesktopServices.openUrl(url)
            return

        # Handle EGS games
        if exec_line.startswith("legendary:launch:"):
            app_name = exec_line.split("legendary:launch:")[1]

            # Get path to .exe from installed.json
            game_exe = get_egs_executable(app_name, self.legendary_config_path)
            if not game_exe or not os.path.exists(game_exe):
                QMessageBox.warning(self, _("Error"), _("Executable not found for EGS game: {0}").format(app_name))
                return

            current_exe = os.path.basename(game_exe)
            if self.game_processes and self.target_exe is not None and self.target_exe != current_exe:
                QMessageBox.warning(self, _("Error"), _("Cannot launch game while another game is running"))
                return

            # Update button
            update_button = button if button is not None else self.current_play_button
            self.current_running_button = update_button
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]

            # Check if game is running
            if self.game_processes and self.target_exe == current_exe:
                # Stop game
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
                    try:
                        update_button.setText(_("Play"))
                        icon = self.theme_manager.get_icon("play")
                        if isinstance(icon, str):
                            icon = QIcon(icon)
                        elif icon is None:
                            icon = QIcon()
                        update_button.setIcon(icon)
                    except RuntimeError:
                        pass
                if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                    self.checkProcessTimer.stop()
                    self.checkProcessTimer.deleteLater()
                    self.checkProcessTimer = None
                self.current_running_button = None
                self.target_exe = None
            else:
                # Launch game via PortProton
                env_vars = os.environ.copy()
                env_vars['LEGENDARY_CONFIG_PATH'] = self.legendary_config_path

                wrapper = self.start_sh or ""

                cmd = [wrapper, game_exe]

                try:
                    process = subprocess.Popen(cmd, env=env_vars, shell=False, preexec_fn=os.setsid)
                    self.game_processes.append(process)
                    save_last_launch(exe_name, datetime.now())
                    if update_button:
                        try:
                            update_button.setText(_("Stop"))
                            icon = self.theme_manager.get_icon("stop")
                            if isinstance(icon, str):
                                icon = QIcon(icon)
                            elif icon is None:
                                icon = QIcon()
                            update_button.setIcon(icon)
                        except RuntimeError:
                            pass

                    # Reset Wine download monitoring
                    self.wine_download_seen = False
                    self.wine_download_percent = 0.0

                    self.checkProcessTimer = QTimer(self)
                    self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                    self.checkProcessTimer.start(500)
                except Exception as e:
                    logger.error(f"Failed to launch EGS game {app_name}: {e}")
                    QMessageBox.warning(self, _("Error"), _("Failed to launch game: {0}").format(str(e)))
            return

        # Handle PortProton games
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            QMessageBox.warning(self, _("Error"), _("Invalid command format (empty exec line)"))
            return
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

        # Update button
        update_button = button if button is not None else self.current_play_button

        # If game already running for this exe - stop it
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
                try:
                    update_button.setText(_("Play"))
                    icon = self.theme_manager.get_icon("play")
                    if isinstance(icon, str):
                        icon = QIcon(icon)
                    elif icon is None:
                        icon = QIcon()
                    update_button.setIcon(icon)
                except RuntimeError:
                    pass
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None
            self.current_running_button = None
            self.target_exe = None
            #self._uninhibit_screensaver()
        else:
            # Save button reference for reset after game completion
            self.current_running_button = update_button
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]
            env_vars = os.environ.copy()

            # Launch game
            try:
                process = subprocess.Popen(entry_exec_split, env=env_vars, shell=False, preexec_fn=os.setsid)
                self.game_processes.append(process)
                save_last_launch(exe_name, datetime.now())
                if update_button:
                    try:
                        update_button.setText(_("Stop"))
                        icon = self.theme_manager.get_icon("stop")
                        if isinstance(icon, str):
                            icon = QIcon(icon)
                        elif icon is None:
                            icon = QIcon()
                        update_button.setIcon(icon)
                    except RuntimeError:
                        pass

                # Reset Wine download monitoring
                self.wine_download_seen = False
                self.wine_download_percent = 0.0

                self.checkProcessTimer = QTimer(self)
                self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                self.checkProcessTimer.start(500)
            except Exception as e:
                logger.error(f"Failed to launch game {exe_name}: {e}")
                QMessageBox.warning(self, _("Error"), _("Failed to launch game: {0}").format(str(e)))

    def closeEvent(self, event):
        """Handle window close: check minimize_to_tray setting.
        If True - minimize to tray (default). Otherwise - fully close.
        """
        minimize_to_tray = read_minimize_to_tray()

        if minimize_to_tray:
            # Just minimize to tray
            event.ignore()
            self.hide()
            return

        # Full application close
        event.accept()

        # Hide and remove tray icon
        if hasattr(self, "tray_manager") and self.tray_manager.tray_icon:
            self.tray_manager.tray_icon.hide()
            self.tray_manager.tray_icon.deleteLater()

        # Save card sizes
        save_card_size(self.card_width)
        save_auto_card_size(self.auto_card_width)

        # Save window sizes (if not in fullscreen mode)
        if not read_fullscreen_config():
            logger.debug(f"Saving window geometry: {self.width()}x{self.height()}")
            save_window_geometry(self.width(), self.height())

        # Terminate all game processes
        for proc in getattr(self, "game_processes", []):
            try:
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        logger.debug(f"Terminating child process {child.pid}")
                        child.terminate()
                    except psutil.NoSuchProcess:
                        logger.debug(f"Child process {child.pid} already terminated")

                psutil.wait_procs(children, timeout=5)
                for child in children:
                    if child.is_running():
                        logger.debug(f"Killing child process {child.pid}")
                        child.kill()

                logger.debug(f"Terminating process group {proc.pid}")
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

            except (psutil.NoSuchProcess, ProcessLookupError) as e:
                logger.debug(f"Process {getattr(proc, 'pid', '?')} already terminated: {e}")
            except Exception as e:
                logger.warning(f"Failed to terminate process {getattr(proc, 'pid', '?')}: {e}")

        self.game_processes = []

        # Universal stop and delete timers
        timers = [
            "games_load_timer",
            "settingsDebounceTimer",
            "searchDebounceTimer",
            "checkProcessTimer",
            "wine_monitor_timer",
        ]

        for tname in timers:
            timer = getattr(self, tname, None)
            if timer and timer.isActive():
                timer.stop()
            if timer:
                timer.deleteLater()
                setattr(self, tname, None)

        # Clean up animations to prevent memory leaks
        if hasattr(self, 'detail_animations'):
            try:
                self.detail_animations.cleanup()
            except RuntimeError:
                # Object already deleted
                pass

        # Clean up debug log manager to ensure logs are properly saved if application closes
        if hasattr(self, 'detail_page_manager') and hasattr(self.detail_page_manager, 'debug_log_manager'):
            try:
                self.detail_page_manager.debug_log_manager.cleanup_on_exit()
            except Exception as e:
                logger.warning(f"Failed to cleanup debug log manager: {e}")

    def _update_card_name_from_metadata(self, exe_name: str, metadata_path: str):
        """Update card name and description from metadata file."""
        # Read the translated metadata using the existing function
        language_code = get_egs_language()  # Use the same language detection as elsewhere
        translations = read_metadata_translations(metadata_path, language_code)

        # Update the card with the new name and description if available
        if exe_name in self.autoInstallGameCards:
            card = self.autoInstallGameCards[exe_name]

            # Defensive check: Ensure card is not a list or other unexpected type
            if isinstance(card, list):
                logger.error(f"Card for {exe_name} is unexpectedly a list: {card}")
                return

            # Additional defensive checks for card validity
            if not hasattr(card, 'nameLabel'):
                logger.warning(f"Card for {exe_name} doesn't have nameLabel attribute")
                return

            if not (hasattr(card, 'nameLabel') and hasattr(card.nameLabel, 'setText')):
                logger.warning(f"Card nameLabel for {exe_name} doesn't have setText method")
                return

            if translations and 'name' in translations and translations['name'] and translations['name'] != _('Unknown Game'):
                # Update the card's internal name reference
                card.name = translations['name']
                # Update the display label
                if hasattr(card, 'nameLabel') and card.nameLabel:
                    card.nameLabel.setText(translations['name'])

            # Update description if available
            if translations and 'description' in translations and translations['description']:
                card.description = translations['description']
                if hasattr(card, 'descriptionLabel') and card.descriptionLabel:
                    card.descriptionLabel.setText(translations['description'])


    def goBackDetailPage(self, page):
        """Bridge method to detail page manager."""
        result = self.detail_page_manager.goBackDetailPage(page)
        # The detail page manager will handle the navigation properly
        return result

    def toggleFavoriteInDetailPage(self, game_name, label):
        """Bridge method to detail page manager."""
        return self.detail_page_manager.toggleFavoriteInDetailPage(game_name, label)
