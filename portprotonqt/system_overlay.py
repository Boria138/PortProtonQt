import subprocess
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QMessageBox
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from portprotonqt.logger import get_logger
from portprotonqt.localization import _

logger = get_logger(__name__)

class SystemOverlay(QDialog):
    """Overlay dialog for system actions like reboot, sleep, shutdown, suspend, and exit."""
    def __init__(self, parent, theme):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle(_("System Overlay"))
        self.setModal(True)
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Reboot button
        reboot_button = QPushButton(_("Reboot"))
        reboot_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        reboot_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        reboot_button.clicked.connect(self.reboot)
        layout.addWidget(reboot_button)

        # Shutdown button
        shutdown_button = QPushButton(_("Shutdown"))
        shutdown_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        shutdown_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        shutdown_button.clicked.connect(self.shutdown)
        layout.addWidget(shutdown_button)

        # Suspend button
        suspend_button = QPushButton(_("Suspend"))
        suspend_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        suspend_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        suspend_button.clicked.connect(self.suspend)
        layout.addWidget(suspend_button)

        # Exit application button
        exit_button = QPushButton(_("Exit Application"))
        exit_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        exit_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        exit_button.clicked.connect(self.exit_application)
        layout.addWidget(exit_button)

        # Cancel button
        cancel_button = QPushButton(_("Cancel"))
        cancel_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        cancel_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

        # Set focus to the first button
        reboot_button.setFocus()

    def reboot(self):
        try:
            subprocess.run(["systemctl", "reboot"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reboot: {e}")
            QMessageBox.warning(self, _("Error"), _("Failed to reboot the system"))
        self.accept()

    def shutdown(self):
        try:
            subprocess.run(["systemctl", "poweroff"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to shutdown: {e}")
            QMessageBox.warning(self, _("Error"), _("Failed to shutdown the system"))
        self.accept()

    def suspend(self):
        try:
            subprocess.run(["systemctl", "suspend"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to suspend: {e}")
            QMessageBox.warning(self, _("Error"), _("Failed to suspend the system"))
        self.accept()

    def exit_application(self):
        QApplication.quit()
        self.accept()
