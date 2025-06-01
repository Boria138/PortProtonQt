import os
import shlex
import glob
import shutil
import subprocess
from PySide6.QtWidgets import QMessageBox, QDialog, QMenu
from PySide6.QtCore import QUrl, QPoint
from PySide6.QtGui import QDesktopServices
from portprotonqt.config_utils import parse_desktop_entry
from portprotonqt.localization import _
from portprotonqt.steam_api import is_game_in_steam, add_to_steam, remove_from_steam

class ContextMenuManager:
    """Manages context menu actions for game management in PortProtonQT."""

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

    def show_context_menu(self, game_card, pos: QPoint):
        """
        Show the context menu for a game card at the specified position.

        Args:
            game_card: The GameCard instance requesting the context menu.
            pos: The position (in widget coordinates) where the menu should appear.
        """

        menu = QMenu(self.parent)
        if game_card.steam_game != "true":
            desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
            desktop_path = os.path.join(desktop_dir, f"{game_card.name}.desktop")
            if os.path.exists(desktop_path):
                remove_action = menu.addAction(_("Remove from Desktop"))
                remove_action.triggered.connect(lambda: self.remove_from_desktop(game_card.name))
            else:
                add_action = menu.addAction(_("Add to Desktop"))
                add_action.triggered.connect(lambda: self.add_to_desktop(game_card.name, game_card.exec_line))

            edit_action = menu.addAction(_("Edit Shortcut"))
            edit_action.triggered.connect(lambda: self.edit_game_shortcut(game_card.name, game_card.exec_line, game_card.cover_path))

            delete_action = menu.addAction(_("Delete from PortProton"))
            delete_action.triggered.connect(lambda: self.delete_game(game_card.name, game_card.exec_line))

            open_folder_action = menu.addAction(_("Open Game Folder"))
            open_folder_action.triggered.connect(lambda: self.open_game_folder(game_card.name, game_card.exec_line))

            applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
            desktop_path = os.path.join(applications_dir, f"{game_card.name}.desktop")
            if os.path.exists(desktop_path):
                remove_action = menu.addAction(_("Remove from Menu"))
                remove_action.triggered.connect(lambda: self.remove_from_menu(game_card.name))
            else:
                add_action = menu.addAction(_("Add to Menu"))
                add_action.triggered.connect(lambda: self.add_to_menu(game_card.name, game_card.exec_line))

            # Add Steam-related actions
            is_in_steam = is_game_in_steam(game_card.name)
            if is_in_steam:
                remove_steam_action = menu.addAction(_("Remove from Steam"))
                remove_steam_action.triggered.connect(lambda: self.remove_from_steam(game_card.name, game_card.exec_line))
            else:
                add_steam_action = menu.addAction(_("Add to Steam"))
                add_steam_action.triggered.connect(lambda: self.add_to_steam(game_card.name, game_card.exec_line, game_card.cover_path))

        menu.exec(game_card.mapToGlobal(pos))

    def _check_portproton(self):
        """Check if PortProton is available."""
        if self.portproton_location is None:
            QMessageBox.warning(self.parent, _("Error"), _("PortProton is not found."))
            return False
        return True

    def _get_desktop_path(self, game_name):
        """Construct the .desktop file path, trying both original and sanitized game names."""
        desktop_path = os.path.join(self.portproton_location, f"{game_name}.desktop")
        if not os.path.exists(desktop_path):
            sanitized_name = game_name.replace("/", "_").replace(":", "_").replace(" ", "_")
            desktop_path = os.path.join(self.portproton_location, f"{sanitized_name}.desktop")
        return desktop_path

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
                        QMessageBox.warning(
                            self.parent, _("Error"),
                            _("No executable command found in .desktop for game: {0}").format(game_name)
                        )
                        return None
                else:
                    QMessageBox.warning(
                        self.parent, _("Error"),
                        _("Failed to parse .desktop file for game: {0}").format(game_name)
                    )
                    return None
            except Exception as e:
                QMessageBox.warning(
                    self.parent, _("Error"),
                    _("Error reading .desktop file: {0}").format(e)
                )
                return None
        else:
            # Fallback: Search all .desktop files
            for file in glob.glob(os.path.join(self.portproton_location, "*.desktop")):
                entry = parse_desktop_entry(file)
                if entry:
                    exec_line = entry.get("Exec", entry.get("exec", "")).strip()
                    if exec_line:
                        return exec_line
            QMessageBox.warning(
                self.parent, _("Error"),
                _(".desktop file not found for game: {0}").format(game_name)
            )
            return None
        return exec_line

    def _parse_exe_path(self, exec_line, game_name):
        """Parse the executable path from exec_line."""
        try:
            entry_exec_split = shlex.split(exec_line)
            if not entry_exec_split:
                QMessageBox.warning(
                    self.parent, _("Error"),
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
                QMessageBox.warning(
                    self.parent, _("Error"),
                    _("Executable file not found: {0}").format(exe_path or "None")
                )
                return None
            return exe_path
        except Exception as e:
            QMessageBox.warning(
                self.parent, _("Error"),
                _("Failed to parse executable command: {0}").format(e)
            )
            return None

    def _remove_file(self, file_path, error_message, success_message, game_name):
        """Remove a file and handle errors."""
        try:
            os.remove(file_path)
            self.parent.statusBar().showMessage(success_message.format(game_name), 3000)
            return True
        except OSError as e:
            QMessageBox.warning(self.parent, _("Error"), error_message.format(e))
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
            QMessageBox.warning(
                self.parent, _("Error"),
                _("Could not locate .desktop file for '{0}'").format(game_name)
            )
            return

        # Get exec_line and parse exe_path
        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        exe_name = os.path.splitext(os.path.basename(exe_path))[0] if exe_path else None

        # Remove .desktop file
        if not self._remove_file(
            desktop_path,
            _("Failed to delete .desktop file: {0}"),
            _("Game '{0}' deleted successfully"),
            game_name
        ):
            return

        # Remove custom data if we got an exe_name
        if exe_name:
            xdg_data_home = os.getenv(
                "XDG_DATA_HOME",
                os.path.join(os.path.expanduser("~"), ".local", "share")
            )
            custom_folder = os.path.join(xdg_data_home, "PortProtonQT", "custom_data", exe_name)
            if os.path.exists(custom_folder):
                try:
                    shutil.rmtree(custom_folder)
                except OSError as e:
                    QMessageBox.warning(
                        self.parent, _("Error"),
                        _("Failed to delete custom data: {0}").format(e)
                    )

        # Refresh UI
        self.parent.games = self.load_games()
        self.update_game_grid()

    def add_to_menu(self, game_name, exec_line):
        """Copy the .desktop file to ~/.local/share/applications."""
        if not self._check_portproton():
            return

        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            QMessageBox.warning(
                self.parent, _("Error"),
                _("Could not locate .desktop file for '{0}'").format(game_name)
            )
            return

        # Destination path
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        os.makedirs(applications_dir, exist_ok=True)
        dest_path = os.path.join(applications_dir, f"{game_name}.desktop")

        # Copy .desktop file
        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)  # Ensure executable permissions
            self.parent.statusBar().showMessage(_("Game '{0}' added to menu").format(game_name), 3000)
        except OSError as e:
            QMessageBox.warning(
                self.parent, _("Error"),
                _("Failed to add game to menu: {0}").format(str(e))
            )

    def remove_from_menu(self, game_name):
        """Remove the .desktop file from ~/.local/share/applications."""
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        desktop_path = os.path.join(applications_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove game from menu: {0}"),
            _("Game '{0}' removed from menu"),
            game_name
        )

    def add_to_desktop(self, game_name, exec_line):
        """Copy the .desktop file to Desktop folder."""
        if not self._check_portproton():
            return

        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            QMessageBox.warning(
                self.parent, _("Error"),
                _("Could not locate .desktop file for '{0}'").format(game_name)
            )
            return

        # Destination path
        desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
        os.makedirs(desktop_dir, exist_ok=True)
        dest_path = os.path.join(desktop_dir, f"{game_name}.desktop")

        # Copy .desktop file
        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)  # Ensure executable permissions
            self.parent.statusBar().showMessage(_("Game '{0}' added to desktop").format(game_name), 3000)
        except OSError as e:
            QMessageBox.warning(
                self.parent, _("Error"),
                _("Failed to add game to desktop: {0}").format(str(e))
            )

    def remove_from_desktop(self, game_name):
        """Remove the .desktop file from Desktop folder."""
        desktop_dir = subprocess.check_output(['xdg-user-dir', 'DESKTOP']).decode('utf-8').strip()
        desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove game from Desktop: {0}"),
            _("Game '{0}' removed from Desktop"),
            game_name
        )

    def edit_game_shortcut(self, game_name, exec_line, cover_path):
        """Opens the AddGameDialog in edit mode to modify an existing .desktop file."""
        from portprotonqt.dialogs import AddGameDialog  # Local import to avoid circular dependency

        if not self._check_portproton():
            return

        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return

        # Open dialog in edit mode
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
                QMessageBox.warning(self.parent, _("Error"), _("Game name and executable path are required."))
                return

            # Generate new .desktop file content
            desktop_entry, new_desktop_path = dialog.getDesktopEntryData()
            if not desktop_entry or not new_desktop_path:
                QMessageBox.warning(self.parent, _("Error"), _("Failed to generate .desktop file data."))
                return

            # If the name has changed, remove the old .desktop file
            old_desktop_path = self._get_desktop_path(game_name)
            if game_name != new_name and os.path.exists(old_desktop_path):
                self._remove_file(
                    old_desktop_path,
                    _("Failed to remove old .desktop file: {0}"),
                    _("Old .desktop file removed for '{0}'"),
                    game_name
                )

            # Save the updated .desktop file
            try:
                with open(new_desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                    os.chmod(new_desktop_path, 0o755)
            except OSError as e:
                QMessageBox.warning(self.parent, _("Error"), _("Failed to save .desktop file: {0}").format(e))
                return

            # Update custom cover if provided
            if os.path.isfile(new_cover_path):
                exe_name = os.path.splitext(os.path.basename(new_exe_path))[0]
                xdg_data_home = os.getenv(
                    "XDG_DATA_HOME",
                    os.path.join(os.path.expanduser("~"), ".local", "share")
                )
                custom_folder = os.path.join(xdg_data_home, "PortProtonQT", "custom_data", exe_name)
                os.makedirs(custom_folder, exist_ok=True)

                ext = os.path.splitext(new_cover_path)[1].lower()
                if ext in [".png", ".jpg", ".jpeg", ".bmp"]:
                    try:
                        shutil.copyfile(new_cover_path, os.path.join(custom_folder, f"cover{ext}"))
                    except OSError as e:
                        QMessageBox.warning(self.parent, _("Error"), _("Failed to copy cover image: {0}").format(e))
                        return

            # Refresh the game list
            self.parent.games = self.load_games()
            self.update_game_grid()

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

        success, message = add_to_steam(game_name, exec_line, cover_path)
        if success:
            QMessageBox.information(
                self.parent, _("Restart Steam"),
                _("The game was added successfully.\nPlease restart Steam for changes to take effect.")
            )
        else:
            QMessageBox.warning(self.parent, _("Error"), message)

    def remove_from_steam(self, game_name, exec_line):
        """Handle removing a non-Steam game from Steam via steam_api."""

        if not self._check_portproton():
            return

        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return

        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return

        success, message = remove_from_steam(game_name, exec_line)
        if success:
            QMessageBox.information(
                self.parent, _("Restart Steam"),
                _("The game was removed successfully.\nPlease restart Steam for changes to take effect.")
            )
        else:
            QMessageBox.warning(self.parent, _("Error"), message)

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
            self.parent.statusBar().showMessage(_("Opened folder for '{0}'").format(game_name), 3000)
        except Exception as e:
            QMessageBox.warning(self.parent, _("Error"), _("Failed to open game folder: {0}").format(str(e)))
