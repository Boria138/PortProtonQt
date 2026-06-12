"""Gamepad configuration settings."""
from portprotonqt.config.base import BaseConfig


class GamepadConfig(BaseConfig):
    """Gamepad configuration settings."""

    _section = "Gamepad"

    def get_gamepad_type(self) -> str:
        """Get configured gamepad type."""
        value = self._get_str("type", "auto").lower()
        if value in ("auto", "xbox", "playstation"):
            return value
        if value in ("ps", "sony"):
            return "playstation"
        return "auto"

    def set_gamepad_type(self, gamepad_type: str) -> None:
        """Set configured gamepad type."""
        value = gamepad_type.lower()
        if value not in ("auto", "xbox", "playstation"):
            value = "auto"
        self._save_value("type", value, "str")
