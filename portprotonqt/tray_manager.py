import sys
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.localization import _
from portprotonqt.config_utils import read_favorites, read_theme_from_config

logger = get_logger(__name__)

class TrayManager:
    """Модуль управления системным треем для PortProtonQt.

    Обеспечивает:
    - Показ/скрытие главного окна по двойному клику на иконку трея.
    - Контекстное меню с опциями: Show/Hide (переключается в зависимости от состояния окна),
      Favorites (быстрый запуск избранных игр), Recent Games (быстрый запуск недавних игр), Exit.
    - Меню Favorites и Recent Games динамически заполняются при показе (через aboutToShow).
    - При закрытии окна (крестик) приложение сворачивается в трей, а не закрывается.
      Полное закрытие только через Exit в меню.
    """

    def __init__(self, main_window, app_name: str | None = None, theme=None):
        self.app_name = app_name if app_name is not None else "PortProtonQt"
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else default_styles
        self.current_theme_name = read_theme_from_config()
        self.main_window = main_window
        self.tray_icon = QSystemTrayIcon(self.main_window)

        icon = self.theme_manager.get_icon("portproton", self.current_theme_name)
        if isinstance(icon, str):
            icon = QIcon(icon)
        elif icon is None:
            icon = QIcon()
        self.tray_icon.setIcon(icon)

        self.tray_icon.activated.connect(self.handle_tray_click)
        self.tray_icon.setToolTip(self.app_name)

        # Контекстное меню
        self.tray_menu = QMenu()
        self.toggle_action = QAction(_("Show"), self.main_window)
        self.toggle_action.triggered.connect(self.toggle_window_action)

        # Подменю для избранных игр
        self.favorites_menu = QMenu(_("Favorites"))
        self.favorites_menu.aboutToShow.connect(self.populate_favorites_menu)

        # Подменю для недавних игр (топ-5 по последнему запуску)
        self.recent_menu = QMenu(_("Recent Games"))
        self.recent_menu.aboutToShow.connect(self.populate_recent_menu)

        # Добавляем действия в меню
        self.tray_menu.addAction(self.toggle_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addMenu(self.favorites_menu)
        self.tray_menu.addMenu(self.recent_menu)
        self.tray_menu.addSeparator()
        exit_action = QAction(_("Exit"), self.main_window)
        exit_action.triggered.connect(self.force_exit)
        self.tray_menu.addAction(exit_action)

        self.tray_menu.aboutToShow.connect(self.update_toggle_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        # Флаг для принудительного выхода
        self.main_window.is_exiting = False

        # Переменные для отслеживания двойного клика
        self.click_count = 0
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.reset_click_count)

    def update_toggle_action(self):
        """Update toggle_action text based on window visibility."""
        if self.main_window.isVisible():
            self.toggle_action.setText(_("Hide"))
        else:
            self.toggle_action.setText(_("Show"))

    def handle_tray_click(self, reason):
        """Обрабатывает клики по иконке трея, отслеживая двойной клик."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.click_count += 1
            if self.click_count == 1:
                # Запускаем таймер для ожидания второго клика (300 мс - стандартное время для двойного клика)
                self.click_timer.start(300)
            elif self.click_count == 2:
                # Двойной клик зафиксирован
                self.click_timer.stop()
                self.toggle_window_action()
                self.click_count = 0

    def reset_click_count(self):
        """Сбрасывает счетчик кликов, если таймер истек."""
        self.click_count = 0

    def toggle_window_action(self):
        """Toggle window visibility and update action text."""
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def populate_favorites_menu(self):
        """Динамически заполняет меню избранных игр с указанием источника."""
        self.favorites_menu.clear()
        favorites = read_favorites()
        if not favorites:
            no_fav_action = QAction(_("No favorites"), self.main_window)
            no_fav_action.setEnabled(False)
            self.favorites_menu.addAction(no_fav_action)
            return

        game_map = {game[0]: (game[4], game[12]) for game in self.main_window.games}

        for fav in sorted(favorites):
            game_data = game_map.get(fav)
            if game_data:
                exec_line, source = game_data
                action_text = f"{fav} ({source})"
                action = QAction(action_text, self.main_window)
                action.triggered.connect(lambda checked=False, el=exec_line: self.main_window.toggleGame(el))
                self.favorites_menu.addAction(action)
            else:
                logger.warning(f"Exec line not found for favorite: {fav}")

    def populate_recent_menu(self):
        """Динамически заполняет меню недавних игр (топ-5 по timestamp) с указанием источника."""
        self.recent_menu.clear()
        if not self.main_window.games:
            no_recent_action = QAction(_("No recent games"), self.main_window)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
            return

        recent_games = sorted(self.main_window.games, key=lambda g: g[10], reverse=True)[:5]

        for game in recent_games:
            game_name = game[0]
            exec_line = game[4]
            source = game[12]
            action_text = f"{game_name} ({source})"
            action = QAction(action_text, self.main_window)
            action.triggered.connect(lambda checked=False, el=exec_line: self.main_window.toggleGame(el))
            self.recent_menu.addAction(action)

    def force_exit(self):
        """Принудительно закрывает приложение."""
        self.main_window.is_exiting = True
        self.main_window.close()
        sys.exit(0)
