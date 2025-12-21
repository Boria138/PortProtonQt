import sys
import subprocess
import shlex
import signal
import psutil
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QMessageBox
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.localization import _
from portprotonqt.config_utils import read_favorites, read_theme_from_config, save_theme_to_config
from portprotonqt.dialogs import GameLaunchDialog

logger = get_logger(__name__)

class TrayManager:
    """Модуль управления системным треем для PortProtonQt.

    Обеспечивает:
    - Показ/скрытие главного окна по двойному клику на иконку трея.
    - Контекстное меню с опциями: Show/Hide, Favorites, Recent Games, Themes, Exit.
    - Динамическое заполнение меню Favorites, Recent Games и Themes.
    - Сворачивание в трей при закрытии окна, полное закрытие через Exit.
    """

    def __init__(self, main_window, app_name: str | None = None, theme=None):
        self.app_name = app_name if app_name is not None else "PortProtonQt"
        self.theme_manager = ThemeManager()
        selected_theme = read_theme_from_config()
        self.current_theme_name = selected_theme
        self.theme = self.theme_manager.apply_theme(selected_theme)
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

        self.tray_menu = QMenu()
        self.toggle_action = QAction(_("Show"), self.main_window)
        self.toggle_action.triggered.connect(self.toggle_window_action)

        self.favorites_menu = QMenu(_("Favorites"))
        self.favorites_menu.aboutToShow.connect(self.populate_favorites_menu)

        self.recent_menu = QMenu(_("Recent Games"))
        self.recent_menu.aboutToShow.connect(self.populate_recent_menu)

        self.themes_menu = QMenu(_("Themes"))
        self.themes_menu.aboutToShow.connect(self.populate_themes_menu)

        self.tray_menu.addAction(self.toggle_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addMenu(self.favorites_menu)
        self.tray_menu.addMenu(self.recent_menu)
        self.tray_menu.addMenu(self.themes_menu)
        self.tray_menu.addSeparator()
        exit_action = QAction(_("Exit"), self.main_window)
        exit_action.triggered.connect(self.force_exit)
        self.tray_menu.addAction(exit_action)

        self.tray_menu.aboutToShow.connect(self.update_toggle_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        self.click_count = 0
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.reset_click_count)

        self.launch_dialog = None

    def update_toggle_action(self):
        if self.main_window.isVisible():
            self.toggle_action.setText(_("Hide"))
        else:
            self.toggle_action.setText(_("Show"))

    def handle_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.click_count += 1
            if self.click_count == 1:
                self.click_timer.start(300)
            elif self.click_count == 2:
                self.click_timer.stop()
                self.toggle_window_action()
                self.click_count = 0

    def reset_click_count(self):
        self.click_count = 0

    def toggle_window_action(self):
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def populate_favorites_menu(self):
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
                action.triggered.connect(lambda checked=False, el=exec_line, name=fav: self.launch_game_with_dialog(el, name))
                self.favorites_menu.addAction(action)
            else:
                logger.warning(f"Exec line not found for favorite: {fav}")

    def populate_recent_menu(self):
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
            action.triggered.connect(lambda checked=False, el=exec_line, name=game_name: self.launch_game_with_dialog(el, name))
            self.recent_menu.addAction(action)

    def launch_game_with_dialog(self, exec_line, game_name):
        """Launch a game with a modal dialog indicating progress."""
        try:
            # Determine target executable
            target_exe = None
            if exec_line.startswith("steam://"):
                # Steam games are handled differently, no target_exe needed
                self.launch_dialog = GameLaunchDialog(self.main_window, game_name=game_name, theme=self.theme)
            else:
                # Extract target executable from exec_line
                entry_exec_split = shlex.split(exec_line)
                if entry_exec_split[0] == "env" and len(entry_exec_split) > 2:
                    file_to_check = entry_exec_split[2]
                elif entry_exec_split[0] == "flatpak" and len(entry_exec_split) > 3:
                    file_to_check = entry_exec_split[3]
                else:
                    file_to_check = entry_exec_split[0]

                if not os.path.exists(file_to_check):
                    logger.error(f"File not found: {file_to_check}")
                    QMessageBox.warning(self.main_window, _("Error"), _("File not found: {0}").format(file_to_check))
                    return

                target_exe = os.path.basename(file_to_check)
                self.launch_dialog = GameLaunchDialog(self.main_window, game_name=game_name, theme=self.theme, target_exe=target_exe)

            self.launch_dialog.rejected.connect(lambda: self.cancel_game_launch(exec_line))
            self.launch_dialog.show()

            self.main_window.toggleGame(exec_line)
        except Exception as e:
            logger.error(f"Failed to launch game {game_name}: {e}")
            if self.launch_dialog:
                self.launch_dialog.reject()
                self.launch_dialog = None
            QMessageBox.warning(self.main_window, _("Error"), _("Failed to launch game: {0}").format(str(e)))

    def cancel_game_launch(self, exec_line):
        """Cancel the game launch and terminate the process, using MainWindow's stop logic."""
        if self.main_window.game_processes and self.main_window.target_exe:
            for proc in self.main_window.game_processes:
                try:
                    parent = psutil.Process(proc.pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    psutil.wait_procs(children, timeout=5)
                    for child in children:
                        if child.is_running():
                            child.kill()
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except psutil.NoSuchProcess:
                    pass
            self.main_window.game_processes = []
            self.main_window.resetPlayButton()
            if self.launch_dialog:
                self.launch_dialog.reject()
                self.launch_dialog = None
            logger.info(f"Game launch cancelled for exec line: {exec_line}")

    def populate_themes_menu(self):
        self.themes_menu.clear()
        available_themes = self.theme_manager.get_available_themes()

        for theme_name in sorted(available_themes):
            action = QAction(theme_name, self.main_window)
            action.setCheckable(True)
            action.setChecked(theme_name == self.current_theme_name)
            action.triggered.connect(lambda checked=False, tn=theme_name: self.switch_theme(tn))
            self.themes_menu.addAction(action)

    def switch_theme(self, theme_name: str):
        try:
            save_theme_to_config(theme_name)
            logger.info(f"Saved theme {theme_name}, restarting application to apply changes")

            executable = sys.executable
            args = sys.argv

            QApplication.quit()

            subprocess.Popen([executable] + args)

        except Exception as e:
            logger.error(f"Failed to switch theme to {theme_name}: {e}")
            save_theme_to_config("standart")
            executable = sys.executable
            args = sys.argv
            QApplication.quit()
            subprocess.Popen([executable] + args)

    def force_exit(self):
        self.main_window.close()
        sys.exit(0)
