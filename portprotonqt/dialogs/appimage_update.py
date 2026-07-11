"""AppImage update dialogs."""

from typing import cast, TYPE_CHECKING
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressDialog, QTextEdit, QVBoxLayout

from portprotonqt.appimage_updater import AppImageUpdateWorker
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.dialogs.base import DraggableDialog
from portprotonqt.localization import _

if TYPE_CHECKING:
    from portprotonqt.input_manager import InputManager


class AppImageUpdateDialog(DraggableDialog):
    """Dialog showing AppImage update changelog and actions."""

    UPDATE = 1
    LATER = 0
    DISABLE = 2

    def __init__(self, parent=None, theme=None, changelog: str = "") -> None:
        super().__init__(parent)
        self.theme = theme
        self.changelog = changelog.replace("\\n", "\n").strip()
        self.input_manager: InputManager | None = None
        self.changelog_text: QTextEdit | None = None
        self.action_buttons: list[AutoSizeButton] = []
        self.setWindowTitle(_("Update available"))
        self.setModal(True)
        self.resize(720, 520)
        if self.theme is not None:
            self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
        self._find_input_manager()
        self._setup_ui()

    def _find_input_manager(self) -> None:
        parent_obj = self.parent()
        while parent_obj:
            im = getattr(parent_obj, 'input_manager', None)
            if im is not None:
                self.input_manager = cast("InputManager", im)
            parent_obj = parent_obj.parent()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel(_("A new AppImage update is available."))
        if self.theme is not None:
            title.setStyleSheet(self.theme.SETTINGS_FRAME_TITLE_STYLE)
        layout.addWidget(title)

        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.changelog_text.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.changelog_text.setPlainText(self.changelog)
        if self.theme is not None:
            self.changelog_text.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE + self.theme.SCROLL_STYLE)
        layout.addWidget(self.changelog_text)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        update_button = self._make_button(_("Update"))
        later_button = self._make_button(_("Later"))
        disable_button = self._make_button(_("Disable updates"))
        self.action_buttons = [update_button, later_button, disable_button]
        buttons_layout.addWidget(update_button)
        buttons_layout.addWidget(later_button)
        buttons_layout.addWidget(disable_button)
        layout.addLayout(buttons_layout)

        update_button.clicked.connect(lambda: self.done(self.UPDATE))
        later_button.clicked.connect(lambda: self.done(self.LATER))
        disable_button.clicked.connect(lambda: self.done(self.DISABLE))

        if self.input_manager:
            self.input_manager.enable_appimage_update_mode(self)

    def _make_button(self, text: str) -> AutoSizeButton:
        button = AutoSizeButton(text)
        if self.theme is not None:
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return button

    def closeEvent(self, event) -> None:
        if self.input_manager:
            self.input_manager.disable_appimage_update_mode()
        super().closeEvent(event)

    def reject(self) -> None:
        if self.input_manager:
            self.input_manager.disable_appimage_update_mode()
        super().reject()

    def accept(self) -> None:
        if self.input_manager:
            self.input_manager.disable_appimage_update_mode()
        super().accept()


class AppImageUpdateProgressDialog(QProgressDialog):
    """Dialog that runs AppImage update and displays tool output."""

    update_finished = Signal(bool)

    def __init__(self, parent=None, update_info: str = "") -> None:
        super().__init__(_("Updating AppImage..."), "", 0, 0, parent)
        self.update_info = update_info
        self.worker: AppImageUpdateWorker | None = None
        self.setWindowTitle(_("Update"))
        self.setCancelButton(None)
        self.setMinimumDuration(0)

    def start_update(self) -> None:
        self.worker = AppImageUpdateWorker("update", self.update_info)
        self.worker.update_output.connect(self.setLabelText)
        self.worker.update_progress.connect(self._set_progress)
        self.worker.update_finished.connect(self._finish_update)
        self.worker.finished.connect(self._clear_worker)
        self.worker.finished.connect(self.worker.deleteLater)
        self.show()
        self.worker.start()

    def _set_progress(self, percent: int, message: str) -> None:
        if self.maximum() == 0:
            self.setRange(0, 100)
        self.setValue(percent)
        self.setLabelText(message)

    def _finish_update(self, success: bool) -> None:
        self.close()
        self.update_finished.emit(success)

    def _clear_worker(self) -> None:
        self.worker = None
