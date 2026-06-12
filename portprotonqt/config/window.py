"""Main window configuration settings."""
from portprotonqt.config.base import BaseConfig, configparser
from portprotonqt.config.validators import validate_int


class MainWindowConfig(BaseConfig):
    """Main window configuration settings."""

    _section = "MainWindow"

    def get_geometry(self) -> tuple[int, int]:
        """Get window width and height."""
        cp = self._read_config()
        if cp is None or not cp.has_section(self._section):
            return (0, 0)
        width = cp.getint(self._section, "width", fallback=0)
        height = cp.getint(self._section, "height", fallback=0)
        return (width, height)

    def set_geometry(self, width: int, height: int):
        """Set window width and height."""
        validate_int(width, "width", min_val=0, max_val=7680)
        validate_int(height, "height", min_val=0, max_val=4320)

        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp[self._section] = {}
        cp[self._section]["width"] = str(width)
        cp[self._section]["height"] = str(height)
        self._save_config(cp)
