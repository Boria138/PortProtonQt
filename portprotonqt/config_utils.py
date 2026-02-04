import os
import configparser
import shutil
import subprocess
from portprotonqt.logger import get_logger
from portprotonqt.localization import get_theme_translations

logger = get_logger(__name__)

_portproton_location = None
_portproton_start_sh = None

# Configuration cache for performance optimization
_config_cache = {}
_config_last_modified = {}

# Paths to configuration files
CONFIG_FILE = os.path.join(
    os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "PortProtonQt.conf"
)

PORTPROTON_CONFIG_FILE = os.path.join(
    os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "PortProton.conf"
)

# Paths to theme directories
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIRS = [
    os.path.join(xdg_data_home, "PortProtonQt", "themes"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
]

def read_config_safely(config_file: str) -> configparser.ConfigParser | None:
    """Safely reads a configuration file and returns a ConfigParser object or None if reading fails.
    Uses caching to avoid repeated file reads for better performance.
    """
    # Check if file exists
    if not os.path.exists(config_file):
        logger.debug(f"Configuration file {config_file} not found")
        return None

    # Get file modification time
    try:
        current_mtime = os.path.getmtime(config_file)
    except OSError:
        logger.warning(f"Failed to get modification time for {config_file}")
        return None

    # Check if we have a cached version that's still valid
    if config_file in _config_cache and config_file in _config_last_modified:
        if _config_last_modified[config_file] == current_mtime:
            logger.debug(f"Using cached config for {config_file}")
            return _config_cache[config_file]

    # Read and parse the config file
    cp = configparser.ConfigParser()
    try:
        cp.read(config_file, encoding="utf-8")
        # Update cache
        _config_cache[config_file] = cp
        _config_last_modified[config_file] = current_mtime
        logger.debug(f"Config file {config_file} loaded and cached")
        return cp
    except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
        logger.warning(f"Invalid configuration file format: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to read configuration file: {e}")
        return None

def invalidate_config_cache(config_file: str = CONFIG_FILE):
    """Invalidates the cached configuration for the specified file."""
    if config_file in _config_cache:
        del _config_cache[config_file]
    if config_file in _config_last_modified:
        del _config_last_modified[config_file]
    logger.debug(f"Config cache invalidated for {config_file}")


def read_theme_from_config():
    """Reads the theme from the [Appearance] section of the configuration file.
    Returns 'standart' if the parameter is not set.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None:
        return "standart"
    return cp.get("Appearance", "theme", fallback="standart")

def save_theme_to_config(theme_name):
    """Saves the selected theme name to the [Appearance] section of the configuration file."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Appearance" not in cp:
        cp["Appearance"] = {}
    cp["Appearance"]["theme"] = theme_name
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_time_config():
    """Reads time settings from the [Time] section of the configuration file.
    If the section or parameter is missing, saves and returns 'detailed' as default.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Time") or not cp.has_option("Time", "detail_level"):
        save_time_config("detailed")
        return "detailed"
    return cp.get("Time", "detail_level", fallback="detailed").lower()

def save_time_config(detail_level):
    """Saves the time detail level to the [Time] section of the configuration file."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Time" not in cp:
        cp["Time"] = {}
    cp["Time"]["detail_level"] = detail_level
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_file_content(file_path):
    """Reads the content of a file and returns it as a string."""
    try:
        # Add timeout protection for file operations using a simple approach
        with open(file_path, encoding="utf-8") as f:
            content = f.read().strip()
            return content
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
        raise  # Re-raise the exception to be handled by the caller

def get_portproton_location():
    """Возвращает путь к PortProton каталогу (строку) или None."""
    global _portproton_location

    if _portproton_location is not None:
        return _portproton_location

    location = None

    if os.path.isfile(PORTPROTON_CONFIG_FILE):
        try:
            location = read_file_content(PORTPROTON_CONFIG_FILE).strip()
            if location and os.path.isdir(location):
                _portproton_location = location
                logger.info(f"PortProton path from configuration: {location}")
                return _portproton_location
            logger.warning(f"Invalid PortProton path in configuration: {location}, using defaults")
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to read PortProton configuration file: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error reading PortProton configuration file: {e}")

    default_flatpak_dir = os.path.join(os.path.expanduser("~"), ".var", "app", "ru.linux_gaming.PortProton")
    if os.path.isdir(default_flatpak_dir):
        _portproton_location = default_flatpak_dir
        logger.info(f"Using Flatpak PortProton directory: {default_flatpak_dir}")
        return _portproton_location

    logger.warning("PortProton configuration and Flatpak directory not found")
    return None

def get_portproton_start_command():
    """Возвращает список команд для запуска PortProton (start.sh или flatpak run)."""

    # Check if flatpak command exists before trying to run it
    try:
        subprocess.run(
            ["flatpak", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5
        )
        flatpak_available = True
    except FileNotFoundError:
        flatpak_available = False
    except Exception:
        flatpak_available = False

    # Приоритет отдается Flatpak-версии, если она доступна
    if flatpak_available:
        try:
            result = subprocess.run(
                ["flatpak", "list"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            if "ru.linux_gaming.PortProton" in result.stdout:
                logger.info("Detected Flatpak installation")
                return ["flatpak", "run", "ru.linux_gaming.PortProton"]
        except subprocess.TimeoutExpired:
            logger.warning("Flatpak list command timed out")
            return None
        except Exception as e:
            logger.warning(f"Error checking flatpak list: {e}")
            pass

    # Если Flatpak недоступен или PortProton не установлен как Flatpak, используем локальную версию
    portproton_path = get_portproton_location()
    if not portproton_path:
        return None

    start_sh_path = os.path.join(portproton_path, "data", "scripts", "start.sh")
    if os.path.exists(start_sh_path):
        return [start_sh_path]

    logger.warning("Neither flatpak nor start.sh found for PortProton")
    return None


def parse_desktop_entry(file_path):
    """Reads and parses a .desktop file using configparser.
    Returns None if the [Desktop Entry] section is missing.
    """
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(file_path, encoding="utf-8")
    if "Desktop Entry" not in cp:
        return None
    return cp["Desktop Entry"]

def load_theme_metainfo(theme_name):
    """Loads theme metadata from metainfo.ini in the theme's root directory.
    Expected fields: author, author_link, description, name.
    """
    meta = {}
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        metainfo_file = os.path.join(theme_folder, "metainfo.ini")
        if os.path.exists(metainfo_file):
            # Load translated theme name and description
            theme_translations = get_theme_translations(metainfo_file)

            cp = configparser.ConfigParser()
            cp.read(metainfo_file, encoding="utf-8")
            if "Metainfo" in cp:
                meta["author"] = cp.get("Metainfo", "author", fallback="Unknown")
                meta["author_link"] = cp.get("Metainfo", "author_link", fallback="")
                # Use translated name and description
                meta["name"] = theme_translations.get("name", theme_name)
                meta["description"] = theme_translations.get("description", "")
            break
    return meta

def read_card_size():
    """Reads the card size (width) from the [Cards] section.
    Returns 250 if the parameter is not set.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Cards") or not cp.has_option("Cards", "card_width"):
        save_card_size(250)
        return 250
    return cp.getint("Cards", "card_width", fallback=250)

def save_card_size(card_width):
    """Saves the card size (width) to the [Cards] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Cards" not in cp:
        cp["Cards"] = {}
    cp["Cards"]["card_width"] = str(card_width)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_auto_card_size():
    """Reads the card size (width) for Auto Install from the [Cards] section.
    Returns 250 if the parameter is not set.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Cards") or not cp.has_option("Cards", "auto_card_width"):
        save_auto_card_size(250)
        return 250
    return cp.getint("Cards", "auto_card_width", fallback=250)

def save_auto_card_size(card_width):
    """Saves the card size (width) for Auto Install to the [Cards] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Cards" not in cp:
        cp["Cards"] = {}
    cp["Cards"]["auto_card_width"] = str(card_width)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()


def read_sort_method():
    """Reads the sort method from the [Games] section.
    Returns 'last_launch' if the parameter is not set.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Games") or not cp.has_option("Games", "sort_method"):
        save_sort_method("last_launch")
        return "last_launch"
    return cp.get("Games", "sort_method", fallback="last_launch").lower()

def save_sort_method(sort_method):
    """Saves the sort method to the [Games] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Games" not in cp:
        cp["Games"] = {}
    cp["Games"]["sort_method"] = sort_method
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_display_filter():
    """Reads the display_filter parameter from the [Games] section.
    Returns 'all' if the parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Games") or not cp.has_option("Games", "display_filter"):
        save_display_filter("all")
        return "all"
    return cp.get("Games", "display_filter", fallback="all").lower()

def save_display_filter(filter_value):
    """Saves the display_filter parameter to the [Games] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Games" not in cp:
        cp["Games"] = {}
    cp["Games"]["display_filter"] = filter_value
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_favorites():
    """Reads the list of favorite games from the [Favorites] section.
    The list is stored as a quoted string with comma-separated names.
    Returns an empty list if the section or parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Favorites") or not cp.has_option("Favorites", "games"):
        return []
    favs = cp.get("Favorites", "games", fallback="").strip()
    if favs.startswith('"') and favs.endswith('"'):
        favs = favs[1:-1]
    return [s.strip() for s in favs.split(",") if s.strip()]

def save_favorites(favorites):
    """Saves the list of favorite games to the [Favorites] section.
    The list is stored as a quoted string with comma-separated names.
    """
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Favorites" not in cp:
        cp["Favorites"] = {}
    fav_str = ", ".join(favorites)
    cp["Favorites"]["games"] = f'"{fav_str}"'
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_rumble_config():
    """Reads the gamepad rumble setting from the [Gamepad] section.
    Returns False if the parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Gamepad") or not cp.has_option("Gamepad", "rumble_enabled"):
        save_rumble_config(False)
        return False
    return cp.getboolean("Gamepad", "rumble_enabled", fallback=False)

def save_rumble_config(rumble_enabled):
    """Saves the gamepad rumble setting to the [Gamepad] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Gamepad" not in cp:
        cp["Gamepad"] = {}
    cp["Gamepad"]["rumble_enabled"] = str(rumble_enabled)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_gamepad_type():
    """Reads the gamepad type from the [Gamepad] section.
    Returns 'xbox' if the parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Gamepad") or not cp.has_option("Gamepad", "type"):
        save_gamepad_type("xbox")
        return "xbox"
    return cp.get("Gamepad", "type", fallback="xbox").lower()

def save_gamepad_type(gpad_type):
    """Saves the gamepad type to the [Gamepad] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Gamepad" not in cp:
        cp["Gamepad"] = {}
    cp["Gamepad"]["type"] = gpad_type
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def ensure_default_proxy_config():
    """Ensures the [Proxy] section exists in the configuration file.
    Creates it with empty values if missing.
    """
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Proxy" not in cp:
        cp.add_section("Proxy")
        cp["Proxy"]["proxy_url"] = ""
        cp["Proxy"]["proxy_user"] = ""
        cp["Proxy"]["proxy_password"] = ""
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            cp.write(configfile)

def read_proxy_config():
    """Reads proxy settings from the [Proxy] section.
    Returns an empty dict if proxy_url is not set or empty.
    """
    ensure_default_proxy_config()
    cp = read_config_safely(CONFIG_FILE)
    if cp is None:
        return {}
    proxy_url = cp.get("Proxy", "proxy_url", fallback="").strip()
    if proxy_url:
        proxy_user = cp.get("Proxy", "proxy_user", fallback="").strip()
        proxy_password = cp.get("Proxy", "proxy_password", fallback="").strip()
        if "://" in proxy_url and "@" not in proxy_url and proxy_user and proxy_password:
            protocol, rest = proxy_url.split("://", 1)
            proxy_url = f"{protocol}://{proxy_user}:{proxy_password}@{rest}"
        return {"http": proxy_url, "https": proxy_url}
    return {}

def save_proxy_config(proxy_url="", proxy_user="", proxy_password=""):
    """Saves proxy settings to the [Proxy] section.
    Creates the section if it does not exist.
    """
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Proxy" not in cp:
        cp["Proxy"] = {}
    cp["Proxy"]["proxy_url"] = proxy_url
    cp["Proxy"]["proxy_user"] = proxy_user
    cp["Proxy"]["proxy_password"] = proxy_password
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_fullscreen_config():
    """Reads the fullscreen mode setting from the [Display] section.
    Returns False if the parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Display") or not cp.has_option("Display", "fullscreen"):
        save_fullscreen_config(False)
        return False
    return cp.getboolean("Display", "fullscreen", fallback=False)

def save_fullscreen_config(fullscreen):
    """Saves the fullscreen mode setting to the [Display] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Display" not in cp:
        cp["Display"] = {}
    cp["Display"]["fullscreen"] = str(fullscreen)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_window_geometry() -> tuple[int, int]:
    """Reads the window width and height from the [MainWindow] section.
    Returns (0, 0) if the parameters are missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("MainWindow"):
        return (0, 0)
    width = cp.getint("MainWindow", "width", fallback=0)
    height = cp.getint("MainWindow", "height", fallback=0)
    return (width, height)

def save_window_geometry(width: int, height: int):
    """Saves the window width and height to the [MainWindow] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "MainWindow" not in cp:
        cp["MainWindow"] = {}
    cp["MainWindow"]["width"] = str(width)
    cp["MainWindow"]["height"] = str(height)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def reset_config():
    """Resets the configuration file by deleting it.
    Subsequent reads will use default values.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
            logger.info("Configuration file %s deleted", CONFIG_FILE)
            # Invalidate cache after deletion
            invalidate_config_cache()
        except Exception as e:
            logger.warning(f"Failed to delete configuration file: {e}")

def clear_cache():
    """Clears the PortProtonQt cache by deleting the cache directory."""
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    cache_dir = os.path.join(xdg_cache_home, "PortProtonQt")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            logger.info("PortProtonQt cache deleted: %s", cache_dir)
        except Exception as e:
            logger.warning(f"Failed to delete cache: {e}")

    # Also clear our internal config cache
    invalidate_config_cache()

def read_auto_fullscreen_gamepad():
    """Reads the auto-fullscreen setting for gamepad from the [Display] section.
    Returns False if the parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Display") or not cp.has_option("Display", "auto_fullscreen_gamepad"):
        save_auto_fullscreen_gamepad(False)
        return False
    return cp.getboolean("Display", "auto_fullscreen_gamepad", fallback=False)

def save_auto_fullscreen_gamepad(auto_fullscreen):
    """Saves the auto-fullscreen setting for gamepad to the [Display] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Display" not in cp:
        cp["Display"] = {}
    cp["Display"]["auto_fullscreen_gamepad"] = str(auto_fullscreen)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_favorite_folders():
    """Reads the list of favorite folders from the [FavoritesFolders] section.
    The list is stored as a quoted string with comma-separated paths.
    Returns an empty list if the section or parameter is missing.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("FavoritesFolders") or not cp.has_option("FavoritesFolders", "folders"):
        return []
    favs = cp.get("FavoritesFolders", "folders", fallback="").strip()
    if favs.startswith('"') and favs.endswith('"'):
        favs = favs[1:-1]
    return [os.path.normpath(s.strip()) for s in favs.split(",") if s.strip() and os.path.isdir(os.path.normpath(s.strip()))]

def save_favorite_folders(folders):
    """Saves the list of favorite folders to the [FavoritesFolders] section.
    The list is stored as a quoted string with comma-separated paths.
    """
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "FavoritesFolders" not in cp:
        cp["FavoritesFolders"] = {}
    fav_str = ", ".join([os.path.normpath(folder) for folder in folders])
    cp["FavoritesFolders"]["folders"] = f'"{fav_str}"'
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_hide_autoinstall_tab():
    """Reads the hide auto-install tab setting from the [Appearance] section.
    Returns False if the parameter is not set.
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Appearance") or not cp.has_option("Appearance", "hide_autoinstall_tab"):
        save_hide_autoinstall_tab(False)
        return False
    return cp.getboolean("Appearance", "hide_autoinstall_tab", fallback=False)

def save_hide_autoinstall_tab(hide_autoinstall_tab):
    """Saves the hide auto-install tab setting to the [Appearance] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Appearance" not in cp:
        cp["Appearance"] = {}
    cp["Appearance"]["hide_autoinstall_tab"] = str(hide_autoinstall_tab)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()

def read_minimize_to_tray():
    """Reads the minimize-to-tray setting from the [Display] section.
    Returns True if the parameter is not set (default: minimize to tray).
    """
    cp = read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("Display") or not cp.has_option("Display", "minimize_to_tray"):
        save_minimize_to_tray(True)
        return True
    return cp.getboolean("Display", "minimize_to_tray", fallback=True)

def save_minimize_to_tray(minimize_to_tray):
    """Saves the minimize-to-tray setting to the [Display] section."""
    cp = read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "Display" not in cp:
        cp["Display"] = {}
    cp["Display"]["minimize_to_tray"] = str(minimize_to_tray)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
    # Invalidate cache after saving
    invalidate_config_cache()
