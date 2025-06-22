import os
import shlex
import glob
import shutil
import subprocess
import threading
import logging
import re
import json
from PySide6.QtWidgets import QMessageBox, QDialog, QMenu, QFileDialog
from PySide6.QtCore import QUrl, QPoint, QObject, Signal, Qt
from PySide6.QtGui import QDesktopServices
from portprotonqt.config_utils import parse_desktop_entry, read_favorites, save_favorites
from portprotonqt.localization import _
from portprotonqt.steam_api import is_game_in_steam, add_to_steam, remove_from_steam, get_steam_home, get_last_steam_user, convert_steam_id
from portprotonqt.dialogs import AddGameDialog
from portprotonqt.egs_api import add_egs_to_steam, get_egs_executable
import vdf

logger = logging.getLogger(__name__)

class ContextMenuSignals(QObject):
    """Signals for thread-safe UI updates from worker threads."""
    show_status_message = Signal(str, int)
    show_warning_dialog = Signal(str, str)
    show_info_dialog = Signal(str, str)

class ContextMenuManager:
    """Manages context menu actions for game management in PortProtonQt."""

    def __init__(self, parent, portproton_location, theme, load_games_callback, update_game_grid_callback):
        """
        Initialize the ContextMenuManager.

        Args:
            parent: The parent widget (MainWindow instance).
            portproton_location: Path to the PortProton directory.
            theme: The current theme object.
            load_games_callback: Callback to reload games list.
            update_game_grid_callback: Callback to update the game grid UI.
        """
        self.parent = parent
        self.portproton_location = portproton_location
        self.theme = theme
        self.load_games = load_games_callback
        self.update_game_grid = update_game_grid_callback
        self.legendary_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache", "legendary"
        )
        self.legendary_config_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache"
        )
        # Initialize signals for thread-safe UI updates
        self.signals = ContextMenuSignals()
        if self.parent.statusBar() is None:
            logger.warning("Status bar is not initialized in MainWindow")
        else:
            self.signals.show_status_message.connect(
                self.parent.statusBar().showMessage,
                Qt.ConnectionType.QueuedConnection
            )
            logger.debug("Connected show_status_message signal to statusBar")
        self.signals.show_warning_dialog.connect(
            self._show_warning_dialog,
            Qt.ConnectionType.QueuedConnection
        )
        self.signals.show_info_dialog.connect(
            self._show_info_dialog,
            Qt.ConnectionType.QueuedConnection
        )

    def _show_warning_dialog(self, title: str, message: str):
        """Show a warning dialog in the main thread."""
        logger.debug("Showing warning dialog: %s - %s", title, message)
        QMessageBox.warning(self.parent, title, message)

    def _show_info_dialog(self, title: str, message: str):
        """Show an info dialog in the main thread."""
        logger.debug("Showing info dialog: %s - %s", title, message)
        QMessageBox.information(self.parent, title, message)

    def _is_egs_game_installed(self, app_name: str) -> bool:
        """
        Check if an EGS game is installed by reading installed.json.

        Args:
            app_name: The Legendary app_name (unique identifier for the game).

        Returns:
            bool: True if the game is installed, False otherwise.
        """
        installed_json_path = os.path.join(self.legendary_config_path, "installed.json")
        if not os.path.exists(installed_json_path):
            logger.debug("installed.json not found at %s", installed_json_path)
            return False

        try:
            with open(installed_json_path, encoding="utf-8") as f:
                installed_games = json.load(f)
            return app_name in installed_games
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to read installed.json: %s", e)
            return False

    def show_context_menu(self, game_card, pos: QPoint):
        """
        Show the context menu for a game card at the specified position.

        Args:
            game_card: The GameCard instance requesting the context menu.
            pos: The position (in widget coordinates) where the menu should appear.
        """
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.theme.CONTEXT_MENU_STYLE)

        favorites = read_favorites()
        is_favorite = game_card.name in favorites

        if is_favorite:
            favorite_action = menu.addAction(_("Remove from Favorites"))
            favorite_action.triggered.connect(lambda: self.toggle_favorite(game_card, False))
        else:
            favorite_action = menu.addAction(_("Add to Favorites"))
            favorite_action.triggered.connect(lambda: self.toggle_favorite(game_card, True))

        if game_card.game_source == "epic":
            # Always show Import to Legendary
            import_action = menu.addAction(_("Import to Legendary"))
            import_action.triggered.connect(
                lambda: self.import_to_legendary(game_card.name, game_card.appid)
            )
            # Show other actions only if the game is installed
            if self._is_egs_game_installed(game_card.appid):
                is_in_steam = is_game_in_steam(game_card.name)
                if is_in_steam:
                    remove_steam_action = menu.addAction(_("Remove from Steam"))
                    remove_steam_action.triggered.connect(
                        lambda: self.remove_from_steam(game_card.name, game_card.exec_line, game_card.game_source)
                    )
                else:
                    add_steam_action = menu.addAction(_("Add to Steam"))
                    add_steam_action.triggered.connect(
                        lambda: self.add_egs_to_steam(game_card.name, game_card.appid)
                    )
                open_folder_action = menu.addAction(_("Open Game Folder"))
                open_folder_action.triggered.connect(
                    lambda: self.open_egs_game_folder(game_card.appid)
                )
                # Add desktop shortcut actions for EGS games
                desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
                desktop_path = os.path.join(desktop_dir, f"{game_card.name}.desktop")
                if os.path.exists(desktop_path):
                    remove_desktop_action = menu.addAction(_("Remove from Desktop"))
                    remove_desktop_action.triggered.connect(
                        lambda: self.remove_egs_from_desktop(game_card.name)
                    )
                else:
                    add_desktop_action = menu.addAction(_("Add to Desktop"))
                    add_desktop_action.triggered.connect(
                        lambda: self.add_egs_to_desktop(game_card.name, game_card.appid)
                    )
                # Add menu shortcut actions for EGS games
                applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
                menu_path = os.path.join(applications_dir, f"{game_card.name}.desktop")
                if os.path.exists(menu_path):
                    remove_menu_action = menu.addAction(_("Remove from Menu"))
                    remove_menu_action.triggered.connect(
                        lambda: self.remove_egs_from_menu(game_card.name)
                    )
                else:
                    add_menu_action = menu.addAction(_("Add to Menu"))
                    add_menu_action.triggered.connect(
                        lambda: self.add_egs_to_menu(game_card.name, game_card.appid)
                    )

        if game_card.game_source not in ("steam", "epic"):
            desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
            desktop_path = os.path.join(desktop_dir, f"{game_card.name}.desktop")
            if os.path.exists(desktop_path):
                remove_action = menu.addAction(_("Remove from Desktop"))
                remove_action.triggered.connect(lambda: self.remove_from_desktop(game_card.name))
            else:
                add_action = menu.addAction(_("Add to Desktop"))
                add_action.triggered.connect(lambda: self.add_to_desktop(game_card.name, game_card.exec_line))

            edit_action = menu.addAction(_("Edit Shortcut"))
            edit_action.triggered.connect(
                lambda: self.edit_game_shortcut(game_card.name, game_card.exec_line, game_card.cover_path)
            )

            delete_action = menu.addAction(_("Delete from PortProton"))
            delete_action.triggered.connect(lambda: self.delete_game(game_card.name, game_card.exec_line))

            open_folder_action = menu.addAction(_("Open Game Folder"))
            open_folder_action.triggered.connect(
                lambda: self.open_game_folder(game_card.name, game_card.exec_line)
            )

            applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
            desktop_path = os.path.join(applications_dir, f"{game_card.name}.desktop")
            if os.path.exists(desktop_path):
                remove_action = menu.addAction(_("Remove from Menu"))
                remove_action.triggered.connect(lambda: self.remove_from_menu(game_card.name))
            else:
                add_action = menu.addAction(_("Add to Menu"))
                add_action.triggered.connect(lambda: self.add_to_menu(game_card.name, game_card.exec_line))

            is_in_steam = is_game_in_steam(game_card.name)
            if is_in_steam:
                remove_steam_action = menu.addAction(_("Remove from Steam"))
                remove_steam_action.triggered.connect(
                    lambda: self.remove_from_steam(game_card.name, game_card.exec_line, game_card.game_source)
                )
            else:
                add_steam_action = menu.addAction(_("Add to Steam"))
                add_steam_action.triggered.connect(
                    lambda: self.add_to_steam(game_card.name, game_card.exec_line, game_card.cover_path)
                )

        menu.exec(game_card.mapToGlobal(pos))

    def add_egs_to_steam(self, game_name: str, app_name: str):
        """
        Adds an EGS game to Steam using the egs_api.

        Args:
            game_name: The display name of the game.
            app_name: The Legendary app_name (unique identifier for the game).
        """
        if not self._check_portproton():
            return

        if not os.path.exists(self.legendary_path):
            self.signals.show_warning_dialog.emit(
                _("Error"), _("Legendary executable not found at {0}").format(self.legendary_path)
            )
            return

        def on_add_to_steam_result(result: tuple[bool, str]):
            success, message = result
            if success:
                self.signals.show_info_dialog.emit(
                    _("Success"),
                    _("'{0}' was added to Steam. Please restart Steam for changes to take effect.").format(game_name)
                )
            else:
                self.signals.show_warning_dialog.emit(_("Error"), message)

        logger.debug("Adding '%s' to Steam", game_name)
        add_egs_to_steam(app_name, game_name, self.legendary_path, on_add_to_steam_result)

    def open_egs_game_folder(self, app_name: str):
        """
        Opens the folder containing the EGS game's executable.

        Args:
            app_name: The Legendary app_name (unique identifier for the game).
        """
        if not self._check_portproton():
            return

        exe_path = get_egs_executable(app_name, self.legendary_config_path)
        if not exe_path or not os.path.exists(exe_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Executable file not found for game: {0}").format(app_name)
            )
            return

        try:
            folder_path = os.path.dirname(os.path.abspath(exe_path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Opened folder for EGS game '{0}'").format(app_name), 3000
                )
                logger.debug("Direct status message: Opened folder for '%s'", app_name)
            else:
                logger.warning("Status bar not available when opening folder for '%s'", app_name)
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to open game folder: {0}").format(str(e))
            )

    def import_to_legendary(self, game_name, app_name):
        """
        Imports an installed Epic Games Store game to Legendary asynchronously.

        Args:
            game_name: The display name of the game.
            app_name: The Legendary app_name (unique identifier for the game).
        """
        if not self._check_portproton():
            return

        folder_path = QFileDialog.getExistingDirectory(
            self.parent,
            _("Select Game Installation Folder"),
            os.path.expanduser("~")
        )
        if not folder_path:
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(_("No folder selected"), 3000)
                logger.debug("Direct status message: No folder selected for '%s'", game_name)
            else:
                logger.warning("Status bar not available when no folder selected for '%s'", game_name)
            return

        if not os.path.exists(self.legendary_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Legendary executable not found at {0}").format(self.legendary_path)
            )
            return

        def run_import():
            cmd = [self.legendary_path, "import", app_name, folder_path]
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

        if self.parent.statusBar():
            self.parent.statusBar().showMessage(
                _("Importing '{0}' to Legendary...").format(game_name), 0
            )
            logger.debug("Direct status message: Importing '%s' to Legendary", game_name)
        else:
            logger.warning("Status bar not available when importing '%s'", game_name)
        threading.Thread(target=run_import, daemon=True).start()

    def toggle_favorite(self, game_card, add: bool):
        """
        Toggle the favorite status of a game and update its icon.

        Args:
            game_card: The GameCard instance to toggle.
            add: True to add to favorites, False to remove.
        """
        favorites = read_favorites()
        if add and game_card.name not in favorites:
            favorites.append(game_card.name)
            game_card.is_favorite = True
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Added '{0}' to favorites").format(game_card.name), 3000
                )
                logger.debug("Direct status message: Added '%s' to favorites", game_card.name)
            else:
                logger.warning("Status bar not available when adding '%s' to favorites", game_card.name)
        elif not add and game_card.name in favorites:
            favorites.remove(game_card.name)
            game_card.is_favorite = False
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Removed '{0}' from favorites").format(game_card.name), 3000
                )
                logger.debug("Direct status message: Removed '%s' from favorites", game_card.name)
            else:
                logger.warning("Status bar not available when removing '%s' from favorites", game_card.name)
        save_favorites(favorites)
        game_card.update_favorite_icon()

    def _check_portproton(self):
        """Check if PortProton is available."""
        if self.portproton_location is None:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("PortProton is not found.")
            )
            return False
        return True

    def _get_desktop_path(self, game_name):
        """Construct the .desktop file path, trying both original and sanitized game names."""
        desktop_path = os.path.join(self.portproton_location, f"{game_name}.desktop")
        if not os.path.exists(desktop_path):
            sanitized_name = game_name.replace("/", "_").replace(":", "_").replace(" ", "_")
            desktop_path = os.path.join(self.portproton_location, f"{sanitized_name}.desktop")
        return desktop_path

    def _get_egs_desktop_path(self, game_name):
        """Construct the .desktop file path for EGS games."""
        desktop_path = os.path.join(self.portproton_location, "egs_desktops", f"{game_name}.desktop")
        return desktop_path

    def _create_egs_desktop_file(self, game_name: str, app_name: str) -> bool:
        """
        Creates a .desktop file for an EGS game in the PortProton egs_desktops directory.

        Args:
            game_name: The display name of the game.
            app_name: The Legendary app_name (unique identifier for the game).

        Returns:
            bool: True if the .desktop file was created successfully, False otherwise.
        """
        if not self._check_portproton():
            return False

        if not os.path.exists(self.legendary_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Legendary executable not found at {0}").format(self.legendary_path)
            )
            return False

        # Determine wrapper
        wrapper = "flatpak run ru.linux_gaming.PortProton"
        start_sh_path = os.path.join(self.portproton_location, "data", "scripts", "start.sh")
        if self.portproton_location and ".var" not in self.portproton_location:
            wrapper = start_sh_path
            if not os.path.exists(start_sh_path):
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("start.sh not found at {0}").format(start_sh_path)
                )
                return False

        # Get cover image path
        image_folder = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "images"
        )
        cover_path = os.path.join(image_folder, f"{app_name}.jpg")
        icon_path = cover_path if os.path.exists(cover_path) else ""

        # Create egs_desktops directory
        egs_desktop_dir = os.path.join(self.portproton_location, "egs_desktops")
        os.makedirs(egs_desktop_dir, exist_ok=True)

        # Create .desktop file with direct Exec line
        desktop_path = self._get_egs_desktop_path(game_name)
        desktop_entry = f"""[Desktop Entry]
Type=Application
Name={game_name}
Exec="{self.legendary_path}" launch {app_name} --no-wine --wrapper "env START_FROM_STEAM=1 {wrapper}"
Icon={icon_path}
Terminal=false
Categories=Game
"""
        try:
            with open(desktop_path, "w", encoding="utf-8") as f:
                f.write(desktop_entry)
            os.chmod(desktop_path, 0o755)
            logger.info(f"Created .desktop file for EGS game: {desktop_path}")
            return True
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to create .desktop file: {0}").format(str(e))
            )
            return False

    def add_egs_to_desktop(self, game_name: str, app_name: str):
        """
        Copies the .desktop file for an EGS game to the Desktop folder.

        Args:
            game_name: The display name of the game.
            app_name: The Legendary app_name (unique identifier for the game).
        """
        if not self._check_portproton():
            return

        desktop_path = self._get_egs_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            # Create the .desktop file if it doesn't exist
            if not self._create_egs_desktop_file(game_name, app_name):
                return

        desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
        os.makedirs(desktop_dir, exist_ok=True)
        dest_path = os.path.join(desktop_dir, f"{game_name}.desktop")

        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Game '{0}' added to desktop").format(game_name), 3000
                )
                logger.debug("Direct status message: Game '{0}' added to desktop", game_name)
            else:
                logger.warning("Status bar not available when adding '{0}' to desktop", game_name)
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add game to desktop: {0}").format(game_name, str(e))
            )

    def remove_egs_from_desktop(self, game_name: str):
        """
        Removes the .desktop file for an EGS game from the Desktop folder.

        Args:
            game_name: The display name of the game.
        """
        desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
        desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove game '{0}' from Desktop: {{0}}").format(game_name),
            _("Successfully removed game '{0}' from Desktop").format(game_name),
            game_name
        )

    def add_egs_to_menu(self, game_name: str, app_name: str):
        """
        Copies the .desktop file for an EGS game to ~/.local/share/applications.

        Args:
            game_name: The display name of the game.
            app_name: The Legendary app_name (unique identifier for the game).
        """
        if not self._check_portproton():
            return

        desktop_path = self._get_egs_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            # Create the .desktop file if it doesn't exist
            if not self._create_egs_desktop_file(game_name, app_name):
                return

        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        os.makedirs(applications_dir, exist_ok=True)
        dest_path = os.path.join(applications_dir, f"{game_name}.desktop")

        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Game '{0}' added to menu").format(game_name), 3000
                )
                logger.debug("Direct status message: Game '{0}' added to menu", game_name)
            else:
                logger.warning("Status bar not available when adding '{0}' to menu", game_name)
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add game '{0}' to menu: {1}").format(game_name, str(e))
            )

    def remove_egs_from_menu(self, game_name: str):
        """
        Removes the .desktop file for an EGS game from ~/.local/share/applications.

        Args:
            game_name: The display name of the game.
        """
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        desktop_path = os.path.join(applications_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove game '{0}' from menu: {{0}}").format(game_name),
            _("Successfully removed game '{0}' from menu").format(game_name),
            game_name
        )

    def _get_exec_line(self, game_name, exec_line):
        """Retrieve and validate exec_line from .desktop file if necessary."""
        if exec_line and exec_line.strip() != "full":
            return exec_line

        desktop_path = self._get_desktop_path(game_name)
        if os.path.exists(desktop_path):
            try:
                entry = parse_desktop_entry(desktop_path)
                if entry:
                    exec_line = entry.get("Exec", entry.get("exec", "")).strip()
                    if not exec_line:
                        self.signals.show_warning_dialog.emit(
                            _("Error"),
                            _("No executable command found in .desktop file for game: {0}").format(game_name)
                        )
                        return None
                else:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to parse .desktop file for game: {0}").format(game_name)
                    )
                    return None
            except Exception as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to read .desktop file: {0}").format(str(e))
                )
                return None
        else:
            for file in glob.glob(os.path.join(self.portproton_location, "*.desktop")):
                entry = parse_desktop_entry(file)
                if entry:
                    exec_line = entry.get("Exec", entry.get("exec", "")).strip()
                    if exec_line:
                        return exec_line
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _(".desktop file not found for game: {0}").format(game_name)
            )
            return None
        return exec_line

    def _parse_exe_path(self, exec_line, game_name):
        """Parse the executable path from exec_line."""
        try:
            entry_exec_split = shlex.split(exec_line)
            if not entry_exec_split:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Invalid executable command: {0}").format(exec_line)
                )
                return None
            if entry_exec_split[0] == "env" and len(entry_exec_split) >= 3:
                exe_path = entry_exec_split[2]
            elif entry_exec_split[0] == "flatpak" and len(entry_exec_split) >= 4:
                exe_path = entry_exec_split[3]
            else:
                exe_path = entry_exec_split[-1]
            if not exe_path or not os.path.exists(exe_path):
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Executable file not found: {0}").format(exe_path or "None")
                )
                return None
            return exe_path
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to parse executable command: {0}").format(str(e))
            )
            return None

    def _remove_file(self, file_path, error_message, success_message, game_name):
        """Remove a file and handle errors."""
        try:
            os.remove(file_path)
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(success_message.format(game_name), 3000)
                logger.debug("Direct status message: %s", success_message.format(game_name))
            else:
                logger.warning("Status bar not available when removing file for '%s'", game_name)
            return True
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                error_message.format(str(e))
            )
            return False

    def delete_game(self, game_name, exec_line):
        """Delete the .desktop file and associated custom data for the game."""
        reply = QMessageBox.question(
            self.parent,
            _("Confirm Deletion"),
            _("Are you sure you want to delete '{0}'? This will remove the .desktop file and custom data.")
                .format(game_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if not self._check_portproton():
            return

        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Could not locate .desktop file for game: {0}").format(game_name)
            )
            return

        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        exe_name = os.path.splitext(os.path.basename(exe_path))[0] if exe_path else None

        if not self._remove_file(
            desktop_path,
            _("Failed to delete .desktop file: {0}"),
            _("Game '{0}' deleted successfully"),
            game_name
        ):
            return

        if exe_name:
            xdg_data_home = os.getenv(
                "XDG_DATA_HOME",
                os.path.join(os.path.expanduser("~"), ".local", "share")
            )
            custom_folder = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", exe_name)
            if os.path.exists(custom_folder):
                try:
                    shutil.rmtree(custom_folder)
                except OSError as e:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to delete custom data: {0}").format(str(e))
                    )

    def add_to_menu(self, game_name, exec_line):
        """Copy the .desktop file to ~/.local/share/applications."""
        if not self._check_portproton():
            return

        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Could not locate .desktop file for game: {0}").format(game_name)
            )
            return

        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        os.makedirs(applications_dir, exist_ok=True)
        dest_path = os.path.join(applications_dir, f"{game_name}.desktop")

        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Game '{0}' added to menu").format(game_name), 3000
                )
                logger.debug("Direct status message: Game '{0}' added to menu", game_name)
            else:
                logger.warning("Status bar not available when adding '{0}' to menu", game_name)
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add game '{0}' to menu: {1}").format(game_name, str(e))
            )

    def remove_from_menu(self, game_name):
        """Remove the .desktop file from ~/.local/share/applications."""
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        desktop_path = os.path.join(applications_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove game '{0}' from menu: {{0}}").format(game_name),
            _("Successfully removed game '{0}' from menu").format(game_name),
            game_name
        )

    def add_to_desktop(self, game_name, exec_line):
        """Copy the .desktop file to Desktop folder."""
        if not self._check_portproton():
            return

        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Could not locate .desktop file for game: {0}").format(game_name)
            )
            return

        desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
        os.makedirs(desktop_dir, exist_ok=True)
        dest_path = os.path.join(desktop_dir, f"{game_name}.desktop")

        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Game '{0}' added to desktop").format(game_name), 3000
                )
                logger.debug("Direct status message: Game '{0}' added to desktop", game_name)
            else:
                logger.warning("Status bar not available when adding '{0}' to desktop", game_name)
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add game '{0}' to desktop: {1}").format(game_name, str(e))
            )

    def remove_from_desktop(self, game_name):
        """Remove the .desktop file from Desktop folder."""
        desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
        desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove game '{0}' from Desktop: {{0}}").format(game_name),
            _("Successfully removed game '{0}' from Desktop").format(game_name),
            game_name
        )

    def edit_game_shortcut(self, game_name, exec_line, cover_path):
        """Opens the AddGameDialog in edit mode to modify an existing .desktop file."""
        if not self._check_portproton():
            return

        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return

        dialog = AddGameDialog(
            parent=self.parent,
            theme=self.theme,
            edit_mode=True,
            game_name=game_name,
            exe_path=exe_path,
            cover_path=cover_path
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.nameEdit.text().strip()
            new_exe_path = dialog.exeEdit.text().strip()
            new_cover_path = dialog.coverEdit.text().strip()

            if not new_name or not new_exe_path:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Game name and executable path are required.")
                )
                return

            desktop_entry, new_desktop_path = dialog.getDesktopEntryData()
            if not desktop_entry or not new_desktop_path:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to generate .desktop file data.")
                )
                return

            old_desktop_path = self._get_desktop_path(game_name)
            if game_name != new_name and os.path.exists(old_desktop_path):
                self._remove_file(
                    old_desktop_path,
                    _("Failed to remove old .desktop file: {0}"),
                    _("Old .desktop file removed for '{0}'"),
                    game_name
                )

            try:
                with open(new_desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                    os.chmod(new_desktop_path, 0o755)
            except OSError as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to save .desktop file: {0}").format(str(e))
                )
                return

            if os.path.isfile(new_cover_path):
                exe_name = os.path.splitext(os.path.basename(new_exe_path))[0]
                xdg_data_home = os.getenv(
                    "XDG_DATA_HOME",
                    os.path.join(os.path.expanduser("~"), ".local", "share")
                )
                custom_folder = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", exe_name)
                os.makedirs(custom_folder, exist_ok=True)

                ext = os.path.splitext(new_cover_path)[1].lower()
                if ext in [".png", ".jpg", ".jpeg", ".bmp"]:
                    try:
                        shutil.copyfile(new_cover_path, os.path.join(custom_folder, f"cover{ext}"))
                    except OSError as e:
                        self.signals.show_warning_dialog.emit(
                            _("Error"),
                            _("Failed to copy cover image: {0}").format(str(e))
                        )
                        return

    def add_to_steam(self, game_name, exec_line, cover_path):
        """Handle adding a non-Steam game to Steam via steam_api."""
        if not self._check_portproton():
            return

        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return

        logger.debug("Adding '{0}' to Steam", game_name)

        try:
            add_to_steam(game_name, exec_line, cover_path)
            self.signals.show_info_dialog.emit(
                _("Success"),
                _("'{0}' was added to Steam. Please restart Steam for changes to take effect.").format(game_name)
            )
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add game '{0}' to Steam: {1}").format(game_name, str(e))
            )

    def remove_from_steam(self, game_name, exec_line, game_source):
        """Handle removing a game from Steam via steam_api, supporting both EGS and non-EGS games."""
        if not self._check_portproton():
            return

        def on_remove_from_steam_result(result: tuple[bool, str]):
            success, message = result
            if success:
                self.signals.show_info_dialog.emit(
                    _("Success"),
                    _("'{0}' was removed from Steam. Please restart Steam for changes to take effect.").format(game_name)
                )
            else:
                self.signals.show_warning_dialog.emit(_("Error"), message)

        if game_source == "epic":
            # For EGS games, construct the script path used in Steam shortcuts.vdf
            if not self.portproton_location:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("PortProton directory not found")
                )
                return
            steam_scripts_dir = os.path.join(self.portproton_location, "steam_scripts")
            safe_game_name = re.sub(r'[<>:"/\\|?*]', '_', game_name.strip())
            script_path = os.path.join(steam_scripts_dir, f"{safe_game_name}_egs.sh")
            quoted_script_path = f'"{script_path}"'

            # Directly remove the shortcut by matching AppName and Exe
            try:
                steam_home = get_steam_home()
                if not steam_home:
                    self.signals.show_warning_dialog.emit(_("Error"), _("Steam directory not found"))
                    return

                last_user = get_last_steam_user(steam_home)
                if not last_user or 'SteamID' not in last_user:
                    self.signals.show_warning_dialog.emit(_("Error"), _("Failed to get Steam user ID"))
                    return

                userdata_dir = os.path.join(steam_home, "userdata")
                user_id = last_user['SteamID']
                unsigned_id = convert_steam_id(user_id)
                user_dir = os.path.join(userdata_dir, str(unsigned_id))
                steam_shortcuts_path = os.path.join(user_dir, "config", "shortcuts.vdf")
                backup_path = f"{steam_shortcuts_path}.backup"

                if not os.path.exists(steam_shortcuts_path):
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Steam shortcuts file not found")
                    )
                    return

                # Backup shortcuts.vdf
                try:
                    shutil.copy2(steam_shortcuts_path, backup_path)
                    logger.info(f"Created backup of shortcuts.vdf at {backup_path}")
                except Exception as e:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to create backup of shortcuts.vdf: {0}").format(str(e))
                    )
                    return

                # Load shortcuts.vdf
                try:
                    with open(steam_shortcuts_path, 'rb') as f:
                        shortcuts_data = vdf.binary_load(f)
                except Exception as e:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to load shortcuts.vdf: {0}").format(str(e))
                    )
                    return

                shortcuts = shortcuts_data.get("shortcuts", {})
                modified = False
                new_shortcuts = {}
                index = 0

                for _key, entry in shortcuts.items():
                    if entry.get("AppName") == game_name and entry.get("Exe") == quoted_script_path:
                        modified = True
                        logger.info(f"Removing EGS game '{game_name}' from Steam shortcuts")
                        continue
                    new_shortcuts[str(index)] = entry
                    index += 1

                if not modified:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Game '{0}' not found in Steam shortcuts").format(game_name)
                    )
                    return

                # Save updated shortcuts.vdf
                try:
                    with open(steam_shortcuts_path, 'wb') as f:
                        vdf.binary_dump({"shortcuts": new_shortcuts}, f)
                    logger.info(f"Updated shortcuts.vdf, removed '{game_name}'")
                    on_remove_from_steam_result((True, f"Game '{game_name}' removed from Steam"))
                except Exception as e:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to update shortcuts.vdf: {0}").format(str(e))
                    )
                    if os.path.exists(backup_path):
                        try:
                            shutil.copy2(backup_path, steam_shortcuts_path)
                            logger.info("Restored shortcuts.vdf from backup")
                        except Exception as restore_err:
                            logger.error(f"Failed to restore shortcuts.vdf: {restore_err}")
                    on_remove_from_steam_result((False, f"Failed to update shortcuts.vdf: {e}"))
                    return

                # Optionally, remove the script file
                if os.path.exists(script_path):
                    try:
                        os.remove(script_path)
                        logger.info(f"Removed EGS script: {script_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove EGS script {script_path}: {e}")

            except Exception as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to remove EGS game '{0}' from Steam: {1}").format(game_name, str(e))
                )
                on_remove_from_steam_result((False, f"Failed to remove EGS game '{game_name}' from Steam: {str(e)}"))
                return

        else:
            # For non-EGS games, use the existing logic without callback
            exec_line = self._get_exec_line(game_name, exec_line)
            if not exec_line:
                return

            exe_path = self._parse_exe_path(exec_line, game_name)
            if not exe_path:
                return

            if self.parent.statusBar():
                logger.debug("Direct status message: Removing '{0}' from Steam", game_name)
            else:
                logger.warning("Status bar not available when removing '{0}' from Steam", game_name)

            try:
                remove_from_steam(game_name, exec_line)
                self.signals.show_info_dialog.emit(
                    _("Success"),
                    _("'{0}' was removed from Steam. Please restart Steam for changes to take effect.").format(game_name)
                )
            except Exception as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to remove game '{0}' from Steam: {1}").format(game_name, str(e))
                )

    def open_game_folder(self, game_name, exec_line):
        """Open the folder containing the game's executable."""
        if not self._check_portproton():
            return

        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return

        try:
            folder_path = os.path.dirname(os.path.abspath(exe_path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
            if self.parent.statusBar():
                self.parent.statusBar().showMessage(
                    _("Successfully opened folder for '{0}'").format(game_name), 3000
                )
                logger.debug("Direct status message: Opened folder for '{0}'", game_name)
            else:
                logger.warning("Status bar not available when opening folder for '{0}'", game_name)
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to open game folder: {0}").format(str(e))
            )
