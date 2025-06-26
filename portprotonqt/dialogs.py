import os
import tempfile
import time


from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton,
    QHBoxLayout, QDialogButtonBox, QFileDialog, QLabel, QVBoxLayout, QListWidget
)
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from icoextract import IconExtractor, IconExtractorError
from PIL import Image

from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.themes.standart.styles import FileExplorerStyles

from evdev import ecodes

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_signal = FileSelectedSignal()
        self.setup_ui()

        # Настройки окна
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(FileExplorerStyles.WINDOW_STYLE)

        # Для управления геймпадом
        self.input_manager = None
        self.gamepad_connected = False
        self.setup_gamepad_handling()

        # Для плавного перемещения
        self.nav_timer = QTimer(self)
        self.nav_timer.timeout.connect(self.handle_navigation_repeat)
        self.current_direction = 0
        self.last_nav_time = 0
        self.initial_nav_delay = 0.1  # Начальная задержка перед первым повторением (сек)
        self.repeat_nav_delay = 0.05  # Интервал между повторениями (сек)
        self.stick_activated = False
        self.stick_value = 0  # Текущее значение стика (для плавности)
        self.dead_zone = 8000  # Мертвая зона стика

    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle("File Explorer")
        self.setGeometry(100, 100, 800, 600)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.setLayout(self.layout)

        self.path_label = QLabel()
        self.path_label.setStyleSheet(FileExplorerStyles.PATH_LABEL_STYLE)
        self.layout.addWidget(self.path_label)

        # Список файлов
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(FileExplorerStyles.LIST_STYLE)
        self.file_list.itemClicked.connect(self.handle_item_click)
        self.layout.addWidget(self.file_list)

        # Кнопки всякие
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.select_button = QPushButton("Select (A)")
        self.cancel_button = QPushButton("Cancel (B)")
        self.select_button.setStyleSheet(FileExplorerStyles.BUTTON_STYLE)
        self.cancel_button.setStyleSheet(FileExplorerStyles.BUTTON_STYLE)
        self.button_layout.addWidget(self.select_button)
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)

        self.select_button.clicked.connect(self.select_item)
        self.cancel_button.clicked.connect(self.reject)

        # Чтобы хомяк открывался
        self.current_path = os.path.expanduser("~")
        self.update_file_list()

    def setup_gamepad_handling(self):
        """Настройка обработки геймпада"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'input_manager'):
                self.input_manager = parent.input_manager
                break
            parent = parent.parent()

        if self.input_manager:
            try:
                # Сохраняем оригинальные обработчики геймпада (нужно для возврата управления)
                self.original_button_handler = self.input_manager.handle_button_slot
                self.original_dpad_handler = self.input_manager.handle_dpad_slot
                self.original_gamepad_state = self.input_manager._gamepad_handling_enabled

                # Устанавливаем свои обработчики геймпада для файлового менеджера
                self.input_manager.handle_button_slot = self.handle_gamepad_button
                self.input_manager.handle_dpad_slot = self.handle_dpad_movement
                self.input_manager._gamepad_handling_enabled = True

                self.gamepad_connected = True
                logger.debug("Gamepad handling successfully connected")
            except Exception as e:
                logger.error(f"Error connecting gamepad handlers: {e}")
                self.gamepad_connected = False

    def handle_gamepad_button(self, button_code):
        """Обработка кнопок геймпада"""
        try:
            if not self or not hasattr(self, 'file_list'):
                return

            if button_code in {ecodes.BTN_SOUTH}:  # Кнопка A
                self.select_item()
            elif button_code in {ecodes.BTN_EAST}:  # Кнопка B
                self.close()
            else:
                if hasattr(self, 'original_button_handler') and self.original_button_handler:
                    self.original_button_handler(button_code)
        except Exception as e:
            logger.error(f"Error in gamepad button handler: {e}")

    def handle_dpad_movement(self, code, value, current_time):
        """Обработка движения D-pad и левого стика"""
        try:
            if not self or not hasattr(self, 'file_list') or not self.file_list:
                return

            if not self.file_list.count():
                return

            if code in (ecodes.ABS_HAT0Y, ecodes.ABS_Y):
                # Для D-pad - реакция с фиксированной скоростью
                if code == ecodes.ABS_HAT0Y:
                    if value != 0:
                        self.current_direction = value
                        self.stick_value = 1.0  # Максимальная скорость для D-pad, чтобы скачков не было
                        if not self.nav_timer.isActive():
                            self.move_selection(self.current_direction)
                            self.last_nav_time = current_time
                            self.nav_timer.start(int(self.initial_nav_delay * 1000))
                    else:
                        self.current_direction = 0
                        self.nav_timer.stop()

                # Для стика - плавное управление с учетом степени отклонения
                elif code == ecodes.ABS_Y:
                    if abs(value) < self.dead_zone:
                        if self.stick_activated:
                            self.current_direction = 0
                            self.nav_timer.stop()
                            self.stick_activated = False
                        return

                    # Рассчитываем "силу" отклонения (0.3 - 1.0)
                    normalized_value = (abs(value) - self.dead_zone) / (32768 - self.dead_zone)
                    speed_factor = 0.3 + (normalized_value * 0.7)  # От 30% до 100% скорости

                    self.current_direction = -1 if value < 0 else 1
                    self.stick_value = speed_factor
                    self.stick_activated = True

                    if not self.nav_timer.isActive():
                        self.move_selection(self.current_direction)
                        self.last_nav_time = current_time
                        self.nav_timer.start(int(self.initial_nav_delay * 1000))

            else:
                if hasattr(self, 'original_dpad_handler') and self.original_dpad_handler:
                    self.original_dpad_handler(code, value, current_time)
        except Exception as e:
            logger.error(f"Error in dpad handler: {e}")

    def handle_navigation_repeat(self):
        """Плавное повторение движения с переменной скоростью"""
        try:
            if not self or not hasattr(self, 'file_list') or not self.file_list:
                return

            if self.current_direction != 0:
                now = time.time()
                # Динамический интервал в зависимости от stick_value
                dynamic_delay = self.repeat_nav_delay / self.stick_value
                if now - self.last_nav_time >= dynamic_delay:
                    self.move_selection(self.current_direction)
                    self.last_nav_time = now
        except Exception as e:
            logger.error(f"Error in navigation repeat: {e}")

    def restore_gamepad_handling(self):
        """Восстановление оригинальных обработчиков главного окна программы (дефолт возвращаем)"""
        try:
            if self.input_manager and self.gamepad_connected:
                if hasattr(self, 'original_button_handler') and self.original_button_handler:
                    self.input_manager.handle_button_slot = self.original_button_handler

                if hasattr(self, 'original_dpad_handler') and self.original_dpad_handler:
                    self.input_manager.handle_dpad_slot = self.original_dpad_handler

                if hasattr(self, 'original_gamepad_state'):
                    self.input_manager._gamepad_handling_enabled = self.original_gamepad_state

                self.gamepad_connected = False
                logger.debug("Gamepad handling successfully restored")
        except Exception as e:
            logger.error(f"Error restoring gamepad handlers: {e}")

    def move_selection(self, direction):
        """Перемещение выбора по списку"""
        current_row = self.file_list.currentRow()
        if direction < 0 and current_row > 0:  # Вверх
            self.file_list.setCurrentRow(current_row - 1)
        elif direction > 0 and current_row < self.file_list.count() - 1:  # Вниз
            self.file_list.setCurrentRow(current_row + 1)
        self.file_list.scrollToItem(self.file_list.currentItem())

    def handle_item_click(self, item):
        """Обработка левого клика мышкой"""
        self.file_list.setCurrentItem(item)
        self.select_item()

    def select_item(self):
        """Обработка выбора файла/папки"""
        if self.file_list.count() == 0:
            return

        selected = self.file_list.currentItem().text()
        full_path = os.path.join(self.current_path, selected)

        if os.path.isdir(full_path):
            self.current_path = full_path
            self.update_file_list()
        else:
            self.file_signal.file_selected.emit(full_path)
            self.accept()

    def update_file_list(self):
        """Обновление списка файлов"""
        self.file_list.clear()
        try:
            if self.current_path != "/":
                self.file_list.addItem("../")

            items = os.listdir(self.current_path)
            dirs = [d for d in items if os.path.isdir(os.path.join(self.current_path, d))]
            files = [f for f in items if os.path.isfile(os.path.join(self.current_path, f))]

            for d in sorted(dirs):
                self.file_list.addItem(f"{d}/")

            for f in sorted(files):
                self.file_list.addItem(f)

            self.path_label.setText(f"Path: {self.current_path}")
            self.file_list.setCurrentRow(0)

        except PermissionError:
            self.path_label.setText(f"Access denied: {self.current_path}")

    def closeEvent(self, event):
        """Закрываем окно"""
        try:
            self.restore_gamepad_handling()
            self.nav_timer.stop()

            if self.parent():
                self.parent().activateWindow()
                self.parent().setFocus()
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")

        super().closeEvent(event)

    def reject(self):
        """Закрываем окно диалога (два)"""
        self.restore_gamepad_handling()
        super().reject()

    def accept(self):
        """Принятие (применение) диалога"""
        self.restore_gamepad_handling()
        super().accept()


class AddGameDialog(QDialog):
    def __init__(self, parent=None, theme=None, edit_mode=False, game_name=None, exe_path=None, cover_path=None):
        super().__init__(parent)
        self.theme = theme if theme else default_styles
        self.edit_mode = edit_mode
        self.original_name = game_name

        self.setWindowTitle(_("Edit Game") if edit_mode else _("Add Game"))
        self.setModal(True)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # Game name
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if game_name:
            self.nameEdit.setText(game_name)
        name_label = QLabel(_("Game Name:"))
        name_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(name_label, self.nameEdit)

        # Exe path
        self.exeEdit = QLineEdit(self)
        self.exeEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if exe_path:
            self.exeEdit.setText(exe_path)
        exeBrowseButton = QPushButton(_("Browse..."), self)
        exeBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        exeBrowseButton.clicked.connect(self.browseExe)

        exeLayout = QHBoxLayout()
        exeLayout.addWidget(self.exeEdit)
        exeLayout.addWidget(exeBrowseButton)
        exe_label = QLabel(_("Path to Executable:"))
        exe_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(exe_label, exeLayout)

        # Cover path
        self.coverEdit = QLineEdit(self)
        self.coverEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if cover_path:
            self.coverEdit.setText(cover_path)
        coverBrowseButton = QPushButton(_("Browse..."), self)
        coverBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        coverBrowseButton.clicked.connect(self.browseCover)

        coverLayout = QHBoxLayout()
        coverLayout.addWidget(self.coverEdit)
        coverLayout.addWidget(coverBrowseButton)
        cover_label = QLabel(_("Custom Cover:"))
        cover_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(cover_label, coverLayout)

        # Preview
        self.coverPreview = QLabel(self)
        self.coverPreview.setStyleSheet(self.theme.CONTENT_STYLE + " QLabel { color: #ffffff; }")
        preview_label = QLabel(_("Cover Preview:"))
        preview_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(preview_label, self.coverPreview)

        # Dialog buttons
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addRow(buttonBox)

        self.coverEdit.textChanged.connect(self.updatePreview)
        self.exeEdit.textChanged.connect(self.updatePreview)

        if edit_mode:
            self.updatePreview()

    def browseExe(self):
        """Открывает файловый менеджер для выбора exe-файла"""
        try:
            file_explorer = FileExplorer(self)
            file_explorer.file_signal.file_selected.connect(self.onExeSelected)

            if self.parent():
                center_point = self.parent().geometry().center()
                file_explorer.move(center_point - file_explorer.rect().center())

            file_explorer.show()
        except Exception as e:
            logger.error(f"Error in browseExe: {e}")

    def onExeSelected(self, file_path):
        """Обработчик выбора файла в FileExplorer"""
        self.exeEdit.setText(file_path)
        if not self.edit_mode:
            # Автоматически заполняем имя игры, если не в режиме редактирования
            game_name = os.path.splitext(os.path.basename(file_path))[0]
            self.nameEdit.setText(game_name)

        # Обновляем превью
        self.updatePreview()

    def browseCover(self):
        fileNameAndFilter = QFileDialog.getOpenFileName(
            self,
            _("Select Cover Image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        fileName = fileNameAndFilter[0]
        if fileName:
            self.coverEdit.setText(fileName)

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
