import os
import shlex
import glob
import shutil
import subprocess
import threading
import orjson
from PySide6.QtWidgets import QMessageBox, QDialog, QMenu, QLineEdit, QApplication
from PySide6.QtCore import QUrl, QPoint, QObject, Signal, Qt, QStandardPaths
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence
from portprotonqt.localization import _
from portprotonqt.config_utils import parse_desktop_entry, read_favorites, save_favorites, read_favorite_folders, save_favorite_folders, get_portproton_start_command
from portprotonqt.steam_api import is_game_in_steam, add_to_steam, remove_from_steam
from portprotonqt.egs_api import add_egs_to_steam, get_egs_executable, remove_egs_from_steam
from portprotonqt.dialogs import AddGameDialog, FileExplorer, generate_thumbnail
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

class ContextMenuSignals(QObject):
    """Signals for thread-safe UI updates from worker threads."""
    show_status_message = Signal(str, int)
    show_warning_dialog = Signal(str, str)
    show_info_dialog = Signal(str, str)

class ContextMenuManager:
    """Manages context menu actions for game management in PortProtonQt."""

    def __init__(self, parent, portproton_location, theme, game_library_manager):
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
        self.theme_manager = ThemeManager()
        self.game_library_manager = game_library_manager
        self.update_game_grid = game_library_manager.update_game_grid
        self.legendary_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache", "legendary"
        )
        self.legendary_config_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache"
        )
        self.signals = ContextMenuSignals()
        if self.parent.statusBar() is None:
            logger.warning("Status bar is not initialized in MainWindow")
        else:
            self.signals.show_status_message.connect(
                self.parent.statusBar().showMessage,
                Qt.ConnectionType.QueuedConnection
            )
            logger.debug("Connected show_status_message signal to status bar")
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
        logger.debug("Displaying warning dialog: %s - %s", title, message)
        QMessageBox.warning(self.parent, title, message)

    def _show_info_dialog(self, title: str, message: str):
        """Show an info dialog in the main thread."""
        logger.debug("Displaying info dialog: %s - %s", title, message)
        QMessageBox.information(self.parent, title, message)

    def _show_status_message(self, message: str, timeout: int = 3000):
        """Show a status message on the status bar if available."""
        if self.parent.statusBar():
            self.parent.statusBar().showMessage(message, timeout)
            logger.debug("Displayed status message: %s", message)
        else:
            logger.warning("Status bar unavailable for message: %s", message)

    def _check_portproton(self):
        """Check if PortProton is available."""
        if self.portproton_location is None:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("PortProton directory not found")
            )
            return False
        return True

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
            with open(installed_json_path, "rb") as f:
                installed_games = orjson.loads(f.read())
            return app_name in installed_games
        except (OSError, orjson.JSONDecodeError) as e:
            logger.error("Error reading installed.json: %s", e)
            return False

    def _is_game_running(self, game_card) -> bool:
        """
        Check if the game associated with the game_card is currently running.

        Args:
            game_card: The GameCard instance containing game data.

        Returns:
            bool: True if the game is running, False otherwise.
        """
        if game_card.game_source == "epic":
            exe_path = get_egs_executable(game_card.appid, self.legendary_config_path)
            if not exe_path or not os.path.exists(exe_path):
                return False
            current_exe = os.path.basename(exe_path)
        elif game_card.game_source == "steam":
            return False
        else:
            exec_line = self._get_exec_line(game_card.name, game_card.exec_line)
            if not exec_line:
                return False
            exe_path = self._parse_exe_path(exec_line, game_card.name)
            if not exe_path:
                return False
            current_exe = os.path.basename(exe_path)

        return hasattr(self.parent, 'target_exe') and self.parent.target_exe == current_exe

    def show_folder_context_menu(self, file_explorer, pos):
        """Shows the context menu for a folder in FileExplorer."""
        try:
            item = file_explorer.file_list.itemAt(pos)
            if not item:
                logger.debug("No folder selected at position %s", pos)
                return
            selected = item.text()
            if not selected.endswith("/"):
                logger.debug("Selected item is not a folder: %s", selected)
                return  # Only for folders
            full_path = os.path.normpath(os.path.join(file_explorer.current_path, selected.rstrip("/")))
            if not os.path.isdir(full_path):
                logger.debug("Path is not a directory: %s", full_path)
                return

            menu = QMenu(file_explorer)
            menu.setStyleSheet(self.theme.CONTEXT_MENU_STYLE)
            menu.setParent(file_explorer, Qt.WindowType.Popup)  # Set transientParent for Wayland

            favorite_folders = read_favorite_folders()
            is_favorite = full_path in favorite_folders
            action_text = _("Remove from Favorites") if is_favorite else _("Add to Favorites")
            favorite_action = menu.addAction(self._get_safe_icon("star" if is_favorite else "star_full"), action_text)
            favorite_action.triggered.connect(lambda: self.toggle_favorite_folder(file_explorer, full_path, not is_favorite))

            # Disconnect file_list signals to prevent navigation during menu interaction
            try:
                file_explorer.file_list.itemClicked.disconnect(file_explorer.handle_item_click)
                file_explorer.file_list.itemDoubleClicked.disconnect(file_explorer.handle_item_double_click)
            except TypeError:
                pass  # Signals may not be connected

            # Reconnect signals after menu closes
            def reconnect_signals():
                try:
                    file_explorer.file_list.itemClicked.connect(file_explorer.handle_item_click)
                    file_explorer.file_list.itemDoubleClicked.connect(file_explorer.handle_item_double_click)
                except Exception as e:
                    logger.error("Error reconnecting file list signals: %s", e)

            menu.aboutToHide.connect(reconnect_signals)

            # Set focus to the first menu item
            actions = menu.actions()
            if actions:
                menu.setActiveAction(actions[0])

            # Map local position to global for menu display
            global_pos = file_explorer.file_list.mapToGlobal(pos)
            menu.exec(global_pos)
        except Exception as e:
            logger.error("Error displaying folder context menu: %s", e)

    def toggle_favorite_folder(self, file_explorer, folder_path, add):
        """Adds or removes a folder from favorites."""
        favorite_folders = read_favorite_folders()
        if add:
            if folder_path not in favorite_folders:
                favorite_folders.append(folder_path)
                save_favorite_folders(favorite_folders)
                logger.info("Added folder to favorites: %s", folder_path)
        else:
            if folder_path in favorite_folders:
                favorite_folders.remove(folder_path)
                save_favorite_folders(favorite_folders)
                logger.info("Removed folder from favorites: %s", folder_path)
        file_explorer.update_drives_list()

    def _get_safe_icon(self, icon_name: str) -> QIcon:
        """Returns a QIcon, ensuring it is valid."""
        icon = self.theme_manager.get_icon(icon_name)
        if isinstance(icon, QIcon):
            return icon
        elif isinstance(icon, str) and os.path.exists(icon):
            return QIcon(icon)
        return QIcon()

    def show_context_menu(self, game_card, pos: QPoint):
        """
        Show the context menu for a game card at the specified position.

        Args:
            game_card: The GameCard instance requesting the context menu.
            pos: The position (in widget coordinates) where the menu should appear.
        """
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.theme.CONTEXT_MENU_STYLE)

        # For non-Steam and non-Epic games, check if exe exists
        if game_card.game_source not in ("steam", "epic"):
            exec_line = self._get_exec_line(game_card.name, game_card.exec_line)
            exe_path = self._parse_exe_path(exec_line, game_card.name) if exec_line else None
            if not exe_path:
                # Show only "Delete from PortProton" if no valid exe
                delete_action = menu.addAction(self._get_safe_icon("delete"), _("Delete from PortProton"))
                delete_action.triggered.connect(lambda: self.delete_game(game_card.name, game_card.exec_line))
                menu.exec(game_card.mapToGlobal(pos))
                return

        # Normal menu for games with valid exe or from Steam/Epic
        is_running = self._is_game_running(game_card)
        action_text = _("Stop Game") if is_running else _("Launch Game")
        action_icon = "stop" if is_running else "play"
        launch_action = menu.addAction(self._get_safe_icon(action_icon), action_text)
        launch_action.triggered.connect(
            lambda: self._launch_game(game_card)
        )

        favorites = read_favorites()
        is_favorite = game_card.name in favorites
        icon_name = "star_full" if is_favorite else "star"
        text = _("Remove from Favorites") if is_favorite else _("Add to Favorites")
        favorite_action = menu.addAction(self._get_safe_icon(icon_name), text)
        favorite_action.triggered.connect(lambda: self.toggle_favorite(game_card, not is_favorite))

        if game_card.game_source == "epic":
            import_action = menu.addAction(self._get_safe_icon("epic_games"), _("Import to Legendary"))
            import_action.triggered.connect(
                lambda: self.import_to_legendary(game_card.name, game_card.appid)
            )
            if self._is_egs_game_installed(game_card.appid):
                is_in_steam = is_game_in_steam(game_card.name)
                icon_name = "delete" if is_in_steam else "steam"
                text = _("Remove from Steam") if is_in_steam else _("Add to Steam")
                steam_action = menu.addAction(self._get_safe_icon(icon_name), text)
                steam_action.triggered.connect(
                    lambda: self.remove_from_steam(game_card.name, game_card.exec_line, game_card.game_source)
                    if is_in_steam
                    else self.add_egs_to_steam(game_card.name, game_card.appid)
                )
                open_folder_action = menu.addAction(self._get_safe_icon("search"), _("Open Game Folder"))
                open_folder_action.triggered.connect(
                    lambda: self.open_egs_game_folder(game_card.appid)
                )
                desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
                desktop_path = os.path.join(desktop_dir, f"{game_card.name}.desktop")
                icon_name = "delete" if os.path.exists(desktop_path) else "desktop"
                text = _("Remove from Desktop") if os.path.exists(desktop_path) else _("Add to Desktop")
                desktop_action = menu.addAction(self._get_safe_icon(icon_name), text)
                desktop_action.triggered.connect(
                    lambda: self.remove_egs_from_desktop(game_card.name)
                    if os.path.exists(desktop_path)
                    else self.add_egs_to_desktop(game_card.name, game_card.appid)
                )
                applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
                menu_path = os.path.join(applications_dir, f"{game_card.name}.desktop")
                menu_action = menu.addAction(
                    self._get_safe_icon("delete" if os.path.exists(menu_path) else "menu"),
                    _("Remove from Menu") if os.path.exists(menu_path) else _("Add to Menu")
                )
                menu_action.triggered.connect(
                    lambda: self.remove_egs_from_menu(game_card.name)
                    if os.path.exists(menu_path)
                    else self.add_egs_to_menu(game_card.name, game_card.appid)
                )

        if game_card.game_source not in ("steam", "epic"):
            desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
            desktop_path = os.path.join(desktop_dir, f"{game_card.name}.desktop")
            icon_name = "delete" if os.path.exists(desktop_path) else "desktop"
            text = _("Remove from Desktop") if os.path.exists(desktop_path) else _("Add to Desktop")
            desktop_action = menu.addAction(self._get_safe_icon(icon_name), text)
            desktop_action.triggered.connect(
                lambda: self.remove_from_desktop(game_card.name)
                if os.path.exists(desktop_path)
                else self.add_to_desktop(game_card.name, game_card.exec_line)
            )
            edit_action = menu.addAction(self._get_safe_icon("edit"), _("Edit Shortcut"))
            edit_action.triggered.connect(
                lambda: self.edit_game_shortcut(game_card.name, game_card.exec_line, game_card.cover_path)
            )
            delete_action = menu.addAction(self._get_safe_icon("delete"), _("Delete from PortProton"))
            delete_action.triggered.connect(lambda: self.delete_game(game_card.name, game_card.exec_line))
            open_folder_action = menu.addAction(self._get_safe_icon("search"), _("Open Game Folder"))
            open_folder_action.triggered.connect(
                lambda: self.open_game_folder(game_card.name, game_card.exec_line)
            )
            applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
            menu_path = os.path.join(applications_dir, f"{game_card.name}.desktop")
            icon_name = "delete" if os.path.exists(menu_path) else "menu"
            text = _("Remove from Menu") if os.path.exists(menu_path) else _("Add to Menu")
            menu_action = menu.addAction(self._get_safe_icon(icon_name), text)
            menu_action.triggered.connect(
                lambda: self.remove_from_menu(game_card.name)
                if os.path.exists(menu_path)
                else self.add_to_menu(game_card.name, game_card.exec_line)
            )
            is_in_steam = is_game_in_steam(game_card.name)
            icon_name = "delete" if is_in_steam else "steam"
            text = _("Remove from Steam") if is_in_steam else _("Add to Steam")
            steam_action = menu.addAction(self._get_safe_icon(icon_name), text)
            steam_action.triggered.connect(
                lambda: (
                    self.remove_from_steam(game_card.name, game_card.exec_line, game_card.game_source)
                    if is_in_steam
                    else self.add_to_steam(game_card.name, game_card.exec_line, game_card.cover_path)
                )
            )

        # Set focus to the first menu item
        actions = menu.actions()
        if actions:
            menu.setActiveAction(actions[0])

            menu.exec(game_card.mapToGlobal(pos))

    def _launch_game(self, game_card):
        """
        Launch or stop a game based on its current state.

        Args:
            game_card: The GameCard instance containing game data.
        """
        if not self._check_portproton():
            return

        # Check if the game is running
        if self._is_game_running(game_card):
            if hasattr(self.parent, "stop_running_game") and self.parent.stop_running_game():
                self._show_status_message(_("Stopped '{game_name}'").format(game_name=game_card.name))
            else:
                self.signals.show_warning_dialog.emit(_("Error"), _("Failed to stop game"))
            return

        # Launch the game
        if game_card.game_source == "epic":
            if not os.path.exists(self.legendary_path):
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Legendary executable not found at {path}").format(path=self.legendary_path)
                )
                return
            # Construct EGS launch command
            wrapper = get_portproton_start_command()
            exec_line = f'"{self.legendary_path}" launch {game_card.appid} --no-wine --wrapper "env START_FROM_STEAM=1 {wrapper}"'
        else:
            exec_line = self._get_exec_line(game_card.name, game_card.exec_line)
            if not exec_line:
                return
        self.parent.toggleGame(exec_line)

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
                _("Error"),
                _("Legendary executable not found at {path}").format(path=self.legendary_path)
            )
            return

        def on_add_to_steam_result(result: tuple[bool, str]):
            success, message = result
            if success:
                if "restart" in message.lower():
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("'{game_name}' was added to Steam. Please restart Steam for changes to take effect.").format(game_name=game_name)
                    )
                else:
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("'{game_name}' was added to Steam.").format(game_name=game_name)
                    )
            else:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _(message).format(game_name=game_name)
                )

        logger.debug("Adding EGS game '%s' to Steam", game_name)
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
                _("Executable not found for game: {game_name}").format(game_name=app_name)
            )
            return
        try:
            folder_path = os.path.dirname(os.path.abspath(exe_path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
            self._show_status_message(_("Opened folder for '{game_name}'").format(game_name=app_name))
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to open folder: {error}").format(error=str(e))
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
        if not os.path.exists(self.legendary_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Legendary executable not found at {path}").format(path=self.legendary_path)
            )
            return

        # Use FileExplorer with directory_only=True
        file_explorer = FileExplorer(
            parent=self.parent,
            theme=self.theme,
            initial_path=os.path.expanduser("~"),
            directory_only=True
        )

        def on_folder_selected(folder_path):
            if not folder_path:
                self._show_status_message(_("No folder selected"))
                return
            def run_import():
                cmd = [self.legendary_path, "import", app_name, folder_path]
                try:
                    subprocess.run(cmd, capture_output=True, text=True, check=True)
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("Imported '{game_name}' to Legendary").format(game_name=game_name)
                    )
                except subprocess.CalledProcessError as e:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to import '{game_name}' to Legendary: {error}").format(
                            game_name=game_name, error=e.stderr
                        )
                    )
            self._show_status_message(_("Importing '{game_name}' to Legendary...").format(game_name=game_name))
            threading.Thread(target=run_import, daemon=True).start()

        # Connect the file selection signal
        file_explorer.file_signal.file_selected.connect(on_folder_selected)

        # Center FileExplorer relative to the parent widget
        parent_widget = self.parent
        if parent_widget:
            parent_geometry = parent_widget.geometry()
            center_point = parent_geometry.center()
            file_explorer_geometry = file_explorer.geometry()
            file_explorer_geometry.moveCenter(center_point)
            file_explorer.setGeometry(file_explorer_geometry)

        file_explorer.show()

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
            message = _("Added '{game_name}' to favorites").format(game_name=game_card.name)
        elif not add and game_card.name in favorites:
            favorites.remove(game_card.name)
            game_card.is_favorite = False
            message = _("Removed '{game_name}' from favorites").format(game_name=game_card.name)
        else:
            return
        save_favorites(favorites)
        game_card.update_favorite_icon()
        self._show_status_message(message)

    def _get_desktop_path(self, game_name):
        """Construct the .desktop file path, trying direct and fallback matching."""
        desktop_path = os.path.join(self.portproton_location, f"{game_name}.desktop")
        if os.path.exists(desktop_path):
            return desktop_path

        sanitized_name = game_name.replace("/", "_").replace(":", "_").replace(" ", "_")
        desktop_path = os.path.join(self.portproton_location, f"{sanitized_name}.desktop")
        if os.path.exists(desktop_path):
            return desktop_path

        normalized_game_name = "".join(ch for ch in game_name.lower() if ch.isalnum())
        desktop_files = glob.glob(os.path.join(self.portproton_location, "*.desktop"))

        if normalized_game_name:
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            xdg_data_home = os.getenv(
                "XDG_DATA_HOME",
                os.path.join(os.path.expanduser("~"), ".local", "share")
            )
            custom_roots = [
                os.path.join(xdg_data_home, "PortProtonQt", "custom_data"),
                os.path.join(repo_root, "portprotonqt", "custom_data"),
            ]
            for custom_root in custom_roots:
                if not os.path.isdir(custom_root):
                    continue
                metadata_files = glob.glob(
                    os.path.join(custom_root, "**", "metadata.txt"),
                    recursive=True,
                )
                for metadata_path in metadata_files:
                    try:
                        metadata_name = ""
                        with open(metadata_path, encoding="utf-8") as metadata_file:
                            for line in metadata_file:
                                if line.startswith("name="):
                                    metadata_name = line[5:].strip()
                                    break
                        if not metadata_name:
                            continue
                        normalized_metadata_name = "".join(
                            ch for ch in metadata_name.lower() if ch.isalnum()
                        )
                        if normalized_metadata_name != normalized_game_name:
                            continue
                        script_name = os.path.basename(os.path.dirname(metadata_path))
                        for file_path in desktop_files:
                            entry = parse_desktop_entry(file_path)
                            if not entry:
                                continue
                            exec_line = entry.get("Exec", entry.get("exec", ""))
                            if script_name.lower() in exec_line.lower():
                                return file_path
                    except OSError:
                        continue

        for file_path in desktop_files:
            entry = parse_desktop_entry(file_path)
            if entry:
                entry_name = entry.get("Name", entry.get("name", "")).strip()
                normalized_entry_name = "".join(ch for ch in entry_name.lower() if ch.isalnum())
                if normalized_entry_name and (
                    normalized_entry_name == normalized_game_name
                    or normalized_entry_name in normalized_game_name
                    or normalized_game_name in normalized_entry_name
                ):
                    return file_path

            stem = os.path.splitext(os.path.basename(file_path))[0]
            normalized_stem = "".join(ch for ch in stem.lower() if ch.isalnum())
            if normalized_stem and (
                normalized_stem == normalized_game_name
                or normalized_stem in normalized_game_name
                or normalized_game_name in normalized_stem
            ):
                return file_path

        return desktop_path

    def _get_egs_desktop_path(self, game_name):
        """Construct the .desktop file path for EGS games."""
        return os.path.join(self.portproton_location, "egs_desktops", f"{game_name}.desktop")

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
                _("Legendary executable not found at {path}").format(path=self.legendary_path)
            )
            return False
        wrapper_command = get_portproton_start_command()
        if not wrapper_command:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("start.sh not found at {path}").format(path="/usr/share/portproton/scripts/start.sh")
            )
            return False
        wrapper = shlex.join(wrapper_command)
        icon_path = os.path.join(self.portproton_location, "data", "img", f"{game_name}.png")
        os.makedirs(os.path.dirname(icon_path), exist_ok=True)

        # Generate 128x128 icon from exe only
        exe_path = get_egs_executable(app_name, self.legendary_config_path)
        if exe_path and os.path.exists(exe_path):
            if not generate_thumbnail(exe_path, icon_path, size=128):
                logger.error("Failed to generate thumbnail for EGS game: %s", exe_path)
                icon_path = ""
        else:
            logger.error("No executable found for EGS game: %s", app_name)
            icon_path = ""

        egs_desktop_dir = os.path.join(self.portproton_location, "egs_desktops")
        os.makedirs(egs_desktop_dir, exist_ok=True)
        desktop_path = self._get_egs_desktop_path(game_name)
        comment = _('Launch game "{name}" with PortProton').format(name=game_name)
        desktop_entry =f"""\
[Desktop Entry]
Name={game_name}
Comment={comment}
Exec="{self.legendary_path}" launch {app_name} --no-wine --wrapper "env START_FROM_STEAM=1 {wrapper}"
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
Icon={icon_path}
    """
        try:
            with open(desktop_path, "w", encoding="utf-8") as f:
                f.write(desktop_entry)
            os.chmod(desktop_path, 0o755)
            logger.info("Created .desktop file for EGS game: %s", desktop_path)
            return True
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to create .desktop file: {error}").format(error=str(e))
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
            if not self._create_egs_desktop_file(game_name, app_name):
                return
        desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        os.makedirs(desktop_dir, exist_ok=True)
        dest_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            self._show_status_message(_("Added '{game_name}' to {location}").format(
                game_name=game_name, location=_("Desktop")
            ))
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add '{game_name}' to {location}: {error}").format(
                    game_name=game_name, location=_("Desktop"), error=str(e)
                )
            )

    def remove_egs_from_desktop(self, game_name: str):
        """
        Removes the .desktop file for an EGS game from the Desktop folder.

        Args:
            game_name: The display name of the game.
        """
        desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove '{game_name}' from {location}: {error}"),
            _("Removed '{game_name}' from {location}"),
            game_name,
            location=_("Desktop")
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
            if not self._create_egs_desktop_file(game_name, app_name):
                return
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        os.makedirs(applications_dir, exist_ok=True)
        dest_path = os.path.join(applications_dir, f"{game_name}.desktop")
        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            self._show_status_message(_("Added '{game_name}' to {location}").format(
                game_name=game_name, location=_("Menu")
            ))
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add '{game_name}' to {location}: {error}").format(
                    game_name=game_name, location=_("Menu"), error=str(e)
                )
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
            _("Failed to remove '{game_name}' from {location}: {error}"),
            _("Removed '{game_name}' from {location}"),
            game_name,
            location=_("Menu")
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
                            _("No executable command found in .desktop file for '{game_name}'").format(game_name=game_name)
                        )
                        return None
                else:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Failed to parse .desktop file for '{game_name}'").format(game_name=game_name)
                    )
                    return None
            except Exception as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Error reading .desktop file: {error}").format(error=str(e))
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
                _("No .desktop file found for '{game_name}'").format(game_name=game_name)
            )
            return None
        return exec_line

    def _parse_exe_path(self, exec_line: str, game_name: str) -> str | None:
        """Parse the executable path from exec_line."""
        try:
            entry_exec_split = shlex.split(exec_line)
            if not entry_exec_split:
                logger.debug("Invalid executable command for game '%s': %s", game_name, exec_line)
                return None
            if entry_exec_split[0] == "env" and len(entry_exec_split) >= 3:
                exe_path = entry_exec_split[2]
            elif entry_exec_split[0] == "flatpak" and len(entry_exec_split) >= 4:
                exe_path = entry_exec_split[3]
            else:
                exe_path = entry_exec_split[-1]
            if not exe_path or not os.path.exists(exe_path):
                logger.debug("Executable not found for game '%s': %s", game_name, exe_path or "None")
                return None
            return exe_path
        except Exception as e:
            logger.debug("Error parsing executable for game '%s': %s", game_name, e)
            return None

    def _remove_file(self, file_path, error_message, success_message, game_name, location=""):
        """Remove a file and handle errors."""
        try:
            os.remove(file_path)
            self._show_status_message(_(success_message).format(game_name=game_name, location=location))
            return True
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _(error_message).format(game_name=game_name, location=location, error=str(e))
            )
            return False

    def _remove_statistics_entry(self, exe_path, game_name):
        """Remove statistics entry for exact executable path."""
        if not exe_path or not self.portproton_location:
            return

        statistics_file = os.path.join(self.portproton_location, "data", "tmp", "statistics")
        if not os.path.exists(statistics_file):
            return

        target_path = os.path.normpath(exe_path)
        kept_lines = []
        removed = False

        try:
            with open(statistics_file, encoding="utf-8") as f:
                for line in f:
                    token = line.strip().split(maxsplit=1)
                    if not token:
                        kept_lines.append(line)
                        continue
                    stat_path = os.path.normpath(token[0].replace("#@_@#", " "))
                    if stat_path == target_path:
                        removed = True
                        continue
                    kept_lines.append(line)

            if removed:
                with open(statistics_file, "w", encoding="utf-8") as f:
                    f.writelines(kept_lines)
                logger.info("Removed statistics entry for '%s' (%s)", game_name, exe_path)
        except OSError as e:
            logger.warning("Failed to clean statistics for '%s': %s", game_name, e)

    def delete_game(self, game_name, exec_line):
        card_exec_line = exec_line
        msg_box = QMessageBox(self.parent)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(_("Confirm Deletion"))
        msg_box.setText(_("Are you sure you want to delete '{game_name}'? This will remove the .desktop file and custom data.").format(game_name=game_name))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        msg_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        reply = msg_box.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not self._check_portproton():
            return
        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("No .desktop file found for '{game_name}'").format(game_name=game_name)
            )
            return
        resolved_exec_line = self._get_exec_line(game_name, exec_line)
        if not resolved_exec_line:
            return
        exe_path = self._parse_exe_path(resolved_exec_line, game_name)
        exe_name = os.path.splitext(os.path.basename(exe_path))[0] if exe_path else None
        if not self._remove_file(
            desktop_path,
            _("Failed to delete .desktop file: {error}"),
            _("Deleted '{game_name}' successfully"),
            game_name
        ):
            return
        self._remove_statistics_entry(exe_path, game_name)
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
                        _("Failed to delete custom data: {error}").format(error=str(e))
                    )

        self.game_library_manager.remove_game_incremental(game_name, card_exec_line or resolved_exec_line)

    def add_game_incremental(self, game_data: tuple):
        """Add game after .desktop creation."""
        if not self._check_portproton():
            return
        # Assume game_data is built from new .desktop (name, desc, cover, etc.)
        self.game_library_manager.add_game_incremental(game_data)
        self._show_status_message(_("Added '{game_name}' successfully").format(game_name=game_data[0]))

    def add_to_menu(self, game_name, exec_line):
        """Copy the .desktop file to ~/.local/share/applications."""
        if not self._check_portproton():
            return
        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("No .desktop file found for '{game_name}'").format(game_name=game_name)
            )
            return
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        os.makedirs(applications_dir, exist_ok=True)
        dest_path = os.path.join(applications_dir, f"{game_name}.desktop")
        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            self._show_status_message(_("Added '{game_name}' to {location}").format(
                game_name=game_name, location=_("Menu")
            ))
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add '{game_name}' to {location}: {error}").format(
                    game_name=game_name, location=_("Menu"), error=str(e)
                )
            )

    def remove_from_menu(self, game_name):
        """
        Removes the game from the menu by removing its .desktop file from ~/.local/share/applications.

        Args:
            game_name: The display name of the game.
        """
        applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        desktop_path = os.path.join(applications_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove '{game_name}' from {location}: {error}"),
            _("Removed '{game_name}' from {location}"),
            game_name,
            location=_("Menu")
        )

    def add_to_desktop(self, game_name, exec_line):
        """
        Copies the .desktop file to the user's Desktop folder.

        Args:
            game_name: The display name of the game.
            exec_line: The executable command line.
        """

        if not self._check_portproton():
            return
        desktop_path = self._get_desktop_path(game_name)
        if not os.path.exists(desktop_path):
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("No .desktop file found for '{game_name}'").format(game_name=game_name)
            )
            return
        # Ensure icon exists
        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return
        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return
        icon_path = os.path.join(self.portproton_location, "data", "img", f"{game_name}.png")
        if not os.path.exists(icon_path):
            if not generate_thumbnail(exe_path, icon_path, size=128):
                logger.error("Failed to generate thumbnail for game: %s", exe_path)

        desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        os.makedirs(desktop_dir, exist_ok=True)
        dest_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        try:
            shutil.copyfile(desktop_path, dest_path)
            os.chmod(dest_path, 0o755)
            self._show_status_message(_("Added '{game_name}' to {location}").format(
                game_name=game_name, location=_("Desktop")
            ))
        except OSError as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add '{game_name}' to {location}: {error}").format(
                    game_name=game_name, location=_("Desktop"), error=str(e)
                )
            )

    def remove_from_desktop(self, game_name):
        """
        Removes the game from the Desktop folder by removing its .desktop file.

        Args:
            game_name: The display name of the game.
        """
        desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
        self._remove_file(
            desktop_path,
            _("Failed to remove '{game_name}' from {location}: {error}"),
            _("Removed '{game_name}' from {location}"),
            game_name,
            location=_("Desktop")
        )

    def edit_game_shortcut(self, game_name, exec_line, cover_path):
        """
        Opens a dialog allowing the user to edit a game shortcut in edit mode to modify an existing .desktop file.

        Args:
            game_name: The display name of the game.
            exec_line: The executable command line of the game.
            cover_path: The path to the game's cover image.
        """
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
            cover_path=cover_path,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.nameEdit.text().strip()
            new_exe_path = dialog.exeEdit.text().strip()
            new_cover_path = dialog.coverEdit.text().strip()
            if not new_name or not new_exe_path:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Game name and executable path are required")
                )
                return
            desktop_entry, new_desktop_path = dialog.getDesktopEntryData()
            if not desktop_entry or not new_desktop_path:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to generate .desktop file data")
                )
                return

            old_path = self._get_desktop_path(game_name)
            if game_name != new_name and os.path.exists(old_path):
                self._remove_file(
                    old_path,
                    _("Failed to delete old .desktop file: {error}"),
                    _("Removed old .desktop file for '{game_name}'"),
                    game_name
                )

            try:
                with open(new_desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                os.chmod(new_desktop_path, 0o755)
            except OSError as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to save .desktop file: {error}").format(error=str(e))
                )
                return
            saved_entry = parse_desktop_entry(new_desktop_path)
            updated_exec_line = new_exe_path
            if saved_entry:
                parsed_exec = saved_entry.get("Exec", saved_entry.get("exec", "")).strip()
                if parsed_exec:
                    updated_exec_line = parsed_exec

            # Check if new_cover_path is a URL by checking for common image extensions
            image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')
            has_image_extension = any(new_cover_path.lower().endswith(ext) for ext in image_extensions)

            # Consider it a URL if it has image extension and is not a local file
            is_url = has_image_extension and not os.path.isfile(new_cover_path)

            # Use the downloaded file path if we have a URL and the file was downloaded, otherwise use the local file
            if os.path.isfile(new_cover_path) or (is_url and dialog.last_cover_path and os.path.isfile(dialog.last_cover_path)):
                exe_name = os.path.splitext(os.path.basename(new_exe_path))[0]
                xdg_data_home = os.getenv(
                    "XDG_DATA_HOME",
                    os.path.join(os.path.expanduser("~"), ".local", "share")
                )
                custom_folder = os.path.join(xdg_data_home, "PortProtonQt", "custom_data", exe_name)
                os.makedirs(custom_folder, exist_ok=True)

                # Use the actual cover file path (either from URL download or local file)
                cover_to_copy = dialog.last_cover_path if is_url and dialog.last_cover_path and os.path.isfile(dialog.last_cover_path) else new_cover_path
                ext = os.path.splitext(cover_to_copy)[1].lower()
                if ext in [".png", ".jpg", ".jpeg", ".bmp"]:
                    target_cover_path = os.path.join(custom_folder, f"cover{ext}")
                    try:
                        if os.path.exists(target_cover_path) and os.path.samefile(cover_to_copy, target_cover_path):
                            logger.debug(
                                "Skipping cover copy for %s: source and destination are identical",
                                new_name,
                            )
                        else:
                            shutil.copyfile(cover_to_copy, target_cover_path)
                    except OSError as e:
                        self.signals.show_warning_dialog.emit(
                            _("Error"),
                            _("Failed to copy cover image: {error}").format(error=str(e))
                        )
                        return
                else:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _("Unsupported image format: {extension}").format(extension=ext)
                    )
                    return

            applications_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
            old_menu_path = os.path.join(applications_dir, f"{game_name}.desktop")
            new_menu_path = os.path.join(applications_dir, f"{new_name}.desktop")
            desktop_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
            old_desktop_path = os.path.join(desktop_dir, f"{game_name}.desktop")
            new_desktop_path_target = os.path.join(desktop_dir, f"{new_name}.desktop")

            if game_name != new_name:
                if os.path.exists(old_menu_path):
                    self.remove_from_menu(game_name)
                if os.path.exists(old_desktop_path):
                    self.remove_from_desktop(game_name)
                if is_game_in_steam(game_name):
                    self.remove_from_steam(game_name, new_exe_path, "portproton")

            if dialog.add_to_menu_checkbox.isChecked():
                if not os.path.exists(new_menu_path):
                    self.add_to_menu(new_name, updated_exec_line)
            elif os.path.exists(new_menu_path):
                self.remove_from_menu(new_name)

            if dialog.add_to_desktop_checkbox.isChecked():
                if not os.path.exists(new_desktop_path_target):
                    self.add_to_desktop(new_name, updated_exec_line)
            elif os.path.exists(new_desktop_path_target):
                self.remove_from_desktop(new_name)

            is_in_steam = is_game_in_steam(new_name)
            if dialog.add_to_steam_checkbox.isChecked():
                if not is_in_steam:
                    self.add_to_steam(new_name, updated_exec_line, new_cover_path)
            elif is_in_steam:
                self.remove_from_steam(new_name, updated_exec_line, "portproton")

    def add_to_steam(self, game_name, exec_line, cover_path):
        """
        Adds a non-Steam game to Steam using steam_api.

        Args:
            game_name: The display name of the game.
            exec_line: The executable command line.
            cover_path: Path to the cover image.
        """
        if not self._check_portproton():
            return
        exec_line = self._get_exec_line(game_name, exec_line)
        if not exec_line:
            return
        exe_path = self._parse_exe_path(exec_line, game_name)
        if not exe_path:
            return
        logger.debug("Adding game '%s' to Steam", game_name)
        try:
            success, message = add_to_steam(game_name, exec_line, cover_path)
            if success:
                if "restart" in message.lower():
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("'{game_name}' was added to Steam. Please restart Steam for changes to take effect.").format(game_name=game_name)
                    )
                else:
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("'{game_name}' was added to Steam.").format(game_name=game_name)
                    )
            else:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _(message).format(game_name=game_name)
                )
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to add '{game_name}' to Steam: {error}").format(
                    game_name=game_name, error=str(e)
                )
            )

    def remove_from_steam(self, game_name, exec_line, game_source):
        """Handle removing a game from Steam via steam_api, supporting both EGS and non-EGS games."""
        if not self._check_portproton():
            return

        def on_remove_from_steam_result(result: tuple[bool, str]):
            success, message = result
            if success:
                if "restart" in message.lower():
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("'{game_name}' was removed from Steam. Please restart Steam for changes to take effect.").format(game_name=game_name)
                    )
                else:
                    self.signals.show_info_dialog.emit(
                        _("Success"),
                        _("'{game_name}' was removed from Steam.").format(game_name=game_name)
                    )
            else:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _(message).format(game_name=game_name)
                )

        if game_source == "epic":
            remove_egs_from_steam(game_name, self.portproton_location, on_remove_from_steam_result)
        else:
            # For non-EGS games, use steam_api
            exec_line = self._get_exec_line(game_name, exec_line)
            if not exec_line:
                return
            exe_path = self._parse_exe_path(exec_line, game_name)
            if not exe_path:
                return
            logger.debug("Removing game '%s' from Steam", game_name)
            try:
                success, message = remove_from_steam(game_name, exec_line)
                if success:
                    if "restart" in message.lower():
                        self.signals.show_info_dialog.emit(
                            _("Success"),
                            _("'{game_name}' was removed from Steam. Please restart Steam for changes to take effect.").format(game_name=game_name)
                        )
                    else:
                        self.signals.show_info_dialog.emit(
                            _("Success"),
                            _("'{game_name}' was removed from Steam.").format(game_name=game_name)
                        )
                else:
                    self.signals.show_warning_dialog.emit(
                        _("Error"),
                        _(message).format(game_name=game_name)
                    )
            except Exception as e:
                self.signals.show_warning_dialog.emit(
                    _("Error"),
                    _("Failed to remove game '{game_name}' from Steam: {error}").format(
                        game_name=game_name, error=str(e)
                    )
                )

    def open_game_folder(self, game_name, exec_line):
        """
        Opens the folder containing the game's executable.

        Args:
            game_name: The display name of the game.
            exec_line: The executable command line.
        """
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
            self._show_status_message(_("Opened folder for '{game_name}'").format(game_name=game_name))
        except Exception as e:
            self.signals.show_warning_dialog.emit(
                _("Error"),
                _("Failed to open folder: {error}").format(error=str(e))
            )

class CustomLineEdit(QLineEdit):

    def __init__(self, *args, theme=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.theme = theme

    def contextMenuEvent(self, event):
        show_themed_line_edit_context_menu(self, event.globalPos(), self.theme)

    def _delete_selected_text(self):
        cursor_pos = self.cursorPosition()
        self.backspace()
        self.setCursorPosition(cursor_pos)


def show_themed_line_edit_context_menu(line_edit: QLineEdit, global_pos: QPoint, theme=None) -> None:
    """Show a themed context menu for any line edit widget."""
    theme_manager = ThemeManager()

    def add_action(menu: QMenu, text: str, shortcut: QKeySequence.StandardKey,
                   icon_name: str, slot, enabled: bool = True) -> None:
        raw_icon = theme_manager.get_icon(icon_name)
        icon = raw_icon if isinstance(raw_icon, QIcon) else QIcon(raw_icon) if isinstance(raw_icon, str) else QIcon()
        shortcut_str = QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText)
        action = menu.addAction(icon, f"{text}\t{shortcut_str}")
        action.triggered.connect(slot)
        action.setEnabled(enabled)

    menu = QMenu(line_edit)
    current_theme = theme if theme is not None else getattr(line_edit, "theme", None)
    if current_theme and hasattr(current_theme, "CONTEXT_MENU_STYLE"):
        menu.setStyleSheet(current_theme.CONTEXT_MENU_STYLE)

    add_action(menu, _("Undo"), QKeySequence.StandardKey.Undo, "undo", line_edit.undo, line_edit.isUndoAvailable())
    add_action(menu, _("Redo"), QKeySequence.StandardKey.Redo, "redo", line_edit.redo, line_edit.isRedoAvailable())
    menu.addSeparator()
    add_action(menu, _("Cut"), QKeySequence.StandardKey.Cut, "cut", line_edit.cut, line_edit.hasSelectedText())
    add_action(menu, _("Copy"), QKeySequence.StandardKey.Copy, "copy", line_edit.copy, line_edit.hasSelectedText())
    add_action(menu, _("Paste"), QKeySequence.StandardKey.Paste, "paste", line_edit.paste,
               QApplication.clipboard().mimeData().hasText())
    add_action(menu, _("Delete"), QKeySequence.StandardKey.Delete, "delete", line_edit.backspace,
               line_edit.hasSelectedText())
    menu.addSeparator()
    add_action(menu, _("Select All"), QKeySequence.StandardKey.SelectAll, "select_all", line_edit.selectAll,
               bool(line_edit.text()))

    menu.exec(global_pos)
