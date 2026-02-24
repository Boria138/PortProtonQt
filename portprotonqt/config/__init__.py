"""Configuration hierarchy for PortProtonQt."""
from portprotonqt.config.base import (
    BaseConfig,
    CONFIG_FILE,
    PORTPROTON_CONFIG_FILE,
    CONFIG_DIR,
    THEMES_DIRS,
    CACHE_DIR,
)
from portprotonqt.config.ui import UIConfig
from portprotonqt.config.game import GameConfig
from portprotonqt.config.cache import CacheConfig
from portprotonqt.config.gamepad import GamepadConfig
from portprotonqt.config.proxy import ProxyConfig
from portprotonqt.config.display import DisplayConfig
from portprotonqt.config.window import MainWindowConfig
from portprotonqt.config.favorites import FavoritesConfig, FavoritesFoldersConfig
from portprotonqt.config.portproton import PortProtonConfig
from portprotonqt.config.validators import ValidationError

__all__ = [
    "BaseConfig",
    "UIConfig",
    "GameConfig",
    "CacheConfig",
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
]
