import os
import shlex
import shutil
import signal
import subprocess
import sys
import psutil
import re
from portprotonqt.logger import get_logger
from portprotonqt.dialogs import AddGameDialog, FileExplorer, WinetricksDialog, ExeSettingsDialog
from portprotonqt.game_card import GameCard
from portprotonqt.animations import DetailPageAnimations
from portprotonqt.custom_widgets import ClickableLabel, AutoSizeButton, NavLabel, FlowLayout
from portprotonqt.detail_pages import DetailPageManager
from portprotonqt.portproton_api import PortProtonAPI
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
    read_auto_card_size, save_auto_card_size, get_portproton_start_command
)
from portprotonqt.localization import _, get_egs_language, read_metadata_translations
from portprotonqt.downloader import Downloader
from portprotonqt.tray_manager import TrayManager
from portprotonqt.game_library_manager import GameLibraryManager
from portprotonqt.virtual_keyboard import VirtualKeyboard

from PySide6.QtWidgets import (QLineEdit, QMainWindow, QStatusBar, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QStackedWidget, QComboBox,
                               QDialog, QFormLayout, QMessageBox, QApplication, QPushButton, QProgressBar, QCheckBox, QSizePolicy, QGridLayout, QScrollArea, QScroller, QSlider)
from PySide6.QtCore import Qt, QAbstractAnimation, QUrl, Signal, QTimer, Slot, QProcess
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

    def __init__(self, app_name: str, version: str):
        super().__init__()
        self.theme_manager = ThemeManager()
        self.is_exiting = False
        selected_theme = read_theme_from_config()
        self.current_theme_name = selected_theme
        # Apply theme but defer heavy font loading
        self.theme = self.theme_manager.apply_theme(selected_theme)
        self.tray_manager = TrayManager(self, app_name, self.current_theme_name)
        self.card_width = read_card_size()
        self.auto_card_width = read_auto_card_size()
        self._last_card_width = self.card_width
        self.setWindowTitle(f"{app_name} {version}")
        self.setMinimumSize(800, 600)

        self.games = []
        self.game_processes = []
        self.target_exe = None
        self.current_running_button = None
        self.portproton_location = get_portproton_location()
        self.start_sh = get_portproton_start_command()

        self.game_library_manager = GameLibraryManager(self, self.theme, None)

        # Initialize detail page manager
        self.detail_page_manager = DetailPageManager(self)

        self.context_menu_manager = ContextMenuManager(
            self,
            self.portproton_location,
            self.theme,
            self.loadGames,
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

        read_time_config()
        self.legendary_config_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache"
        )
        os.makedirs(self.legendary_config_path, exist_ok=True)
        os.environ["LEGENDARY_CONFIG_PATH"] = self.legendary_config_path

        self.legendary_path = os.path.join(self.legendary_config_path, "legendary")
        self.downloader = Downloader(max_workers=4)
        self.portproton_api = PortProtonAPI(self.downloader)

        # Статус-бар
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
        self.current_install_script = None
        self.install_process = None
        self.install_monitor_timer = None

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
        headerLayout.addStretch()

        self.input_manager = InputManager(cast(MainWindowProtocol, self))
        self.input_manager.button_event.connect(self.updateControlHints)
        self.input_manager.dpad_moved.connect(self.updateControlHints)

        # 2. НАВИГАЦИЯ (КНОПКИ ВКЛАДОК)
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

        # Вкладки
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

        # 3. QStackedWidget (ВКЛАДКИ)
        self.stackedWidget = QStackedWidget()
        mainLayout.addWidget(self.stackedWidget)

        self.createInstalledTab()
        self.createAutoInstallTab()
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

            # иконка кнопки
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

            # текст действия
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

        # Special function to create combination hint for Guide+Select
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

            # Second icon (Select button)
            select_icon = QLabel()
            select_icon.setFixedSize(26, 26)
            select_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

            # текст действия
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
            if action == "guide_select":
                # For the Guide+Select combination, create a special combination hint
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

        gamepad_actions = ['confirm', 'back', 'add_game', 'context_menu', 'menu', 'search', 'guide_select']

        for container, icon_element, action in self.hintsLabels:
            if action in gamepad_actions:  # Gamepad hint
                if is_gamepad_connected:
                    container.setVisible(True)
                    # Check if this is a combination hint (array of icons) or single icon hint
                    if isinstance(icon_element, list) and len(icon_element) == 3 and action == "guide_select":
                        # This is a combination hint for Guide+Select
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

                        # Determine select icon based on gamepad type
                        if gtype == GamepadType.XBOX:
                            select_icon_name = "xbox_view"  # Xbox Select button
                        elif gtype == GamepadType.PLAYSTATION:
                            select_icon_name = "ps_share"  # PS Share button
                        else:
                            select_icon_name = "xbox_view"  # Default to Xbox Select

                        # Load Select icon
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
        self.current_install_script = script_name
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

    def monitor_install_progress(self):
        """Monitor /tmp/PortProton_$USER/process.log for progress."""
        user = os.getenv('USER', 'unknown')
        log_file = f"/tmp/PortProton_{user}/process.log"
        if not os.path.exists(log_file):
            return
        try:
            with open(log_file, encoding='utf-8') as f:
                content = f.read()
            # Extract all percentage matches, including .0% as 0.0
            matches = re.findall(r'([0-9]*\.?[0-9]+)%', content)
            if matches:
                try:
                    percent = float(matches[-1])
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
        except Exception as e:
            logger.error(f"Error monitoring log: {e}")

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
        self.current_install_script = None
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

    def open_portproton_forum_topic(self, topic_name: str):
        """Open the PortProton forum topic or search page for this game."""
        result = self.portproton_api.get_forum_topic_slug(topic_name)
        base_url = "https://linux-gaming.ru/"
        if result.startswith("search?q="):
            url = QUrl(f"{base_url}{result}")
        else:
            url = QUrl(f"{base_url}t/{result}")
        QDesktopServices.openUrl(url)

    def loadGames(self):
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
                        # Уникальный ключ: имя + exec_line
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
                f"steam://rungameid/{appid}",
                info.get('controller_support', ''),
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
                exec_line,
                steam_info.get("controller_support", ""),
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

    # ВКЛАДКИ
    def switchTab(self, index):
        """Устанавливает активную вкладку по индексу."""
        for i, btn in self.tabButtons.items():
            btn.setChecked(i == index)
        self.stackedWidget.setCurrentIndex(index)
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
        self.search_action = self.searchEdit.addAction(icon, action_pos)
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
                        exec_line,
                        steam_info.get("controller_support", ""),
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

        # Верхняя панель с заголовком и поиском
        headerWidget = QWidget()
        headerLayout = QHBoxLayout(headerWidget)
        headerLayout.setContentsMargins(0, 10, 0, 10)
        headerLayout.setSpacing(10)

        # Заголовок
        titleLabel = QLabel(_("Auto Install"))
        titleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        titleLabel.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        headerLayout.addWidget(titleLabel)

        headerLayout.addStretch()

        # Поисковая строка
        self.autoInstallSearchLineEdit = CustomLineEdit(self, theme=self.theme)
        icon: QIcon = cast(QIcon, self.theme_manager.get_icon("search"))
        action_pos = QLineEdit.ActionPosition.LeadingPosition
        self.search_action = self.autoInstallSearchLineEdit.addAction(icon, action_pos)
        self.autoInstallSearchLineEdit.setMaximumWidth(200)
        self.autoInstallSearchLineEdit.setPlaceholderText(_("Find Games ..."))
        self.autoInstallSearchLineEdit.setClearButtonEnabled(True)
        self.autoInstallSearchLineEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)
        self.autoInstallSearchLineEdit.textChanged.connect(self.filterAutoInstallGames)
        headerLayout.addWidget(self.autoInstallSearchLineEdit)

        autoInstallLayout.addWidget(headerWidget)

        # Прогресс-бар
        self.autoInstallProgress = QProgressBar()
        self.autoInstallProgress.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        self.autoInstallProgress.setVisible(False)
        autoInstallLayout.addWidget(self.autoInstallProgress)

        # Скролл
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

        # Хранение карточек
        self.autoInstallGameCards = {}
        self.allAutoInstallCards = []

        # Обновление обложки
        def on_autoinstall_cover_updated(exe_name, local_path):
            if exe_name in self.autoInstallGameCards and local_path:
                card = self.autoInstallGameCards[exe_name]
                card.cover_path = local_path
                load_pixmap_async(local_path, self.auto_card_width, int(self.auto_card_width * 1.5), card.on_cover_loaded)


        # Загрузка игр
        def on_autoinstall_games_loaded(games: list[tuple]):
            self.autoInstallProgress.setVisible(False)

            # Очистка
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

            # Callback для открытия детальной страницы автоустановки
            def select_callback(name, description, cover_path, appid, exec_line, controller_support, *_):
                if not exec_line or not exec_line.startswith("autoinstall:"):
                    logger.warning(f"Invalid exec_line for autoinstall: {exec_line}")
                    return
                self.detail_page_manager.openAutoInstallDetailPage(name, description, cover_path, exec_line, "portproton")

            # Создаём карточки
            for game_tuple in games:
                name, description, cover_path, appid, controller_support, exec_line, *_ , game_source, exe_name = game_tuple

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

            # Загружаем недостающие обложки и метаданные
            for game_tuple in games:
                name, description, cover_path, appid, controller_support, exec_line, *_ , game_source, exe_name = game_tuple
                if not cover_path:
                    self.portproton_api.download_autoinstall_cover_async(
                        exe_name, timeout=5,
                        callback=lambda path, ex=exe_name: on_autoinstall_cover_updated(ex, path)
                    )

                # Always try to download metadata for better descriptions
                # Update the card when metadata is downloaded
                def metadata_callback(path, exe_name=exe_name):
                    if path and os.path.exists(path):  # If metadata file was successfully downloaded
                        try:
                            # Update card name from metadata
                            self._update_card_name_from_metadata(exe_name, path)
                        except Exception as e:
                            logger.error(f"Error updating card metadata for {exe_name}: {e}")

                self.portproton_api.download_autoinstall_metadata_async(
                    exe_name, timeout=5,
                    callback=metadata_callback
                )

            self.autoInstallContainer.updateGeometry()
            self.autoInstallScrollArea.updateGeometry()
            self.filterAutoInstallGames()

        # Показываем прогресс
        self.autoInstallProgress.setVisible(True)
        self.autoInstallProgress.setRange(0, 0)

        # Store the thread to prevent premature destruction
        self.autoInstallLoadThread = self.portproton_api.start_autoinstall_games_load(on_autoinstall_games_loaded)

        # Optional: Clean up thread when finished (prevents leak)
        if self.autoInstallLoadThread:
            def on_thread_finished():
                self.autoInstallLoadThread = None  # Release reference
            self.autoInstallLoadThread.finished.connect(on_thread_finished)

        self.stackedWidget.addWidget(autoInstallPage)

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
        visible_count = 0

        for card in self.allAutoInstallCards:
            if search_text in card.name.lower():
                card.setVisible(True)
                visible_count += 1
            else:
                card.setVisible(False)

        # Re-layout the container
        self.autoInstallContainerLayout.invalidate()
        self.autoInstallContainer.updateGeometry()
        self.autoInstallScrollArea.updateGeometry()

    def createWineTab(self):
        """Вкладка 'Wine Settings'."""
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

        self.wine_versions = [d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))]
        self.wineCombo = QComboBox()
        self.wineCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.wineCombo.addItems(self.wine_versions)
        self.wineCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.wineCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.wineTitleLabel = QLabel(_("Compatibility tool:"))
        self.wineTitleLabel.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.wineTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if self.wine_versions:
            self.wineCombo.setCurrentIndex(0)
        formLayout.addRow(self.wineTitleLabel, self.wineCombo)

        self.prefixes = [d for d in os.listdir(prefixes_path) if os.path.isdir(os.path.join(prefixes_path, d))] if os.path.exists(prefixes_path) else []
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
            (_("Delete Compatibility Tool"), self.delete_compat_tool),
            (_("Delete Prefix"), self.delete_prefix),
            (_("Clear Prefix"), self.clear_prefix),
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

        # Показываем прогресс-бар перед запуском
        self.wine_progress_bar.setVisible(True)
        self.update_status_message.emit(_("Launching tool..."), 0)

        proc = QProcess(self)
        proc.finished.connect(lambda exitCode, exitStatus: self._on_wine_tool_finished(exitCode, cli_arg))
        proc.errorOccurred.connect(lambda error: self._on_wine_tool_error(error, cli_arg))
        proc.start(cmd[0], cmd[1:])

        if not proc.waitForStarted(5000):
            self.wine_progress_bar.setVisible(False)
            self.update_status_message.emit("", 0)
            QMessageBox.warning(self, _("Error"), _("Failed to start process."))
            return

        self._start_wine_process_monitor(cli_arg)

    def _start_wine_process_monitor(self, cli_arg):
        """Запускает таймер для мониторинга запуска Wine утилиты."""
        self.wine_monitor_timer = QTimer(self)
        self.wine_monitor_timer.setInterval(500)
        self.wine_monitor_timer.timeout.connect(lambda: self._check_wine_process(cli_arg))
        self.wine_monitor_timer.start()

    def _check_wine_process(self, cli_arg):
        """Проверяет, запустился ли целевой .exe процесс."""
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

        # Проверяем процессы через psutil
        for proc in psutil.process_iter(attrs=["name"]):
            if proc.info["name"].lower() == target_exe.lower():
                # Процесс запустился — скрываем прогресс-бар и останавливаем мониторинг
                self.wine_progress_bar.setVisible(False)
                self.update_status_message.emit("", 0)
                if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
                    self.wine_monitor_timer.stop()
                    self.wine_monitor_timer.deleteLater()
                    self.wine_monitor_timer = None
                logger.info(f"Wine tool {target_exe} started successfully")
                return

    def _on_wine_tool_finished(self, exitCode, cli_arg):
        """Обработчик завершения Wine утилиты."""
        self.wine_progress_bar.setVisible(False)
        self.update_status_message.emit("", 0)
        # Останавливаем мониторинг, если он активен
        if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
            self.wine_monitor_timer.stop()
            self.wine_monitor_timer.deleteLater()
            self.wine_monitor_timer = None
        if exitCode == 0:
            logger.info(f"Wine tool {cli_arg} finished successfully")
        else:
            logger.warning(f"Wine tool {cli_arg} finished with exit code {exitCode}")

    def _on_wine_tool_error(self, error, cli_arg):
        """Обработчик ошибки запуска Wine утилиты."""
        self.wine_progress_bar.setVisible(False)
        self.update_status_message.emit("", 0)
        # Останавливаем мониторинг, если он активен
        if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
            self.wine_monitor_timer.stop()
            self.wine_monitor_timer.deleteLater()
            self.wine_monitor_timer = None
        logger.error(f"Wine tool {cli_arg} error: {error}")
        QMessageBox.warning(self, _("Error"), f"Failed to launch tool: {error}")

    def clear_prefix(self):
        """Очищает префикс"""
        selected_prefix = self.prefixCombo.currentText()
        selected_wine = self.wineCombo.currentText()

        if not selected_prefix or not selected_wine:
            return
        if not self.portproton_location or not self.start_sh:
            return

        reply = QMessageBox.question(
            self,
            _("Confirm Clear"),
            _("Are you sure you want to clear prefix '{}'?").format(selected_prefix),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        start_sh = self.start_sh

        self.wine_progress_bar.setVisible(True)
        self.update_status_message.emit(_("Clearing prefix..."), 0)

        self.clear_process = QProcess(self)
        self.clear_process.finished.connect(lambda exitCode, exitStatus: self._on_clear_prefix_finished(exitCode))
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
        self.backup_process.finished.connect(lambda exitCode, exitStatus: self._on_backup_finished(exitCode))
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
        self.restore_process.finished.connect(lambda exitCode, exitStatus: self._on_restore_finished(exitCode))
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

        reply = QMessageBox.question(
            self,
            _("Confirm Deletion"),
            _("Are you sure you want to delete prefix '{}'?").format(selected_prefix),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(prefix_path)
                QMessageBox.information(self, _("Success"), _("Prefix '{}' deleted.").format(selected_prefix))
                # обновляем список
                self.prefixCombo.clear()
                prefixes_path = os.path.join(self.portproton_location, "data", "prefixes")
                self.prefixes = [d for d in os.listdir(prefixes_path)
                                if os.path.isdir(os.path.join(prefixes_path, d))]
                self.prefixCombo.addItems(self.prefixes)
            except Exception as e:
                QMessageBox.warning(self, _("Error"), _("Failed to delete prefix: {}").format(str(e)))

    def delete_compat_tool(self):
        """Удаляет выбранный Wine/Proton дистрибутив из каталога dist."""
        if not self.portproton_location:
            return

        selected_tool = self.wineCombo.currentText()
        if not selected_tool:
            return

        tool_path = os.path.join(self.portproton_location, "data", "dist", selected_tool)
        if not os.path.exists(tool_path):
            return

        reply = QMessageBox.question(
            self,
            _("Confirm Deletion"),
            _("Are you sure you want to delete compatibility tool '{}'?").format(selected_tool),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(tool_path)
                QMessageBox.information(self, _("Success"), _("Compatibility tool '{}' deleted.").format(selected_tool))
                # обновляем список
                self.wineCombo.clear()
                self.wine_versions = [d for d in os.listdir(os.path.join(self.portproton_location, "data", "dist"))
                                      if os.path.isdir(os.path.join(self.portproton_location, "data", "dist", d))]
                self.wineCombo.addItems(self.wine_versions)
            except Exception as e:
                QMessageBox.warning(self, _("Error"), _("Failed to delete compatibility tool: {}").format(str(e)))

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
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # 1. Time detail_level
        self.timeDetailCombo = QComboBox()
        self.timeDetailCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.gamesSortCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.gamesDisplayCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

        # 4 Gamepad Type
        self.gamepadTypeCombo = QComboBox()
        self.gamepadTypeCombo.addItems(["Xbox", "PlayStation"])
        self.gamepadTypeCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamepadTypeCombo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamepadTypeTitle = QLabel(_("Gamepad Type:"))
        self.gamepadTypeTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.gamepadTypeTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_type_str = read_gamepad_type()
        if current_type_str == "playstation":
            self.gamepadTypeCombo.setCurrentText("PlayStation")
        else:
            self.gamepadTypeCombo.setCurrentText("Xbox")
        formLayout.addRow(self.gamepadTypeTitle, self.gamepadTypeCombo)

        # 5. Proxy settings
        self.proxyUrlEdit = CustomLineEdit(self, theme=self.theme)
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

        self.proxyUserEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyUserEdit.setPlaceholderText(_("Proxy Username"))
        self.proxyUserEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        self.proxyUserEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyUserTitle = QLabel(_("Proxy Username:"))
        self.proxyUserTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.proxyUserTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        formLayout.addRow(self.proxyUserTitle, self.proxyUserEdit)

        self.proxyPasswordEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyPasswordEdit.setPlaceholderText(_("Proxy Password"))
        self.proxyPasswordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxyPasswordEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        self.proxyPasswordEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyPasswordTitle = QLabel(_("Proxy Password:"))
        self.proxyPasswordTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.proxyPasswordTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        formLayout.addRow(self.proxyPasswordTitle, self.proxyPasswordEdit)

        # 6. Fullscreen setting for application
        self.fullscreenCheckBox = QCheckBox(_("Launch Application in Fullscreen"))
        self.fullscreenCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.fullscreenCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fullscreenTitle = QLabel(_("Application Fullscreen Mode:"))
        self.fullscreenTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.fullscreenTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_fullscreen = read_fullscreen_config()
        self.fullscreenCheckBox.setChecked(current_fullscreen)
        formLayout.addRow(self.fullscreenTitle, self.fullscreenCheckBox)

        # 7. Minimize to tray setting
        self.minimizeToTrayCheckBox = QCheckBox(_("Minimize to tray on close"))
        self.minimizeToTrayCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.minimizeToTrayCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.minimizeToTrayTitle = QLabel(_("Application Close Mode:"))
        self.minimizeToTrayTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.minimizeToTrayTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_minimize_to_tray = read_minimize_to_tray()
        self.minimizeToTrayCheckBox.setChecked(current_minimize_to_tray)
        self.minimizeToTrayCheckBox.toggled.connect(lambda checked: save_minimize_to_tray(checked))
        formLayout.addRow(self.minimizeToTrayTitle, self.minimizeToTrayCheckBox)

        # 8. Automatic fullscreen on gamepad connection
        self.autoFullscreenGamepadCheckBox = QCheckBox(_("Auto Fullscreen on Gamepad connected"))
        self.autoFullscreenGamepadCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.autoFullscreenGamepadCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.autoFullscreenGamepadCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.autoFullscreenGamepadTitle = QLabel(_("Auto Fullscreen on Gamepad connected:"))
        self.autoFullscreenGamepadTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.autoFullscreenGamepadTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_auto_fullscreen = read_auto_fullscreen_gamepad()
        self.autoFullscreenGamepadCheckBox.setChecked(current_auto_fullscreen)
        formLayout.addRow(self.autoFullscreenGamepadTitle, self.autoFullscreenGamepadCheckBox)

        # 9. Gamepad haptic feedback config
        self.gamepadRumbleCheckBox = QCheckBox(_("Gamepad haptic feedback"))
        self.gamepadRumbleCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamepadRumbleCheckBox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE)
        self.gamepadRumbleTitle = QLabel(_("Gamepad haptic feedback:"))
        self.gamepadRumbleTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.gamepadRumbleTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_rumble_state = read_rumble_config()
        self.gamepadRumbleCheckBox.setChecked(current_rumble_state)
        formLayout.addRow(self.gamepadRumbleTitle, self.gamepadRumbleCheckBox)

        # # 9. Legendary Authentication
        # self.legendaryAuthButton = AutoSizeButton(
        #     _("Open Legendary Login"),
        #     icon=self.theme_manager.get_icon("login")self.theme_manager.get_icon("login")
        # )
        # self.legendaryAuthButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        # self.legendaryAuthButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # self.legendaryAuthButton.clicked.connect(self.openLegendaryLogin)
        # self.legendaryAuthTitle = QLabel(_("Legendary Authentication:"))
        # self.legendaryAuthTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        # self.legendaryAuthTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # formLayout.addRow(self.legendaryAuthTitle, self.legendaryAuthButton)
        #
        # self.legendaryCodeEdit = CustomLineEdit(self, theme=self.theme)
        # self.legendaryCodeEdit.setPlaceholderText(_("Enter Legendary Authorization Code"))
        # self.legendaryCodeEdit.setStyleSheet(self.theme.PROXY_INPUT_STYLE)
        # self.legendaryCodeEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # self.legendaryCodeTitle = QLabel(_("Authorization Code:"))
        # self.legendaryCodeTitle.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        # self.legendaryCodeTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # formLayout.addRow(self.legendaryCodeTitle, self.legendaryCodeEdit)
        #
        # self.submitCodeButton = AutoSizeButton(
        #     _("Submit Code"),
        #     icon=self.theme_manager.get_icon("save")
        # )
        # self.submitCodeButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        # self.submitCodeButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # self.submitCodeButton.clicked.connect(self.submitLegendaryCode)
        # formLayout.addRow(QLabel(""), self.submitCodeButton)

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

        for card in self.game_library_manager.game_card_cache.values():
            card.update_badge_visibility(filter_key)

        if self.currentDetailPage and self.current_exec_line:
            current_game = next((game for game in self.games if game[4] == self.current_exec_line), None)
            if current_game:
                self.stackedWidget.removeWidget(self.currentDetailPage)
                self.currentDetailPage.deleteLater()
                self.currentDetailPage = None
                self.detail_page_manager.openGameDetailPage(*current_game)

        self.settingsDebounceTimer.start()

        gamepad_connected = self.input_manager.find_gamepad() is not None
        if fullscreen or (auto_fullscreen_gamepad and gamepad_connected):
            self.showFullScreen()

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

        self.applyButton = AutoSizeButton(_("Apply Theme"), icon=self.theme_manager.get_icon("apply"))
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

    def open_exe_settings(self, exe_path):
        """Open the ExeSettingsDialog for the given executable."""
        if not os.path.exists(exe_path):
            QMessageBox.warning(self, _("Error"), _("Executable not found: {0}").format(exe_path))
            return
        dialog = ExeSettingsDialog(self, self.theme, exe_path)
        dialog.exec()

    def openGameDetailPage(self, name, description, cover_path=None, appid="", exec_line="", controller_support="", last_launch="", formatted_playtime="", protondb_tier="", game_source="", anticheat_status=""):
        # Delegate to the detail page manager
        self.detail_page_manager.openGameDetailPage(
            name, description, cover_path, appid, exec_line, controller_support,
            last_launch, formatted_playtime, protondb_tier, game_source, anticheat_status
        )


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
                        focused_widget.game_source
                    )
        parent = focused_widget.parent()
        while parent:
            if isinstance(parent, FileExplorer):
                parent.select_item()
                break
            parent = parent.parent()


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
                try:
                    self.current_running_button.setText(_("Stop"))
                except RuntimeError:
                    self.current_running_button = None
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

    def toggleGame(self, exec_line, button=None):
        # Обработка Steam-игр
        if exec_line.startswith("steam://"):
            url = QUrl(exec_line)
            QDesktopServices.openUrl(url)
            return

        # Обработка EGS-игр
        if exec_line.startswith("legendary:launch:"):
            app_name = exec_line.split("legendary:launch:")[1]

            # Получаем путь к .exe из installed.json
            game_exe = get_egs_executable(app_name, self.legendary_config_path)
            if not game_exe or not os.path.exists(game_exe):
                QMessageBox.warning(self, _("Error"), _("Executable not found for EGS game: {0}").format(app_name))
                return

            current_exe = os.path.basename(game_exe)
            if self.game_processes and self.target_exe is not None and self.target_exe != current_exe:
                QMessageBox.warning(self, _("Error"), _("Cannot launch game while another game is running"))
                return

            # Обновляем кнопку
            update_button = button if button is not None else self.current_play_button
            self.current_running_button = update_button
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]

            # Проверяем, запущена ли игра
            if self.game_processes and self.target_exe == current_exe:
                # Останавливаем игру
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
                self._gameLaunched = False
            else:
                # Запускаем игру через PortProton
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
                            update_button.setText(_("Launching"))
                            icon = self.theme_manager.get_icon("stop")
                            if isinstance(icon, str):
                                icon = QIcon(icon)
                            elif icon is None:
                                icon = QIcon()
                            update_button.setIcon(icon)
                        except RuntimeError:
                            pass

                    self.checkProcessTimer = QTimer(self)
                    self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                    self.checkProcessTimer.start(500)
                except Exception as e:
                    logger.error(f"Failed to launch EGS game {app_name}: {e}")
                    QMessageBox.warning(self, _("Error"), _("Failed to launch game: {0}").format(str(e)))
            return

        # Обработка PortProton-игр
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

        # Обновляем кнопку
        update_button = button if button is not None else self.current_play_button

        # Если игра уже запущена для этого exe – останавливаем её
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
            self._gameLaunched = False
            #self._uninhibit_screensaver()
        else:
            # Сохраняем ссылку на кнопку для сброса после завершения игры
            self.current_running_button = update_button
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]
            env_vars = os.environ.copy()

            # Запускаем игру
            try:
                process = subprocess.Popen(entry_exec_split, env=env_vars, shell=False, preexec_fn=os.setsid)
                self.game_processes.append(process)
                save_last_launch(exe_name, datetime.now())
                if update_button:
                    try:
                        update_button.setText(_("Launching"))
                        icon = self.theme_manager.get_icon("stop")
                        if isinstance(icon, str):
                            icon = QIcon(icon)
                        elif icon is None:
                            icon = QIcon()
                        update_button.setIcon(icon)
                    except RuntimeError:
                        pass

                self.checkProcessTimer = QTimer(self)
                self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                self.checkProcessTimer.start(500)
            except Exception as e:
                logger.error(f"Failed to launch game {exe_name}: {e}")
                QMessageBox.warning(self, _("Error"), _("Failed to launch game: {0}").format(str(e)))

    def closeEvent(self, event):
        """Обработчик закрытия окна: проверяет настройку minimize_to_tray.
        Если True — сворачиваем в трей (по умолчанию). Иначе — полностью закрываем.
        """
        minimize_to_tray = read_minimize_to_tray()

        if minimize_to_tray:
            # Просто сворачиваем в трей
            event.ignore()
            self.hide()
            return

        # Полное закрытие приложения
        self.is_exiting = True
        event.accept()

        # Скрываем и удаляем иконку трея
        if hasattr(self, "tray_manager") and self.tray_manager.tray_icon:
            self.tray_manager.tray_icon.hide()
            self.tray_manager.tray_icon.deleteLater()

        # Сохраняем размеры карточек
        save_card_size(self.card_width)
        save_auto_card_size(self.auto_card_width)

        # Сохраняем размеры окна (если не в полноэкранном режиме)
        if not read_fullscreen_config():
            logger.debug(f"Saving window geometry: {self.width()}x{self.height()}")
            save_window_geometry(self.width(), self.height())

        # Завершаем все игровые процессы
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

        # Универсальная остановка и удаление таймеров
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

    def _update_card_name_from_metadata(self, exe_name: str, metadata_path: str):
        """Update card name from metadata file."""
        # Read the translated metadata using the existing function
        language_code = get_egs_language()  # Use the same language detection as elsewhere
        translations = read_metadata_translations(metadata_path, language_code)

        # Update the card with the new name if available
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


    def goBackDetailPage(self, page):
        """Bridge method to detail page manager."""
        result = self.detail_page_manager.goBackDetailPage(page)
        # The detail page manager will handle the navigation properly
        return result

    def toggleFavoriteInDetailPage(self, game_name, label):
        """Bridge method to detail page manager."""
        return self.detail_page_manager.toggleFavoriteInDetailPage(game_name, label)
