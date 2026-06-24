"""Base dialogs for PortProtonQt."""

import os
import tempfile
from typing import cast, TYPE_CHECKING
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout,
    QProgressBar, QSizePolicy, QWidget, QCheckBox
)
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QStandardPaths, QSize
import psutil

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

from portprotonqt.config import (
    LAUNCH_FILE_EXTENSIONS,
    THEMED_LAUNCH_ICON_NAMES,
    create_desktop_file,
    ui_config,
)
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.downloader import Downloader
from portprotonqt.virtual_keyboard import VirtualKeyboard
from portprotonqt.localization import _
from portprotonqt.image_utils import COVER_IMAGE_EXTENSIONS, set_animated_cover
from portprotonqt.icon_extractor import generate_thumbnail

logger = get_logger(__name__)
theme_manager = ThemeManager()
DISC_IMAGE_EXTENSIONS = (".iso", ".mdf", ".nrg")


class FileSelectedSignal(QObject):
    """Signal class for file selection."""
    file_selected = Signal(str)


class DraggableDialog(QDialog):
    """Dialog with support for system move on left mouse press."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            window_handle = self.window().windowHandle()
            if window_handle is not None:
                window_handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


class GameLaunchDialog(DraggableDialog):
    """Modal dialog to indicate game launch progress, similar to Steam's launch dialog."""

    def __init__(self, parent=None, game_name=None, theme=None, target_exe=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(ui_config.get_theme())
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

        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel", as_path=True))
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


class AddGameDialog(DraggableDialog):
    """Dialog for adding or editing a game."""

    def __init__(self, parent=None, theme=None, edit_mode=False, game_name=None, exe_path=None, cover_path=None):
        super().__init__(parent)
        from portprotonqt.context_menu_manager import CustomLineEdit
        self.theme = theme if theme else theme_manager.apply_theme(ui_config.get_theme())
        self.edit_mode = edit_mode
        self.last_exe_path = exe_path
        self.last_cover_path = cover_path
        self.downloader = Downloader(max_workers=4)

        self.setWindowTitle(_("Edit Shortcut") if edit_mode else _("Add a shortcut"))
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
        name_label = QLabel(_("Name:"))
        name_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        layout.addRow(name_label, self.nameEdit)

        exe_label = QLabel(_("Path to Executable:"))
        exe_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)

        self.exeEdit = CustomLineEdit(self, theme=self.theme)
        self.exeEdit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        if exe_path:
            self.exeEdit.setText(exe_path)

        exeBrowseButton = AutoSizeButton(_("Browse…"), icon=theme_manager.get_icon("search", as_path=True))
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

        coverBrowseButton = AutoSizeButton(_("Browse…"), icon=theme_manager.get_icon("search", as_path=True))
        coverBrowseButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        coverBrowseButton.clicked.connect(self.browseCover)
        coverBrowseButton.setObjectName("coverBrowseButton")

        layout.addRow(cover_label, self.coverEdit)
        layout.addRow(empty_label, coverBrowseButton)

        self.add_to_steam_checkbox = QCheckBox()
        self.add_to_menu_checkbox = QCheckBox()
        self.add_to_desktop_checkbox = QCheckBox()
        self.add_to_steam_checkbox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.add_to_menu_checkbox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        self.add_to_desktop_checkbox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        if icon := theme_manager.get_icon("menu_steam"):
            self.add_to_steam_checkbox.setIcon(icon)
        if icon := theme_manager.get_icon("menu"):
            self.add_to_menu_checkbox.setIcon(icon)
        if icon := theme_manager.get_icon("desktop"):
            self.add_to_desktop_checkbox.setIcon(icon)
        self.add_to_steam_checkbox.setIconSize(QSize(20, 20))
        self.add_to_menu_checkbox.setIconSize(QSize(20, 20))
        self.add_to_desktop_checkbox.setIconSize(QSize(20, 20))
        options_layout = QHBoxLayout()
        options_layout.setSpacing(12)
        options_layout.addWidget(self.add_to_steam_checkbox)
        options_layout.addWidget(self.add_to_menu_checkbox)
        options_layout.addWidget(self.add_to_desktop_checkbox)
        options_layout.addStretch()
        options_widget = QWidget(self)
        options_widget.setLayout(options_layout)
        options_label = QLabel(_("Add shortcut to:"))
        options_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        layout.addRow(options_label, options_widget)

        current_name = game_name.strip() if game_name else self.nameEdit.text().strip()
        self.add_to_steam_checkbox.setChecked(self._steam_shortcut_exists(current_name))
        self.add_to_menu_checkbox.setChecked(self._menu_shortcut_exists(current_name))
        self.add_to_desktop_checkbox.setChecked(self._desktop_shortcut_exists(current_name))

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
        self.select_button = AutoSizeButton(_("Apply"), icon=theme_manager.get_icon("apply", as_path=True))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=theme_manager.get_icon("cancel", as_path=True))
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

    def _steam_shortcut_exists(self, game_name):
        """Check whether the game already exists in Steam shortcuts."""
        if not game_name:
            return False
        from portprotonqt.steam_api import is_game_in_steam
        return is_game_in_steam(game_name)

    def _menu_shortcut_exists(self, game_name):
        """Check whether the game .desktop shortcut exists in applications menu."""
        if not game_name:
            return False
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        return os.path.exists(os.path.join(applications_dir, f"{game_name}.desktop"))

    def _desktop_shortcut_exists(self, game_name):
        """Check whether the game .desktop shortcut exists on the Desktop."""
        if not game_name:
            return False
        desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        return os.path.exists(os.path.join(desktop_dir, f"{game_name}.desktop"))

    def init_keyboard(self):
        """Initialize virtual keyboard."""
        self.keyboard = VirtualKeyboard(self, theme=self.theme, button_width=40)
        self.keyboard.hide()

    def show_keyboard_for_widget(self, widget):
        """Show keyboard for specified widget."""
        if not widget or not widget.isVisible():
            return

        self.keyboard.show_for_widget(widget)

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
        """Open file manager to select executable or disc image."""
        try:
            from portprotonqt.dialogs.file_explorer import FileExplorer
            initial_path = os.path.dirname(self.last_exe_path) if self.last_exe_path and os.path.isfile(self.last_exe_path) else None
            file_explorer = FileExplorer(self, file_filter=LAUNCH_FILE_EXTENSIONS, initial_path=initial_path)
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
            file_explorer = FileExplorer(self, file_filter=COVER_IMAGE_EXTENSIONS, initial_path=initial_path)
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
        if file_path and os.path.splitext(file_path)[1].lower() in COVER_IMAGE_EXTENSIONS:
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
                if set_animated_cover(self.coverPreview, file_path, 250, 250):
                    return
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
        launch_path = exe_path

        if exe_path.lower().endswith(DISC_IMAGE_EXTENSIONS):
            parent_widget = cast("MainWindow | None", self.parentWidget())
            if parent_widget and hasattr(parent_widget, "resolve_launch_file_path"):
                resolved_path = parent_widget.resolve_launch_file_path(exe_path)
                if resolved_path and os.path.isfile(resolved_path):
                    launch_path = resolved_path

        has_image_extension = any(cover_path.lower().endswith(ext) for ext in COVER_IMAGE_EXTENSIONS)

        if has_image_extension and not os.path.isfile(cover_path):
            suffix = os.path.splitext(cover_path)[1].lower() or ".png"
            fd, local_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            os.unlink(local_path)

            download_url = cover_path if cover_path.startswith(('http://', 'https://')) else f'https://{cover_path}'
            self.downloader.download_async(
                url=download_url,
                local_path=local_path,
                timeout=10,
                callback=self.handleDownloadedCover
            )
            self.coverPreview.setText(_("Downloading cover…"))
        elif cover_path and os.path.isfile(cover_path):
            if set_animated_cover(self.coverPreview, cover_path, 250, 250):
                return
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                self.coverPreview.setPixmap(pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.coverPreview.setText(_("Invalid image"))
        elif os.path.isfile(launch_path) and launch_path.lower().endswith(".exe"):
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp.close()
            if generate_thumbnail(launch_path, tmp.name, size=128):
                pixmap = QPixmap(tmp.name)
                self.coverPreview.setPixmap(pixmap)
            os.unlink(tmp.name)
        elif os.path.isfile(launch_path):
            file_icon_name = THEMED_LAUNCH_ICON_NAMES.get(os.path.splitext(launch_path)[1].lower())
            file_icon_path = theme_manager.get_icon(file_icon_name, as_path=True) if file_icon_name else ""
            pixmap = QPixmap(file_icon_path) if isinstance(file_icon_path, str) and file_icon_path else QPixmap()
            if not pixmap.isNull():
                self.coverPreview.setPixmap(pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.coverPreview.setText(_("No cover selected"))
        else:
            self.coverPreview.setText(_("No cover selected"))

    def getDesktopEntryData(self):
        """Returns the .desktop content and save path."""
        exe_path = self.exeEdit.text().strip()
        name = self.nameEdit.text().strip()
        launch_path = exe_path

        if not exe_path or not os.path.isfile(exe_path):
            return None, None

        if not name:
            return None, None

        if exe_path.lower().endswith(DISC_IMAGE_EXTENSIONS):
            parent_widget = cast("MainWindow | None", self.parentWidget())
            if not parent_widget or not hasattr(parent_widget, "resolve_launch_file_path"):
                return None, None
            resolved_path = parent_widget.resolve_launch_file_path(exe_path)
            if not resolved_path or not os.path.isfile(resolved_path):
                return None, None
            launch_path = resolved_path

        result = create_desktop_file(exe_path, name)
        if not result:
            return None, None
        desktop_entry, desktop_path, icon_path = result

        file_icon_name = THEMED_LAUNCH_ICON_NAMES.get(os.path.splitext(launch_path)[1].lower())
        file_icon_path = theme_manager.get_icon(file_icon_name, as_path=True) if file_icon_name else ""
        if not self.last_cover_path and file_icon_path:
            desktop_entry = desktop_entry.replace(f"Icon={icon_path}\n", f"Icon={file_icon_path}\n")
        elif not self.last_cover_path and not generate_thumbnail(launch_path, icon_path, size=128):
            logger.error(f"Failed to generate thumbnail from exe: {launch_path}")
            desktop_entry = desktop_entry.replace(f"Icon={icon_path}\n", "Icon=\n")

        return desktop_entry, desktop_path
