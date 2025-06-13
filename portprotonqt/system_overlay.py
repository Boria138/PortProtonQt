import subprocess
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QMessageBox
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from portprotonqt.logger import get_logger
import os
from portprotonqt.localization import _
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.theme_manager import ThemeManager

logger = get_logger(__name__)

class SystemOverlay(QDialog):
    """Overlay dialog for system actions like reboot, sleep, shutdown, suspend, and exit."""
    def __init__(self, parent, theme):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle(_("System Overlay"))
        self.setModal(True)
        self.setFixedSize(400, 300)
        self.theme_manager = ThemeManager()
        self.setStyleSheet(self.theme.OVERLAY_WINDOW_STYLE)

        # Убираем рамку окна
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Reboot button
        reboot_button = AutoSizeButton(
            _("Reboot"),
            icon=self.theme_manager.get_icon("reboot")
        )
        reboot_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        reboot_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        reboot_button.clicked.connect(self.reboot)
        layout.addWidget(reboot_button)

        # Shutdown button
        shutdown_button = AutoSizeButton(
            _("Shutdown"),
            icon=self.theme_manager.get_icon("shutdown")
        )
        shutdown_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        shutdown_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        shutdown_button.clicked.connect(self.shutdown)
        layout.addWidget(shutdown_button)

        # Suspend button
        suspend_button = AutoSizeButton(
            _("Suspend"),
            icon=self.theme_manager.get_icon("suspend")
        )
        suspend_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        suspend_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        suspend_button.clicked.connect(self.suspend)
        layout.addWidget(suspend_button)

        # Exit application button
        exit_button = AutoSizeButton(
            _("Exit Application"),
            icon=self.theme_manager.get_icon("exit")
        )
        exit_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        exit_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        exit_button.clicked.connect(self.exit_application)
        layout.addWidget(exit_button)

        # Return to Desktop button
        desktop_button = AutoSizeButton(
            _("Return to Desktop"),
            icon=self.theme_manager.get_icon("desktop")
        )
        desktop_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        desktop_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        desktop_button.clicked.connect(self.return_to_desktop)
        script_path = "/usr/bin/portprotonqt-session-select"
        script_exists = os.path.isfile(script_path)
        desktop_button.setEnabled(script_exists)
        if not script_exists:
            desktop_button.setToolTip(_("portprotonqt-session-select file not found at /usr/bin/"))
        layout.addWidget(desktop_button)

        # Cancel button
        cancel_button = AutoSizeButton(
            _("Cancel"),
            icon=self.theme_manager.get_icon("cancel")
        )
        cancel_button.setStyleSheet(self.theme.OVERLAY_BUTTON_STYLE)
        cancel_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

    def showEvent(self, event):
        """Переопределяем showEvent для центрирования окна и установки фокуса"""
        super().showEvent(event)

        # Центрируем окно относительно родителя или экрана
        if self.parent():
            self.move(self.parent().geometry().center() - self.rect().center())
        else:
            screen_geometry = QApplication.primaryScreen().availableGeometry()
            self.move(screen_geometry.center() - self.rect().center())

        # Устанавливаем фокус на первый элемент
        self.setFocus()
        self.findChild(QPushButton).setFocus()

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

    def return_to_desktop(self):
        try:
            script_path = os.path.join(os.path.dirname(__file__), "portprotonqt-session-select")
            subprocess.run([script_path, "desktop"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to return to desktop: {e}")
            QMessageBox.warning(self, _("Error"), _("Failed to return to desktop"))
        self.accept()

    def exit_application(self):
        QApplication.quit()
        self.accept()
