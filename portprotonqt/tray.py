from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from portprotonqt.theme_manager import ThemeManager
from typing import cast
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.config_utils import read_theme_from_config

class SystemTray:
    def __init__(self, app, theme=None):
        self.app = app
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else default_styles
        self.current_theme_name = read_theme_from_config()
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(cast(QIcon, self.theme_manager.get_icon("ppqt-tray", self.current_theme_name)))
        self.tray.setToolTip("PortProtonQt")
        self.tray.setVisible(True)

        # Создаём меню
        self.menu = QMenu()

        self.hide_action = QAction("Скрыть окно")
        self.menu.addAction(self.hide_action)

        self.show_action = QAction("Показать окно")
        self.menu.addAction(self.show_action)

        self.quit_action = QAction("Выход")
        self.quit_action.triggered.connect(app.quit)
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)

    def hide_tray(self):
        """Скрыть иконку трея"""
        if self.tray:
            self.tray.setVisible(False)
            self.tray.setContextMenu(None)

    def cleanup(self):
        """Очистка ресурсов трея"""
        self.hide_tray()
        if self.menu:
            self.menu.deleteLater()
            self.menu = None
        if self.tray:
            self.tray.deleteLater()
            self.tray = None
