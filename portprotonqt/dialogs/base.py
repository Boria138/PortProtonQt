"""Base dialogs for PortProtonQt."""

import os
import tempfile
from typing import cast, TYPE_CHECKING
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout,
    QProgressBar, QSizePolicy, QWidget
)
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from icoextract import IconExtractor, IconExtractorError
from PIL import Image
import psutil

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

from portprotonqt.config_utils import get_portproton_location, read_theme_from_config
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.downloader import Downloader
from portprotonqt.virtual_keyboard import VirtualKeyboard
from portprotonqt.localization import _

logger = get_logger(__name__)
theme_manager = ThemeManager()


def generate_thumbnail(inputfile, outfile, size=128, force_resize=True):
    """
    Generates a thumbnail for an .exe file.

    inputfile: the input file path (%i)
    outfile: output filename (%o)
    size: determines the thumbnail output size (%s)
    """
    logger.debug(f"Starting thumbnail generation: {inputfile} → {outfile}, size={size}, force={force_resize}")

    try:
        extractor = IconExtractor(inputfile)
        logger.debug("IconExtractor created successfully.")
    except (RuntimeError, IconExtractorError) as e:
        logger.warning(f"Failed to create IconExtractor: {e}")
        return False

    try:
        data = extractor.get_icon()
        im = Image.open(data)
        logger.debug(f"Extracted icon size {im.size}, formats: {im.format}, frames: {getattr(im, 'n_frames', 1)}")
    except Exception as e:
        logger.warning(f"Error extracting icon: {e}")
        return False

    if force_resize:
        logger.debug(f"Forcing icon resize to {size}x{size}")
        im = im.resize((size, size))
    else:
        if size > 256:
            logger.warning('Requested size larger than 256, set to 256')
            size = 256
        elif size not in (128, 256):
            logger.warning(f'Unsupported size {size}, set to 128')
            size = 128

        if size == 256:
            logger.debug("Saving icon without resize (256x256)")
            im.save(outfile, "PNG")
            logger.info(f"Icon saved to {outfile}")
            return True

        frames = getattr(im, 'n_frames', 1)
        try:
            for frame in range(frames):
                im.seek(frame)
                if im.size == (size, size):
                    logger.debug(f"Found frame with size {size}x{size}")
                    break
        except EOFError:
            logger.debug("Frames ended before finding required size.")

        if im.size != (size, size):
            logger.debug(f"Resizing from {im.size} to {size}x{size}")
            im = im.resize((size, size))

    try:
        im.save(outfile, "PNG")
        logger.info(f"Thumbnail successfully saved to {outfile}")
        return True
    except Exception as e:
        logger.error(f"Error saving thumbnail: {e}")
        return False


class FileSelectedSignal(QObject):
    """Signal class for file selection."""
    file_selected = Signal(str)


class GameLaunchDialog(QDialog):
    """Modal dialog to indicate game launch progress, similar to Steam's launch dialog."""

    def __init__(self, parent=None, game_name=None, theme=None, target_exe=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.game_name = game_name
        self.target_exe = target_exe
        self.setWindowTitle(_("Launching {0}").format(self.game_name))
        self.setModal(True)
        self.setFixedSize(400, 200)
        self.setStyleSheet(self.theme.MESSAGE_BOX_STYLE)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        label = QLabel(_("Launching {0}").format(self.game_name))
        label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel"))
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)

        if parent:
            parent_geometry = parent.geometry()
            center_point = parent_geometry.center()
            dialog_geometry = self.geometry()
            dialog_geometry.moveCenter(center_point)
            self.setGeometry(dialog_geometry)

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
            self.accept()
            self.check_process_timer.stop()
            self.check_process_timer.deleteLater()
        elif not hasattr(self.parent(), 'game_processes') or not any(proc.poll() is None for proc in cast("MainWindow", self.parent()).game_processes):
            self.check_process_timer.stop()
            self.check_process_timer.deleteLater()

    def reject(self):
        """Handle dialog cancellation."""
        logger.info(f"Game launch cancelled for {self.game_name}")
        self.check_process_timer.stop()
        self.check_process_timer.deleteLater()
        super().reject()


class AddGameDialog(QDialog):
    """Dialog for adding or editing a game."""

    def __init__(self, parent=None, theme=None, edit_mode=False, game_name=None, exe_path=None, cover_path=None):
        super().__init__(parent)
        from portprotonqt.context_menu_manager import CustomLineEdit
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.edit_mode = edit_mode
        self.last_exe_path = exe_path
        self.last_cover_path = cover_path
        self.downloader = Downloader(max_workers=4)

        self.setWindowTitle(_("Edit Game") if edit_mode else _("Add Game"))
        self.setModal(True)
        self.setFixedWidth(600)
        self.setFixedHeight(600)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.nameEdit = CustomLineEdit(self, theme=self.theme)
        self.nameEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if game_name:
            self.nameEdit.setText(game_name)
        name_label = QLabel(_("Game Name:"))
        name_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        layout.addRow(name_label, self.nameEdit)

        exe_label = QLabel(_("Path to Executable:"))
        exe_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)

        self.exeEdit = CustomLineEdit(self, theme=self.theme)
        self.exeEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if exe_path:
            self.exeEdit.setText(exe_path)

        exeBrowseButton = AutoSizeButton(_("Browse..."), icon=theme_manager.get_icon("search"))
        exeBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        exeBrowseButton.clicked.connect(self.browseExe)
        exeBrowseButton.setObjectName("exeBrowseButton")

        layout.addRow(exe_label, self.exeEdit)

        empty_label = QLabel("")
        empty_label.setFixedWidth(exe_label.sizeHint().width())
        layout.addRow(empty_label, exeBrowseButton)

        cover_label = QLabel(_("Custom Cover:"))
        cover_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)

        self.coverEdit = CustomLineEdit(self, theme=self.theme)
        self.coverEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        self.coverEdit.setPlaceholderText(_("Enter local path or URL for cover image"))
        if cover_path:
            self.coverEdit.setText(cover_path)

        coverBrowseButton = AutoSizeButton(_("Browse..."), icon=theme_manager.get_icon("search"))
        coverBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        coverBrowseButton.clicked.connect(self.browseCover)
        coverBrowseButton.setObjectName("coverBrowseButton")

        layout.addRow(cover_label, self.coverEdit)
        layout.addRow(empty_label, coverBrowseButton)

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

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.select_button = AutoSizeButton(_("Apply"), icon=theme_manager.get_icon("apply"))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel"))
        self.select_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.button_layout.addWidget(self.select_button)
        self.button_layout.addWidget(self.cancel_button)
        layout.addRow(self.button_layout)

        self.select_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.cover_preview_timer = QTimer(self)
        self.cover_preview_timer.setSingleShot(True)
        self.cover_preview_timer.timeout.connect(self.updatePreview)

        self.coverEdit.textChanged.connect(self.onCoverTextChanged)
        self.exeEdit.textChanged.connect(self.updatePreview)

        def update_button_widths():
            exeBrowseButton.setFixedWidth(self.exeEdit.width())
            coverBrowseButton.setFixedWidth(self.coverEdit.width())

        QTimer.singleShot(0, update_button_widths)

        if edit_mode:
            self.updatePreview()

        self.init_keyboard()
        QTimer.singleShot(0, lambda: self.nameEdit.setFocus())

    def init_keyboard(self):
        """Initialize virtual keyboard."""
        self.keyboard = VirtualKeyboard(self, theme=self.theme, button_width=40)
        self.keyboard.hide()

    def show_keyboard_for_widget(self, widget):
        """Show keyboard for specified widget."""
        if not widget or not widget.isVisible():
            return

        self.keyboard.current_input_widget = widget

        keyboard_height = 220
        self.keyboard.setFixedWidth(self.width())
        self.keyboard.setFixedHeight(keyboard_height)
        self.keyboard.move(0, self.height() - keyboard_height)

        self.keyboard.setParent(self)
        self.keyboard.show()
        self.keyboard.raise_()

        first_button = self.keyboard.findFirstFocusableButton()
        if first_button:
            QTimer.singleShot(50, lambda: first_button.setFocus())

    def closeEvent(self, event):
        """Handle window close."""
        if hasattr(self, 'keyboard'):
            self.keyboard.hide()
        super().closeEvent(event)

    def reject(self):
        """Handle Cancel button."""
        if hasattr(self, 'keyboard'):
            self.keyboard.hide()
        super().reject()

    def accept(self):
        """Handle Apply button."""
        if hasattr(self, 'keyboard'):
            self.keyboard.hide()
        super().accept()

    def browseExe(self):
        """Open file manager to select exe file."""
        try:
            from portprotonqt.dialogs.file_explorer import FileExplorer
            initial_path = os.path.dirname(self.last_exe_path) if self.last_exe_path and os.path.isfile(self.last_exe_path) else None
            file_explorer = FileExplorer(self, file_filter='.exe', initial_path=initial_path)
            file_explorer.file_signal.file_selected.connect(self.onExeSelected)

            parent_widget = self.parentWidget()
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
        """Handle file selection in FileExplorer."""
        self.exeEdit.setText(file_path)
        self.last_exe_path = file_path
        if not self.edit_mode and not self.nameEdit.text().strip():
            game_name = os.path.splitext(os.path.basename(file_path))[0]
            self.nameEdit.setText(game_name)
        self.updatePreview()

    def browseCover(self):
        """Open file manager to select cover image."""
        try:
            from portprotonqt.dialogs.file_explorer import FileExplorer
            initial_path = os.path.dirname(self.last_cover_path) if self.last_cover_path and os.path.isfile(self.last_cover_path) else None
            file_explorer = FileExplorer(self, file_filter=('.png', '.jpg', '.jpeg', '.bmp'), initial_path=initial_path)
            file_explorer.file_signal.file_selected.connect(self.onCoverSelected)

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
        """Handle cover file selection in FileExplorer."""
        if file_path and os.path.splitext(file_path)[1].lower() in ('.png', '.jpg', '.jpeg', '.bmp'):
            self.coverEdit.setText(file_path)
            self.last_cover_path = file_path
            self.updatePreview()
        else:
            logger.warning(f"Selected file is not a valid image: {file_path}")

    def handleDownloadedCover(self, file_path):
        """Handle the downloaded cover image and update the preview."""
        if not hasattr(self, 'coverPreview') or self.coverPreview is None:
            return

        try:
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
        except RuntimeError:
            pass

    def onCoverTextChanged(self):
        """Handle cover text changes with debounce."""
        self.cover_preview_timer.start(500)

    def updatePreview(self):
        """Update the cover preview image."""
        cover_path = self.coverEdit.text().strip()
        exe_path = self.exeEdit.text().strip()

        image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')
        has_image_extension = any(cover_path.lower().endswith(ext) for ext in image_extensions)

        if has_image_extension and not os.path.isfile(cover_path):
            fd, local_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            os.unlink(local_path)

            download_url = cover_path if cover_path.startswith(('http://', 'https://')) else f'https://{cover_path}'
            self.downloader.download_async(
                url=download_url,
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
        """Returns the .desktop content and save path."""
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

        if not self.last_cover_path and not generate_thumbnail(exe_path, icon_path, size=128):
            logger.error(f"Failed to generate thumbnail from exe: {exe_path}")
            icon_path = ""

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
