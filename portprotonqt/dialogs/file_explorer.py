"""File Explorer dialog for PortProtonQt."""

import os
import tempfile
from collections.abc import Callable
from typing import cast, TYPE_CHECKING
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QScrollArea, QWidget, QScroller, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, QObject, Signal, QMimeDatabase, QThreadPool, QRunnable, Slot

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

from portprotonqt.config_utils import read_favorite_folders, read_theme_from_config
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.localization import _
from portprotonqt.dialogs.dialog_utils import create_dialog_hints_widget, update_dialog_hints
from portprotonqt.dialogs.base import generate_thumbnail, FileSelectedSignal

logger = get_logger(__name__)
theme_manager = ThemeManager()


class FileExplorer(QDialog):
    """File explorer dialog for selecting files and directories."""

    class ThumbnailLoader(QRunnable):
        """Class for asynchronous thumbnail loading in a separate thread."""

        class Signals(QObject):
            thumbnail_ready = Signal(str, QIcon)

        def __init__(
            self,
            file_path: str,
            mime_type: str,
            size=64,
            resolve_launch_file_path: Callable[[str | None], str | None] | None = None
        ):
            super().__init__()
            self.file_path = file_path
            self.mime_type = mime_type
            self.size = size
            self.resolve_launch_file_path = resolve_launch_file_path
            self.signals = self.Signals()

        @Slot()
        def run(self):
            """Performs thumbnail loading in a background thread."""
            try:
                if self.mime_type.startswith("image/"):
                    pixmap = QPixmap(self.file_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(self.size, self.size, Qt.AspectRatioMode.KeepAspectRatio)
                        self.signals.thumbnail_ready.emit(self.file_path, QIcon(scaled_pixmap))
                    else:
                        logger.warning("Failed to load image: %s", self.file_path)
                elif self.file_path.lower().endswith((".exe", ".iso")):
                    thumbnail_source = self.file_path
                    if self.file_path.lower().endswith(".iso") and callable(self.resolve_launch_file_path):
                        resolved_path = self.resolve_launch_file_path(self.file_path)
                        if not resolved_path or not os.path.isfile(resolved_path):
                            logger.warning("Failed to resolve executable in ISO for preview: %s", self.file_path)
                            return
                        thumbnail_source = resolved_path

                    if not thumbnail_source.lower().endswith(".exe"):
                        return

                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        if generate_thumbnail(thumbnail_source, tmp.name, size=self.size):
                            pixmap = QPixmap(tmp.name)
                            if not pixmap.isNull():
                                self.signals.thumbnail_ready.emit(self.file_path, QIcon(pixmap))
                            os.unlink(tmp.name)
                        else:
                            logger.warning("Failed to generate thumbnail for file: %s", self.file_path)
            except Exception as e:
                logger.error("Error loading thumbnail for %s: %s", self.file_path, str(e))

    def __init__(self, parent=None, theme=None, file_filter=None, initial_path=None, directory_only=False):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.file_signal = FileSelectedSignal()
        self.file_filter = file_filter
        self.directory_only = directory_only
        self.mime_db = QMimeDatabase()
        self.path_history = {}
        self.initial_path = initial_path
        self.thumbnail_cache = {}
        self.pending_thumbnails = set()
        self.main_window = None
        self.setup_ui()

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.input_manager = None
        self.context_menu_manager = None
        parent_obj = self.parent()
        while parent_obj:
            if hasattr(parent_obj, 'input_manager'):
                self.input_manager = cast("MainWindow", parent_obj).input_manager
                self.main_window = parent_obj
            if hasattr(parent_obj, 'context_menu_manager'):
                self.context_menu_manager = cast("MainWindow", parent_obj).context_menu_manager
            parent_obj = parent_obj.parent()

        if self.input_manager:
            self.input_manager.enable_file_explorer_mode(self)

        self.update_drives_list()

        self.current_path = os.path.expanduser("~") if not initial_path else os.path.normpath(initial_path)
        if initial_path and not os.path.isdir(self.current_path):
            self.current_path = os.path.expanduser("~")
        self.update_file_list()

        self.current_theme_name = read_theme_from_config()
        self.hints_widget, self.hints_labels = create_dialog_hints_widget(
            self.theme, self.main_window, self.input_manager, context='file_explorer'
        )
        self.main_layout.addWidget(self.hints_widget)

        if self.input_manager:
            self.input_manager.button_event.connect(
                lambda *args: update_dialog_hints(self.hints_labels, self.main_window, self.input_manager, theme_manager, self.current_theme_name)
            )
            self.input_manager.dpad_moved.connect(
                lambda *args: update_dialog_hints(self.hints_labels, self.main_window, self.input_manager, theme_manager, self.current_theme_name)
            )
            update_dialog_hints(self.hints_labels, self.main_window, self.input_manager, theme_manager, self.current_theme_name)

    def async_load_thumbnails(self, files, mime_db):
        """Asynchronously loads thumbnails for a list of files."""
        thread_pool = QThreadPool.globalInstance()
        thread_pool.setMaxThreadCount(4)

        for f in files:
            file_path = os.path.join(self.current_path, f)
            if file_path in self.thumbnail_cache or file_path in self.pending_thumbnails:
                continue
            mime_type = mime_db.mimeTypeForFile(file_path).name()
            if mime_type.startswith("image/") or file_path.lower().endswith((".exe", ".iso")):
                self.pending_thumbnails.add(file_path)
                resolver = None
                main_window = cast("MainWindow | None", self.main_window)
                if main_window and hasattr(main_window, "resolve_launch_file_path"):
                    resolver = main_window.resolve_launch_file_path
                loader = self.ThumbnailLoader(file_path, mime_type, size=64, resolve_launch_file_path=resolver)
                loader.signals.thumbnail_ready.connect(self.update_thumbnail)
                thread_pool.start(loader)

    @Slot(str, QIcon)
    def update_thumbnail(self, file_path, icon):
        """Updates the icon for a file list item after thumbnail loading."""
        try:
            self.thumbnail_cache[file_path] = icon
            self.pending_thumbnails.discard(file_path)
            file_name = os.path.basename(file_path)
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item.text() == file_name:
                    item.setIcon(icon)
                    break
        except Exception as e:
            logger.error("Error updating thumbnail for %s: %s", file_path, str(e))

    def load_visible_thumbnails(self):
        """Load thumbnails only for visible items in the file list."""
        try:
            visible_range = self.file_list.count()
            first_visible = max(0, self.file_list.indexAt(self.file_list.viewport().rect().topLeft()).row())
            last_visible = min(visible_range - 1, self.file_list.indexAt(self.file_list.viewport().rect().bottomRight()).row() + 5)

            files_to_load = []
            for i in range(first_visible, last_visible + 1):
                item = self.file_list.item(i)
                if not item:
                    continue
                file_name = item.text()
                if file_name.endswith("/"):
                    continue
                file_path = os.path.join(self.current_path, file_name)
                if file_path not in self.thumbnail_cache and file_path not in self.pending_thumbnails:
                    files_to_load.append(file_name)

            if files_to_load:
                self.async_load_thumbnails(files_to_load, self.mime_db)
        except Exception as e:
            logger.error("Error loading visible thumbnails: %s", str(e))

    def get_mounted_drives(self):
        """Retrieve a list of mounted drives from /proc/mounts, excluding system paths."""
        mounted_drives = []
        try:
            with open('/proc/mounts') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                    mount_point = parts[1]
                    if (mount_point.startswith(('/dev', '/sys', '/proc', '/tmp', '/snap', '/var/lib')) or
                        (mount_point.startswith('/run') and not mount_point.startswith('/run/media'))):
                        continue
                    if os.path.isdir(mount_point) and os.access(mount_point, os.R_OK):
                        mounted_drives.append(mount_point)
            return sorted(mounted_drives)
        except Exception as e:
            logger.error(f"Error retrieving mounted drives: {e}")
            return []

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle(_("File Explorer"))
        self.setGeometry(100, 100, 600, 600)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        self.setLayout(self.main_layout)

        self.drives_layout = QHBoxLayout()
        self.drives_scroll = QScrollArea()
        self.drives_scroll.setWidgetResizable(True)
        self.drives_container = QWidget()
        self.drives_container.setLayout(self.drives_layout)
        self.drives_scroll.setWidget(self.drives_container)
        self.drives_scroll.setStyleSheet(self.theme.SCROLL_STYLE + self.theme.TRANSPARENT_BACKGROUND_STYLE)
        self.drives_scroll.setFixedHeight(70)
        self.main_layout.addWidget(self.drives_scroll)
        self.drives_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.drives_scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.path_label = QLabel()
        self.path_label.setStyleSheet(self.theme.FILE_EXPLORER_PATH_LABEL_STYLE)
        self.main_layout.addWidget(self.path_label)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet(self.theme.FILE_EXPLORER_STYLE + self.theme.SCROLL_STYLE)
        self.file_list.itemClicked.connect(self.handle_item_click)
        self.file_list.itemDoubleClicked.connect(self.handle_item_double_click)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.file_list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.file_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        QScroller.grabGesture(self.file_list.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        self.main_layout.addWidget(self.file_list)

        self.file_list.verticalScrollBar().valueChanged.connect(self.load_visible_thumbnails)

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.select_button = AutoSizeButton(_("Select"), icon=theme_manager.get_icon("apply"))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel"))
        self.select_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.button_layout.addWidget(self.select_button)
        self.button_layout.addWidget(self.cancel_button)
        self.main_layout.addLayout(self.button_layout)

        self.select_button.clicked.connect(self.select_item)
        self.cancel_button.clicked.connect(self.reject)

    def show_folder_context_menu(self, pos):
        """Shows the context menu for a folder using ContextMenuManager."""
        if self.context_menu_manager:
            self.context_menu_manager.show_folder_context_menu(self, pos)
        else:
            logger.warning("ContextMenuManager not found in parent")

    def move_selection(self, direction):
        """Move selection in the list."""
        current_row = self.file_list.currentRow()
        if direction < 0 and current_row > 0:
            self.file_list.setCurrentRow(current_row - 1)
        elif direction > 0 and current_row < self.file_list.count() - 1:
            self.file_list.setCurrentRow(current_row + 1)
        self.file_list.scrollToItem(self.file_list.currentItem())

    def handle_item_click(self, item):
        """Handle single mouse click."""
        try:
            self.file_list.setCurrentItem(item)
            self.path_history[self.current_path] = item.text()
            logger.debug("Selected item: %s", item.text())
        except Exception as e:
            logger.error("Error in handle_item_click: %s", e)

    def handle_item_double_click(self, item):
        """Handle double mouse click on a list item."""
        try:
            self.file_list.setCurrentItem(item)
            self.path_history[self.current_path] = item.text()
            selected = item.text()
            full_path = os.path.join(self.current_path, selected)
            if os.path.isdir(full_path):
                if selected == "../":
                    self.previous_dir()
                else:
                    self.current_path = os.path.normpath(full_path)
                    self.update_file_list()
            elif not self.directory_only:
                self.file_signal.file_selected.emit(os.path.normpath(full_path))
                self.accept()
            else:
                logger.debug("Double-clicked item is not a directory, ignoring: %s", full_path)
        except Exception as e:
            logger.error("Error in handle_item_double_click: %s", e)

    def select_item(self):
        """Handle file/folder selection."""
        if self.file_list.count() == 0:
            return

        selected = self.file_list.currentItem().text()
        full_path = os.path.join(self.current_path, selected)

        if os.path.isdir(full_path):
            if self.directory_only:
                self.file_signal.file_selected.emit(os.path.normpath(full_path))
                self.accept()
            else:
                self.current_path = os.path.normpath(full_path)
                self.update_file_list()
        else:
            if not self.directory_only:
                self.file_signal.file_selected.emit(os.path.normpath(full_path))
                self.accept()
            else:
                logger.debug("Selected item is not a directory, ignoring: %s", full_path)

    def previous_dir(self):
        """Navigate to parent directory."""
        try:
            if self.current_path == "/":
                return

            normalized_path = os.path.normpath(self.current_path)
            parent_dir = os.path.dirname(normalized_path)

            if not parent_dir:
                parent_dir = "/"

            current_dir_name = os.path.basename(normalized_path)
            self.path_history[parent_dir] = current_dir_name + "/" if current_dir_name else "../"
            self.current_path = parent_dir
            self.update_file_list()
        except Exception as e:
            logger.error(f"Error navigating to parent directory: {e}")

    def ensure_button_visible(self, button):
        """Ensure the specified button is visible in the drives_scroll area."""
        try:
            if not button or not self.drives_scroll:
                return
            self.drives_scroll.ensureWidgetVisible(button, 50, 50)
            logger.debug(f"Ensured button {button.text()} is visible in drives_scroll")
        except Exception as e:
            logger.error(f"Error ensuring button visible: {e}")

    def update_drives_list(self):
        """Update the list of mounted drives and favorite folders."""
        for i in reversed(range(self.drives_layout.count())):
            item = self.drives_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                self.drives_layout.removeWidget(widget)
                widget.deleteLater()

        self.drive_buttons = []
        drives = self.get_mounted_drives()
        favorite_folders = read_favorite_folders()

        for drive in drives:
            drive_name = os.path.basename(drive) or drive.split('/')[-1] or drive
            button = AutoSizeButton(drive_name, icon=theme_manager.get_icon("mount_point"))
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(lambda checked, path=drive: self.change_drive(path))
            self.drives_layout.addWidget(button)
            self.drive_buttons.append(button)

        for folder in favorite_folders:
            folder_name = os.path.basename(folder) or folder.split('/')[-1] or folder
            button = AutoSizeButton(folder_name, icon=theme_manager.get_icon("folder"))
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(lambda checked, path=folder: self.change_drive(path))
            self.drives_layout.addWidget(button)
            self.drive_buttons.append(button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.drives_layout.addWidget(spacer)

    def select_drive(self):
        """Handle drive or favorite folder selection via gamepad."""
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, AutoSizeButton) and focused_widget in self.drive_buttons:
            drive_name = focused_widget.text().strip()
            logger.debug(f"Selected name: {drive_name}")

            if drive_name == "/":
                if os.path.isdir("/") and os.access("/", os.R_OK):
                    self.current_path = "/"
                    self.update_file_list()
                    logger.info("Selected root directory")
                    return
                else:
                    logger.warning("Root directory is inaccessible: insufficient permissions or path error")
                    return

            favorite_folders = read_favorite_folders()
            logger.debug(f"Favorite folders: {favorite_folders}")
            for folder in favorite_folders:
                folder_name = os.path.basename(os.path.normpath(folder)) or folder
                if folder_name == drive_name and os.path.isdir(folder) and os.access(folder, os.R_OK):
                    self.current_path = os.path.normpath(folder)
                    self.update_file_list()
                    logger.info(f"Selected favorite folder: {self.current_path}")
                    return

            mounted_drives = self.get_mounted_drives()
            logger.debug(f"Mounted drives: {mounted_drives}")
            for drive in mounted_drives:
                drive_basename = os.path.basename(os.path.normpath(drive)) or drive
                if drive_basename == drive_name and os.path.isdir(drive) and os.access(drive, os.R_OK):
                    self.current_path = os.path.normpath(drive)
                    self.update_file_list()
                    logger.info(f"Selected mounted drive: {self.current_path}")
                    return

            logger.warning(f"Path is inaccessible: {drive_name}.")

    def change_drive(self, drive_path):
        """Navigate to the selected drive."""
        if os.path.isdir(drive_path) and os.access(drive_path, os.R_OK):
            self.current_path = os.path.normpath(drive_path)
            self.update_file_list()
        else:
            logger.warning(f"Drive path is inaccessible: {drive_path}")

    def update_file_list(self):
        """Update the file list with asynchronous thumbnail loading."""
        self.file_list.clear()
        self.thumbnail_cache.clear()
        self.pending_thumbnails.clear()
        try:
            if self.directory_only:
                item = QListWidgetItem("./")
                folder_icon = theme_manager.get_icon("folder")
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()
                item.setIcon(folder_icon)
                self.file_list.addItem(item)
            if self.current_path != "/":
                item = QListWidgetItem("../")
                folder_icon = theme_manager.get_icon("folder")
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()
                item.setIcon(folder_icon)
                self.file_list.addItem(item)

            items = os.listdir(self.current_path)
            dirs = [d for d in items if os.path.isdir(os.path.join(self.current_path, d))]

            for d in sorted(dirs):
                item = QListWidgetItem(f"{d}/")
                folder_icon = theme_manager.get_icon("folder")
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()
                item.setIcon(folder_icon)
                self.file_list.addItem(item)

            if not self.directory_only:
                files = [f for f in items if os.path.isfile(os.path.join(self.current_path, f))]
                if self.file_filter:
                    if isinstance(self.file_filter, str):
                        files = [f for f in files if f.lower().endswith(self.file_filter)]
                    elif isinstance(self.file_filter, tuple):
                        files = [f for f in files if any(f.lower().endswith(ext) for ext in self.file_filter)]

                for f in sorted(files):
                    item = QListWidgetItem(f)
                    self.file_list.addItem(item)

                self.load_visible_thumbnails()

            self.path_label.setText(_("Path: ") + self.current_path)

            last_item = self.path_history.get(self.current_path)
            if last_item:
                for i in range(self.file_list.count()):
                    if self.file_list.item(i).text() == last_item:
                        self.file_list.setCurrentRow(i)
                        self.file_list.scrollToItem(self.file_list.currentItem())
                        break
                else:
                    self.file_list.setCurrentRow(0)
            else:
                self.file_list.setCurrentRow(0)

            self.file_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.file_list.setTextElideMode(Qt.TextElideMode.ElideRight)
            self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.file_list.setAlternatingRowColors(True)

        except PermissionError:
            self.path_label.setText(_("Access denied: %s") % self.current_path)

    def closeEvent(self, event):
        """Handle window closing."""
        try:
            if self.input_manager:
                self.input_manager.disable_file_explorer_mode()
            if self.parent():
                parent = cast("MainWindow", self.parent())
                parent.activateWindow()
                parent.setFocus()
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")

        super().closeEvent(event)

    def reject(self):
        """Close the dialog."""
        if self.input_manager:
            self.input_manager.disable_file_explorer_mode()
        super().reject()

    def accept(self):
        """Accept the dialog."""
        if self.input_manager:
            self.input_manager.disable_file_explorer_mode()
        super().accept()
