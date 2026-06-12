"""Game-related configuration settings."""
from portprotonqt.config.base import BaseConfig
from portprotonqt.config.validators import validate_string


class GameConfig(BaseConfig):
    """Game-related configuration settings."""

    _section = "Games"

    def get_sort_method(self) -> str:
        """Get game sort method."""
        return self._get_str("sort_method", "last_launch")

    def set_sort_method(self, method: str):
        """Set game sort method."""
        validate_string(method, "sort_method", min_len=1, max_len=50)
        self._save_value("sort_method", method, "str")

    def get_display_filter(self) -> str:
        """Get game display filter."""
        return self._get_str("display_filter", "all")

    def set_display_filter(self, filter_value: str):
        """Set game display filter."""
        validate_string(filter_value, "display_filter", min_len=1, max_len=50)
        self._save_value("display_filter", filter_value, "str")
