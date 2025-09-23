import os
import tempfile
import re
from typing import cast, TYPE_CHECKING
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QListWidget, QScrollArea, QWidget, QListWidgetItem, QSizePolicy, QApplication, QProgressBar
)
from PySide6.QtCore import Qt, QObject, Signal, QMimeDatabase, QTimer, QThreadPool, QRunnable, Slot
from icoextract import IconExtractor, IconExtractorError
from PIL import Image
from portprotonqt.config_utils import get_portproton_location, read_favorite_folders, read_theme_from_config
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.downloader import Downloader
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
            if item and item.widget():
                widget = item.widget()
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
