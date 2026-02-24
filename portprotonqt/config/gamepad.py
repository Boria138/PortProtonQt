"""Gamepad configuration settings."""
from portprotonqt.config.base import BaseConfig
from portprotonqt.config.validators import validate_bool, validate_string


class GamepadConfig(BaseConfig):
    """Gamepad configuration settings."""

    _section = "Gamepad"

    def get_rumble_enabled(self) -> bool:
        """Get gamepad rumble setting."""
        return self._get_bool("rumble_enabled", False)

    def set_rumble_enabled(self, enabled: bool):
        """Set gamepad rumble setting."""
        validate_bool(enabled, "rumble_enabled")
        self._save_value("rumble_enabled", enabled, "bool")

    def get_type(self) -> str:
        """Get gamepad type."""
        return self._get_str("type", "xbox")

    def set_type(self, gpad_type: str):
        """Set gamepad type."""
        validate_string(gpad_type, "type", min_len=1, max_len=20)
        self._save_value("type", gpad_type, "str")
