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

    def get_steam_account_id(self) -> str:
        """Get selected Steam account ID or automatic selection."""
        return self._get_str("steam_account_id", "auto")

    def set_steam_account_id(self, account_id: str) -> None:
        """Set selected Steam account ID or automatic selection."""
        validate_string(account_id, "steam_account_id", min_len=1, max_len=20)
        self._save_value("steam_account_id", account_id, "str")
