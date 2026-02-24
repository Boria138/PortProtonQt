"""Display configuration settings."""
from portprotonqt.config.base import BaseConfig
from portprotonqt.config.validators import validate_bool


class DisplayConfig(BaseConfig):
    """Display configuration settings."""

    _section = "Display"

    def get_fullscreen(self) -> bool:
        """Get fullscreen mode setting."""
        return self._get_bool("fullscreen", False)

    def set_fullscreen(self, fullscreen: bool):
        """Set fullscreen mode."""
        validate_bool(fullscreen, "fullscreen")
        self._save_value("fullscreen", fullscreen, "bool")

    def get_auto_fullscreen_gamepad(self) -> bool:
        """Get auto-fullscreen for gamepad setting."""
        return self._get_bool("auto_fullscreen_gamepad", False)

    def set_auto_fullscreen_gamepad(self, auto: bool):
        """Set auto-fullscreen for gamepad."""
        validate_bool(auto, "auto_fullscreen_gamepad")
        self._save_value("auto_fullscreen_gamepad", auto, "bool")

    def get_minimize_to_tray(self) -> bool:
        """Get minimize-to-tray setting."""
        return self._get_bool("minimize_to_tray", True)

    def set_minimize_to_tray(self, minimize: bool):
        """Set minimize-to-tray setting."""
        validate_bool(minimize, "minimize_to_tray")
        self._save_value("minimize_to_tray", minimize, "bool")
