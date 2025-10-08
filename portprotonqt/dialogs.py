import os
import tempfile
import re
from typing import cast, TYPE_CHECKING
from PySide6.QtGui import QPixmap, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QListWidget, QScrollArea, QWidget, QListWidgetItem, QSizePolicy, QApplication, QProgressBar, QScroller,
    QTabWidget, QTableWidget, QHeaderView, QMessageBox, QTableWidgetItem, QTextEdit, QAbstractItemView, QStackedWidget
)

from PySide6.QtCore import Qt, QObject, Signal, QMimeDatabase, QTimer, QThreadPool, QRunnable, Slot, QProcess, QProcessEnvironment
from icoextract import IconExtractor, IconExtractorError
from PIL import Image
from portprotonqt.config_utils import get_portproton_location, read_favorite_folders, read_theme_from_config
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.downloader import Downloader
from portprotonqt.preloader import Preloader
import psutil

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

logger = get_logger(__name__)
theme_manager = ThemeManager()

def generate_thumbnail(inputfile, outfile, size=128, force_resize=True):
    """
    Generates a thumbnail for an .exe file.

    inputfile: the input file path (%i)
    outfile: output filename (%o)
    size: determines the thumbnail output size (%s)
    """
    logger.debug(f"Начинаем генерацию миниатюры: {inputfile} → {outfile}, размер={size}, принудительно={force_resize}")

    try:
        extractor = IconExtractor(inputfile)
        logger.debug("IconExtractor успешно создан.")
    except (RuntimeError, IconExtractorError) as e:
        logger.warning(f"Не удалось создать IconExtractor: {e}")
        return False

    try:
        data = extractor.get_icon()
        im = Image.open(data)
        logger.debug(f"Извлечена иконка размером {im.size}, форматы: {im.format}, кадры: {getattr(im, 'n_frames', 1)}")
    except Exception as e:
        logger.warning(f"Ошибка при извлечении иконки: {e}")
        return False

    if force_resize:
        logger.debug(f"Принудительное изменение размера иконки на {size}x{size}")
        im = im.resize((size, size))
    else:
        if size > 256:
            logger.warning('Запрошен размер больше 256, установлен 256')
            size = 256
        elif size not in (128, 256):
            logger.warning(f'Неподдерживаемый размер {size}, установлен 128')
            size = 128

        if size == 256:
            logger.debug("Сохраняем иконку без изменения размера (256x256)")
            im.save(outfile, "PNG")
            logger.info(f"Иконка сохранена в {outfile}")
            return True

        frames = getattr(im, 'n_frames', 1)
        try:
            for frame in range(frames):
                im.seek(frame)
                if im.size == (size, size):
                    logger.debug(f"Найден кадр с размером {size}x{size}")
                    break
        except EOFError:
            logger.debug("Кадры закончились до нахождения нужного размера.")

        if im.size != (size, size):
            logger.debug(f"Изменение размера с {im.size} на {size}x{size}")
            im = im.resize((size, size))

    try:
        im.save(outfile, "PNG")
        logger.info(f"Миниатюра успешно сохранена в {outfile}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении миниатюры: {e}")
        return False

class FileSelectedSignal(QObject):
    file_selected = Signal(str)  # Сигнал с путем к выбранному файлу

class GameLaunchDialog(QDialog):
    """Modal dialog to indicate game launch progress, similar to Steam's launch dialog."""
    def __init__(self, parent=None, game_name=None, theme=None, target_exe=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.game_name = game_name
        self.target_exe = target_exe  # Store the target executable name
        self.setWindowTitle(_("Launching {0}").format(self.game_name))
        self.setModal(True)
        self.setFixedSize(400, 200)
        self.setStyleSheet(self.theme.MESSAGE_BOX_STYLE)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Game name label
        label = QLabel(_("Launching {0}").format(self.game_name))
        label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # Progress bar (indeterminate)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        layout.addWidget(self.progress_bar)

        # Cancel button
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel"))
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Center dialog on parent
        if parent:
            parent_geometry = parent.geometry()
            center_point = parent_geometry.center()
            dialog_geometry = self.geometry()
            dialog_geometry.moveCenter(center_point)
            self.setGeometry(dialog_geometry)

        # Timer to check if the game process is running
        self.check_process_timer = QTimer(self)
        self.check_process_timer.timeout.connect(self.check_target_exe)
        self.check_process_timer.start(500)

    def is_target_exe_running(self):
        """Check if the target executable is running using psutil."""
        if not self.target_exe:
            return False
        for proc in psutil.process_iter(attrs=["name"]):
            if proc.info["name"].lower() == self.target_exe.lower():
                return True
        return False

    def check_target_exe(self):
        """Check if the game process is running and close the dialog if it is."""
        if self.is_target_exe_running():
            logger.info(f"Game {self.game_name} process detected as running, closing launch dialog")
            self.accept()  # Close dialog when game is running
            self.check_process_timer.stop()
            self.check_process_timer.deleteLater()
        elif not hasattr(self.parent(), 'game_processes') or not any(proc.poll() is None for proc in cast("MainWindow", self.parent()).game_processes):
            # If no child processes are running, stop the timer but keep dialog open
            self.check_process_timer.stop()
            self.check_process_timer.deleteLater()


    def reject(self):
        """Handle dialog cancellation."""
        logger.info(f"Game launch cancelled for {self.game_name}")
        self.check_process_timer.stop()
        self.check_process_timer.deleteLater()
        super().reject()

class FileExplorer(QDialog):
    def __init__(self, parent=None, theme=None, file_filter=None, initial_path=None, directory_only=False):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.file_signal = FileSelectedSignal()
        self.file_filter = file_filter  # Store the file filter
        self.directory_only = directory_only  # Store the directory_only flag
        self.mime_db = QMimeDatabase()  # Initialize QMimeDatabase for mimetype detection
        self.path_history = {}  # Dictionary to store last selected item per directory
        self.initial_path = initial_path  # Store initial path if provided
        self.thumbnail_cache = {}  # Cache for loaded thumbnails
        self.pending_thumbnails = set()  # Track files pending thumbnail loading
        self.setup_ui()

        # Window settings
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Find InputManager and ContextMenuManager from parent
        self.input_manager = None
        self.context_menu_manager = None
        parent = self.parent()
        while parent:
            if hasattr(parent, 'input_manager'):
                self.input_manager = cast("MainWindow", parent).input_manager
            if hasattr(parent, 'context_menu_manager'):
                self.context_menu_manager = cast("MainWindow", parent).context_menu_manager
            parent = parent.parent()

        if self.input_manager:
            self.input_manager.enable_file_explorer_mode(self)

        # Initialize drives list
        self.update_drives_list()

        # Set initial path if provided, else default to home
        self.current_path = os.path.expanduser("~") if not initial_path else os.path.normpath(initial_path)
        if initial_path and not os.path.isdir(self.current_path):
            self.current_path = os.path.expanduser("~")  # Fallback to home if initial path is invalid
        self.update_file_list()

    class ThumbnailLoader(QRunnable):
        """Class for asynchronous thumbnail loading in a separate thread."""
        class Signals(QObject):
            thumbnail_ready = Signal(str, QIcon)  # Signal for ready thumbnail: file path and icon

        def __init__(self, file_path, mime_type, size=64):
            super().__init__()
            self.file_path = file_path
            self.mime_type = mime_type
            self.size = size
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
                elif self.file_path.lower().endswith(".exe"):
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        if generate_thumbnail(self.file_path, tmp.name, size=self.size):
                            pixmap = QPixmap(tmp.name)
                            if not pixmap.isNull():
                                self.signals.thumbnail_ready.emit(self.file_path, QIcon(pixmap))
                            os.unlink(tmp.name)
                        else:
                            logger.warning("Failed to generate thumbnail for .exe: %s", self.file_path)
            except Exception as e:
                logger.error("Error loading thumbnail for %s: %s", self.file_path, str(e))


    def async_load_thumbnails(self, files, mime_db):
        """
        Asynchronously loads thumbnails for a list of files.

        Args:
            files (list): List of file names to process.
            mime_db (QMimeDatabase): QMimeDatabase instance for file type detection.
        """
        thread_pool = QThreadPool.globalInstance()
        thread_pool.setMaxThreadCount(4)  # Limit the number of threads

        for f in files:
            file_path = os.path.join(self.current_path, f)
            if file_path in self.thumbnail_cache or file_path in self.pending_thumbnails:
                continue  # Skip if already cached or pending
            mime_type = mime_db.mimeTypeForFile(file_path).name()
            if mime_type.startswith("image/") or file_path.lower().endswith(".exe"):
                self.pending_thumbnails.add(file_path)
                loader = self.ThumbnailLoader(file_path, mime_type, size=64)
                loader.signals.thumbnail_ready.connect(self.update_thumbnail)
                thread_pool.start(loader)


    @Slot(str, QIcon)
    def update_thumbnail(self, file_path, icon):
        """
        Updates the icon for a file list item after thumbnail loading.

        Args:
            file_path (str): Path to the file for which the thumbnail was loaded.
            icon (QIcon): Loaded icon.
        """
        try:
            # Cache the thumbnail
            self.thumbnail_cache[file_path] = icon
            self.pending_thumbnails.discard(file_path)
            # Update the item in the file list
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
                    continue  # Skip directories
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
                    # Exclude system and temporary paths, but keep /run/media
                    if (mount_point.startswith(('/dev', '/sys', '/proc', '/tmp', '/snap', '/var/lib')) or
                        (mount_point.startswith('/run') and not mount_point.startswith('/run/media'))):
                        continue
                    # Check if the mount point is a directory and accessible
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

        # Panel for mounted drives and favorite folders
        self.drives_layout = QHBoxLayout()
        self.drives_scroll = QScrollArea()
        self.drives_scroll.setWidgetResizable(True)
        self.drives_container = QWidget()
        self.drives_container.setLayout(self.drives_layout)
        self.drives_scroll.setWidget(self.drives_container)
        self.drives_scroll.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        self.drives_scroll.setFixedHeight(70)
        self.main_layout.addWidget(self.drives_scroll)
        self.drives_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.drives_scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Path label
        self.path_label = QLabel()
        self.path_label.setStyleSheet(self.theme.FILE_EXPLORER_PATH_LABEL_STYLE)
        self.main_layout.addWidget(self.path_label)

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(self.theme.FILE_EXPLORER_STYLE)
        self.file_list.itemClicked.connect(self.handle_item_click)
        self.file_list.itemDoubleClicked.connect(self.handle_item_double_click)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.file_list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.file_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        QScroller.grabGesture(self.file_list.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        self.main_layout.addWidget(self.file_list)

        # Connect scroll signal for lazy loading
        self.file_list.verticalScrollBar().valueChanged.connect(self.load_visible_thumbnails)

        # Buttons
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
        if direction < 0 and current_row > 0:  # Up
            self.file_list.setCurrentRow(current_row - 1)
        elif direction > 0 and current_row < self.file_list.count() - 1:  # Down
            self.file_list.setCurrentRow(current_row + 1)
        self.file_list.scrollToItem(self.file_list.currentItem())

    def handle_item_click(self, item):
        """Handle single mouse click."""
        try:
            self.file_list.setCurrentItem(item)
            self.path_history[self.current_path] = item.text()  # Save selected item
            logger.debug("Selected item: %s", item.text())
        except Exception as e:
            logger.error("Error in handle_item_click: %s", e)

    def handle_item_double_click(self, item):
        """Handle double mouse click on a list item."""
        try:
            self.file_list.setCurrentItem(item)
            self.path_history[self.current_path] = item.text()  # Save selected item
            selected = item.text()
            full_path = os.path.join(self.current_path, selected)
            if os.path.isdir(full_path):
                if selected == "../":
                    # Navigate to parent directory
                    self.previous_dir()
                else:
                    # Open directory
                    self.current_path = os.path.normpath(full_path)
                    self.update_file_list()
            elif not self.directory_only:
                # Select file if directory_only=False
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
                # Confirm directory selection
                self.file_signal.file_selected.emit(os.path.normpath(full_path))
                self.accept()
            else:
                # Open directory
                self.current_path = os.path.normpath(full_path)
                self.update_file_list()
        else:
            if not self.directory_only:
                # Emit normalized path for file
                self.file_signal.file_selected.emit(os.path.normpath(full_path))
                self.accept()
            else:
                logger.debug("Selected item is not a directory, ignoring: %s", full_path)

    def previous_dir(self):
        """Navigate to parent directory."""
        try:
            if self.current_path == "/":
                return  # Already at root

            # Normalize path (remove trailing slash if present)
            normalized_path = os.path.normpath(self.current_path)
            # Get parent directory
            parent_dir = os.path.dirname(normalized_path)

            if not parent_dir:
                parent_dir = "/"

            # Save the current directory as the last selected item for the parent
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
            # Ensure the button is visible in the scroll area
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

        # Add mounted drives
        for drive in drives:
            drive_name = os.path.basename(drive) or drive.split('/')[-1] or drive
            button = AutoSizeButton(drive_name, icon=theme_manager.get_icon("mount_point"))
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(lambda checked, path=drive: self.change_drive(path))
            self.drives_layout.addWidget(button)
            self.drive_buttons.append(button)

        # Add favorite folders
        for folder in favorite_folders:
            folder_name = os.path.basename(folder) or folder.split('/')[-1] or folder
            button = AutoSizeButton(folder_name, icon=theme_manager.get_icon("folder"))
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(lambda checked, path=folder: self.change_drive(path))
            self.drives_layout.addWidget(button)
            self.drive_buttons.append(button)

        # Add spacer to align elements
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.drives_layout.addWidget(spacer)

    def select_drive(self):
        """Handle drive or favorite folder selection via gamepad."""
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, AutoSizeButton) and focused_widget in self.drive_buttons:
            drive_name = focused_widget.text().strip()  # Remove whitespace
            logger.debug(f"Selected name: {drive_name}")

            # Special handling for root directory
            if drive_name == "/":
                if os.path.isdir("/") and os.access("/", os.R_OK):
                    self.current_path = "/"
                    self.update_file_list()
                    logger.info("Selected root directory")
                    return
                else:
                    logger.warning("Root directory is inaccessible: insufficient permissions or path error")
                    return

            # Check favorite folders
            favorite_folders = read_favorite_folders()
            logger.debug(f"Favorite folders: {favorite_folders}")
            for folder in favorite_folders:
                folder_name = os.path.basename(os.path.normpath(folder)) or folder  # For root paths
                if folder_name == drive_name and os.path.isdir(folder) and os.access(folder, os.R_OK):
                    self.current_path = os.path.normpath(folder)
                    self.update_file_list()
                    logger.info(f"Selected favorite folder: {self.current_path}")
                    return

            # Check mounted drives
            mounted_drives = self.get_mounted_drives()
            logger.debug(f"Mounted drives: {mounted_drives}")
            for drive in mounted_drives:
                drive_basename = os.path.basename(os.path.normpath(drive)) or drive  # For root paths
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
        self.thumbnail_cache.clear()  # Clear cache when changing directories
        self.pending_thumbnails.clear()  # Clear pending thumbnails
        try:
            if self.directory_only:
                item = QListWidgetItem("./")
                folder_icon = theme_manager.get_icon("folder")
                # Ensure the icon is a QIcon
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()  # Fallback to empty icon
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

            # Add directories
            for d in sorted(dirs):
                item = QListWidgetItem(f"{d}/")
                folder_icon = theme_manager.get_icon("folder")
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()
                item.setIcon(folder_icon)
                self.file_list.addItem(item)

            # Add files only if directory_only=False
            if not self.directory_only:
                files = [f for f in items if os.path.isfile(os.path.join(self.current_path, f))]
                if self.file_filter:
                    if isinstance(self.file_filter, str):
                        files = [f for f in files if f.lower().endswith(self.file_filter)]
                    elif isinstance(self.file_filter, tuple):
                        files = [f for f in files if any(f.lower().endswith(ext) for ext in self.file_filter)]

                # Add files to the list without immediate thumbnail loading
                for f in sorted(files):
                    item = QListWidgetItem(f)
                    self.file_list.addItem(item)

                # Load thumbnails for visible items only
                self.load_visible_thumbnails()

            self.path_label.setText(_("Path: ") + self.current_path)

            # Restore last selected item for this directory
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

class AddGameDialog(QDialog):
    def __init__(self, parent=None, theme=None, edit_mode=False, game_name=None, exe_path=None, cover_path=None):
        super().__init__(parent)
        from portprotonqt.context_menu_manager import CustomLineEdit   # Локальный импорт
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.edit_mode = edit_mode
        self.original_name = game_name
        self.last_exe_path = exe_path  # Store last selected exe path
        self.last_cover_path = cover_path  # Store last selected cover path
        self.downloader = Downloader(max_workers=4)  # Initialize Downloader

        self.setWindowTitle(_("Edit Game") if edit_mode else _("Add Game"))
        self.setModal(True)
        self.setFixedWidth(600)
        self.setFixedHeight(600)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Game name
        self.nameEdit = CustomLineEdit(self, theme=self.theme)
        self.nameEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if game_name:
            self.nameEdit.setText(game_name)
        name_label = QLabel(_("Game Name:"))
        name_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        layout.addRow(name_label, self.nameEdit)

        # Exe path
        exe_label = QLabel(_("Path to Executable:"))
        exe_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)

        self.exeEdit = CustomLineEdit(self, theme=self.theme)
        self.exeEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if exe_path:
            self.exeEdit.setText(exe_path)

        exeBrowseButton = AutoSizeButton(_("Browse..."), icon=theme_manager.get_icon("search"))
        exeBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        exeBrowseButton.clicked.connect(self.browseExe)
        exeBrowseButton.setObjectName("exeBrowseButton")  # Для поиска кнопки

        # Добавляем поле ввода для exe
        layout.addRow(exe_label, self.exeEdit)

        # Добавляем кнопку обзора под полем ввода с выравниванием
        empty_label = QLabel("")
        empty_label.setFixedWidth(exe_label.sizeHint().width())
        layout.addRow(empty_label, exeBrowseButton)

        # Cover path
        cover_label = QLabel(_("Custom Cover:"))
        cover_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)

        self.coverEdit = CustomLineEdit(self, theme=self.theme)
        self.coverEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if cover_path:
            self.coverEdit.setText(cover_path)

        coverBrowseButton = AutoSizeButton(_("Browse..."), icon=theme_manager.get_icon("search"))
        coverBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        coverBrowseButton.clicked.connect(self.browseCover)
        coverBrowseButton.setObjectName("coverBrowseButton")  # Для поиска кнопки

        # Добавляем поле ввода для обложки
        layout.addRow(cover_label, self.coverEdit)

        # Добавляем кнопку обзора под полем ввода с выравниванием
        layout.addRow(empty_label, coverBrowseButton)

        # Preview
        self.coverPreview = QLabel(self)
        self.coverPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.coverPreview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        preview_widget = QWidget(self)
        preview_widget.setStyleSheet(self.theme.PREVIEW_WIDGET_STYLE)
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_label = QLabel(_("Cover Preview:"))
        preview_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        preview_layout.addWidget(preview_label, alignment=Qt.AlignmentFlag.AlignLeft)
        preview_layout.addWidget(self.coverPreview, stretch=1)
        layout.addRow(preview_widget)

        # Dialog buttons
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.select_button = AutoSizeButton(_("Apply"), icon=theme_manager.get_icon("apply"))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel"))
        self.select_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.button_layout.addWidget(self.select_button)
        self.button_layout.addWidget(self.cancel_button)
        layout.addRow(self.button_layout)

        # Подключение сигналов
        self.select_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.coverEdit.textChanged.connect(self.updatePreview)
        self.exeEdit.textChanged.connect(self.updatePreview)

        # Установка одинаковой ширины для кнопок и полей ввода
        def update_button_widths():
            exeBrowseButton.setFixedWidth(self.exeEdit.width())
            coverBrowseButton.setFixedWidth(self.coverEdit.width())

        # Вызываем после отображения окна, когда размеры установлены
        QTimer.singleShot(0, update_button_widths)

        # Обновляем превью, если в режиме редактирования
        if edit_mode:
            self.updatePreview()

    def browseExe(self):
        """Открывает файловый менеджер для выбора exe-файла"""
        try:
            # Use last_exe_path if available and valid, otherwise fallback to home
            initial_path = os.path.dirname(self.last_exe_path) if self.last_exe_path and os.path.isfile(self.last_exe_path) else None
            file_explorer = FileExplorer(self, file_filter='.exe', initial_path=initial_path)
            file_explorer.file_signal.file_selected.connect(self.onExeSelected)

            # Центрируем FileExplorer относительно родительского виджета
            parent_widget = self.parentWidget()  # QWidget или None
            if parent_widget:
                parent_geometry = parent_widget.geometry()
                center_point = parent_geometry.center()
                file_explorer_geometry = file_explorer.geometry()
                file_explorer_geometry.moveCenter(center_point)
                file_explorer.setGeometry(file_explorer_geometry)

            file_explorer.show()
        except Exception as e:
            logger.error(f"Error in browseExe: {e}")

    def onExeSelected(self, file_path):
        """Обработчик выбора файла в FileExplorer"""
        self.exeEdit.setText(file_path)
        self.last_exe_path = file_path  # Update last selected exe path
        if not self.edit_mode:
            # Автоматически заполняем имя игры, если не в режиме редактирования
            game_name = os.path.splitext(os.path.basename(file_path))[0]
            self.nameEdit.setText(game_name)

        # Обновляем превью
        self.updatePreview()

    def browseCover(self):
        """Открывает файловый менеджер для выбора изображения обложки"""
        try:
            # Use last_cover_path if available and valid, otherwise fallback to home
            initial_path = os.path.dirname(self.last_cover_path) if self.last_cover_path and os.path.isfile(self.last_cover_path) else None
            file_explorer = FileExplorer(self, file_filter=('.png', '.jpg', '.jpeg', '.bmp'), initial_path=initial_path)
            file_explorer.file_signal.file_selected.connect(self.onCoverSelected)

            # Центрируем FileExplorer относительно родительского виджета
            parent_widget = self.parentWidget()
            if parent_widget:
                parent_geometry = parent_widget.geometry()
                center_point = parent_geometry.center()
                file_explorer_geometry = file_explorer.geometry()
                file_explorer_geometry.moveCenter(center_point)
                file_explorer.setGeometry(file_explorer_geometry)

            file_explorer.show()
        except Exception as e:
            logger.error(f"Error in browseCover: {e}")

    def onCoverSelected(self, file_path):
        """Обработчик выбора файла обложки в FileExplorer"""
        if file_path and os.path.splitext(file_path)[1].lower() in ('.png', '.jpg', '.jpeg', '.bmp'):
            self.coverEdit.setText(file_path)
            self.last_cover_path = file_path
            self.updatePreview()
        else:
            logger.warning(f"Selected file is not a valid image: {file_path}")

    def handleDownloadedCover(self, file_path):
        """Handle the downloaded cover image and update the preview."""
        if file_path and os.path.isfile(file_path):
            self.last_cover_path = file_path
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.coverPreview.setPixmap(pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.coverPreview.setText(_("Invalid image"))
        else:
            self.coverPreview.setText(_("Failed to download cover"))
            logger.warning(f"Failed to download cover to {file_path}")

    def updatePreview(self):
        """Update the cover preview image."""
        cover_path = self.coverEdit.text().strip()
        exe_path = self.exeEdit.text().strip()

        # Check if cover_path is a URL
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if re.match(url_pattern, cover_path):
            # Create a temporary file for the downloaded image
            fd, local_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            os.unlink(local_path)

            # Start asynchronous download
            self.downloader.download_async(
                url=cover_path,
                local_path=local_path,
                timeout=10,
                callback=self.handleDownloadedCover
            )
            self.coverPreview.setText(_("Downloading cover..."))
        elif cover_path and os.path.isfile(cover_path):
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                self.coverPreview.setPixmap(pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.coverPreview.setText(_("Invalid image"))
        elif os.path.isfile(exe_path):
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp.close()
            if generate_thumbnail(exe_path, tmp.name, size=128):
                pixmap = QPixmap(tmp.name)
                self.coverPreview.setPixmap(pixmap)
            os.unlink(tmp.name)
        else:
            self.coverPreview.setText(_("No cover selected"))

    def getDesktopEntryData(self):
        """Returns the .desktop content and save path"""
        exe_path = self.exeEdit.text().strip()
        name = self.nameEdit.text().strip()

        if not exe_path or not os.path.isfile(exe_path):
            return None, None

        if not name:
            return None, None

        portproton_path = get_portproton_location()
        if portproton_path is None:
            return None, None

        is_flatpak = ".var" in portproton_path
        base_path = os.path.join(portproton_path, "data")

        if is_flatpak:
            exec_str = f'flatpak run ru.linux_gaming.PortProton "{exe_path}"'
        else:
            start_sh = os.path.join(base_path, "scripts", "start.sh")
            exec_str = f'env "{start_sh}" "{exe_path}"'

        icon_path = os.path.join(base_path, "img", f"{name}.png")
        desktop_path = os.path.join(portproton_path, f"{name}.desktop")
        working_dir = os.path.join(base_path, "scripts")

        os.makedirs(os.path.dirname(icon_path), exist_ok=True)

        # Generate thumbnail (128x128) from exe if no cover is provided
        if not self.last_cover_path and not generate_thumbnail(exe_path, icon_path, size=128):
            logger.error(f"Failed to generate thumbnail from exe: {exe_path}")
            icon_path = ""  # Set empty icon if generation fails

        comment = _('Launch game "{name}" with PortProton').format(name=name)

        desktop_entry = f"""[Desktop Entry]
Name={name}
Comment={comment}
Exec={exec_str}
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
Path={working_dir}
Icon={icon_path}
"""

        return desktop_entry, desktop_path

class WinetricksDialog(QDialog):
    """Dialog for managing Winetricks components in a prefix."""

    def __init__(self, parent=None, theme=None, prefix_path: str | None = None, wine_use: str | None = None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.prefix_path: str | None = prefix_path
        self.wine_use: str | None = wine_use
        self.portproton_path = get_portproton_location()
        if self.portproton_path is None:
            logger.error("PortProton location not found")
            return
        self.tmp_path = os.path.join(self.portproton_path, "data", "tmp")
        os.makedirs(self.tmp_path, exist_ok=True)
        self.winetricks_path = os.path.join(self.tmp_path, "winetricks")
        if self.prefix_path is None:
            logger.error("Prefix path not provided")
            return
        self.log_path = os.path.join(self.prefix_path, "winetricks.log")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            open(self.log_path, 'a').close()

        self.downloader = Downloader(max_workers=4)
        self.apply_process: QProcess | None = None

        self.setWindowTitle(_("Prefix Manager"))
        self.setModal(True)
        self.resize(700, 700)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        self.update_winetricks()
        self.setup_ui()
        self.load_lists()

    def update_winetricks(self):
        """Update the winetricks script."""
        if not self.downloader.has_internet():
            logger.warning("No internet connection, skipping winetricks update")
            return

        url = "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks"
        temp_path = os.path.join(self.tmp_path, "winetricks_temp")

        try:
            self.downloader.download(url, temp_path)
            with open(temp_path) as f:
                ext_content = f.read()
            ext_ver_match = re.search(r'WINETRICKS_VERSION\s*=\s*[\'"]?([^\'"\s]+)', ext_content)
            ext_ver = ext_ver_match.group(1) if ext_ver_match else None
            logger.info(f"External winetricks version: {ext_ver}")
        except Exception as e:
            logger.error(f"Failed to get external version: {e}")
            ext_ver = None
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return

        int_ver = None
        if os.path.exists(self.winetricks_path):
            try:
                with open(self.winetricks_path) as f:
                    int_content = f.read()
                int_ver_match = re.search(r'WINETRICKS_VERSION\s*=\s*[\'"]?([^\'"\s]+)', int_content)
                int_ver = int_ver_match.group(1) if int_ver_match else None
                logger.info(f"Internal winetricks version: {int_ver}")
            except Exception as e:
                logger.error(f"Failed to read internal winetricks version: {e}")

        update_needed = not os.path.exists(self.winetricks_path) or (int_ver != ext_ver and ext_ver)

        if update_needed:
            try:
                self.downloader.download(url, self.winetricks_path)
                os.chmod(self.winetricks_path, 0o755)
                logger.info(f"Winetricks updated to version {ext_ver}")
                self.apply_modifications(self.winetricks_path)
            except Exception as e:
                logger.error(f"Failed to update winetricks: {e}")
        elif os.path.exists(self.winetricks_path):
            self.apply_modifications(self.winetricks_path)

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def apply_modifications(self, file_path):
        """Apply custom modifications to the winetricks script."""
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path) as f:
                content = f.read()

            # Apply sed-like replacements
            content = re.sub(r'w_metadata vcrun2015 dlls \\', r'w_metadata !dont_use_2015! dlls \\', content)
            content = re.sub(r'w_metadata vcrun2017 dlls \\', r'w_metadata !dont_use_2017! dlls \\', content)
            content = re.sub(r'w_metadata vcrun2019 dlls \\', r'w_metadata !dont_use_2019! dlls \\', content)
            content = re.sub(r'w_set_winver win2k3', r'w_set_winver win7', content)

            with open(file_path, 'w') as f:
                f.write(content)
            logger.info("Winetricks modifications applied")
        except Exception as e:
            logger.error(f"Error applying modifications to winetricks: {e}")

    def setup_ui(self):
        """Set up the user interface with tabs and tables."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(self.theme.WINETRICKS_LOG_STYLE)
        main_layout.addWidget(self.log_output)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self.theme.WINETRICKS_TAB_STYLE)

        table_base_style = self.theme.WINETRICKS_TABBLE_STYLE

        # DLLs tab
        self.dll_table = QTableWidget()
        self.dll_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.dll_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dll_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.dll_table.setColumnCount(3)
        self.dll_table.setHorizontalHeaderLabels([_("Set"), _("Libraries"), _("Information")])
        self.dll_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.dll_table.horizontalHeader().resizeSection(0, 50)
        self.dll_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.dll_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.dll_table.setStyleSheet(table_base_style)

        self.dll_preloader = Preloader()
        dll_preloader_container = QWidget()
        dll_preloader_layout = QVBoxLayout(dll_preloader_container)
        dll_preloader_layout.addStretch()
        dll_preloader_hlayout = QHBoxLayout()
        dll_preloader_hlayout.addStretch()
        dll_preloader_hlayout.addWidget(self.dll_preloader)
        dll_preloader_hlayout.addStretch()
        dll_preloader_layout.addLayout(dll_preloader_hlayout)
        dll_preloader_layout.addStretch()
        dll_preloader_layout.setContentsMargins(0, 0, 0, 0)
        dll_preloader_layout.setSpacing(0)

        self.dll_container = QStackedWidget()
        self.dll_container.addWidget(dll_preloader_container)
        self.dll_container.addWidget(self.dll_table)
        self.tab_widget.addTab(self.dll_container, "DLLs")

        # Fonts tab
        self.fonts_table = QTableWidget()
        self.fonts_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fonts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fonts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.fonts_table.setColumnCount(3)
        self.fonts_table.setHorizontalHeaderLabels([_("Set"), _("Fonts"), _("Information")])
        self.fonts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.fonts_table.horizontalHeader().resizeSection(0, 50)
        self.fonts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fonts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.fonts_table.setStyleSheet(table_base_style)

        self.fonts_preloader = Preloader()
        fonts_preloader_container = QWidget()
        fonts_preloader_layout = QVBoxLayout(fonts_preloader_container)
        fonts_preloader_layout.addStretch()
        fonts_preloader_hlayout = QHBoxLayout()
        fonts_preloader_hlayout.addStretch()
        fonts_preloader_hlayout.addWidget(self.fonts_preloader)
        fonts_preloader_hlayout.addStretch()
        fonts_preloader_layout.addLayout(fonts_preloader_hlayout)
        fonts_preloader_layout.addStretch()
        fonts_preloader_layout.setContentsMargins(0, 0, 0, 0)
        fonts_preloader_layout.setSpacing(0)

        self.fonts_container = QStackedWidget()
        self.fonts_container.addWidget(fonts_preloader_container)
        self.fonts_container.addWidget(self.fonts_table)
        self.tab_widget.addTab(self.fonts_container, _("Fonts"))

        # Settings tab
        self.settings_table = QTableWidget()
        self.settings_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.settings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.settings_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.settings_table.setColumnCount(3)
        self.settings_table.setHorizontalHeaderLabels([_("Set"), _("Settings"), _("Information")])
        self.settings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.settings_table.horizontalHeader().resizeSection(0, 50)
        self.settings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.settings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.settings_table.setStyleSheet(table_base_style)

        self.settings_preloader = Preloader()
        settings_preloader_container = QWidget()
        settings_preloader_layout = QVBoxLayout(settings_preloader_container)
        settings_preloader_layout.addStretch()
        settings_preloader_hlayout = QHBoxLayout()
        settings_preloader_hlayout.addStretch()
        settings_preloader_hlayout.addWidget(self.settings_preloader)
        settings_preloader_hlayout.addStretch()
        settings_preloader_layout.addLayout(settings_preloader_hlayout)
        settings_preloader_layout.addStretch()
        settings_preloader_layout.setContentsMargins(0, 0, 0, 0)
        settings_preloader_layout.setSpacing(0)

        self.settings_container = QStackedWidget()
        self.settings_container.addWidget(settings_preloader_container)
        self.settings_container.addWidget(self.settings_table)
        self.tab_widget.addTab(self.settings_container, _("Settings"))

        self.containers = {
            "dlls": self.dll_container,
            "fonts": self.fonts_container,
            "settings": self.settings_container
        }

        main_layout.addWidget(self.tab_widget)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel"))
        self.force_button = AutoSizeButton(_("Force Install"), icon=theme_manager.get_icon("apply"))
        self.install_button = AutoSizeButton(_("Install"), icon=theme_manager.get_icon("apply"))
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.force_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.install_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.force_button)
        button_layout.addWidget(self.install_button)
        main_layout.addLayout(button_layout)

        self.cancel_button.clicked.connect(self.reject)
        self.force_button.clicked.connect(lambda: self.install_selected(force=True))
        self.install_button.clicked.connect(lambda: self.install_selected(force=False))

    def load_lists(self):
        """Load and populate the lists for DLLs, Fonts, and Settings"""
        if not os.path.exists(self.winetricks_path):
            QMessageBox.warning(self, _("Error"), _("Winetricks not found. Please try again."))
            self.reject()
            return

        assert self.prefix_path is not None
        env = QProcessEnvironment.systemEnvironment()
        env.insert("WINEPREFIX", self.prefix_path)
        if self.wine_use is not None:
            env.insert("WINE", self.wine_use)

        cwd = os.path.dirname(self.winetricks_path)

        # DLLs
        self.containers["dlls"].setCurrentIndex(0)
        self._start_list_process("dlls", self.dll_table, self.get_dll_exclusions(), env, cwd)

        # Fonts
        self.containers["fonts"].setCurrentIndex(0)
        self._start_list_process("fonts", self.fonts_table, self.get_fonts_exclusions(), env, cwd)

        # Settings
        self.containers["settings"].setCurrentIndex(0)
        self._start_list_process("settings", self.settings_table, self.get_settings_exclusions(), env, cwd)

    def _start_list_process(self, category, table, exclusion_pattern, env, cwd):
        """Запускает QProcess для списка."""
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setProcessEnvironment(env)
        process.finished.connect(lambda exit_code, exit_status: self._on_list_finished(category, table, exclusion_pattern, process, exit_code, exit_status))
        process.start(self.winetricks_path, [category, "list"])

    def _on_list_finished(self, category, table, exclusion_pattern, process: QProcess | None, exit_code, exit_status):
        """Обработчик завершения списка."""
        if process is None:
            logger.error(f"Process is None for {category}")
            self.containers[category].setCurrentIndex(1)
            return
        output = bytes(process.readAllStandardOutput().data()).decode('utf-8', 'ignore')
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self.populate_table(table, output, exclusion_pattern, self.log_path)
            # Restore focus after populating
            if table.rowCount() > 0:
                table.setCurrentCell(0, 0)
                table.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            error_output = bytes(process.readAllStandardError().data()).decode('utf-8', 'ignore')
            logger.error(f"Failed to list {category}: {error_output}")

        self.containers[category].setCurrentIndex(1)

    def get_dll_exclusions(self):
        """Get regex pattern for DLL exclusions."""
        return r'(d3d|directx9|dont_use|dxvk|vkd3d|galliumnine|faudio1|Foundation)'

    def get_fonts_exclusions(self):
        """Get regex pattern for Fonts exclusions."""
        return r'dont_use'

    def get_settings_exclusions(self):
        """Get regex pattern for Settings exclusions."""
        return r'(vista|alldlls|autostart_|bad|good|win|videomemory|vd=|isolate_home)'

    def populate_table(self, table, output, exclusion_pattern, log_path):
        """Populate the table with items from output, checking installation status."""
        table.setRowCount(0)
        table.verticalHeader().setVisible(False)
        lines = output.strip().split('\n')
        installed = set()
        if os.path.exists(log_path):
            with open(log_path) as f:
                for line in f:
                    installed.add(line.strip())

        # regex-парсинг (имя - первое слово, остальное - описание)
        line_re = re.compile(r"^\s*(?:\[(.)]\s+)?([^\s]+)\s*(.*)")

        for line in lines:
            line = line.strip()
            if not line or re.search(exclusion_pattern, line, re.I):
                continue

            line = line.split('(', 1)[0].strip()

            match = line_re.match(line)
            if not match:
                continue

            _status, name, info = match.groups()
            # Очищаем info от мусора
            info = re.sub(r'\[.*?\]', '', info).strip()  # Удаляем [скачивания] и т.п.

            # To match bash desc extraction: after name, substr(2) to trim leading space
            if info.startswith(' '):
                info = info[1:].lstrip()

            # Фильтр служебных строк
            if '/' in name or '\\' in name or name.lower() in ('executing', 'using', 'warning:') or name.endswith(':'):
                continue

            checked = Qt.CheckState.Checked if name in installed else Qt.CheckState.Unchecked

            row = table.rowCount()
            table.insertRow(row)

            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setCheckState(checked)
            table.setItem(row, 0, checkbox)

            # Name
            name_item = QTableWidgetItem(name)
            table.setItem(row, 1, name_item)

            # Info
            info_item = QTableWidgetItem(info)
            table.setItem(row, 2, info_item)

    def install_selected(self, force=False):
        """Install selected components."""
        selected = []
        for table in [self.dll_table, self.fonts_table, self.settings_table]:
            for row in range(table.rowCount()):
                checkbox = table.item(row, 0)
                if checkbox is not None and checkbox.checkState() == Qt.CheckState.Checked:
                    name_item = table.item(row, 1)
                    if name_item is not None:
                        name = name_item.text()
                        if name and name not in selected:
                            selected.append(name)

        # Load installed
        installed = set()
        if os.path.exists(self.log_path):
            with open(self.log_path) as f:
                for line in f:
                    installed.add(line.strip())

        # Filter to new selected
        new_selected = [name for name in selected if name not in installed]

        if not new_selected:
            QMessageBox.information(self, _("Warning"), _("No components selected."))
            return

        self.install_button.setEnabled(False)
        self.force_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        self._start_install_process(new_selected, force)

    def _start_install_process(self, selected, force):
        """Запускает QProcess для установки."""
        assert self.prefix_path is not None
        env = QProcessEnvironment.systemEnvironment()
        env.insert("WINEPREFIX", self.prefix_path)
        if self.wine_use is not None:
            env.insert("WINE", self.wine_use)

        self.apply_process = QProcess(self)
        self.apply_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.apply_process.setProcessEnvironment(env)
        self.apply_process.readyReadStandardOutput.connect(self._on_ready_read)
        self.apply_process.finished.connect(lambda exit_code, exit_status: self._on_install_finished(exit_code, exit_status, selected))
        args = ["--unattended"] + (["--force"] if force else []) + selected
        self.apply_process.start(self.winetricks_path, args)

    def _on_ready_read(self):
        """Handle ready read for install process."""
        if self.apply_process is None:
            return
        data = self.apply_process.readAllStandardOutput().data()
        message = bytes(data).decode('utf-8', 'ignore').strip()
        self._log(message)

    def _on_install_finished(self, exit_code, exit_status, selected):
        """Обработчик завершения установки."""
        error_message = ""
        if self.apply_process is not None:
            # Читаем вывод в зависимости от режима каналов
            if self.apply_process.processChannelMode() == QProcess.ProcessChannelMode.MergedChannels:
                # Если каналы объединены, читаем из StandardOutput
                output_data = self.apply_process.readAllStandardOutput().data()
                error_message = bytes(output_data).decode('utf-8', 'ignore')
            else:
                # Если каналы разделены, читаем из StandardError
                error_data = self.apply_process.readAllStandardError().data()
                error_message = bytes(error_data).decode('utf-8', 'ignore')

        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            logger.error(f"Winetricks install failed: {error_message}")
            QMessageBox.warning(self, _("Error"), _("Installation failed. Check logs."))
        else:
            if os.path.exists(self.log_path):
                with open(self.log_path) as f:
                    existing = {line.strip() for line in f if line.strip()}
            else:
                existing = set()
            with open(self.log_path, 'a') as f:
                for name in selected:
                    if name not in existing:
                        f.write(f"{name}\n")
            logger.info("Winetricks installation completed successfully.")
            QMessageBox.information(self, _("Success"), _("Components installed successfully."))
            self.load_lists()

        # Разблокировка
        self.install_button.setEnabled(True)
        self.force_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def _log(self, message):
        """Добавляет в лог."""
        self.log_output.append(message)
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
