import os
import tempfile
from typing import cast, TYPE_CHECKING
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton,
    QHBoxLayout, QLabel, QVBoxLayout, QListWidget, QScrollArea, QWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QObject, Signal, QMimeDatabase, QTimer
from icoextract import IconExtractor, IconExtractorError
from PIL import Image
from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

logger = get_logger(__name__)

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

class FileExplorer(QDialog):
    def __init__(self, parent=None, theme=None, file_filter=None, initial_path=None):
        super().__init__(parent)
        self.theme = theme if theme else default_styles
        self.theme_manager = ThemeManager()
        self.file_signal = FileSelectedSignal()
        self.file_filter = file_filter  # Store the file filter
        self.mime_db = QMimeDatabase()  # Initialize QMimeDatabase for mimetype detection
        self.path_history = {}  # Dictionary to store last selected item per directory
        self.initial_path = initial_path  # Store initial path if provided
        self.setup_ui()

        # Настройки окна
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Find InputManager from parent
        self.input_manager = None
        parent = self.parent()
        while parent:
            if hasattr(parent, 'input_manager'):
                self.input_manager = cast("MainWindow", parent).input_manager
                break
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

    def get_mounted_drives(self):
        """Получение списка смонтированных дисков из /proc/mounts, исключая системные пути"""
        mounted_drives = []
        try:
            with open('/proc/mounts') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                    mount_point = parts[1]
                    # Исключаем системные и временные пути
                    if mount_point.startswith(('/run', '/dev', '/sys', '/proc', '/tmp', '/snap', '/var/lib')):
                        continue
                    # Проверяем, является ли точка монтирования директорией и доступна ли она
                    if os.path.isdir(mount_point) and os.access(mount_point, os.R_OK):
                        mounted_drives.append(mount_point)
            return sorted(mounted_drives)
        except Exception as e:
            logger.error(f"Ошибка при получении смонтированных дисков: {e}")
            return []

    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle("File Explorer")
        self.setGeometry(100, 100, 600, 600)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        self.setLayout(self.main_layout)

        # Панель для смонтированных дисков
        self.drives_layout = QHBoxLayout()
        self.drives_scroll = QScrollArea()
        self.drives_scroll.setWidgetResizable(True)
        self.drives_container = QWidget()
        self.drives_container.setLayout(self.drives_layout)
        self.drives_scroll.setWidget(self.drives_container)
        self.drives_scroll.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        self.drives_scroll.setFixedHeight(60)
        self.main_layout.addWidget(self.drives_scroll)

        # Путь
        self.path_label = QLabel()
        self.path_label.setStyleSheet(self.theme.FILE_EXPLORER_PATH_LABEL_STYLE)
        self.main_layout.addWidget(self.path_label)

        # Список файлов
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(self.theme.FILE_EXPLORER_STYLE)
        self.file_list.itemClicked.connect(self.handle_item_click)
        self.main_layout.addWidget(self.file_list)

        # Кнопки
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.select_button = AutoSizeButton(_("Select"), icon=self.theme_manager.get_icon("apply"))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=self.theme_manager.get_icon("cancel"))
        self.select_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.button_layout.addWidget(self.select_button)
        self.button_layout.addWidget(self.cancel_button)
        self.main_layout.addLayout(self.button_layout)

        self.select_button.clicked.connect(self.select_item)
        self.cancel_button.clicked.connect(self.reject)

    def move_selection(self, direction):
        """Перемещение выбора по списку"""
        current_row = self.file_list.currentRow()
        if direction < 0 and current_row > 0:  # Вверх
            self.file_list.setCurrentRow(current_row - 1)
        elif direction > 0 and current_row < self.file_list.count() - 1:  # Вниз
            self.file_list.setCurrentRow(current_row + 1)
        self.file_list.scrollToItem(self.file_list.currentItem())

    def handle_item_click(self, item):
        """Обработка клика мышью"""
        self.file_list.setCurrentItem(item)
        self.path_history[self.current_path] = item.text()  # Save the selected item
        self.select_item()

    def select_item(self):
        """Обработка выбора файла/папки"""
        if self.file_list.count() == 0:
            return

        selected = self.file_list.currentItem().text()
        full_path = os.path.join(self.current_path, selected)

        if os.path.isdir(full_path):
            # Если выбрана директория, нормализуем путь
            self.current_path = os.path.normpath(full_path)
            self.update_file_list()
        else:
            # Для файла отправляем нормализованный путь
            self.file_signal.file_selected.emit(os.path.normpath(full_path))
            self.accept()

    def previous_dir(self):
        """Возврат к родительской директории"""
        try:
            if self.current_path == "/":
                return  # Уже в корне

            # Нормализуем путь (убираем конечный слеш, если есть)
            normalized_path = os.path.normpath(self.current_path)
            # Получаем родительскую директорию
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

    def update_drives_list(self):
        """Обновление списка смонтированных дисков"""
        for i in reversed(range(self.drives_layout.count())):
            widget = self.drives_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        drives = self.get_mounted_drives()
        for drive in drives:
            drive_name = os.path.basename(drive) or drive.split('/')[-1] or drive
            button = AutoSizeButton(drive_name, icon=self.theme_manager.get_icon("mount_point"))
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            button.clicked.connect(lambda checked, path=drive: self.change_drive(path))
            self.drives_layout.addWidget(button)
        self.drives_layout.addStretch()

    def change_drive(self, drive_path):
        """Переход к выбранному диску"""
        if os.path.isdir(drive_path) and os.access(drive_path, os.R_OK):
            self.current_path = os.path.normpath(drive_path)
            self.update_file_list()
        else:
            logger.warning(f"Путь диска недоступен: {drive_path}")

    def update_file_list(self):
        """Обновление списка файлов с превью в виде иконок"""
        self.file_list.clear()
        try:
            if self.current_path != "/":
                item = QListWidgetItem("../")
                folder_icon = self.theme_manager.get_icon("folder")
                # Ensure the icon is a QIcon
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()  # Fallback to empty icon
                item.setIcon(folder_icon)
                self.file_list.addItem(item)

            items = os.listdir(self.current_path)
            dirs = [d for d in items if os.path.isdir(os.path.join(self.current_path, d))]

            # Apply file filter if provided
            files = [f for f in items if os.path.isfile(os.path.join(self.current_path, f))]
            if self.file_filter:
                if isinstance(self.file_filter, str):
                    files = [f for f in files if f.lower().endswith(self.file_filter)]
                elif isinstance(self.file_filter, tuple):
                    files = [f for f in files if any(f.lower().endswith(ext) for ext in self.file_filter)]

            for d in sorted(dirs):
                item = QListWidgetItem(f"{d}/")
                folder_icon = self.theme_manager.get_icon("folder")
                # Ensure the icon is a QIcon
                if isinstance(folder_icon, str) and os.path.isfile(folder_icon):
                    folder_icon = QIcon(folder_icon)
                elif not isinstance(folder_icon, QIcon):
                    folder_icon = QIcon()  # Fallback to empty icon
                item.setIcon(folder_icon)
                self.file_list.addItem(item)

            for f in sorted(files):
                item = QListWidgetItem(f)
                file_path = os.path.join(self.current_path, f)
                mime_type = self.mime_db.mimeTypeForFile(file_path).name()

                if mime_type.startswith("image/"):
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        item.setIcon(QIcon(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)))
                elif file_path.lower().endswith(".exe"):
                    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    tmp.close()
                    if generate_thumbnail(file_path, tmp.name, size=64):
                        pixmap = QPixmap(tmp.name)
                        if not pixmap.isNull():
                            item.setIcon(QIcon(pixmap))
                        os.unlink(tmp.name)

                self.file_list.addItem(item)

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
            self.path_label.setText(f"Access denied: {self.current_path}")

    def closeEvent(self, event):
        """Закрытие окна"""
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
        """Закрытие диалога"""
        if self.input_manager:
            self.input_manager.disable_file_explorer_mode()
        super().reject()

    def accept(self):
        """Принятие диалога"""
        if self.input_manager:
            self.input_manager.disable_file_explorer_mode()
        super().accept()

class AddGameDialog(QDialog):
    def __init__(self, parent=None, theme=None, edit_mode=False, game_name=None, exe_path=None, cover_path=None):
        super().__init__(parent)
        self.theme = theme if theme else default_styles
        self.theme_manager = ThemeManager()
        self.edit_mode = edit_mode
        self.original_name = game_name
        self.last_exe_path = exe_path  # Store last selected exe path
        self.last_cover_path = cover_path  # Store last selected cover path

        self.setWindowTitle(_("Edit Game") if edit_mode else _("Add Game"))
        self.setModal(True)
        self.setFixedWidth(600)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Game name
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if game_name:
            self.nameEdit.setText(game_name)
        name_label = QLabel(_("Game Name:"))
        name_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(name_label, self.nameEdit)

        # Exe path
        exe_label = QLabel(_("Path to Executable:"))
        exe_label.setStyleSheet(
            self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")

        self.exeEdit = QLineEdit(self)
        self.exeEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if exe_path:
            self.exeEdit.setText(exe_path)

        exeBrowseButton = QPushButton(_("Browse..."), self)
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
        cover_label.setStyleSheet(
            self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")

        self.coverEdit = QLineEdit(self)
        self.coverEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if cover_path:
            self.coverEdit.setText(cover_path)

        coverBrowseButton = QPushButton(_("Browse..."), self)
        coverBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        coverBrowseButton.clicked.connect(self.browseCover)
        coverBrowseButton.setObjectName("coverBrowseButton")  # Для поиска кнопки

        # Добавляем поле ввода для обложки
        layout.addRow(cover_label, self.coverEdit)

        # Добавляем кнопку обзора под полем ввода с выравниванием
        layout.addRow(empty_label, coverBrowseButton)

        # Preview
        self.coverPreview = QLabel(self)
        self.coverPreview.setStyleSheet(self.theme.CONTENT_STYLE + " QLabel { color: #ffffff; }")
        preview_label = QLabel(_("Cover Preview:"))
        preview_label.setStyleSheet(
            self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(preview_label, self.coverPreview)

        # Dialog buttons
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.select_button = AutoSizeButton(_("Select"), icon=self.theme_manager.get_icon("apply"))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=self.theme_manager.get_icon("cancel"))
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

        # Вызываем после отображения окна, когда размеры установлены, чтобы реально дождаться, когда всё сформируется
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
            self.last_cover_path = file_path  # Update last selected cover path
        else:
            logger.warning(f"Selected file is not a valid image: {file_path}")

    def updatePreview(self):
        """Update the cover preview image."""
        cover_path = self.coverEdit.text().strip()
        exe_path = self.exeEdit.text().strip()
        if cover_path and os.path.isfile(cover_path):
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

        if not exe_path or not name:
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

        # Generate thumbnail (128x128) from exe
        if not generate_thumbnail(exe_path, icon_path, size=128):
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
