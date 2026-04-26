"""Configuration API for PortProtonQt."""
from portprotonqt.config.base import (
    BaseConfig,
    CACHE_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    PORTPROTON_CONFIG_FILE,
    THEMES_DIRS,
    reset_main_config,
)
from portprotonqt.config.cache import CacheConfig, CacheManager
from portprotonqt.config.display import DisplayConfig, apply_xdg_autostart
from portprotonqt.config.favorites import FavoritesConfig, FavoritesFoldersConfig
from portprotonqt.config.game import GameConfig
from portprotonqt.config.gamepad import GamepadConfig
from portprotonqt.config.portproton import (
    PortProtonConfig,
    create_desktop_file,
    find_game_by_exe,
    get_portproton_location,
    get_portproton_scripts_path,
    get_portproton_start_command,
    parse_desktop_entry,
    read_portdata_path_from_config,
    save_portdata_path_to_config,
)
from portprotonqt.config.proxy import ProxyConfig
from portprotonqt.config.ui import UIConfig, load_theme_metainfo
from portprotonqt.config.validators import ValidationError
from portprotonqt.config.window import MainWindowConfig

ui_config = UIConfig()
game_config = GameConfig()
cache_config = CacheConfig()
gamepad_config = GamepadConfig()
proxy_config = ProxyConfig()
display_config = DisplayConfig()
window_config = MainWindowConfig()
favorites_config = FavoritesConfig()
favorites_folders_config = FavoritesFoldersConfig()
portproton_config = PortProtonConfig()

__all__ = [
    "BaseConfig",
    "UIConfig",
    "GameConfig",
    "CacheConfig",
    "CacheManager",
    "GamepadConfig",
    "ProxyConfig",
    "DisplayConfig",
    "MainWindowConfig",
    "FavoritesConfig",
    "FavoritesFoldersConfig",
    "PortProtonConfig",
    "CONFIG_FILE",
    "PORTPROTON_CONFIG_FILE",
    "CONFIG_DIR",
    "THEMES_DIRS",
    "CACHE_DIR",
    "ValidationError",
    "ui_config",
    "game_config",
    "cache_config",
    "gamepad_config",
    "proxy_config",
    "display_config",
    "window_config",
    "favorites_config",
    "favorites_folders_config",
    "portproton_config",
    "load_theme_metainfo",
    "apply_xdg_autostart",
    "read_portdata_path_from_config",
    "save_portdata_path_to_config",
    "get_portproton_scripts_path",
    "get_portproton_start_command",
    "get_portproton_location",
    "parse_desktop_entry",
    "find_game_by_exe",
    "create_desktop_file",
    "reset_main_config",
]
