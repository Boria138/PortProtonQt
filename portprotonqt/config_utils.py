"""Backward compatibility module for config_utils.

This module provides legacy function names that wrap the new config classes.
New code should use portprotonqt.config directly.
"""
import os
import configparser
import subprocess
from pathlib import Path
from portprotonqt.logger import get_logger
from portprotonqt.localization import _
from portprotonqt.config import (
    UIConfig,
    GameConfig,
    CacheConfig,
    GamepadConfig,
    ProxyConfig,
    DisplayConfig,
    MainWindowConfig,
    FavoritesConfig,
    FavoritesFoldersConfig,
    PortProtonConfig,
    CONFIG_FILE,
    THEMES_DIRS,
)

logger = get_logger(__name__)
AUTOSTART_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "ru.linux_gaming.PortProtonQt.desktop"

# Legacy module-level instances for backward compatibility
_ui_config = None
_game_config = None
_cache_config = None
_gamepad_config = None
_proxy_config = None
_display_config = None
_window_config = None
_favorites_config = None
_favorites_folders_config = None
_portproton_config = None
_portproton_start_sh = None


def _get_ui_config() -> UIConfig:
    """Get or create UIConfig instance."""
    global _ui_config
    if _ui_config is None:
        _ui_config = UIConfig()
    return _ui_config


def _get_game_config() -> GameConfig:
    """Get or create GameConfig instance."""
    global _game_config
    if _game_config is None:
        _game_config = GameConfig()
    return _game_config


def _get_cache_config() -> CacheConfig:
    """Get or create CacheConfig instance."""
    global _cache_config
    if _cache_config is None:
        _cache_config = CacheConfig()
    return _cache_config


def _get_gamepad_config() -> GamepadConfig:
    """Get or create GamepadConfig instance."""
    global _gamepad_config
    if _gamepad_config is None:
        _gamepad_config = GamepadConfig()
    return _gamepad_config


def _get_proxy_config() -> ProxyConfig:
    """Get or create ProxyConfig instance."""
    global _proxy_config
    if _proxy_config is None:
        _proxy_config = ProxyConfig()
    return _proxy_config


def _get_display_config() -> DisplayConfig:
    """Get or create DisplayConfig instance."""
    global _display_config
    if _display_config is None:
        _display_config = DisplayConfig()
    return _display_config


def _get_window_config() -> MainWindowConfig:
    """Get or create MainWindowConfig instance."""
    global _window_config
    if _window_config is None:
        _window_config = MainWindowConfig()
    return _window_config


def _get_favorites_config() -> FavoritesConfig:
    """Get or create FavoritesConfig instance."""
    global _favorites_config
    if _favorites_config is None:
        _favorites_config = FavoritesConfig()
    return _favorites_config


def _get_favorites_folders_config() -> FavoritesFoldersConfig:
    """Get or create FavoritesFoldersConfig instance."""
    global _favorites_folders_config
    if _favorites_folders_config is None:
        _favorites_folders_config = FavoritesFoldersConfig()
    return _favorites_folders_config


def _get_portproton_config() -> PortProtonConfig:
    """Get or create PortProtonConfig instance."""
    global _portproton_config
    if _portproton_config is None:
        _portproton_config = PortProtonConfig()
    return _portproton_config


# Legacy functions for theme/appearance settings
def read_theme_from_config() -> str:
    """Reads the theme from the [Appearance] section."""
    return _get_ui_config().get_theme()


def save_theme_to_config(theme_name: str):
    """Saves the selected theme name to the [Appearance] section."""
    _get_ui_config().set_theme(theme_name)


def read_time_config() -> str:
    """Reads time settings from the [Time] section."""
    return _get_ui_config().get_time_detail_level()


def save_time_config(detail_level: str):
    """Saves the time detail level to the [Time] section."""
    _get_ui_config().set_time_detail_level(detail_level)


def read_card_size() -> int:
    """Reads the card size (width) from the [Cards] section."""
    return _get_ui_config().get_card_width()


def save_card_size(card_width: int):
    """Saves the card size (width) to the [Cards] section."""
    _get_ui_config().set_card_width(card_width)


def read_auto_card_size() -> int:
    """Reads the card size (width) for Auto Install."""
    return _get_ui_config().get_auto_card_width()


def save_auto_card_size(card_width: int):
    """Saves the card size (width) for Auto Install."""
    _get_ui_config().set_auto_card_width(card_width)


def read_hide_autoinstall_tab() -> bool:
    """Reads the hide auto-install tab setting."""
    return _get_ui_config().get_hide_autoinstall_tab()


def save_hide_autoinstall_tab(hide_autoinstall_tab: bool):
    """Saves the hide auto-install tab setting."""
    _get_ui_config().set_hide_autoinstall_tab(hide_autoinstall_tab)


def read_badge_view_mode() -> str:
    """Reads badge view mode from the [Appearance] section."""
    mode = _get_ui_config().get_badge_view_mode()
    return mode if mode in ("detailed", "compact", "hidden") else "detailed"


def save_badge_view_mode(mode: str):
    """Saves badge view mode to the [Appearance] section."""
    _get_ui_config().set_badge_view_mode(mode)


def read_economy_mode() -> bool:
    """Reads economy mode from the [Appearance] section."""
    return _get_ui_config().get_economy_mode()


def save_economy_mode(enabled: bool):
    """Saves economy mode to the [Appearance] section."""
    _get_ui_config().set_economy_mode(enabled)


def load_theme_metainfo(theme_name: str) -> dict:
    """Loads theme metadata from metainfo.ini."""
    from portprotonqt.localization import get_theme_translations

    meta = {}
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        metainfo_file = os.path.join(theme_folder, "metainfo.ini")
        if os.path.exists(metainfo_file):
            theme_translations = get_theme_translations(metainfo_file)
            cp = configparser.ConfigParser()
            cp.read(metainfo_file, encoding="utf-8")
            if "Metainfo" in cp:
                meta["author"] = cp.get("Metainfo", "author", fallback="Unknown")
                meta["author_link"] = cp.get("Metainfo", "author_link", fallback="")
                meta["name"] = theme_translations.get("name", theme_name)
                meta["description"] = theme_translations.get("description", "")
            break
    return meta


# Legacy functions for game settings
def read_sort_method() -> str:
    """Reads the sort method from the [Games] section."""
    return _get_game_config().get_sort_method()


def save_sort_method(sort_method: str):
    """Saves the sort method to the [Games] section."""
    _get_game_config().set_sort_method(sort_method)


def read_display_filter() -> str:
    """Reads the display_filter parameter from the [Games] section."""
    return _get_game_config().get_display_filter()


def save_display_filter(filter_value: str):
    """Saves the display_filter parameter to the [Games] section."""
    _get_game_config().set_display_filter(filter_value)


# Legacy functions for favorites
def read_favorites() -> list[str]:
    """Reads the list of favorite games."""
    return _get_favorites_config().get_games()


def save_favorites(favorites: list[str]):
    """Saves the list of favorite games."""
    _get_favorites_config().set_games(favorites)


def read_favorite_folders() -> list[str]:
    """Reads the list of favorite folders."""
    return _get_favorites_folders_config().get_folders()


def save_favorite_folders(folders: list[str]):
    """Saves the list of favorite folders."""
    _get_favorites_folders_config().set_folders(folders)


# Legacy functions for gamepad settings
def read_rumble_config() -> bool:
    """Reads the gamepad rumble setting."""
    return _get_gamepad_config().get_rumble_enabled()


def save_rumble_config(rumble_enabled: bool):
    """Saves the gamepad rumble setting."""
    _get_gamepad_config().set_rumble_enabled(rumble_enabled)


def read_gamepad_type() -> str:
    """Reads the gamepad type."""
    return _get_gamepad_config().get_type()


def save_gamepad_type(gpad_type: str):
    """Saves the gamepad type."""
    _get_gamepad_config().set_type(gpad_type)


# Legacy functions for proxy settings
def read_proxy_config() -> dict[str, str]:
    """Reads proxy settings."""
    return _get_proxy_config().get_proxy()


def save_proxy_config(proxy_url: str = "", proxy_user: str = "", proxy_password: str = ""):
    """Saves proxy settings."""
    _get_proxy_config().set_proxy(proxy_url, proxy_user, proxy_password)


def ensure_default_proxy_config():
    """Ensures the [Proxy] section exists."""
    _get_proxy_config().ensure_section()


# Legacy functions for display settings
def read_fullscreen_config() -> bool:
    """Reads the fullscreen mode setting."""
    return _get_display_config().get_fullscreen()


def save_fullscreen_config(fullscreen: bool):
    """Saves the fullscreen mode setting."""
    _get_display_config().set_fullscreen(fullscreen)


def read_auto_fullscreen_gamepad() -> bool:
    """Reads the auto-fullscreen setting for gamepad."""
    return _get_display_config().get_auto_fullscreen_gamepad()


def save_auto_fullscreen_gamepad(auto_fullscreen: bool):
    """Saves the auto-fullscreen setting for gamepad."""
    _get_display_config().set_auto_fullscreen_gamepad(auto_fullscreen)


def read_minimize_to_tray() -> bool:
    """Reads the minimize-to-tray setting."""
    return _get_display_config().get_minimize_to_tray()


def save_minimize_to_tray(minimize_to_tray: bool):
    """Saves the minimize-to-tray setting."""
    _get_display_config().set_minimize_to_tray(minimize_to_tray)


def read_autostart_enabled() -> bool:
    """Reads the autostart setting."""
    autostart_enabled = _get_display_config().get_autostart_enabled()
    if autostart_enabled and not AUTOSTART_FILE.exists():
        _get_display_config().set_autostart_enabled(False)
        return False
    return autostart_enabled


def save_autostart_enabled(autostart_enabled: bool):
    """Saves the autostart setting."""
    _get_display_config().set_autostart_enabled(autostart_enabled)


def read_start_minimized() -> bool:
    """Reads the start minimized setting."""
    return _get_display_config().get_start_minimized()


def save_start_minimized(start_minimized: bool):
    """Saves the start minimized setting."""
    _get_display_config().set_start_minimized(start_minimized)


def apply_xdg_autostart(enabled: bool) -> bool:
    """Create or remove xdg-autostart desktop entry."""
    try:
        if enabled:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            exec_command = "portprotonqt"
            repo_root = Path(__file__).resolve().parent.parent
            venv_portprotonqt = repo_root / ".venv" / "bin" / "portprotonqt"
            if repo_root.joinpath(".git").exists() and venv_portprotonqt.exists():
                exec_command = f'"{venv_portprotonqt}"'

            desktop_entry = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=PortProtonQt\n"
                f"Exec={exec_command}\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            AUTOSTART_FILE.write_text(desktop_entry, encoding="utf-8")
            logger.info("Enabled xdg-autostart at %s", AUTOSTART_FILE)
            return True

        if AUTOSTART_FILE.exists():
            AUTOSTART_FILE.unlink()
            logger.info("Disabled xdg-autostart at %s", AUTOSTART_FILE)
        return True
    except OSError as e:
        logger.error("Failed to update xdg-autostart: %s", e)
        return False


# Legacy functions for window settings
def read_window_geometry() -> tuple[int, int]:
    """Reads the window width and height."""
    return _get_window_config().get_geometry()


def save_window_geometry(width: int, height: int):
    """Saves the window width and height."""
    _get_window_config().set_geometry(width, height)


# Legacy functions for PortProton location
def get_portproton_location() -> str | None:
    """Return PortProton directory path."""
    return _get_portproton_config().get_location()


def get_portproton_scripts_path() -> str | None:
    """Return PortProton scripts directory path."""
    sharun_prefix = os.getenv("SHARUN_DIR")
    prefixes = [Path("/usr"), Path("/app")]
    if sharun_prefix:
        prefixes.append(Path(sharun_prefix))

    scripts_dirs = (
        Path(__file__).resolve().parent.parent / "build-aux" / "share" / "portproton" / "scripts",
        *[prefix / "share" / "portproton" / "scripts" for prefix in prefixes],
    )
    for scripts_dir in scripts_dirs:
        if scripts_dir.exists():
            return str(scripts_dir)
    return None


def get_portproton_start_command() -> list[str] | None:
    """Return command list for PortProton launch."""
    global _portproton_start_sh

    if _portproton_start_sh is not None:
        return _portproton_start_sh

    # Check if flatpak command exists
    try:
        subprocess.run(
            ["flatpak", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        flatpak_available = True
    except FileNotFoundError:
        flatpak_available = False
    except Exception as e:
        logger.debug("Flatpak version check failed: %s", e)
        flatpak_available = False

    if flatpak_available:
        try:
            result = subprocess.run(
                ["flatpak", "list"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if "ru.linux_gaming.PortProton" in result.stdout:
                logger.info("Detected Flatpak installation")
                _portproton_start_sh = ["flatpak", "run", "ru.linux_gaming.PortProton"]
                return _portproton_start_sh
        except subprocess.TimeoutExpired:
            logger.warning("Flatpak list command timed out")
            return None
        except Exception as e:
            logger.warning("Error checking flatpak list: %s", e)
            pass

    scripts_path = get_portproton_scripts_path()
    if scripts_path:
        _portproton_start_sh = [os.path.join(scripts_path, "start.sh")]
        return _portproton_start_sh

    logger.warning("Neither flatpak nor start.sh found for PortProton")
    return None


# Legacy utility functions
def parse_desktop_entry(file_path: str) -> configparser.SectionProxy | None:
    """Reads and parses a .desktop file using configparser."""
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(file_path, encoding="utf-8")
    if "Desktop Entry" not in cp:
        return None
    return cp["Desktop Entry"]


def find_game_by_exe(exe_path: str) -> configparser.SectionProxy | None:
    """Find a game in the library by its executable path.

    Args:
        exe_path: Full path to the executable file

    Returns:
        Parsed desktop entry if found, None otherwise
    """
    import shlex

    portproton_path = get_portproton_location()
    if not portproton_path:
        return None

    desktop_files = [entry.path for entry in os.scandir(portproton_path)
                     if entry.name.endswith(".desktop")]

    # Normalize the target exe path for comparison
    target_exe = os.path.abspath(exe_path)

    for desktop_path in desktop_files:
        desktop_name = os.path.basename(desktop_path)

        # Skip system desktop files
        if desktop_name.lower() in ["portproton.desktop", "readme.desktop"]:
            continue

        entry = parse_desktop_entry(desktop_path)
        if not entry:
            continue

        exec_line = entry.get("Exec", "")
        if not exec_line:
            continue

        # Parse exec line to extract the game executable
        try:
            parts = shlex.split(exec_line)

            # For PortProton: env "/path/to/start.sh" "/path/to/game.exe"
            # The game exe is typically the 4th element (index 3)
            game_exe = None
            if len(parts) >= 4:
                game_exe = os.path.expanduser(parts[3])
            elif len(parts) >= 2:
                # Try to find .exe in any part
                for part in parts:
                    if part.endswith(".exe"):
                        game_exe = part
                        break

            if not game_exe:
                continue

            # Compare paths (normalize for comparison)
            if os.path.abspath(game_exe) == target_exe:
                return entry
        except (ValueError, IndexError):
            # shlex.split can fail on malformed exec lines
            continue

    return None


def create_desktop_file(exe_path: str, game_name: str | None = None) -> tuple[str, str] | None:
    """Create a .desktop file for a game.

    Args:
        exe_path: Full path to the executable file
        game_name: Optional game name (defaults to exe filename without extension)

    Returns:
        Tuple of (desktop_entry_content, desktop_file_path) if successful, None otherwise
    """
    if not os.path.isfile(exe_path):
        logger.error(f"Executable not found: {exe_path}")
        return None

    if not game_name:
        game_name = os.path.splitext(os.path.basename(exe_path))[0]

    portproton_path = get_portproton_location()
    if not portproton_path:
        logger.error("PortProton location not found")
        return None

    is_flatpak = ".var" in portproton_path
    base_path = os.path.join(portproton_path, "data")
    working_dir = get_portproton_scripts_path()
    if not working_dir:
        logger.error("PortProton scripts path not found")
        return None

    if is_flatpak:
        exec_str = f'flatpak run ru.linux_gaming.PortProton "{exe_path}"'
    else:
        start_sh = os.path.join(working_dir, "start.sh")
        if not os.path.exists(start_sh):
            logger.error("start.sh not found in supported paths")
            return None
        exec_str = f'env "{start_sh}" "{exe_path}"'

    icon_path = os.path.join(base_path, "img", f"{game_name}.png")
    desktop_path = os.path.join(portproton_path, f"{game_name}.desktop")

    os.makedirs(os.path.dirname(icon_path), exist_ok=True)

    comment = _('Launch game "{name}" with PortProton').format(name=game_name)

    desktop_entry = f"""[Desktop Entry]
Name={game_name}
Comment={comment}
Exec={exec_str}
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
Path={working_dir}
Icon={icon_path}
"""

    return desktop_entry, desktop_path


def read_config_safely(config_file: str | Path = CONFIG_FILE) -> configparser.ConfigParser | None:
    """Safely reads a configuration file."""
    from portprotonqt.config.base import _config_cache, _config_mtime

    config_path = str(config_file)
    config_path_obj = Path(config_file)

    if not config_path_obj.exists():
        logger.debug("Configuration file %s not found", config_path)
        return None

    try:
        current_mtime = config_path_obj.stat().st_mtime
    except OSError:
        logger.warning("Failed to get modification time for %s", config_path)
        return None

    if config_path in _config_cache and config_path in _config_mtime:
        if _config_mtime[config_path] == current_mtime:
            logger.debug("Using cached config for %s", config_path)
            return _config_cache[config_path]

    cp = configparser.ConfigParser()
    try:
        cp.read(config_path, encoding="utf-8")
        _config_cache[config_path] = cp
        _config_mtime[config_path] = current_mtime
        logger.debug("Config file %s loaded and cached", config_path)
        return cp
    except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
        logger.warning("Invalid configuration file format: %s", e)
        return None
    except Exception as e:
        logger.warning("Failed to read configuration file: %s", e)
        return None


def clear_cache():
    """Clears the PortProtonQt cache."""
    _get_cache_config().clear_cache()


def reset_config():
    """Resets the configuration file by deleting it."""
    if os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
            logger.info("Configuration file %s deleted", CONFIG_FILE)
            from portprotonqt.config.base import _config_cache, _config_mtime

            config_path = str(CONFIG_FILE)
            if config_path in _config_cache:
                del _config_cache[config_path]
            if config_path in _config_mtime:
                del _config_mtime[config_path]
        except Exception as e:
            logger.warning("Failed to delete configuration file: %s", e)
