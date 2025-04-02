from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from portprotonqt.theme_manager import ThemeManager
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.config_utils import read_theme_from_config


class SystemTray:
    def __init__(self, app, theme=None):
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else default_styles
        self.current_theme_name = read_theme_from_config()
        self.tray = QSystemTrayIcon()
        #self.tray.setIcon(self.theme_manager.get_theme_logo(self.current_theme_name))
        self.tray.setIcon(self.theme_manager.get_icon("addgame.svg", self.current_theme_name))
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
