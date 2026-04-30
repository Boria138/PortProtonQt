import os
import re
import subprocess

import psutil
from typing import Any

from PySide6.QtWidgets import QDialog, QMessageBox, QWidget, QStackedWidget, QSlider, QTableWidget, QApplication

from portprotonqt.config import ui_config
from portprotonqt.context_menu_manager import ContextMenuManager
from portprotonqt.dialogs import FileExplorer
from portprotonqt.input_manager import InputManager
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.tabs.control_hints import MainWindowControlHintsMixin
from portprotonqt.theme_manager import ThemeManager

logger = get_logger(__name__)
DISALLOWED_PORTDATA_FS_TYPES = {"exfat", "fat", "vfat", "msdos", "umsdos", "ncpfs", "iso9660"}
DISALLOWED_PORTDATA_FS_PATTERNS = (re.compile(r"^ntfs"),)


def _get_filesystem_type(path: str) -> str:
    """Get filesystem type for a path."""
    try:
        resolved_path = os.path.realpath(path)
        partitions = sorted(psutil.disk_partitions(all=True), key=lambda p: len(p.mountpoint), reverse=True)
        for partition in partitions:
            mount_point = partition.mountpoint.rstrip("/") or "/"
            if resolved_path == mount_point or resolved_path.startswith(mount_point + "/"):
                fs_type = partition.fstype.lower()
                if fs_type != "fuseblk" or not partition.device:
                    return fs_type

                result = subprocess.run(
                    ["lsblk", "-no", "FSTYPE", partition.device],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().lower()
                return fs_type
    except Exception:
        return ""
    return ""


def _is_disallowed_portdata_fs(path: str) -> bool:
    """Check if path is on a filesystem without Linux symlink support."""
    if not os.path.exists(path):
        path = os.path.dirname(path)
    fs_type = _get_filesystem_type(path)
    if not fs_type:
        return True
    logger.info("Creating PortProton data folder on filesystem type: %s", fs_type)
    return fs_type in DISALLOWED_PORTDATA_FS_TYPES or any(
        pattern.search(fs_type) for pattern in DISALLOWED_PORTDATA_FS_PATTERNS
    )


class _BootstrapStatusBar:
    """Minimal status bar object for bootstrap ContextMenuManager."""

    def showMessage(self, message: str, timeout: int = 0) -> None:
        return


class _BootstrapGameLibraryManager:
    """Minimal game library object for bootstrap ContextMenuManager."""

    def update_game_grid(self) -> None:
        return


class _BootstrapInputHost(MainWindowControlHintsMixin, QWidget):
    """Minimal host object for InputManager before MainWindow exists."""

    stackedWidget: QStackedWidget
    tabButtons: dict[int, QWidget]
    gamesListWidget: QWidget
    autoInstallContainer: QWidget | None
    currentDetailPage: QWidget | None
    current_exec_line: str | None
    current_add_game_dialog: Any
    game_library_manager: Any
    context_menu_manager: ContextMenuManager | None
    auto_size_slider: QSlider | None
    _status_bar: _BootstrapStatusBar

    def __init__(self):
        super().__init__()
        self.input_manager = None
        self.stackedWidget = QStackedWidget(self)
        self.tabButtons = {}
        self.gamesListWidget = QWidget(self)
        self.autoInstallContainer = None
        self.currentDetailPage = None
        self.current_exec_line = None
        self.current_add_game_dialog = None
        self.game_library_manager = _BootstrapGameLibraryManager()
        self.context_menu_manager = None
        self.auto_size_slider = None
        self._status_bar = _BootstrapStatusBar()

    def statusBar(self) -> _BootstrapStatusBar:
        return self._status_bar

    def activateFocusedWidget(self) -> None:
        return

    def goBackDetailPage(self, page: QWidget | None) -> None:
        return

    def switchTab(self, index: int) -> None:
        return

    def openAddGameDialog(self, exe_path: str | None = None) -> None:
        return

    def toggleGame(self, exec_line: str | None, button: QWidget | None = None) -> None:
        return

    def on_slider_released(self) -> None:
        return

    def on_auto_slider_released(self) -> None:
        return

    def refreshGames(self) -> None:
        return

    def handleSystemTableGamepadAction(self, table: QTableWidget, action: str) -> bool:
        return False

    def handleSystemGamepadAction(self, action: str) -> bool:
        return False

def ask_portdata_path() -> str | None:
    """Ask user to select PORT_DATA_PATH when autodetection failed."""
    default_path = os.path.join(os.path.expanduser("~"), "PortProtonQt")
    if not os.path.isdir(default_path):
        try:
            os.makedirs(default_path, exist_ok=True)
        except OSError:
            pass
    current_path = default_path if os.path.isdir(default_path) else os.path.expanduser("~")
    theme = ThemeManager().apply_theme(ui_config.get_theme())
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setStyle("Fusion")
        main_style = getattr(theme, "MAIN_WINDOW_STYLE", "")
        message_box_style = getattr(theme, "MESSAGE_BOX_STYLE", "")
        app.setStyleSheet(main_style + message_box_style)
    input_host = _BootstrapInputHost()
    input_manager = InputManager(input_host)
    input_host.input_manager = input_manager
    input_host.context_menu_manager = ContextMenuManager(
        input_host,
        None,
        theme,
        input_host.game_library_manager,
    )

    try:
        while True:
            selected_path: str | None = None
            file_explorer = FileExplorer(
                parent=input_host,
                theme=theme,
                initial_path=current_path,
                directory_only=True,
            )
            file_explorer.setWindowTitle(_("Choose PortProton data folder"))

            def on_path_selected(path: str) -> None:
                nonlocal selected_path
                selected_path = path

            file_explorer.file_signal.file_selected.connect(on_path_selected)
            dialog_result = file_explorer.exec()
            if dialog_result != QDialog.DialogCode.Accepted or not selected_path:
                return None
            if _is_disallowed_portdata_fs(selected_path):
                message_box = QMessageBox(file_explorer)
                message_box.setIcon(QMessageBox.Icon.Warning)
                message_box.setWindowTitle(_("Error"))
                message_box.setText(
                    _("Selected folder is on an unsupported filesystem. Choose another folder for PortProton data.")
                )
                main_style = getattr(file_explorer.theme, "MAIN_WINDOW_STYLE", "")
                message_box_style = getattr(file_explorer.theme, "MESSAGE_BOX_STYLE", "")
                message_box.setStyleSheet(main_style + message_box_style)
                message_box.exec()
                current_path = selected_path
                continue
            return os.path.normpath(selected_path)
    finally:
        input_manager.cleanup()
        input_host.deleteLater()
