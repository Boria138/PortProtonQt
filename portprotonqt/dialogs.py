import os
import shutil
import tempfile

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton,
    QHBoxLayout, QDialogButtonBox, QFileDialog, QLabel
)
from PySide6.QtCore import Qt
from icoextract import IconExtractor, IconExtractorError
from PIL import Image

from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
import portprotonqt.themes.standart.styles as default_styles

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

        # Game name
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE + " QLineEdit { color: #ffffff; font-size: 14px; }")
        if game_name:
            self.nameEdit.setText(game_name)
        name_label = QLabel(_("Game Name:"))
        name_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE + " QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }")
        layout.addRow(name_label, self.nameEdit)

        # Exe path
        self.exeEdit = QLineEdit(self)
        self.exeEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE + " QLineEdit { color: #ffffff; font-size: 14px; }")
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
        self.coverEdit.setStyleSheet(self.theme.SEARCH_EDIT_STYLE + " QLineEdit { color: #ffffff; font-size: 14px; }")
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
        fileNameAndFilter = QFileDialog.getOpenFileName(
            self,
            _("Select Executable"),
            "",
            "Windows Executables (*.exe)"
        )
        fileName = fileNameAndFilter[0]
        if fileName:
            self.exeEdit.setText(fileName)
            if not self.edit_mode:
                self.nameEdit.setText(os.path.splitext(os.path.basename(fileName))[0])

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

        user_cover_path = self.coverEdit.text().strip()
        if os.path.isfile(user_cover_path):
            shutil.copy(user_cover_path, icon_path)
        else:
            os.makedirs(os.path.dirname(icon_path), exist_ok=True)
            os.system(f'exe-thumbnailer "{exe_path}" "{icon_path}"')

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
