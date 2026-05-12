import sys
import subprocess
import shlex
import signal
import psutil
import os
import shutil
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QMessageBox
from PySide6.QtGui import QIcon, QAction, QFont
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.localization import _
from portprotonqt.config import favorites_config, ui_config
from portprotonqt.dialogs import GameLaunchDialog

logger = get_logger(__name__)


class TrayManager:
    """Tray management module for PortProtonQt.

    Provides:
    - Flat context menu with categories: Stop Game, Favorites, Recent, Exit.
    - Dynamic population of game lists without nested submenus.
    - Minimize to tray on window close, full exit via Exit.
    """

    def __init__(self, main_window, app_name: str | None = None, theme=None):
        self.app_name = app_name if app_name is not None else "PortProtonQt"
        self.theme_manager = ThemeManager()
        selected_theme = ui_config.get_theme()
        self.current_theme_name = selected_theme
        self.theme = self.theme_manager.apply_theme(selected_theme)
        self.main_window = main_window
        self.tray_icon = QSystemTrayIcon(self.main_window)

        icon = self.theme_manager.get_icon("tray_portproton", self.current_theme_name)
        if isinstance(icon, str):
            icon = QIcon(icon)
        elif icon is None:
            icon = QIcon()
        self.tray_icon.setIcon(icon)
        self.tray_icon.activated.connect(self.handle_tray_click)
        self.tray_icon.setToolTip(self.app_name)

        self.tray_menu = QMenu()

        self.stop_game_action = QAction(_("Stop Game"), self.main_window)
        self.stop_game_action.setEnabled(False)
        self.stop_game_action.triggered.connect(self.stop_game)

        self.tray_menu.addAction(self.stop_game_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addSeparator()

        exit_action = QAction(_("Exit"), self.main_window)
        exit_action.triggered.connect(self.force_exit)
        self.tray_menu.addAction(exit_action)

        self.tray_menu.aboutToShow.connect(self.refresh_tray_menu)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        self.launch_dialog = None

    def _add_category_header(self, title: str) -> QAction:
        header = QAction(title, self.main_window)
        header.setEnabled(False)
        font = QFont(header.font())
        font.setBold(True)
        header.setFont(font)
        self.tray_menu.addAction(header)
        return header

    def refresh_tray_menu(self):
        self.tray_menu.clear()

        self.tray_menu.addAction(self.stop_game_action)
        self.tray_menu.addSeparator()

        self.update_stop_game_action()

        self._add_category_header(_("Favorites"))
        self._populate_favorites_flat()
        self.tray_menu.addSeparator()

        self._add_category_header(_("Recent Games"))
        self._populate_recent_flat()
        self.tray_menu.addSeparator()

        exit_action = QAction(_("Exit"), self.main_window)
        exit_action.triggered.connect(self.force_exit)
        self.tray_menu.addAction(exit_action)

    def update_stop_game_action(self) -> None:
        game_processes = getattr(self.main_window, "game_processes", [])
        target_exe = getattr(self.main_window, "target_exe", None)
        has_running_game = bool(game_processes or target_exe)
        self.stop_game_action.setEnabled(has_running_game)

    def handle_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.refresh_tray_menu()
            return
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window_action()

    def toggle_window_action(self):
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def stop_game(self) -> None:
        if self.main_window.stop_running_game():
            self.update_stop_game_action()
            return

        QMessageBox.warning(self.main_window, _("Error"), _("Failed to stop game"))

    def _populate_favorites_flat(self):
        favorites = favorites_config.get_games()
        if not favorites:
            no_fav_action = QAction(_("No favorites"), self.main_window)
            no_fav_action.setEnabled(False)
            self.tray_menu.addAction(no_fav_action)
            return

        game_map = {game[0]: (game[5], game[12]) for game in self.main_window.games}

        for fav in sorted(favorites):
            game_data = game_map.get(fav)
            if game_data:
                exec_line, source = game_data
                action_text = f"{fav} ({source})"
                action = QAction(action_text, self.main_window)
                action.triggered.connect(
                    lambda checked=False, el=exec_line, name=fav: self.launch_game_with_dialog(el, name)
                )
                self.tray_menu.addAction(action)
            else:
                logger.warning(f"Exec line not found for favorite: {fav}")

    def _populate_recent_flat(self):
        if not self.main_window.games:
            no_recent_action = QAction(_("No recent games"), self.main_window)
            no_recent_action.setEnabled(False)
            self.tray_menu.addAction(no_recent_action)
            return

        recent_games = sorted(self.main_window.games, key=lambda g: g[10], reverse=True)[:5]

        for game in recent_games:
            game_name = game[0]
            exec_line = game[5]
            source = game[12]
            action_text = f"{game_name} ({source})"
            action = QAction(action_text, self.main_window)
            action.triggered.connect(
                lambda checked=False, el=exec_line, name=game_name: self.launch_game_with_dialog(el, name)
            )
            self.tray_menu.addAction(action)

    def launch_game_with_dialog(self, exec_line, game_name):
        """Launch a game with a modal dialog indicating progress."""
        try:
            target_exe = None
            if exec_line.startswith("steam://"):
                self.launch_dialog = GameLaunchDialog(
                    self.main_window, game_name=game_name, theme=self.theme
                )
            else:
                entry_exec_split = shlex.split(exec_line)
                if "--silent" in entry_exec_split and len(entry_exec_split) > 1:
                    silent_index = entry_exec_split.index("--silent")
                    file_to_check = (
                        entry_exec_split[silent_index + 1]
                        if len(entry_exec_split) > silent_index + 1
                        else ""
                    )
                elif entry_exec_split[0] == "env" and len(entry_exec_split) > 2:
                    file_to_check = entry_exec_split[2]
                elif entry_exec_split[0] == "flatpak" and len(entry_exec_split) > 3:
                    file_to_check = entry_exec_split[3]
                else:
                    file_to_check = entry_exec_split[0]

                if not os.path.exists(file_to_check):
                    logger.error(f"File not found: {file_to_check}")
                    QMessageBox.warning(
                        self.main_window, _("Error"), _("File not found: {0}").format(file_to_check)
                    )
                    return

                target_exe = os.path.basename(file_to_check)
                self.launch_dialog = GameLaunchDialog(
                    self.main_window, game_name=game_name, theme=self.theme, target_exe=target_exe
                )

            self.launch_dialog.rejected.connect(lambda: self.cancel_game_launch(exec_line))
            self.launch_dialog.show()
            self.main_window.toggleGame(exec_line, game_name=game_name)

        except Exception as e:
            logger.error(f"Failed to launch game {game_name}: {e}")
            if self.launch_dialog:
                self.launch_dialog.reject()
                self.launch_dialog = None
            QMessageBox.warning(
                self.main_window, _("Error"), _("Failed to launch game: {0}").format(str(e))
            )

    def cancel_game_launch(self, exec_line):
        """Cancel the game launch and terminate the process."""
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

    def switch_theme(self, theme_name: str):
        try:
            ui_config.set_theme(theme_name)
            logger.info(f"Saved theme {theme_name}, restarting application to apply changes")
            restart_application_with_muvm()
        except Exception as e:
            logger.error(f"Failed to switch theme to {theme_name}: {e}")
            ui_config.set_theme("standart")
            restart_application_with_muvm()

    def force_exit(self):
        self.main_window.close()
        sys.exit(0)

    def shutdown(self):
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()


def restart_application_with_muvm():
    """
    Universal application restart function with muvm support.
    Checks if app was launched under muvm, and if so,
    restarts with the same context.
    """
    if 'PORTPROTONQT_MUVM' in os.environ:
        muvm_path = shutil.which('muvm')
        if muvm_path:
            env = os.environ.copy()
            args = [muvm_path, "-i", "-e", "PORTPROTONQT_MUVM=1", sys.executable] + sys.argv[1:]
            QApplication.quit()
            subprocess.Popen(args, env=env)
            return

    executable = sys.executable
    args = sys.argv
    QApplication.quit()
    subprocess.Popen([executable] + args)
