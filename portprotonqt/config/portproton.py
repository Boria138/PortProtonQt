"""PortProton location configuration."""
import os
from pathlib import Path
from portprotonqt.config.base import BaseConfig, PORTPROTON_CONFIG_FILE
from portprotonqt.config.validators import validate_path
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


class PortProtonConfig(BaseConfig):
    """PortProton location configuration."""

    _section = "PortProton"
    _portproton_location: str | None = None

    def __init__(self):
        super().__init__()
        self._config_file = PORTPROTON_CONFIG_FILE

    def get_location(self) -> str | None:
        """Get PortProton directory location."""
        if self._portproton_location is not None:
            return self._portproton_location

        location = None

        if self._config_file.exists():
            try:
                location = self._config_file.read_text(encoding="utf-8").strip()
                if location and os.path.isdir(location):
                    self._portproton_location = location
                    logger.info("PortProton path from configuration: %s", location)
                    return self._portproton_location
                logger.warning("Invalid PortProton path in configuration: %s", location)
            except (OSError, PermissionError) as e:
                logger.warning("Failed to read PortProton configuration file: %s", e)
            except Exception as e:
                logger.warning("Unexpected error reading PortProton configuration file: %s", e)

        default_flatpak_dir = Path.home() / ".var" / "app" / "ru.linux_gaming.PortProton"
        if default_flatpak_dir.is_dir():
            self._portproton_location = str(default_flatpak_dir)
            logger.info("Using Flatpak PortProton directory: %s", default_flatpak_dir)
            return self._portproton_location

        logger.warning("PortProton configuration and Flatpak directory not found")
        return None

    def set_location(self, location: str):
        """Set PortProton directory location."""
        validate_path(location, "portproton_location", must_exist=True)
        self._config_file.write_text(location, encoding="utf-8")
        self._portproton_location = location
        logger.info("PortProton location set to: %s", location)
