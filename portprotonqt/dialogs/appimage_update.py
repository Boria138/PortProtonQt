"""AppImage update dialogs."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressDialog, QTextEdit, QVBoxLayout

from portprotonqt.appimage_updater import AppImageUpdateWorker
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.dialogs.base import DraggableDialog
from portprotonqt.localization import _


class AppImageUpdateDialog(DraggableDialog):
    """Dialog showing AppImage update changelog and actions."""

    UPDATE = 1
    LATER = 0
    DISABLE = 2

    def __init__(self, parent=None, theme=None, changelog: str = "") -> None:
        super().__init__(parent)
        self.theme = theme
        self.changelog = changelog.replace("\\n", "\n").strip()
        self.setWindowTitle(_("Update available"))
        self.setModal(True)
        self.resize(720, 520)
        if self.theme is not None:
            self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel(_("A new AppImage update is available."))
        if self.theme is not None:
            title.setStyleSheet(self.theme.SETTINGS_FRAME_TITLE_STYLE)
        layout.addWidget(title)

        changelog_text = QTextEdit()
        changelog_text.setReadOnly(True)
        changelog_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        changelog_text.setPlainText(self.changelog)
        if self.theme is not None:
            changelog_text.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE + self.theme.SCROLL_STYLE)
        layout.addWidget(changelog_text)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        update_button = self._make_button(_("Update"))
        later_button = self._make_button(_("Later"))
        disable_button = self._make_button(_("Disable updates"))
        buttons_layout.addWidget(update_button)
        buttons_layout.addWidget(later_button)
        buttons_layout.addWidget(disable_button)
        layout.addLayout(buttons_layout)

        update_button.clicked.connect(lambda: self.done(self.UPDATE))
        later_button.clicked.connect(lambda: self.done(self.LATER))
        disable_button.clicked.connect(lambda: self.done(self.DISABLE))

    def _make_button(self, text: str) -> AutoSizeButton:
        button = AutoSizeButton(text)
        if self.theme is not None:
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return button


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
        self.worker.update_finished.connect(self._finish_update)
        self.worker.finished.connect(self._clear_worker)
        self.worker.finished.connect(self.worker.deleteLater)
        self.show()
        self.worker.start()

    def _finish_update(self, success: bool) -> None:
        self.close()
        self.update_finished.emit(success)

    def _clear_worker(self) -> None:
        self.worker = None
