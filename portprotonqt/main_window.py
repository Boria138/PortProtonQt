import os
import signal
import shlex
import shutil
import subprocess
import psutil
import re
from portprotonqt.logger import get_logger
from portprotonqt.dialogs import AddGameDialog, FileExplorer, WinetricksDialog, ExeSettingsDialog, generate_thumbnail
from portprotonqt.game_card import GameCard
from portprotonqt.animations import DetailPageAnimations
from portprotonqt.custom_widgets import ClickableLabel, AutoSizeButton, NavLabel, FlowLayout
from portprotonqt.detail_pages import DetailPageManager
from portprotonqt.portproton_api import PortProtonAPI, get_user_conf_setting, set_user_conf_setting
from portprotonqt.debug_utils import get_selectable_gpu_list, get_prefix_name, get_system_dpi_for_wine
from portprotonqt.input_manager import InputManager, MainWindowProtocol
from portprotonqt.context_menu_manager import ContextMenuManager, CustomLineEdit

from portprotonqt.image_utils import (
    COVER_IMAGE_EXTENSIONS,
    ImageCarousel,
    load_pixmap_async,
    set_all_animated_covers_suspended,
)
from portprotonqt.steam_api import get_steam_game_info_async, get_full_steam_game_info_async, get_cached_steam_game_info, get_steam_installed_games, is_game_in_steam, fetch_sgdb_cover_async, get_steam_compatibilitytools_dir
from portprotonqt.theme_manager import ThemeManager, load_theme_screenshots
from portprotonqt.time_utils import save_last_launch, get_last_launch, get_playtime_for_exe, format_playtime, get_last_launch_timestamp, format_last_launch
from portprotonqt.config import (
    get_portproton_location,
    ui_config,
    parse_desktop_entry,
    load_theme_metainfo,
    game_config,
    favorites_config,
    proxy_config,
    display_config,
    extract_exec_target_path,
    window_config,
    reset_main_config,
    cache_config,
    get_portproton_start_command,
    get_portproton_scripts_path,
    apply_xdg_autostart,
    find_game_by_exe,
    migrate_legacy_shortcut,
)
from portprotonqt.cli import add_steam_compat_tool, remove_steam_compat_tool, is_steam_compat_tool_installed

from portprotonqt.tray_manager import restart_application_with_muvm
from portprotonqt.version_utils import prefix_sort_key, version_sort_key
from portprotonqt.localization import _, get_metadata_language, read_metadata_translations
from portprotonqt.downloader import Downloader
from portprotonqt.tray_manager import TrayManager
from portprotonqt.game_library_manager import GameLibraryManager
from portprotonqt.virtual_keyboard import VirtualKeyboard
from portprotonqt.disc_image_utils import DiscImageManager
from portprotonqt.dialogs.proton_manager import show_proton_manager
from portprotonqt.tabs.control_hints import MainWindowControlHintsMixin
from portprotonqt.tabs.system_tab import MainWindowSystemTabMixin
from portprotonqt.tabs.workers import MainWindowWorkersMixin

from PySide6.QtWidgets import (QLineEdit, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QStackedWidget, QComboBox,
                               QDialog, QFormLayout, QMessageBox, QApplication, QPushButton, QProgressBar, QCheckBox, QSizePolicy, QGridLayout, QScrollArea, QScroller, QSlider, QFrame)
from PySide6.QtCore import Qt, QAbstractAnimation, QEvent, QUrl, Signal, QTimer, Slot, QProcess, QProcessEnvironment, QFileSystemWatcher, QStandardPaths
from PySide6.QtGui import QIcon, QColor, QDesktopServices, QHideEvent, QShowEvent
from typing import cast
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = get_logger(__name__)
DISC_IMAGE_EXTENSIONS = (".iso", ".mdf")

class MainWindow(MainWindowControlHintsMixin, MainWindowSystemTabMixin, MainWindowWorkersMixin, QMainWindow):
    games_loaded = Signal(list)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            corner_size = 20
            width = self.width()
            height = self.height()
            click_pos = event.pos()

            if click_pos.x() >= width - corner_size and click_pos.y() >= height - corner_size:
                self.window().windowHandle().startSystemResize(
                    Qt.Edge.BottomEdge | Qt.Edge.RightEdge  # type: ignore
                )
            else:
                self.window().windowHandle().startSystemMove()
            event.accept()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange):
            self._update_animated_covers_activity()

    def hideEvent(self, event: QHideEvent) -> None:
        self._set_animated_covers_suspended(True)
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._update_animated_covers_activity()

    def _on_application_state_changed(self, _state: Qt.ApplicationState) -> None:
        self._update_animated_covers_activity()

    def _update_animated_covers_activity(self) -> None:
        should_suspend = (
            not self.isVisible() or
            self.isMinimized() or
            not self.isActiveWindow()
        )
        self._set_animated_covers_suspended(should_suspend)

    def _set_animated_covers_suspended(self, suspended: bool) -> None:
        if getattr(self, "_animated_covers_suspended", False) == suspended:
            return
        self._animated_covers_suspended = suspended
        set_all_animated_covers_suspended(suspended)
        self._set_inactive_background_suspended(suspended)
        if not suspended and hasattr(self, "game_library_manager"):
            QTimer.singleShot(0, self.game_library_manager.load_visible_images)
        if not suspended and hasattr(self, "input_manager") and not self._has_running_game_process():
            self.input_manager.resume_gamepad_polling()

    def _set_inactive_background_suspended(self, suspended: bool) -> None:
        if hasattr(self, "game_library_manager") and suspended:
            self.game_library_manager.stop_background_activity()

    def _get_lg_versions_from_var(self) -> list[str]:
        """Read Proton/Wine LG versions from scripts/var."""
        scripts_path = get_portproton_scripts_path()
        if not scripts_path:
            return []

        var_path = os.path.join(scripts_path, "var")
        if not os.path.exists(var_path):
            return []

        versions: list[str] = []
        target_keys = ("PW_PROTON_LG_VER", "PW_WINE_LG_VER")
        try:
            with open(var_path, encoding="utf-8") as var_file:
                for line in var_file:
                    line_stripped = line.strip()
                    for key in target_keys:
                        prefix = f"export {key}="
                        if line_stripped.startswith(prefix):
                            value = line_stripped[len(prefix):].strip().strip('"\'')
                            if value and value not in versions:
                                versions.append(value)
        except OSError as exc:
            logger.warning("Failed to read LG versions from %s: %s", var_path, exc)
        return versions

    def __init__(self, app_name: str, version: str, launch_exe: str | None = None, resolution: tuple[int, int] | None = None, show_system_tab: bool = False):
        super().__init__()
        self.theme_manager = ThemeManager()
        selected_theme = ui_config.get_theme()
        self.current_theme_name = selected_theme
        # Apply theme but defer heavy font loading
        self.theme = self.theme_manager.apply_theme(selected_theme)
        self.tray_manager = TrayManager(self, app_name, self.current_theme_name)
        self.card_width = ui_config.get_card_width()
        self.auto_card_width = ui_config.get_auto_card_width()
        self.setWindowTitle(f"{app_name} {version}")
        self.setMinimumSize(890, 600)
        self._pending_resolution = resolution  # Store resolution for later application
        self._show_system_tab = show_system_tab
        self.system_tab_index = -1  # Default, set when system tab is created
        self._animated_covers_suspended = False

        self.games = []
        self.game_processes = []
        self.target_exe = None
        self.current_running_button = None
        self.disc_image_manager = DiscImageManager()
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
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)
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

        ui_config.get_time_detail_level()

        # Start watching dist and prefixes directories if they exist
        QTimer.singleShot(0, self.start_watching_directories)  # Delay to ensure portproton_location is set
        self.downloader = Downloader(max_workers=4)
        self.portproton_api = PortProtonAPI(self.downloader)

        self.installing = False
        self.install_process = None
        self.install_stop_process = None
        self.install_monitor_timer = None
        self.install_stop_requested = False
        self.current_install_script = None
        self.current_install_button = None
        self.current_install_button_text = None
        self.current_install_button_icon = None

        # Dependency setup monitoring during game launch
        self.wine_download_timer = None
        self.wine_download_percent = 0.0
        self.wine_download_seen = False
        self.wine_download_status = _("Downloading Wine...")
        self.game_launch_started = False

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
        self.input_manager.gamepad_hotplug.connect(self.updateControlHints)

        # 2. NAVIGATION (TAB BUTTONS)
        self.navWidget = QWidget()
        self.navWidget.setStyleSheet(self.theme.NAV_WIDGET_STYLE)
        navLayout = QHBoxLayout(self.navWidget)
        navLayout.setContentsMargins(10, 0, 10, 0)
        navLayout.setSpacing(10)

         # Left navigation button (key_left or button_lb)
        self.leftNavButton = NavLabel()
        self.leftNavButton.setFixedSize(32, 32)
        self.leftNavButton.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.leftNavButton.clicked.connect(lambda: self.switchVisibleTab(-1))
        navLayout.addWidget(self.leftNavButton)

        # Tabs
        self.tabButtons = {}
        tabs = [
            _("Library"),
            _("Auto Install"),
            _("Wine Settings"),
            _("PPQT Settings"),
            _("System"),
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
        self.rightNavButton = NavLabel()
        self.rightNavButton.setFixedSize(32, 32)
        self.rightNavButton.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rightNavButton.clicked.connect(lambda: self.switchVisibleTab(1))
        navLayout.addWidget(self.rightNavButton)

        # Initial update of navigation buttons based on input device
        self.updateNavButtons()

        mainLayout.addWidget(self.navWidget)

        # 3. QStackedWidget (TABS)
        self.stackedWidget = QStackedWidget()
        self.stackedWidget.currentChanged.connect(self.updateControlHints)
        mainLayout.addWidget(self.stackedWidget)

        self.createInstalledTab()

        # Always create auto-install tab but set visibility based on settings
        self.createAutoInstallTab()
        self.auto_install_tab_index = 1  # Auto Install tab is always at index 1

        # Set visibility based on settings
        hide_autoinstall = ui_config.get_hide_autoinstall_tab()
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
        if self._show_system_tab:
            self.createSystemTab()
        else:
            # Keep tab indexes stable when System tab is disabled.
            self.stackedWidget.addWidget(QWidget())
            if hasattr(self, 'tabButtons') and 4 in self.tabButtons:
                system_tab_button = self.tabButtons[4]
                system_tab_button.setVisible(False)
            hidden_system_page = self.stackedWidget.widget(4)
            if hidden_system_page:
                hidden_system_page.setVisible(False)
        self.createThemeTab()

        self.controlHintsWidget = self.createControlHintsWidget()
        self.controlHintsWidget.setStyleSheet(self.theme.HINT_BAR_STYLE)
        mainLayout.addWidget(self.controlHintsWidget)

        self.updateControlHints()

        self.restore_state()

        self.keyboard = VirtualKeyboard(self, self.theme)

        self.detail_animations = DetailPageAnimations(self, self.theme)
        self._animations = {}
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.applicationStateChanged.connect(self._on_application_state_changed)

        if display_config.get_fullscreen():
            self.showFullScreen()
        elif self._pending_resolution:
            # Apply resolution from command line
            self.resize(self._pending_resolution[0], self._pending_resolution[1])
            self.showNormal()
        else:
            width, height = window_config.get_geometry()
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

    def launch_autoinstall(
        self, script_name: str, button: AutoSizeButton | None = None
    ) -> None:
        """Launch auto-install script."""
        if self.installing:
            if script_name == self.current_install_script:
                self.stop_autoinstall()
                return
            QMessageBox.warning(self, _("Warning"), _("Installation already in progress."))
            return
        self.installing = True
        self.install_stop_requested = False
        self.current_install_script = script_name
        self._set_install_button_stop(button)
        self._set_install_button_progress_text(_("Installing..."))
        self.seen_progress = False
        self.current_percent = 0.0
        start_sh = self.start_sh
        if not start_sh:
            self._reset_install_state()
            return
        cmd = start_sh + ["cli", "--autoinstall", script_name]
        self.install_process = QProcess(self)
        self.install_process.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        self.install_process.finished.connect(self.on_install_finished)
        self.install_process.errorOccurred.connect(self.on_install_error)
        self.install_process.start(cmd[0], cmd[1:])
        if not self.install_process.waitForStarted(5000):
            self._reset_install_state()
            QMessageBox.warning(self, _("Error"), _("Failed to start installation."))
            return
        self.install_monitor_timer = QTimer(self)
        self.install_monitor_timer.timeout.connect(self.monitor_install_progress)
        self.install_monitor_timer.start(2000)  # Start monitoring after 2s

    def _set_install_button_stop(self, button: AutoSizeButton | None = None) -> None:
        """Switch the active auto-install button to stop action."""
        self.current_install_button = button
        if button is None:
            return

        self.current_install_button_text = button.text()
        self.current_install_button_icon = button.rawIcon()
        icon = self.theme_manager.get_icon("stop", as_path=True)
        if icon:
            button.setIcon(icon)
        button.setText(_("Stop"))

    def _set_install_button_progress_text(
        self, status: str | None = None, percent: float | None = None
    ) -> None:
        """Update auto-install button text with current progress."""
        if self.current_install_button is None:
            return
        try:
            if percent is not None and percent > 0:
                progress_text = f"{int(percent)}%"
                button_text = f"{status} {progress_text}" if status else progress_text
                self.current_install_button.setText(button_text)
                return
            if status:
                self.current_install_button.setText(status)
                return
            self.current_install_button.setText(_("Stop"))
        except RuntimeError:
            self.current_install_button = None

    def _reset_install_state(self) -> None:
        """Reset auto-install process state and restore button."""
        self.installing = False
        self.install_stop_requested = False
        self.current_install_script = None
        if self.current_install_button is not None:
            try:
                if self.current_install_button_icon is not None:
                    self.current_install_button.setIcon(self.current_install_button_icon)
                if self.current_install_button_text is not None:
                    self.current_install_button.setText(self.current_install_button_text)
            except RuntimeError:
                pass
        self.current_install_button = None
        self.current_install_button_text = None
        self.current_install_button_icon = None

    def stop_autoinstall(self) -> None:
        """Stop current auto-install process."""
        if not self.install_process:
            self._reset_install_state()
            return
        if (
            self.install_stop_process is not None
            and self.install_stop_process.state() != QProcess.ProcessState.NotRunning
        ):
            return

        self.install_stop_requested = True
        if self.install_monitor_timer is not None:
            self.install_monitor_timer.stop()
        if not self.start_sh:
            logger.warning("PortProton start command is unavailable for stop")
            self.install_stop_requested = False
            return

        def on_stop_finished(exit_code: int, exit_status: QProcess.ExitStatus) -> None:
            if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
                self.install_stop_requested = False
                QMessageBox.warning(self, _("Error"), _("Failed to stop installation."))
            if self.install_stop_process:
                self.install_stop_process.deleteLater()
                self.install_stop_process = None

        def on_stop_error(error: QProcess.ProcessError) -> None:
            logger.error("Failed to execute PortProton stop command: %s", error)
            self.install_stop_requested = False
            if self.install_stop_process:
                self.install_stop_process.deleteLater()
                self.install_stop_process = None

        self.install_stop_process = QProcess(self)
        self.install_stop_process.finished.connect(on_stop_finished)
        self.install_stop_process.errorOccurred.connect(on_stop_error)
        self.install_stop_process.start(self.start_sh[0], self.start_sh[1:] + ["cli", "--stop"])

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

    def _parse_process_log_status(self) -> tuple[str | None, float | None, bool] | None:
        """Parse current launch download/extraction status from process.log."""
        user = os.getenv('USER', 'unknown')
        log_file = f"/tmp/PortProton_{user}/process.log"
        if not os.path.exists(log_file):
            return None

        try:
            with open(log_file, encoding='utf-8') as f:
                lines = f.readlines()
        except OSError as e:
            logger.error("Error parsing process log status: %s", e)
            return None

        status = percent = None
        launch_started = False
        for line in lines[-80:]:
            line_lower = line.lower()
            if "the prefix has been updated" in line_lower \
                    or "log wine:" in line_lower \
                    or "log from runtime and wine:" in line_lower:
                status = None
                percent = None
                launch_started = True
            elif "unpacking file:" in line_lower or "download" in line_lower:
                action = _("Extracting") if "unpacking file:" in line_lower else _("Downloading")
                launch_started = False
                percent = None
                if "plugins" in line_lower:
                    status = _("{0} Plugins...").format(action)
                elif "libs" in line_lower or "libraries" in line_lower:
                    status = _("{0} Libs...").format(action)
                elif "wine" in line_lower or "proton" in line_lower:
                    status = _("{0} Wine...").format(action)
                else:
                    status = _("{0} components...").format(action)

            matches = re.findall(r'([0-9]*\.?[0-9]+)%', line)
            if matches:
                percent = float(matches[-1])

        if status is None and percent is None and not launch_started:
            return None
        if status is None:
            if launch_started:
                status = None
            else:
                status = _("Preparing PortProton...")
        return status, percent, launch_started

    def monitor_install_progress(self):
        """Monitor /tmp/PortProton_$USER/process.log for progress."""
        state = self._parse_process_log_status()
        status = None
        percent = None
        if state is not None:
            status, percent, _ = state
        if percent is None:
            percent = self._parse_process_log_progress()
        if percent is None:
            self._set_install_button_progress_text(status=status)
            return
        try:
            if percent > 0:
                self.seen_progress = True
                self.current_percent = percent
                self._set_install_button_progress_text(status=status, percent=percent)
            elif self.seen_progress and percent == 0:
                self.current_percent = 100.0
                self._set_install_button_progress_text(status=status, percent=100.0)
                if self.install_monitor_timer is not None:
                    self.install_monitor_timer.stop()
            elif status:
                self._set_install_button_progress_text(status=status)
            if self.current_percent >= 100:
                if self.install_monitor_timer is not None:
                    self.install_monitor_timer.stop()
        except ValueError:
            pass  # Ignore invalid floats

    @Slot(int, int)
    def on_install_finished(self, exit_code: int, exit_status: int):
        """Handle installation finish."""
        if self.install_monitor_timer is not None:
            self.install_monitor_timer.stop()
            self.install_monitor_timer.deleteLater()
            self.install_monitor_timer = None
        if self.install_stop_requested:
            if self.install_process:
                self.install_process.deleteLater()
                self.install_process = None
            self._reset_install_state()
            return
        if exit_code == 0:
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
            QMessageBox.warning(self, _("Error"), f"Installation failed (code: {exit_code}).")

        if self.install_process:
            self.install_process.deleteLater()
            self.install_process = None
        self._reset_install_state()

    def on_install_error(self, error: QProcess.ProcessError):
        """Handle installation error."""
        if self.install_monitor_timer is not None:
            self.install_monitor_timer.stop()
            self.install_monitor_timer.deleteLater()
            self.install_monitor_timer = None
        if self.install_stop_requested:
            if self.install_process:
                self.install_process.deleteLater()
                self.install_process = None
            self._reset_install_state()
            return
        QMessageBox.warning(self, _("Error"), f"Process error: {error}")
        self._reset_install_state()

    @Slot(list)
    def on_games_loaded(self, games: list[tuple]):
        self.games = games
        self.game_library_manager.set_games(games)

        # Clear the refresh in progress flag
        if hasattr(self, '_refresh_in_progress'):
            self._refresh_in_progress = False

        # Re-enable the refresh button if it exists
        if hasattr(self, 'refreshButton'):
            self.refreshButton.setEnabled(True)
            self.refreshButton.setText(_("Refresh Grid"))

    def loadGames(self, force_load: bool = False):
        # Skip loading library if launching a specific exe
        if self.launch_exe and not force_load:
            return

        if force_load:
            self.launch_exe = None

        display_filter = game_config.get_display_filter()
        favorites = favorites_config.get_games()
        self.pending_games = []
        self.games = []

        def start_loading():
            if display_filter == "steam":
                self._load_steam_games_async(lambda games: self.games_loaded.emit(games))
            elif display_filter == "portproton":
                self._load_portproton_games_async(lambda games: self.games_loaded.emit(games))
            elif display_filter == "favorites":
                def on_all_games_favorites(portproton_games, steam_games):
                    games = [game for game in portproton_games + steam_games if game[0] in favorites]
                    self.games_loaded.emit(games)

                # Load games from different sources in parallel to prevent blocking
                results = {'portproton': [], 'steam': []}
                completed = {'portproton': False, 'steam': False}

                def check_completion():
                    if all(completed.values()):
                        QApplication.processEvents()  # Keep UI responsive
                        on_all_games_favorites(results['portproton'], results['steam'])

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

                self._load_portproton_games_async(portproton_callback)
                self._load_steam_games_async(steam_callback)
            else:
                # For 'all' filter - load games from different sources in parallel to prevent blocking
                results = {'portproton': [], 'steam': []}
                completed = {'portproton': False, 'steam': False}

                def on_all_games():
                    seen = set()
                    games = []
                    for game in results['portproton'] + results['steam']:
                        # Unique key: name + exec_line
                        key = (game[0], game[5])
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

                # Load all sources in parallel
                self._load_portproton_games_async(portproton_callback)
                self._load_steam_games_async(steam_callback)

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
                "steam",
                info.get("anticheat_slug", ""),
            ))
            processed_count += 1
            self.pending_games.append(None)
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
        processed_count = 0
        def on_desktop_processed(result: tuple | None, games=games):
            nonlocal processed_count
            if result:
                games.append(result)
            self.pending_games.append(None)
            processed_count += 1
            if processed_count == len(desktop_files):
                callback(games)
        with ThreadPoolExecutor() as executor:
            for file_path in desktop_files:
                executor.submit(self._process_desktop_file_async, file_path, on_desktop_processed)

    def _generate_missing_portproton_icon(self, game_exe: str, icon_path: str, desktop_name: str) -> str:
        if not self.portproton_location:
            return ""
        if not game_exe.lower().endswith(".exe") or not os.path.isfile(game_exe):
            return ""

        img_dir = os.path.join(self.portproton_location, "data", "img")
        os.makedirs(img_dir, exist_ok=True)
        target_path = ""

        if icon_path:
            expanded_icon = os.path.expanduser(icon_path)
            abs_icon = os.path.abspath(expanded_icon)
            abs_img_dir = os.path.abspath(img_dir)
            if abs_icon.startswith(abs_img_dir + os.sep):
                target_path = abs_icon
            elif not os.path.isabs(expanded_icon):
                icon_name = os.path.basename(expanded_icon)
                if not os.path.splitext(icon_name)[1]:
                    icon_name = f"{icon_name}.png"
                target_path = os.path.join(img_dir, icon_name)

        if not target_path:
            safe_name = os.path.basename(desktop_name) or os.path.splitext(os.path.basename(game_exe))[0]
            target_path = os.path.join(img_dir, f"{safe_name}.png")

        if os.path.isfile(target_path):
            return target_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        if generate_thumbnail(game_exe, target_path, size=128):
            return target_path
        return ""

    def _process_desktop_file_async(
        self,
        file_path: str,
        callback: Callable[[tuple | None], None],
        assets_checked: bool = False,
    ):
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
            game_exe = extract_exec_target_path(exec_line) or ""

        xdg_data_home = os.getenv("XDG_DATA_HOME",
                                os.path.join(os.path.expanduser("~"), ".local", "share"))
        user_custom_folder = os.path.join(xdg_data_home, "PortProtonQt", "custom_data")
        os.makedirs(user_custom_folder, exist_ok=True)

        user_cover = ""
        user_game_folder = ""
        generated_img_icon = ""
        economy_mode = ui_config.get_economy_mode()

        if game_exe:
            exe_name = os.path.splitext(os.path.basename(game_exe))[0]
            user_game_folder = os.path.join(user_custom_folder, exe_name)
            os.makedirs(user_game_folder, exist_ok=True)
            generated_img_icon = self._generate_missing_portproton_icon(
                game_exe, entry.get("Icon", ""), desktop_name
            )

            # Check if local game folder is empty and download assets if it is
            if not economy_mode and not assets_checked and not os.listdir(user_game_folder):
                logger.debug(f"Local folder for {exe_name} is empty, checking repository")
                def on_assets_downloaded(results):
                    if results["cover"]:
                        logger.info(f"Downloaded assets for {exe_name}: {results}")
                    if results["metadata"]:
                        logger.info(f"Downloaded metadata for {exe_name}: {results['metadata']}")
                    self._process_desktop_file_async(file_path, callback, assets_checked=True)
                self.portproton_api.download_game_assets_async(exe_name, timeout=5, callback=on_assets_downloaded)
                return

            user_files = set(os.listdir(user_game_folder)) if os.path.exists(user_game_folder) else set()
            for ext in COVER_IMAGE_EXTENSIONS:
                candidate = f"cover{ext}"
                if candidate in user_files:
                    user_cover = os.path.join(user_game_folder, candidate)
                    break

            # Read statistics
            if self.portproton_location:
                statistics_file = os.path.join(self.portproton_location, "data", "tmp", "statistics")
                try:
                    playtime_from_stats = get_playtime_for_exe(statistics_file, game_exe)
                    if playtime_from_stats is not None:
                        playtime_seconds = playtime_from_stats
                        formatted_playtime = format_playtime(playtime_seconds)
                except Exception as e:
                    logger.error(f"Failed to parse playtime data: {e}")

        def on_steam_info(steam_info: dict):
            # Get current language
            language_code = get_metadata_language()

            # Read translations from metadata.txt
            user_metadata_file = os.path.join(user_game_folder, "metadata.txt")

            translations = {'name': desktop_name, 'description': ''}
            if os.path.exists(user_metadata_file):
                translations = read_metadata_translations(user_metadata_file, language_code)

            final_name = translations['name']
            final_desc = translations['description'] or steam_info.get("description", "")
            final_cover = (
                user_cover if user_cover else
                steam_info.get("cover", "") or generated_img_icon or entry.get("Icon", "")
            )

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
                "portproton",
                steam_info.get("anticheat_slug", ""),
            ))

        if economy_mode:
            language_code = get_metadata_language()
            user_metadata_file = os.path.join(user_game_folder, "metadata.txt")
            translations = {'name': desktop_name, 'description': ''}
            if os.path.exists(user_metadata_file):
                translations = read_metadata_translations(user_metadata_file, language_code)
            cached_steam_info = get_cached_steam_game_info(desktop_name, exec_line)
            final_name = translations['name'] or cached_steam_info.get("name", "")
            final_desc = translations['description'] or cached_steam_info.get("description", "")
            final_cover = (
                user_cover or cached_steam_info.get("cover", "") or
                generated_img_icon or entry.get("Icon", "")
            )
            if not final_cover and game_exe and game_exe.lower().endswith(".exe") and os.path.exists(game_exe):
                xdg_cache_home = os.getenv(
                    "XDG_CACHE_HOME",
                    os.path.join(os.path.expanduser("~"), ".cache"),
                )
                icon_cache_dir = os.path.join(xdg_cache_home, "PortProtonQt", "images", "exe_icons")
                os.makedirs(icon_cache_dir, exist_ok=True)
                safe_exe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(game_exe))
                generated_cover_path = os.path.join(icon_cache_dir, f"{safe_exe_name}.png")
                if not os.path.exists(generated_cover_path):
                    if not generate_thumbnail(game_exe, generated_cover_path, size=128):
                        generated_cover_path = ""
                if generated_cover_path and os.path.exists(generated_cover_path):
                    final_cover = generated_cover_path
            callback((
                final_name,
                final_desc,
                final_cover,
                cached_steam_info.get("appid", ""),
                cached_steam_info.get("controller_support", ""),
                exec_line,
                get_last_launch(exe_name) if exe_name else _("Never"),
                formatted_playtime,
                "",
                "",
                get_last_launch_timestamp(exe_name) if exe_name else 0,
                playtime_seconds,
                "portproton",
                "",
            ))
            return

        get_steam_game_info_async(desktop_name, exec_line, on_steam_info)

    def _replace_game_from_desktop_file(self, file_path: str, old_name: str, old_exec_line: str):
        """Refresh one library card from its .desktop file."""
        def on_game_data(game_data: tuple | None):
            if not game_data:
                return
            self.game_library_manager.replace_game_incremental(old_name, old_exec_line, game_data)
            QTimer.singleShot(200, self.game_library_manager.load_visible_images)

        self._process_desktop_file_async(file_path, on_game_data)

    def finalize_game_loading(self):
        logger.info("Finalizing game loading, pending_games: %d", len(self.pending_games))
        if self.pending_games and all(x is None for x in self.pending_games):
            logger.info("All games processed, clearing pending_games")
            self.pending_games = []

    # TABS
    def switchVisibleTab(self, step: int) -> None:
        """Switch to the previous or next visible tab."""
        visible_indices = [
            i for i, btn in self.tabButtons.items()
            if btn.isVisible()
        ]
        visible_indices.sort()
        if not visible_indices:
            return

        current_index = self.stackedWidget.currentIndex()
        try:
            current_pos = visible_indices.index(current_index)
        except ValueError:
            current_pos = 0

        new_index = visible_indices[(current_pos + step) % len(visible_indices)]
        self.switchTab(new_index)

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

        current_index = self.stackedWidget.currentIndex()
        if hasattr(self, "game_library_manager"):
            mgr = self.game_library_manager
            if current_index == 0 and mgr.gamesListWidget and mgr.gamesListLayout:
                mgr.gamesListLayout.invalidate()
                mgr.gamesListWidget.adjustSize()
                mgr.gamesListWidget.updateGeometry()
        if current_index == self.auto_install_tab_index:
            if hasattr(self, "autoInstallContainer") and hasattr(self, "autoInstallContainerLayout"):
                self.autoInstallContainerLayout.invalidate()
                self.autoInstallContainer.adjustSize()
                self.autoInstallContainer.updateGeometry()

        if self.stackedWidget.currentIndex() == getattr(self, "system_tab_index", -1):
            QTimer.singleShot(0, self._focusSystemNetworkOnTabEnter)

    def createSearchWidget(self) -> tuple[QWidget, CustomLineEdit]:
        self.container = QWidget()
        self.container.setStyleSheet(self.theme.CONTAINER_STYLE)
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)

        self.GameLibraryTitle = QLabel(_("Game Library"))
        self.GameLibraryTitle.setStyleSheet(self.theme.INSTALLED_TAB_TITLE_STYLE)
        layout.addWidget(self.GameLibraryTitle)

        self.addGameButton = AutoSizeButton(_("Add Game"), icon=self.theme_manager.get_icon("addgame", as_path=True))
        self.addGameButton.setStyleSheet(self.theme.ADDGAME_BACK_BUTTON_STYLE)
        self.addGameButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.addGameButton.clicked.connect(self.openAddGameDialog)
        layout.addWidget(self.addGameButton)

        # Refresh button
        self.refreshButton = AutoSizeButton(_("Refresh Grid"), icon=self.theme_manager.get_icon("update", as_path=True))
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
            return

        # Mark that a refresh is in progress
        self._refresh_in_progress = True

        # Clear the search field to ensure all games are shown after refresh
        self.searchEdit.clear()

        # Disable the refresh button during refresh to prevent multiple clicks
        self.refreshButton.setEnabled(False)
        self.refreshButton.setText(_("Refreshing..."))

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
        QTimer.singleShot(50, lambda: self.loadGames(force_load=True))

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
                if url.toLocalFile().lower().endswith((".exe",) + DISC_IMAGE_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".exe",) + DISC_IMAGE_EXTENSIONS):
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
                self._write_desktop_file(desktop_entry, desktop_path)

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
                    if os.path.isfile(user_cover) and ext in COVER_IMAGE_EXTENSIONS:
                        copied_cover = os.path.join(custom_folder, f"cover{ext}")
                        shutil.copyfile(user_cover, copied_cover)
                        cover_path = copied_cover

                # Parse .desktop (adapt from _process_desktop_file_async)
                entry = parse_desktop_entry(desktop_path)
                if not entry:
                    return
                description = entry.get("Comment", "")
                exec_line = entry.get("Exec", exe_path)
                cover_for_shortcut = dialog.last_cover_path if dialog.last_cover_path else user_cover
                self._sync_game_shortcuts_from_dialog(dialog, name, exec_line, cover_for_shortcut)

                # User cover fallback
                user_cover_path = cover_path  # Already set if user provided

                # Statistics (playtime, last launch - defaults for new)
                playtime_seconds = 0
                formatted_playtime = format_playtime(playtime_seconds)
                last_played_timestamp = 0
                last_launch = _("Never")

                # Language for translations
                language_code = get_metadata_language()

                # Read translations from metadata.txt
                user_metadata_file = os.path.join(custom_folder, "metadata.txt")

                translations = {'name': name, 'description': description}
                if os.path.exists(user_metadata_file):
                    translations = read_metadata_translations(user_metadata_file, language_code)

                final_name = translations['name']
                final_desc = translations['description']

                def on_steam_info(steam_info: dict):
                    nonlocal final_name, final_desc
                    # Adapt final_cover logic from _process_desktop_file_async
                    final_cover = (
                        user_cover_path
                        if user_cover_path
                        else steam_info.get("cover", "") or entry.get("Icon", "")
                    )

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
                        "portproton",
                        steam_info.get("anticheat_slug", ""),
                    )

                    # Incremental add
                    self.game_library_manager.add_game_incremental(game_data)

                    # Trigger visible images load
                    QTimer.singleShot(200, self.game_library_manager.load_visible_images)

                from portprotonqt.steam_api import get_steam_game_info_async
                if ui_config.get_economy_mode():
                    cached_steam_info = get_cached_steam_game_info(final_name, exec_line)
                    game_data = (
                        final_name,
                        final_desc or cached_steam_info.get("description", ""),
                        user_cover_path or cached_steam_info.get("cover", "") or entry.get("Icon", ""),
                        cached_steam_info.get("appid", ""),
                        cached_steam_info.get("controller_support", ""),
                        exec_line,
                        last_launch,
                        formatted_playtime,
                        cached_steam_info.get("protondb_tier", ""),
                        cached_steam_info.get("anticheat_status", ""),
                        last_played_timestamp,
                        playtime_seconds,
                        "portproton",
                        cached_steam_info.get("anticheat_slug", ""),
                    )
                    self.game_library_manager.add_game_incremental(game_data)
                    QTimer.singleShot(200, self.game_library_manager.load_visible_images)
                else:
                    get_steam_game_info_async(final_name, exec_line, on_steam_info)

    def _sync_game_shortcuts_from_dialog(self, dialog, game_name, exec_line, cover_path):
        """Apply shortcut options selected in add/edit game dialog."""
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        menu_path = os.path.join(applications_dir, f"{game_name}.desktop")
        if dialog.add_to_menu_checkbox.isChecked():
            if not os.path.exists(menu_path):
                self.context_menu_manager.add_to_menu(game_name, exec_line)
        elif os.path.exists(menu_path):
            self.context_menu_manager.remove_from_menu(game_name)

        desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        if dialog.add_to_desktop_checkbox.isChecked():
            if not os.path.exists(desktop_path):
                self.context_menu_manager.add_to_desktop(game_name, exec_line)
        elif os.path.exists(desktop_path):
            self.context_menu_manager.remove_from_desktop(game_name)

        is_in_steam = is_game_in_steam(game_name)
        if dialog.add_to_steam_checkbox.isChecked():
            if not is_in_steam:
                self.context_menu_manager.add_to_steam(game_name, exec_line, cover_path)
        elif is_in_steam:
            self.context_menu_manager.remove_from_steam(game_name, exec_line, "portproton")

    def createAutoInstallTab(self):
        autoInstallPage = QWidget()
        autoInstallPage.setStyleSheet(self.theme.LIBRARY_WIDGET_STYLE)
        autoInstallLayout = QVBoxLayout(autoInstallPage)
        autoInstallLayout.setSpacing(15)

        searchWidget = QWidget()
        searchWidget.setStyleSheet(self.theme.CONTAINER_STYLE)
        searchLayout = QHBoxLayout(searchWidget)
        searchLayout.setContentsMargins(0, 6, 0, 0)
        searchLayout.setSpacing(10)

        titleLabel = QLabel(_("Auto Install"))
        titleLabel.setStyleSheet(self.theme.INSTALLED_TAB_TITLE_STYLE)
        searchLayout.addWidget(titleLabel)
        searchLayout.addStretch()

        self.autoInstallSearchLineEdit = CustomLineEdit(self, theme=self.theme)
        icon: QIcon = cast(QIcon, self.theme_manager.get_icon("search"))
        action_pos = QLineEdit.ActionPosition.LeadingPosition
        self.autoInstallSearchLineEdit.addAction(icon, action_pos)
        self.autoInstallSearchLineEdit.setMaximumWidth(200)
        self.autoInstallSearchLineEdit.setPlaceholderText(_("Find Games ..."))
        self.autoInstallSearchLineEdit.setClearButtonEnabled(True)
        self.autoInstallSearchLineEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE)
        self.autoInstallSearchLineEdit.textChanged.connect(self.filterAutoInstallGames)
        searchLayout.addWidget(self.autoInstallSearchLineEdit)
        autoInstallLayout.addWidget(searchWidget)

        self.autoInstallScrollArea = QScrollArea()
        self.autoInstallScrollArea.setWidgetResizable(True)
        self.autoInstallScrollArea.setStyleSheet(self.theme.SCROLL_STYLE + self.theme.TRANSPARENT_BACKGROUND_STYLE)
        QScroller.grabGesture(self.autoInstallScrollArea.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        self.autoInstallContainer = QWidget()
        self.autoInstallContainer.setStyleSheet(self.theme.LIST_WIDGET_STYLE)
        self.autoInstallContainerLayout = FlowLayout(self.autoInstallContainer)
        self.autoInstallContainer.setLayout(self.autoInstallContainerLayout)
        self.autoInstallScrollArea.setWidget(self.autoInstallContainer)

        autoInstallLayout.addWidget(self.autoInstallScrollArea)

        self.auto_size_slider = QSlider(Qt.Orientation.Horizontal, autoInstallPage)
        self.auto_size_slider.setMinimum(200)
        self.auto_size_slider.setMaximum(250)
        self.auto_size_slider.setValue(self.auto_card_width)
        self.auto_size_slider.setTickInterval(10)
        self.auto_size_slider.setFixedWidth(150)
        self.auto_size_slider.setToolTip(f"{self.auto_card_width} px")
        self.auto_size_slider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        self.auto_size_slider.sliderReleased.connect(self.on_auto_slider_released)

        sliderLayout = QHBoxLayout()
        sliderLayout.addStretch()
        sliderLayout.addWidget(self.auto_size_slider)
        autoInstallLayout.addLayout(sliderLayout)

        auto_layout_mode = str(getattr(self.theme, "LIBRARY_LAYOUT_MODE", "grid")).lower()
        self.auto_size_slider.setVisible(auto_layout_mode != "list")
        if auto_layout_mode == "list":
            self.auto_card_width = self.auto_size_slider.maximum()
            self.auto_size_slider.setValue(self.auto_card_width)
            self.auto_size_slider.setToolTip(f"{self.auto_card_width} px")

        # Store cards
        self.autoInstallGameCards = {}
        self.allAutoInstallCards = []
        self.autoInstallLoaded = False
        self.autoInstallLoading = False

        # Load games
        def on_autoinstall_games_loaded(games: list[tuple]):
            self.autoInstallLoaded = True
            self.autoInstallLoading = False
            economy_mode = ui_config.get_economy_mode()

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
                theme_cover = self.theme_manager.get_theme_image(exe_name, self.current_theme_name)
                has_theme_cover = isinstance(theme_cover, str) and "autoinstall_covers" in theme_cover
                if auto_layout_mode == "list" and has_theme_cover:
                    cover_path = theme_cover
                elif not cover_path:
                    if has_theme_cover:
                        cover_path = theme_cover
                    elif economy_mode:
                        classic_cover = self.theme_manager.get_theme_image(exe_name, "classic")
                        if isinstance(classic_cover, str) and "autoinstall_covers" in classic_cover:
                            cover_path = classic_cover

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
                    if card.list_layout:
                        theme_cover = self.theme_manager.get_theme_image(exe_name, self.current_theme_name)
                        if isinstance(theme_cover, str) and "autoinstall_covers" in theme_cover:
                            return
                    card.cover_path = local_path
                    cover_width = 64 if card.list_layout else self.auto_card_width
                    cover_height = cover_width if card.list_layout else int(self.auto_card_width * 1.5)
                    load_pixmap_async(local_path, cover_width, cover_height, card.on_cover_loaded)

            def batch_metadata_callback(exe_name, local_path):
                logger.debug(f"Metadata callback called for {exe_name}: {local_path}")
                if local_path and os.path.exists(local_path):
                    try:
                        self._update_card_name_from_metadata(exe_name, local_path)
                        logger.info(f"Updated metadata for {exe_name}")
                    except Exception as e:
                        logger.error(f"Error updating card metadata for {exe_name}: {e}")

            if exe_names_to_load and not economy_mode:
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
        auto_layout_mode = str(getattr(self.theme, "LIBRARY_LAYOUT_MODE", "grid")).lower()
        if hasattr(self, 'auto_size_slider') and self.auto_size_slider:
            if auto_layout_mode != "list":
                self.auto_card_width = self.auto_size_slider.value()
            self.auto_size_slider.setToolTip(f"{self.auto_card_width} px")
            if auto_layout_mode != "list":
                ui_config.set_auto_card_width(self.auto_card_width)
        if not hasattr(self, 'allAutoInstallCards'):
            return
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
        self._normalize_prefix_directories(prefixes_path)

        if not os.path.exists(dist_path):
            return

        formLayout = QFormLayout()
        formLayout.setContentsMargins(0, 10, 0, 0)
        formLayout.setSpacing(self.theme.wineSettingsSetSpacing)
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.wine_versions = sorted([d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))], key=version_sort_key)
        for version in self._get_lg_versions_from_var():
            if version not in self.wine_versions:
                self.wine_versions.append(version)
        self.wine_versions.sort(key=version_sort_key)
        self.wineCombo = QComboBox()
        self.wineCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.wineCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.wineCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.wineCombo.addItems(self.wine_versions)
        self.wineCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.wineCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.wineTitleLabel = QLabel("WINE/Proton:")
        self.wineTitleLabel.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.wineTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if self.wine_versions:
            self.wineCombo.setCurrentIndex(0)
        formLayout.addRow(self.wineTitleLabel, self.wineCombo)

        self.prefixes = sorted([d for d in os.listdir(prefixes_path) if os.path.isdir(os.path.join(prefixes_path, d))], key=prefix_sort_key) if os.path.exists(prefixes_path) else []
        self.prefixCombo = QComboBox()
        self.prefixCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.prefixCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.prefixCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.prefixCombo.addItems(self.prefixes)
        self.prefixCombo.setEditable(True)
        self.prefixCombo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        prefix_line_edit = self.prefixCombo.lineEdit()
        if prefix_line_edit is not None:
            prefix_line_edit.setPlaceholderText(_("Enter prefix name"))
        self.prefixCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
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
            row = i // 2
            col = i % 2
            btn = AutoSizeButton(text, update_size=False)
            btn.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if callback:
                btn.clicked.connect(callback)
            additional_grid.addWidget(btn, row, col)

        for col in range(2):
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
        raw_prefix = self.prefixCombo.currentText().strip()
        prefix = re.sub(r"[ \t]", "_", raw_prefix).upper() if raw_prefix else ""
        if not wine or not prefix:
            return
        if not self.portproton_location or not self.start_sh:
            return
        env_vars = os.environ.copy()
        self._check_missing_prefix_by_name_before_launch(prefix, env_vars)
        start_sh = self.start_sh
        cmd = start_sh + ["cli", cli_arg, wine, prefix]

        # Show progress bar before launch
        self.wine_progress_bar.setVisible(True)

        proc = QProcess(self)
        process_env = QProcessEnvironment.systemEnvironment()
        if env_vars.get("DISABLE_CP_DEFPFX") == "1":
            process_env.insert("DISABLE_CP_DEFPFX", "1")
        else:
            process_env.remove("DISABLE_CP_DEFPFX")
        proc.setProcessEnvironment(process_env)
        proc.finished.connect(lambda exitCode: self._on_wine_tool_finished(exitCode, cli_arg))
        proc.errorOccurred.connect(lambda error: self._on_wine_tool_error(error, cli_arg))
        proc.start(cmd[0], cmd[1:])

        if not proc.waitForStarted(5000):
            self.wine_progress_bar.setVisible(False)
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
                if hasattr(self, 'wine_monitor_timer') and self.wine_monitor_timer is not None:
                    self.wine_monitor_timer.stop()
                    self.wine_monitor_timer.deleteLater()
                    self.wine_monitor_timer = None
                logger.info(f"Wine tool {target_exe} started successfully")
                return

    def _on_wine_tool_finished(self, exitCode, cli_arg):
        """Handle Wine utility completion."""
        self.wine_progress_bar.setVisible(False)
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
        selected_prefix = self.prefixCombo.currentText().strip()
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

        self.clear_process = QProcess(self)
        self.clear_process.finished.connect(lambda exitCode: self._on_clear_prefix_finished(exitCode))
        self.clear_process.errorOccurred.connect(lambda error: self._on_clear_prefix_error(error))
        cmd = start_sh + ["cli", "--clear_pfx", selected_wine, selected_prefix]
        self.clear_process.start(cmd[0], cmd[1:])

        if not self.clear_process.waitForStarted(5000):
            self.wine_progress_bar.setVisible(False)
            QMessageBox.warning(self, _("Error"), _("Failed to start prefix clear process."))
            return

    def _on_clear_prefix_finished(self, exitCode):
        self.wine_progress_bar.setVisible(False)
        if exitCode == 0:
            QMessageBox.information(self, _("Success"), _("Prefix cleared successfully."))
        else:
            QMessageBox.warning(self, _("Error"), _("Prefix clear failed with exit code {}.").format(exitCode))

    def _on_clear_prefix_error(self, error):
        self.wine_progress_bar.setVisible(False)
        QMessageBox.warning(self, _("Error"), _("Failed to run clear prefix command: {}").format(error))

    def create_prefix_backup(self):
        selected_prefix = self.prefixCombo.currentText().strip()
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
        selected_prefix = self.prefixCombo.currentText().strip()
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
        for version in self._get_lg_versions_from_var():
            if version not in self.wine_versions:
                self.wine_versions.append(version)
        self.wine_versions.sort(key=version_sort_key)
        self.wineCombo.clear()
        self.wineCombo.addItems(self.wine_versions)

    def refresh_prefix_combo(self):
        """Refresh the prefix combo box when prefixes directory changes."""
        if not self.portproton_location:
            return

        current_prefix = self.prefixCombo.currentText().strip()
        normalized_current_prefix = re.sub(r"[ \t]", "_", current_prefix).upper() if current_prefix else ""
        prefixes_path = os.path.join(self.portproton_location, "data", "prefixes")
        if not os.path.exists(prefixes_path):
            return

        self._normalize_prefix_directories(prefixes_path)

        # Update the prefixes list with sorting
        self.prefixes = sorted([d for d in os.listdir(prefixes_path) if os.path.isdir(os.path.join(prefixes_path, d))], key=prefix_sort_key)
        self.prefixCombo.clear()
        self.prefixCombo.addItems(self.prefixes)
        if normalized_current_prefix:
            self.prefixCombo.setCurrentText(normalized_current_prefix)

    def _normalize_prefix_directories(self, prefixes_path):
        if not os.path.isdir(prefixes_path):
            return

        for prefix_name in os.listdir(prefixes_path):
            current_path = os.path.join(prefixes_path, prefix_name)
            if not os.path.isdir(current_path):
                continue

            normalized_name = re.sub(r"[ \t]", "_", prefix_name).upper()
            if normalized_name == prefix_name:
                continue

            normalized_path = os.path.join(prefixes_path, normalized_name)
            if os.path.isdir(normalized_path):
                logger.warning(
                    "Cannot rename prefix %s to %s: target already exists",
                    prefix_name,
                    normalized_name
                )
                continue

            try:
                os.rename(current_path, normalized_path)
            except OSError as exc:
                logger.warning("Failed to rename prefix %s: %s", prefix_name, exc)

    def open_winetricks(self):
        """Open the Winetricks dialog for the selected prefix and wine."""
        selected_prefix = self.prefixCombo.currentText().strip()
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
        self.settingsScrollArea.setStyleSheet(self.theme.SCROLL_STYLE + self.theme.TRANSPARENT_BACKGROUND_STYLE)
        self.settingsScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        # Disable horizontal scroll
        self.settingsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        QScroller.grabGesture(self.settingsScrollArea.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        scrollWidget = QWidget()
        scrollWidget.setStyleSheet(self.theme.TRANSPARENT_BACKGROUND_STYLE)
        scrollLayout = QVBoxLayout(scrollWidget)
        scrollLayout.setContentsMargins(0, 0, 10, 0)
        scrollLayout.setSpacing(10)  # Uniform spacing between sections

        # Helper to create styled sections
        def create_section(title_text, theme):
            section_frame = QFrame()
            section_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            section_frame.setStyleSheet(self.theme.SETTINGS_FRAME_STYLE)
            section_layout = QVBoxLayout(section_frame)
            section_layout.setContentsMargins(*theme.portProtonPageMargins)
            section_layout.setSpacing(theme.portProtonPageSectionHeaderSpacing)

            section_title = QLabel(title_text)
            section_title.setStyleSheet(self.theme.SETTINGS_FRAME_TITLE_STYLE)
            section_layout.addWidget(section_title)

            section_form = QFormLayout()
            section_form.setSpacing(10)
            section_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            section_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            section_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            section_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            section_form.setHorizontalSpacing(theme.portProtonPageHorizontalSpacing)
            section_form.setVerticalSpacing(theme.portProtonPageVerticalSpacing)
            section_layout.addLayout(section_form)
            return section_frame, section_form

        # 1. Library Settings Section
        genFrame, genForm = create_section(_("Library Settings"), self.theme)
        genForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(genFrame)

        self.timeDetailCombo = QComboBox()
        self.timeDetailCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.timeDetailCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.timeDetailCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.time_keys = ["detailed", "brief"]
        self.time_labels = [_("Detailed"), _("Brief")]
        self.timeDetailCombo.addItems(self.time_labels)
        self.timeDetailCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.timeDetailCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.timeDetailTitle = QLabel(_("Time Detail Level:"))
        self.timeDetailTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.timeDetailTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.timeDetailTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = ui_config.get_time_detail_level()
        try:
            idx = self.time_keys.index(current)
        except ValueError:
            idx = 0
        self.timeDetailCombo.setCurrentIndex(idx)
        genForm.addRow(self.timeDetailTitle, self.timeDetailCombo)

        self.gamesSortCombo = QComboBox()
        self.gamesSortCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.gamesSortCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.gamesSortCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sort_keys = ["last_launch", "playtime", "alphabetical"]
        self.sort_labels = [_("Last launch"), _("Playtime"), _("Alphabetical")]
        self.gamesSortCombo.addItems(self.sort_labels)
        self.gamesSortCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.gamesSortCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamesSortTitle = QLabel(_("Games Sort Method:"))
        self.gamesSortTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.gamesSortTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.gamesSortTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = game_config.get_sort_method()
        try:
            idx = self.sort_keys.index(current)
        except ValueError:
            idx = 0
        self.gamesSortCombo.setCurrentIndex(idx)
        genForm.addRow(self.gamesSortTitle, self.gamesSortCombo)

        self.filter_keys = ["all", "steam", "portproton", "favorites"]
        self.filter_labels = [_("All"), "Steam", "PortProton", _("Favorites")]
        self.gamesDisplayCombo = QComboBox()
        self.gamesDisplayCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.gamesDisplayCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.gamesDisplayCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.gamesDisplayCombo.addItems(self.filter_labels)
        self.gamesDisplayCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.gamesDisplayCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamesDisplayTitle = QLabel(_("Games Display Filter:"))
        self.gamesDisplayTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.gamesDisplayTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.gamesDisplayTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = game_config.get_display_filter()
        try:
            idx = self.filter_keys.index(current)
        except ValueError:
            idx = 0
        self.gamesDisplayCombo.setCurrentIndex(idx)
        genForm.addRow(self.gamesDisplayTitle, self.gamesDisplayCombo)

        self.badge_view_keys = ["detailed", "compact", "hidden"]
        self.badge_view_labels = [_("Detailed"), _("Compact"), _("Hidden")]
        self.badgeViewCombo = QComboBox()
        self.badgeViewCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.badgeViewCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.badgeViewCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.badgeViewCombo.addItems(self.badge_view_labels)
        self.badgeViewCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.badgeViewCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.badgeViewTitle = QLabel(_("Badge View Type:"))
        self.badgeViewTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.badgeViewTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.badgeViewTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = ui_config.get_badge_view_mode()
        try:
            idx = self.badge_view_keys.index(current)
        except ValueError:
            idx = 0
        self.badgeViewCombo.setCurrentIndex(idx)
        if ui_config.get_economy_mode():
            self.badgeViewCombo.setCurrentIndex(self.badge_view_keys.index("hidden"))
            self.badgeViewCombo.setEnabled(False)
        genForm.addRow(self.badgeViewTitle, self.badgeViewCombo)

        # 2. Interface Settings Section
        uiFrame, uiForm = create_section(_("Interface Settings"), self.theme)
        uiForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(uiFrame)

        self.tray_menu_mode_keys = ["compact", "detailed"]
        self.tray_menu_mode_labels = [_("Compact"), _("Detailed")]
        self.trayMenuModeCombo = QComboBox()
        self.trayMenuModeCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.trayMenuModeCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.trayMenuModeCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.trayMenuModeCombo.addItems(self.tray_menu_mode_labels)
        self.trayMenuModeCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.trayMenuModeCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.trayMenuModeTitle = QLabel(_("Tray Menu Type:"))
        self.trayMenuModeTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.trayMenuModeTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.trayMenuModeTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current = display_config.get_tray_menu_mode()
        try:
            idx = self.tray_menu_mode_keys.index(current)
        except ValueError:
            idx = 0
        self.trayMenuModeCombo.setCurrentIndex(idx)
        uiForm.addRow(self.trayMenuModeTitle, self.trayMenuModeCombo)

        self.fullscreenCheckBox = QCheckBox()  # Removed text
        self.fullscreenCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.fullscreenCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fullscreenTitle = QLabel(_("Launch Application in Fullscreen"))
        self.fullscreenTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.fullscreenTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.fullscreenTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_fullscreen = display_config.get_fullscreen()
        self.fullscreenCheckBox.setChecked(current_fullscreen)
        fullscreen_layout = QHBoxLayout()
        fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        fullscreen_layout.addWidget(self.fullscreenCheckBox)
        fullscreen_layout.addWidget(self.fullscreenTitle)
        fullscreen_layout.addStretch()
        uiForm.addRow(fullscreen_layout)

        self.minimizeToTrayCheckBox = QCheckBox()  # Removed text
        self.minimizeToTrayCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.minimizeToTrayCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.minimizeToTrayTitle = QLabel(_("Minimize to tray on close"))
        self.minimizeToTrayTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.minimizeToTrayTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.minimizeToTrayTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_minimize_to_tray = display_config.get_minimize_to_tray()
        self.minimizeToTrayCheckBox.setChecked(current_minimize_to_tray)
        self.minimizeToTrayCheckBox.toggled.connect(lambda checked: display_config.set_minimize_to_tray(checked))
        minimize_layout = QHBoxLayout()
        minimize_layout.setContentsMargins(0, 0, 0, 0)
        minimize_layout.addWidget(self.minimizeToTrayCheckBox)
        minimize_layout.addWidget(self.minimizeToTrayTitle)
        minimize_layout.addStretch()
        uiForm.addRow(minimize_layout)

        self.autostartCheckBox = QCheckBox()
        self.autostartCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.autostartCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.autostartTitle = QLabel(_("Run at system startup"))
        self.autostartTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.autostartTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.autostartTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.autostartCheckBox.setChecked(display_config.get_autostart_enabled())
        autostart_layout = QHBoxLayout()
        autostart_layout.setContentsMargins(0, 0, 0, 0)
        autostart_layout.addWidget(self.autostartCheckBox)
        autostart_layout.addWidget(self.autostartTitle)
        autostart_layout.addStretch()
        uiForm.addRow(autostart_layout)

        self.startMinimizedCheckBox = QCheckBox()
        self.startMinimizedCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.startMinimizedCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.startMinimizedTitle = QLabel(_("Start in tray"))
        self.startMinimizedTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.startMinimizedTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.startMinimizedTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.startMinimizedCheckBox.setChecked(display_config.get_start_minimized())
        start_minimized_layout = QHBoxLayout()
        start_minimized_layout.setContentsMargins(0, 0, 0, 0)
        start_minimized_layout.addWidget(self.startMinimizedCheckBox)
        start_minimized_layout.addWidget(self.startMinimizedTitle)
        start_minimized_layout.addStretch()
        uiForm.addRow(start_minimized_layout)

        self.hideAutoInstallTabCheckBox = QCheckBox()  # Removed text
        self.hideAutoInstallTabCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.hideAutoInstallTabCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hideAutoInstallTabTitle = QLabel(_("Hide Auto-Install Tab"))
        self.hideAutoInstallTabTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.hideAutoInstallTabTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.hideAutoInstallTabTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_hide_autoinstall = ui_config.get_hide_autoinstall_tab()
        self.hideAutoInstallTabCheckBox.setChecked(current_hide_autoinstall)
        self.hideAutoInstallTabCheckBox.toggled.connect(lambda checked: ui_config.set_hide_autoinstall_tab(checked))
        hide_autoinstall_layout = QHBoxLayout()
        hide_autoinstall_layout.setContentsMargins(0, 0, 0, 0)
        hide_autoinstall_layout.addWidget(self.hideAutoInstallTabCheckBox)
        hide_autoinstall_layout.addWidget(self.hideAutoInstallTabTitle)
        hide_autoinstall_layout.addStretch()
        uiForm.addRow(hide_autoinstall_layout)

        self.steamCompatCheckBox = QCheckBox()
        self.steamCompatCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.steamCompatCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.steamCompatTitle = QLabel(_("Add to Steam compatibility tools"))
        self.steamCompatTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.steamCompatTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.steamCompatTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_steam_compat = is_steam_compat_tool_installed()
        self.steamCompatCheckBox.setChecked(current_steam_compat)
        steam_compat_layout = QHBoxLayout()
        steam_compat_layout.setContentsMargins(0, 0, 0, 0)
        steam_compat_layout.addWidget(self.steamCompatCheckBox)
        steam_compat_layout.addWidget(self.steamCompatTitle)
        steam_compat_layout.addStretch()
        uiForm.addRow(steam_compat_layout)

        if get_steam_compatibilitytools_dir() is not None:
            self.downloadWineToSteamCheckBox = QCheckBox()
            self.downloadWineToSteamCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
            self.downloadWineToSteamCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.downloadWineToSteamTitle = QLabel(_("Download WINE/Proton to Steam"))
            self.downloadWineToSteamTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.downloadWineToSteamTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
            self.downloadWineToSteamTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.downloadWineToSteamCheckBox.setChecked(ui_config.get_download_wine_to_steam())
            download_wine_to_steam_layout = QHBoxLayout()
            download_wine_to_steam_layout.setContentsMargins(0, 0, 0, 0)
            download_wine_to_steam_layout.addWidget(self.downloadWineToSteamCheckBox)
            download_wine_to_steam_layout.addWidget(self.downloadWineToSteamTitle)
            download_wine_to_steam_layout.addStretch()
            uiForm.addRow(download_wine_to_steam_layout)

        self.economyModeCheckBox = QCheckBox()
        self.economyModeCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.economyModeCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.economyModeTitle = QLabel(_("Economy mode"))
        self.economyModeTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.economyModeTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.economyModeTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.economyModeCheckBox.setChecked(ui_config.get_economy_mode())
        def update_economy_controls(enabled: bool):
            if enabled:
                self.badgeViewCombo.setCurrentIndex(self.badge_view_keys.index("hidden"))
                self.badgeViewCombo.setEnabled(False)
                return
            self.badgeViewCombo.setEnabled(True)

        self.economyModeCheckBox.toggled.connect(update_economy_controls)
        update_economy_controls(self.economyModeCheckBox.isChecked())
        economy_mode_layout = QHBoxLayout()
        economy_mode_layout.setContentsMargins(0, 0, 0, 0)
        economy_mode_layout.addWidget(self.economyModeCheckBox)
        economy_mode_layout.addWidget(self.economyModeTitle)
        economy_mode_layout.addStretch()
        uiForm.addRow(economy_mode_layout)

        self.forceSystemDpiCheckBox = QCheckBox()
        self.forceSystemDpiCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.forceSystemDpiCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.forceSystemDpiTitle = QLabel(_("Force system DPI for Wine"))
        self.forceSystemDpiTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.forceSystemDpiTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.forceSystemDpiTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_force_dpi = get_user_conf_setting('PW_FORCE_SYSTEM_DPI')
        self.forceSystemDpiCheckBox.setChecked(str(current_force_dpi) == "1")
        force_system_dpi_layout = QHBoxLayout()
        force_system_dpi_layout.setContentsMargins(0, 0, 0, 0)
        force_system_dpi_layout.addWidget(self.forceSystemDpiCheckBox)
        force_system_dpi_layout.addWidget(self.forceSystemDpiTitle)
        force_system_dpi_layout.addStretch()
        uiForm.addRow(force_system_dpi_layout)

        # 3. Gamepad Settings Section
        padFrame, padForm = create_section(_("Gamepad Settings"), self.theme)
        padForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(padFrame)

        self.autoFullscreenGamepadCheckBox = QCheckBox()  # Removed text
        self.autoFullscreenGamepadCheckBox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.autoFullscreenGamepadCheckBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.autoFullscreenGamepadTitle = QLabel(_("Auto Fullscreen on Gamepad connected"))
        self.autoFullscreenGamepadTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.autoFullscreenGamepadTitle.setStyleSheet(self.theme.SETTINGS_TITLE_CHECKBOX_STYLE)
        self.autoFullscreenGamepadTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        current_auto_fullscreen = display_config.get_auto_fullscreen_gamepad()
        self.autoFullscreenGamepadCheckBox.setChecked(current_auto_fullscreen)
        auto_fullscreen_layout = QHBoxLayout()
        auto_fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        auto_fullscreen_layout.addWidget(self.autoFullscreenGamepadCheckBox)
        auto_fullscreen_layout.addWidget(self.autoFullscreenGamepadTitle)
        auto_fullscreen_layout.addStretch()
        padForm.addRow(auto_fullscreen_layout)

        # 4. Hardware Settings Section
        hwFrame, hwForm = create_section(_("Hardware Settings"), self.theme)
        hwForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(hwFrame)

        filtered_gpu_list = get_selectable_gpu_list()
        hwFrame.setVisible(len(filtered_gpu_list) != 1)
        if len(filtered_gpu_list) > 1:
            self.gpuCombo = QComboBox()
            self.gpuCombo.view().window().setWindowFlags(
                Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            )
            self.gpuCombo.view().window().setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground
            )
            self.gpuCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.gpuCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.gpuCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
            self.gpuCombo.addItems(filtered_gpu_list)
            current_gpu = get_user_conf_setting('PW_GPU_USE')
            if current_gpu and current_gpu != "disabled" and current_gpu in filtered_gpu_list:
                self.gpuCombo.setCurrentText(current_gpu)
            elif current_gpu and current_gpu != "disabled":
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
        elif not filtered_gpu_list:
            hwForm.addRow(QLabel(_("No GPUs found")), QLabel(""))

        # 5. Proxy Settings Section
        proxyFrame, proxyForm = create_section(_("Proxy Settings"), self.theme)
        proxyForm.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        scrollLayout.addWidget(proxyFrame)

        self.proxyUrlEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyUrlEdit.setPlaceholderText(_("Proxy URL"))
        self.proxyUrlEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.proxyUrlEdit.setStyleSheet(self.theme.LINE_EDIT_STYLE)
        self.proxyUrlEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.proxyUrlTitle = QLabel(_("Proxy URL:"))
        self.proxyUrlTitle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.proxyUrlTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        self.proxyUrlTitle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        proxy_cfg = proxy_config.get_proxy()
        if proxy_cfg.get("http", ""):
            self.proxyUrlEdit.setText(proxy_cfg["http"])
        proxyForm.addRow(self.proxyUrlTitle, self.proxyUrlEdit)

        self.proxyUserEdit = CustomLineEdit(self, theme=self.theme)
        self.proxyUserEdit.setPlaceholderText(_("Proxy Username"))
        self.proxyUserEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.proxyUserEdit.setStyleSheet(self.theme.LINE_EDIT_STYLE)
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
        self.proxyPasswordEdit.setStyleSheet(self.theme.LINE_EDIT_STYLE)
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

        self.saveButton = AutoSizeButton(_("Save Settings"), icon=self.theme_manager.get_icon("save", as_path=True))
        self.saveButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.saveButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.saveButton.clicked.connect(self.savePortProtonSettings)
        buttonsLayout.addWidget(self.saveButton)

        self.resetSettingsButton = AutoSizeButton(_("Reset Settings"), icon=self.theme_manager.get_icon("update", as_path=True))
        self.resetSettingsButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.resetSettingsButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.resetSettingsButton.clicked.connect(self.resetSettings)
        buttonsLayout.addWidget(self.resetSettingsButton)

        self.migrateShortcutsButton = AutoSizeButton(_("Migrate legacy shortcuts"), icon=self.theme_manager.get_icon("update", as_path=True))
        self.migrateShortcutsButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.migrateShortcutsButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.migrateShortcutsButton.clicked.connect(self.migrateLegacyShortcuts)
        buttonsLayout.addWidget(self.migrateShortcutsButton)

        self.clearCacheButton = AutoSizeButton(_("Clear Cache"), icon=self.theme_manager.get_icon("update", as_path=True))
        self.clearCacheButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.clearCacheButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clearCacheButton.clicked.connect(self.clearCache)
        buttonsLayout.addWidget(self.clearCacheButton)

        layout.addLayout(buttonsLayout)
        self.stackedWidget.addWidget(self.portProtonWidget)

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
            reset_main_config()
            # Restart application
            QTimer.singleShot(1000, lambda: self.restart_application())

    def migrateLegacyShortcuts(self):
        """Migrate legacy shortcuts after user confirmation."""
        portproton_location = get_portproton_location()
        if not portproton_location:
            QMessageBox.warning(self, _("Error"), _("PortProton directory not found"))
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Migrate legacy shortcuts"))
        msg_box.setText(_("Migrate old PortProton shortcuts to PortProtonQt format?"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return

        migrated = migrate_legacy_shortcut(portproton_location)
        logger.info("Migrated legacy shortcuts: %d", migrated)

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
            cache_config.clear_cache()

    def applySettingsDelayed(self):
        ui_config.get_time_detail_level()
        self.games = []
        self.loadGames()
        display_filter = game_config.get_display_filter()
        for card in self.game_library_manager.game_card_cache.values():
            card.update_badge_visibility(display_filter)

    def savePortProtonSettings(self):
        previous_economy_mode = ui_config.get_economy_mode()
        time_idx = self.timeDetailCombo.currentIndex()
        time_key = self.time_keys[time_idx]
        ui_config.set_time_detail_level(time_key)

        sort_idx = self.gamesSortCombo.currentIndex()
        sort_key = self.sort_keys[sort_idx]
        game_config.set_sort_method(sort_key)

        filter_idx = self.gamesDisplayCombo.currentIndex()
        filter_key = self.filter_keys[filter_idx]
        economy_mode = self.economyModeCheckBox.isChecked()
        ui_config.set_economy_mode(economy_mode)
        economy_mode_changed = previous_economy_mode != economy_mode
        game_config.set_display_filter(filter_key)
        badge_view_idx = self.badgeViewCombo.currentIndex()
        badge_view_mode = self.badge_view_keys[badge_view_idx]
        if economy_mode:
            badge_view_mode = "hidden"
        ui_config.set_badge_view_mode(badge_view_mode)

        proxy_url = self.proxyUrlEdit.text().strip()
        proxy_user = self.proxyUserEdit.text().strip()
        proxy_password = self.proxyPasswordEdit.text().strip()
        proxy_config.set_proxy(proxy_url, proxy_user, proxy_password)

        fullscreen = self.fullscreenCheckBox.isChecked()
        display_config.set_fullscreen(fullscreen)

        auto_fullscreen_gamepad = self.autoFullscreenGamepadCheckBox.isChecked()
        display_config.set_auto_fullscreen_gamepad(auto_fullscreen_gamepad)

        autostart_enabled = self.autostartCheckBox.isChecked()
        display_config.set_autostart_enabled(autostart_enabled)
        if not apply_xdg_autostart(autostart_enabled):
            QMessageBox.warning(self, _("Error"), _("Failed to update xdg-autostart entry."))

        start_minimized = self.startMinimizedCheckBox.isChecked()
        display_config.set_start_minimized(start_minimized)

        tray_menu_mode_idx = self.trayMenuModeCombo.currentIndex()
        tray_menu_mode = self.tray_menu_mode_keys[tray_menu_mode_idx]
        display_config.set_tray_menu_mode(tray_menu_mode)

        steam_compat = self.steamCompatCheckBox.isChecked()
        currently_installed = is_steam_compat_tool_installed()
        if steam_compat and not currently_installed:
            add_steam_compat_tool()
        elif not steam_compat and currently_installed:
            remove_steam_compat_tool()

        if hasattr(self, 'downloadWineToSteamCheckBox'):
            ui_config.set_download_wine_to_steam(self.downloadWineToSteamCheckBox.isChecked())

        # Save GPU selection to user.conf (only if the combo box exists)
        if hasattr(self, 'gpuCombo') and self.gpuCombo.count() > 1:
            selected_gpu = self.gpuCombo.currentText()
            set_user_conf_setting('PW_GPU_USE', selected_gpu)
        if hasattr(self, 'forceSystemDpiCheckBox'):
            if self.forceSystemDpiCheckBox.isChecked():
                system_dpi = get_system_dpi_for_wine(get_user_conf_setting('PW_SCREEN_RESOLUTION'))
                set_user_conf_setting('PW_FORCE_SYSTEM_DPI', "1")
                set_user_conf_setting('PW_WINE_DPI_VALUE', system_dpi)
            else:
                set_user_conf_setting('PW_FORCE_SYSTEM_DPI', "0")

        # Get hide auto-install tab setting
        hide_autoinstall = self.hideAutoInstallTabCheckBox.isChecked()

        if hasattr(self, 'input_manager'):
            self.updateControlHints()
            if hasattr(self, 'keyboard'):
                self.keyboard.update_keyboard()

        if economy_mode_changed:
            if self.game_library_manager.gamesListLayout is not None:
                self.game_library_manager.clear_layout(self.game_library_manager.gamesListLayout)
        else:
            for card in self.game_library_manager.game_card_cache.values():
                card.update_badge_visibility(filter_key)
                card.update_badge_view_mode(badge_view_mode)

        if (
            self.currentDetailPage
            and self.current_exec_line
            and self.stackedWidget.currentWidget() is self.currentDetailPage
        ):
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
                    "anticheat_slug": current_game[13] if len(current_game) > 13 else "",
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
        ui_config.set_hide_autoinstall_tab(hide_autoinstall)

    def createThemeTab(self):
        """Themes tab"""
        self.themeTabWidget = QWidget()
        self.themeTabWidget.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE + self.theme.THEME_TAB_FOCUS_STYLE)
        self.themeTabWidget.setObjectName("otherPage")
        mainLayout = QVBoxLayout(self.themeTabWidget)
        mainLayout.setContentsMargins(10, 14, 10, 10)
        mainLayout.setSpacing(10)

        # 1. Top line: Title and theme list
        self.themeTabHeaderLayout = QHBoxLayout()

        self.themeTabTitleLabel = QLabel(_("Select Theme:"))
        self.themeTabTitleLabel.setObjectName("tabTitle")
        self.themeTabTitleLabel.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        self.themeTabTitleLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.themeTabHeaderLayout.addWidget(self.themeTabTitleLabel)

        self.themesCombo = QComboBox()
        self.themesCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.themesCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.themesCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themesCombo.setObjectName("themeTabCombo")
        self.themesCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        theme_names = self.theme_manager.get_available_themes()
        available_themes = ui_config.get_theme_bases(theme_names)
        current_theme_base = ui_config.get_theme_base()
        if current_theme_base in available_themes:
            available_themes.remove(current_theme_base)
            available_themes.insert(0, current_theme_base)
        self.themesCombo.addItems(available_themes)
        self.themeTabHeaderLayout.addWidget(self.themesCombo)

        self.themeVariantCombo = QComboBox()
        self.themeVariantCombo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.themeVariantCombo.view().window().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.themeVariantCombo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.themeVariantCombo.setObjectName("themeVariantCombo")
        self.themeVariantCombo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeVariantCombo.addItem(_("Dark"), "dark")
        self.themeVariantCombo.addItem(_("Light"), "light")
        self.themeVariantCombo.addItem(_("Auto"), "auto")
        current_variant = ui_config.get_theme_variant()
        variant_index = self.themeVariantCombo.findData(current_variant)
        if variant_index >= 0:
            self.themeVariantCombo.setCurrentIndex(variant_index)
        self.themeTabHeaderLayout.addWidget(self.themeVariantCombo)
        self.themeTabHeaderLayout.addStretch(1)

        mainLayout.addLayout(self.themeTabHeaderLayout)

        def hasThemeVariants(theme_name: str) -> bool:
            return ui_config.resolve_theme(theme_name, "dark") != ui_config.resolve_theme(theme_name, "light")

        def updateThemeVariantVisibility(*_args: object) -> None:
            self.themeVariantCombo.setVisible(hasThemeVariants(self.themesCombo.currentText()))

        # 2. Screenshots carousel
        self.screenshotsCarousel = ImageCarousel([])
        self.screenshotsCarousel.setStyleSheet(self.theme.CAROUSEL_WIDGET_STYLE)
        self.screenshotsCarousel.setObjectName("themeScreenshotsCarousel")
        self.screenshotsCarousel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.screenshotsCarousel.prevArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.screenshotsCarousel.nextArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        mainLayout.addWidget(self.screenshotsCarousel, stretch=1)

        # 3. Theme info
        self.themeInfoLayout = QVBoxLayout()
        self.themeInfoLayout.setSpacing(10)

        self.themeMetainfoLabel = QLabel()
        self.themeMetainfoLabel.setWordWrap(True)
        self.themeMetainfoLabel.setOpenExternalLinks(True)
        self.themeMetainfoLabel.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.themeMetainfoLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.themeInfoLayout.addWidget(self.themeMetainfoLabel)

        self.applyButton = AutoSizeButton(_("Apply Theme"), icon=self.theme_manager.get_icon("apply", as_path=True))
        self.applyButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.applyButton.setObjectName("themeApplyButton")
        self.applyButton.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.themeInfoLayout.addWidget(self.applyButton)

        mainLayout.addLayout(self.themeInfoLayout)

        # Preview update function
        def updateThemePreview(*_args: object) -> None:
            updateThemeVariantVisibility()
            base_theme = self.themesCombo.currentText()
            variant = self.themeVariantCombo.currentData() or "light"
            theme_name = ui_config.resolve_theme(base_theme, variant)
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

            screenshots = load_theme_screenshots(theme_name)
            if screenshots:
                self.screenshotsCarousel.update_images([
                    (pixmap, caption)
                    for pixmap, caption in screenshots
                ])
                self.screenshotsCarousel.show()
            else:
                self.screenshotsCarousel.hide()

        updateThemePreview()
        self.themesCombo.currentTextChanged.connect(updateThemePreview)
        self.themeVariantCombo.currentTextChanged.connect(updateThemePreview)

        # Theme apply logic
        def on_apply() -> None:
            selected_theme = ui_config.resolve_theme(
                self.themesCombo.currentText(),
                self.themeVariantCombo.currentData() or "light",
            )
            if selected_theme:
                theme_module = self.theme_manager.apply_theme(selected_theme)
                if theme_module:
                    ui_config.set_theme(selected_theme)
                    ui_config.set_theme_variant(self.themeVariantCombo.currentData() or "light")
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

        self.applyButton.clicked.connect(on_apply)

        # Add widget to stackedWidget
        self.theme_tab_index = self.stackedWidget.addWidget(self.themeTabWidget)

    def restart_application(self):
        """Restart application."""
        if not self.isFullScreen():
            window_config.set_geometry(self.width(), self.height())
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
                        logger.info("Restoring to theme tab")
                        theme_index = getattr(self, "theme_tab_index", -1)
                        if theme_index >= 0 and self.stackedWidget.count() > theme_index:
                            self.switchTab(theme_index)
                        else:
                            logger.warning("Theme tab is not available yet")
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

    def resolve_launch_file_path(self, file_path: str | None) -> str | None:
        """Resolve launch path to actual executable path for settings/logs."""
        if not file_path:
            return None
        normalized = os.path.abspath(os.path.expanduser(file_path))
        if normalized.lower().endswith(DISC_IMAGE_EXTENSIONS):
            resolved = self._resolve_iso_executable(normalized)
            if resolved:
                return resolved
            return None
        return normalized

    def open_exe_settings(self, exe_path, appid=None, game_source=None):
        """Open the ExeSettingsDialog for the given executable."""
        resolved_exe_path = self.resolve_launch_file_path(exe_path)
        if not resolved_exe_path or not os.path.exists(resolved_exe_path):
            QMessageBox.warning(self, _("Error"), _("Executable not found: {0}").format(exe_path))
            return
        dialog = ExeSettingsDialog(
            self, self.theme, resolved_exe_path, appid=appid, game_source=game_source
        )
        dialog.exec()

    def openGameDetailPage(self, game_data: dict) -> None:
        """Open game detail page."""
        self.detail_page_manager.openGameDetailPage(game_data)

    def _write_desktop_file(self, desktop_entry: str, desktop_path: str) -> None:
        """Write desktop file with executable permissions."""
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(desktop_entry)
        os.chmod(desktop_path, 0o755)
        logger.info("Created desktop file: %s", desktop_path)

    def handle_launch_exe(self, exe_path: str) -> None:
        """Handle launching a supported file from CLI.

        If the game exists in the library, open its detail page.
        If not, open detail page without creating a shortcut automatically.

        Args:
            exe_path: Full path to the launch file (.exe or disc image)
        """
        # Normalize the exe path
        exe_path = os.path.abspath(exe_path)
        exe_name = os.path.splitext(os.path.basename(exe_path))[0]
        economy_mode = ui_config.get_economy_mode()

        xdg_data_home = os.getenv(
            "XDG_DATA_HOME",
            os.path.join(os.path.expanduser("~"), ".local", "share")
        )
        user_game_folder = os.path.join(
            xdg_data_home,
            "PortProtonQt",
            "custom_data",
            exe_name
        )

        local_cover_path = ""
        if os.path.isdir(user_game_folder):
            for ext in COVER_IMAGE_EXTENSIONS:
                candidate_cover = os.path.join(user_game_folder, f"cover{ext}")
                if os.path.exists(candidate_cover):
                    local_cover_path = candidate_cover
                    break

        generated_cover_path = ""
        if not local_cover_path and os.path.isfile(exe_path) and exe_path.lower().endswith(".exe"):
            xdg_cache_home = os.getenv(
                "XDG_CACHE_HOME",
                os.path.join(os.path.expanduser("~"), ".cache")
            )
            icon_cache_dir = os.path.join(xdg_cache_home, "PortProtonQt", "images", "exe_icons")
            os.makedirs(icon_cache_dir, exist_ok=True)
            safe_exe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(exe_path))
            generated_cover_path = os.path.join(icon_cache_dir, f"{safe_exe_name}.png")
            if not os.path.exists(generated_cover_path):
                if not generate_thumbnail(exe_path, generated_cover_path, size=128):
                    generated_cover_path = ""
            if generated_cover_path and not os.path.exists(generated_cover_path):
                generated_cover_path = ""

        # Check if the game already exists in the library
        existing_entry = find_game_by_exe(exe_path)

        if existing_entry:
            # Game exists - open detail page
            game_name = existing_entry.get("Name", _("Unknown Game"))
            icon_path = existing_entry.get("Icon", "")
            exec_line = existing_entry.get("Exec", "")
            if economy_mode:
                cached_steam_info = get_cached_steam_game_info(game_name, exec_line)
                game_data = {
                    "name": game_name,
                    "description": cached_steam_info.get("description", ""),
                    "cover_path": local_cover_path or cached_steam_info.get("cover", "") or generated_cover_path or icon_path,
                    "appid": cached_steam_info.get("appid", ""),
                    "controller_support": cached_steam_info.get("controller_support", ""),
                    "exec_line": exec_line,
                    "last_launch": _("Never"),
                    "formatted_playtime": "0:00",
                    "protondb_tier": cached_steam_info.get("protondb_tier", ""),
                    "anticheat_status": cached_steam_info.get("anticheat_status", ""),
                    "game_source": "portproton",
                    "anticheat_slug": cached_steam_info.get("anticheat_slug", ""),
                }
                self.openGameDetailPage(game_data)
                return

            # Get Steam game info asynchronously to fetch appid, cover, etc.
            def on_steam_info(steam_info: dict):
                steam_cover_path = ""
                sgdb_cover_path = ""
                steam_info_cover = steam_info.get("cover", "")
                is_steam_game = steam_info.get("steam_game", "false") == "true"
                if is_steam_game:
                    steam_cover_path = steam_info_cover
                    appid = str(steam_info.get("appid", "")).strip()
                    if not steam_cover_path and appid:
                        steam_cover_path = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
                else:
                    sgdb_cover_path = steam_info_cover

                final_cover_path = local_cover_path or steam_cover_path or sgdb_cover_path or generated_cover_path or icon_path

                if not (local_cover_path or steam_cover_path or sgdb_cover_path):
                    def on_sgdb_cover(cover: str) -> None:
                        game_data = {
                            "name": game_name,
                            "description": steam_info.get("description", ""),
                            "cover_path": local_cover_path or steam_cover_path or cover or generated_cover_path or icon_path,
                            "appid": steam_info.get("appid", ""),
                            "controller_support": steam_info.get("controller_support", ""),
                            "exec_line": exec_line,
                            "last_launch": _("Never"),
                            "formatted_playtime": "0:00",
                            "protondb_tier": steam_info.get("protondb_tier", ""),
                            "anticheat_status": steam_info.get("anticheat_status", ""),
                            "game_source": "portproton",
                            "anticheat_slug": steam_info.get("anticheat_slug", ""),
                        }
                        self.openGameDetailPage(game_data)

                    fetch_sgdb_cover_async(game_name, on_sgdb_cover)
                    return

                game_data = {
                    "name": game_name,
                    "description": steam_info.get("description", ""),
                    "cover_path": final_cover_path,
                    "appid": steam_info.get("appid", ""),
                    "controller_support": steam_info.get("controller_support", ""),
                    "exec_line": exec_line,
                    "last_launch": _("Never"),
                    "formatted_playtime": "0:00",
                    "protondb_tier": steam_info.get("protondb_tier", ""),
                    "anticheat_status": steam_info.get("anticheat_status", ""),
                    "game_source": "portproton",
                    "anticheat_slug": steam_info.get("anticheat_slug", ""),
                }
                # Open detail page for the newly added game
                self.openGameDetailPage(game_data)

            get_steam_game_info_async(game_name, exec_line, on_steam_info)
        else:
            # Game not found in library: open detail page without creating .desktop file
            game_name_from_exe = os.path.splitext(os.path.basename(exe_path))[0]
            direct_exec_line = shlex.quote(exe_path)
            if economy_mode:
                cached_steam_info = get_cached_steam_game_info(game_name_from_exe, direct_exec_line)
                game_data = {
                    "name": game_name_from_exe,
                    "description": cached_steam_info.get("description", ""),
                    "cover_path": local_cover_path or cached_steam_info.get("cover", "") or generated_cover_path,
                    "appid": cached_steam_info.get("appid", ""),
                    "controller_support": cached_steam_info.get("controller_support", ""),
                    "exec_line": direct_exec_line,
                    "last_launch": _("Never"),
                    "formatted_playtime": "0:00",
                    "protondb_tier": cached_steam_info.get("protondb_tier", ""),
                    "anticheat_status": cached_steam_info.get("anticheat_status", ""),
                    "game_source": "portproton",
                    "anticheat_slug": cached_steam_info.get("anticheat_slug", ""),
                }
                self.openGameDetailPage(game_data)
                return

            def on_steam_info_missing(steam_info: dict):
                steam_cover_path = ""
                sgdb_cover_path = ""
                steam_info_cover = steam_info.get("cover", "")
                is_steam_game = steam_info.get("steam_game", "false") == "true"
                if is_steam_game:
                    steam_cover_path = steam_info_cover
                    appid = str(steam_info.get("appid", "")).strip()
                    if not steam_cover_path and appid:
                        steam_cover_path = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg"
                else:
                    sgdb_cover_path = steam_info_cover

                final_cover_path = local_cover_path or steam_cover_path or sgdb_cover_path or generated_cover_path

                if not (local_cover_path or steam_cover_path or sgdb_cover_path):
                    def on_sgdb_cover(cover: str) -> None:
                        game_data = {
                            "name": game_name_from_exe,
                            "description": steam_info.get("description", ""),
                            "cover_path": local_cover_path or steam_cover_path or cover or generated_cover_path,
                            "appid": steam_info.get("appid", ""),
                            "controller_support": steam_info.get("controller_support", ""),
                            "exec_line": direct_exec_line,
                            "last_launch": _("Never"),
                            "formatted_playtime": "0:00",
                            "protondb_tier": steam_info.get("protondb_tier", ""),
                            "anticheat_status": steam_info.get("anticheat_status", ""),
                            "game_source": "portproton",
                            "anticheat_slug": steam_info.get("anticheat_slug", ""),
                        }
                        self.openGameDetailPage(game_data)

                    fetch_sgdb_cover_async(game_name_from_exe, on_sgdb_cover)
                    return

                game_data = {
                    "name": game_name_from_exe,
                    "description": steam_info.get("description", ""),
                    "cover_path": final_cover_path,
                    "appid": steam_info.get("appid", ""),
                    "controller_support": steam_info.get("controller_support", ""),
                    "exec_line": direct_exec_line,
                    "last_launch": _("Never"),
                    "formatted_playtime": "0:00",
                    "protondb_tier": steam_info.get("protondb_tier", ""),
                    "anticheat_status": steam_info.get("anticheat_status", ""),
                    "game_source": "portproton",
                    "anticheat_slug": steam_info.get("anticheat_slug", ""),
                }
                self.openGameDetailPage(game_data)

            get_steam_game_info_async(game_name_from_exe, direct_exec_line, on_steam_info_missing)


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
        child_running = self._has_running_game_process()

        if target_running or (self.game_launch_started and child_running):
            self.game_launch_started = True
            # Game started - set flag, update button to "Stop"
            if self.current_running_button is not None:
                try:
                    self.current_running_button.setText(_("Stop"))
                    icon = self.theme_manager.get_icon("stop", as_path=True)
                    self.current_running_button.setIcon(icon)
                except RuntimeError:
                    self.current_running_button = None
                #self._inhibit_screensaver()
        elif self.monitor_wine_download_progress():
            # Dependencies are downloading/extracting - update button with progress
            if self.current_running_button is not None:
                try:
                    status = self.wine_download_status
                    if self.wine_download_percent > 0:
                        status = status.replace("...", f"... {int(self.wine_download_percent)}%")
                    self.current_running_button.setText(status)
                    icon = self.theme_manager.get_icon("save", as_path=True)
                    self.current_running_button.setIcon(icon)
                except RuntimeError:
                    pass
        elif child_running:
            if self.current_running_button is not None:
                try:
                    self.current_running_button.setText(_("Stop"))
                    icon = self.theme_manager.get_icon("stop", as_path=True)
                    self.current_running_button.setIcon(icon)
                except RuntimeError:
                    self.current_running_button = None
        elif not child_running:
            # Game completed - reset flag, reset button and stop timer
            self.resetPlayButton()
            #self._uninhibit_screensaver()
            if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
                self.checkProcessTimer.stop()
                self.checkProcessTimer.deleteLater()
                self.checkProcessTimer = None

    def monitor_wine_download_progress(self) -> bool:
        """Monitor /tmp/PortProton_$USER/process.log for dependency progress.

        Returns:
            bool: True if dependency setup is in progress, False otherwise.
        """
        state = self._parse_process_log_status()
        if state is None:
            return False
        try:
            status, percent, launch_started = state
            if launch_started:
                self.game_launch_started = True
                return False
            if status is None:
                return False
            logger.debug("Launch dependency progress: %s %s", status, percent)
            self.wine_download_status = status
            if percent is None:
                self.wine_download_seen = True
                self.wine_download_percent = 0.0
                return True
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
                icon = self.theme_manager.get_icon("play", as_path=True)
                self.current_running_button.setIcon(icon)
            except RuntimeError:
                pass
            self.current_running_button = None
        self.target_exe = None
        # Reset dependency setup monitoring
        self.wine_download_seen = False
        self.wine_download_percent = 0.0
        self.wine_download_status = _("Downloading Wine...")
        self.game_launch_started = False
        self.game_processes = [proc for proc in self.game_processes if proc.poll() is None]
        if not getattr(self, "_animated_covers_suspended", False):
            self.input_manager.resume_gamepad_polling()

    def _has_running_game_process(self) -> bool:
        return any(proc.poll() is None for proc in self.game_processes)

    def _terminate_game_processes(self) -> None:
        for proc in self.game_processes:
            if proc.poll() is not None:
                continue
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                continue
            except OSError as e:
                logger.warning("Failed to terminate game process group %s: %s", proc.pid, e)

    def _run_portproton_stop_command(self) -> bool:
        """Run PortProton CLI stop command."""
        if not self.start_sh:
            logger.warning("PortProton start command is unavailable for stop")
            return False

        if not QProcess.startDetached(self.start_sh[0], self.start_sh[1:] + ["cli", "--stop"]):
            logger.error("Failed to execute PortProton stop command")
            return False

        return True

    def stop_running_game(self, button=None) -> bool:
        """Stop current game via PortProton CLI stop command."""
        if button is not None:
            self.current_running_button = button

        if not self._run_portproton_stop_command():
            return False

        self._terminate_game_processes()
        self.game_processes = []
        if hasattr(self, 'checkProcessTimer') and self.checkProcessTimer is not None:
            self.checkProcessTimer.stop()
            self.checkProcessTimer.deleteLater()
            self.checkProcessTimer = None
        self.resetPlayButton()
        return True

    def _check_missing_prefix_by_name_before_launch(self, prefix_name: str, env_vars: dict[str, str]) -> None:
        """Check prefix presence and optionally disable default recommended libs."""
        if not prefix_name or not self.portproton_location:
            return

        prefix_path = os.path.join(self.portproton_location, "data", "prefixes", prefix_name)
        if os.path.isdir(prefix_path):
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Prefix not found"))
        msg_box.setText(_("Prefix '{0}' was not found. Install recommended libraries?").format(prefix_name))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.No:
            env_vars["DISABLE_CP_DEFPFX"] = "1"

    def _check_missing_prefix_before_launch(self, game_exe_path: str, env_vars: dict[str, str]) -> None:
        """Check game prefix and optionally disable default recommended libs."""
        if not game_exe_path:
            return

        prefix_name = get_prefix_name(game_exe_path)
        self._check_missing_prefix_by_name_before_launch(prefix_name, env_vars)

    def _resolve_iso_launch_parts(self, iso_path: str) -> list[str] | None:
        """Resolve executable and launch arguments from disc image autorun.inf."""
        return self.disc_image_manager.resolve_iso_launch_parts(iso_path)

    def _resolve_iso_executable(self, iso_path: str) -> str | None:
        """Resolve executable for disc image by reading [autorun] open= in autorun.inf."""
        return self.disc_image_manager.resolve_iso_executable(iso_path)

    def _get_game_name_for_exec_line(self, exec_line: str) -> str:
        for game in self.games:
            if len(game) > 5 and game[5] == exec_line and game[0]:
                return str(game[0])
        return ""

    def toggleGame(self, exec_line, button=None, game_name=None):
        # Handle Steam games
        if exec_line.startswith("steam://"):
            url = QUrl(exec_line)
            QDesktopServices.openUrl(url)
            return

        # Handle PortProton games
        entry_exec_split = shlex.split(exec_line)
        if not entry_exec_split:
            QMessageBox.warning(self, _("Error"), _("Invalid command format (empty exec line)"))
            return
        launch_cmd = entry_exec_split
        file_to_check = extract_exec_target_path(entry_exec_split)
        if not file_to_check:
            QMessageBox.warning(self, _("Error"), _("Invalid command format (native)"))
            return

        first_exec_part = os.path.expanduser(entry_exec_split[0])
        if file_to_check.lower().endswith(DISC_IMAGE_EXTENSIONS):
            resolved_iso_parts = self._resolve_iso_launch_parts(file_to_check)
            if not resolved_iso_parts:
                QMessageBox.warning(
                    self,
                    _("Error"),
                    _("Failed to launch game: {0}").format("autorun.inf or open executable not found")
                )
                return
            file_to_check = resolved_iso_parts[0]
            if not self.start_sh:
                QMessageBox.warning(self, _("Error"), _("PortProton start script not found"))
                return
            launch_cmd = self.start_sh + resolved_iso_parts
        elif self.start_sh and file_to_check.lower().endswith(".exe"):
            launch_file_parts = entry_exec_split if file_to_check == first_exec_part else [file_to_check]
            launch_cmd = self.start_sh + launch_file_parts

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
            if not self.stop_running_game(update_button):
                QMessageBox.warning(self, _("Error"), _("Failed to stop game"))
        else:
            # Save button reference for reset after game completion
            self.current_running_button = update_button
            self.target_exe = current_exe
            exe_name = os.path.splitext(current_exe)[0]
            env_vars = os.environ.copy()
            inhibit_game_name = game_name or self._get_game_name_for_exec_line(exec_line)
            if inhibit_game_name:
                env_vars["PW_INHIBIT_NAME"] = inhibit_game_name
            game_exe_for_prefix = file_to_check if file_to_check.lower().endswith(".exe") else ""
            self._check_missing_prefix_before_launch(game_exe_for_prefix, env_vars)

            # Launch game
            try:
                process = subprocess.Popen(launch_cmd, env=env_vars, shell=False, preexec_fn=os.setsid)
                self.game_processes.append(process)
                self.input_manager.suspend_gamepad_polling()
                save_last_launch(exe_name, datetime.now())
                if update_button:
                    try:
                        update_button.setText(_("Stop"))
                        icon = self.theme_manager.get_icon("stop", as_path=True)
                        update_button.setIcon(icon)
                    except RuntimeError:
                        pass

                # Reset dependency setup monitoring
                self.wine_download_seen = False
                self.wine_download_percent = 0.0
                self.wine_download_status = _("Downloading Wine...")
                self.game_launch_started = False

                self.checkProcessTimer = QTimer(self)
                self.checkProcessTimer.timeout.connect(self.checkTargetExe)
                self.checkProcessTimer.start(500)
            except Exception as e:
                logger.error(f"Failed to launch game {exe_name}: {e}")
                QMessageBox.warning(self, _("Error"), _("Failed to launch game: {0}").format(str(e)))

    def closeEvent(self, event):
        """Handle window close: check minimize_to_tray setting.
        If True - minimize to tray. Otherwise - fully close.
        """
        minimize_to_tray = display_config.get_minimize_to_tray()

        if minimize_to_tray:
            # Just minimize to tray
            event.ignore()
            self.hide()
            return

        # Full application close
        event.accept()

        # Hide and remove tray icon
        if hasattr(self, "tray_manager"):
            self.tray_manager.shutdown()

        # Save card sizes only for grid layouts.
        layout_mode = str(getattr(self.theme, "LIBRARY_LAYOUT_MODE", "grid")).lower()
        size_slider = getattr(self.game_library_manager, 'sizeSlider', None)
        if size_slider is None or layout_mode != "list":
            ui_config.set_card_width(self.card_width)
        if hasattr(self, 'auto_size_slider') and layout_mode != "list":
            ui_config.set_auto_card_width(self.auto_card_width)

        # Save window sizes (if not in fullscreen mode)
        if not display_config.get_fullscreen():
            logger.debug(f"Saving window geometry: {self.width()}x{self.height()}")
            window_config.set_geometry(self.width(), self.height())

        if self.game_processes:
            if not self.stop_running_game():
                logger.warning("Failed to stop running game during application shutdown")

        if self.install_process and self.install_process.state() != QProcess.ProcessState.NotRunning:
            if not self._run_portproton_stop_command():
                logger.warning("Failed to stop installation during application shutdown")

        self.disc_image_manager.cleanup_iso_rw_paths()
        self._stopBackgroundWorkers()

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
        language_code = get_metadata_language()
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
