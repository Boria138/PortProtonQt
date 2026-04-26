"""Base configuration class for PortProtonQt."""
import os
import configparser
from pathlib import Path
from portprotonqt.logger import get_logger
from portprotonqt.config.validators import validate_string, validate_int, validate_bool, ValidationError

logger = get_logger(__name__)

# Export configparser for use in other modules
__all__ = ["configparser"]

# Configuration file paths
CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_FILE = CONFIG_DIR / "PortProtonQt.conf"
PORTPROTON_CONFIG_FILE = CONFIG_DIR / "PortProton.conf"

# Theme directories
XDG_DATA_HOME = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
THEMES_DIRS = [
    XDG_DATA_HOME / "PortProtonQt" / "themes",
    Path(__file__).parent.parent / "themes",
]

# Cache paths
CACHE_DIR = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "PortProtonQt"

# Module-level cache storage
_config_cache: dict[str, configparser.ConfigParser] = {}
_config_mtime: dict[str, float] = {}


def reset_main_config() -> None:
    """Delete main config file and invalidate cache."""
    if not CONFIG_FILE.exists():
        return
    try:
        CONFIG_FILE.unlink()
        logger.info("Configuration file %s deleted", CONFIG_FILE)
    except OSError as error:
        logger.warning("Failed to delete configuration file: %s", error)
        return

    config_path = str(CONFIG_FILE)
    _config_cache.pop(config_path, None)
    _config_mtime.pop(config_path, None)


class BaseConfig:
    """Base configuration class providing common functionality."""

    _section: str = ""

    def __init__(self, config_file: Path = CONFIG_FILE):
        self._config_file = config_file

    def _read_config(self) -> configparser.ConfigParser | None:
        """Read configuration file with caching."""
        config_path = str(self._config_file)

        if not self._config_file.exists():
            logger.debug("Configuration file %s not found", config_path)
            return None

        try:
            current_mtime = self._config_file.stat().st_mtime
        except OSError:
            logger.warning("Failed to get modification time for %s", config_path)
            return None

        if config_path in _config_cache and config_path in _config_mtime:
            if _config_mtime[config_path] == current_mtime:
                return _config_cache[config_path]

        cp = configparser.ConfigParser()
        try:
            cp.read(config_path, encoding="utf-8")
            _config_cache[config_path] = cp
            _config_mtime[config_path] = current_mtime
            return cp
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.warning("Invalid configuration file format: %s", e)
            return None
        except Exception as e:
            logger.warning("Failed to read configuration file: %s", e)
            return None

    def _save_config(self, cp: configparser.ConfigParser):
        """Save configuration to file."""
        with open(self._config_file, "w", encoding="utf-8") as f:
            cp.write(f)
        self._invalidate_cache()

    def _invalidate_cache(self):
        """Invalidate configuration cache."""
        config_path = str(self._config_file)
        if config_path in _config_cache:
            del _config_cache[config_path]
        if config_path in _config_mtime:
            del _config_mtime[config_path]

    def _get_value(self, option: str, default, value_type: str = "str"):
        """Get a configuration value with type conversion."""
        cp = self._read_config()
        if cp is None or not cp.has_section(self._section):
            return self._save_value(option, default, value_type)

        try:
            if value_type == "int":
                return cp.getint(self._section, option, fallback=default)
            elif value_type == "bool":
                return cp.getboolean(self._section, option, fallback=default)
            else:
                return cp.get(self._section, option, fallback=default)
        except (ValueError, configparser.Error) as e:
            logger.warning("Error reading %s: %s", option, e)
            return self._save_value(option, default, value_type)

    def _get_str(self, option: str, default: str) -> str:
        """Get a string configuration value."""
        return str(self._get_value(option, default, "str"))

    def _get_int(self, option: str, default: int) -> int:
        """Get an integer configuration value."""
        return int(self._get_value(option, default, "int"))

    def _get_bool(self, option: str, default: bool) -> bool:
        """Get a boolean configuration value."""
        return bool(self._get_value(option, default, "bool"))

    def _save_value(self, option: str, value, value_type: str = "str"):
        """Save a configuration value with validation."""
        try:
            if value_type == "int":
                validate_int(value, option)
            elif value_type == "bool":
                validate_bool(value, option)
            else:
                validate_string(value, option)
        except ValidationError as e:
            logger.warning("Validation failed for %s: %s", option, e)
            raise

        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp[self._section] = {}

        cp[self._section][option] = str(value)
        self._save_config(cp)
        return value
