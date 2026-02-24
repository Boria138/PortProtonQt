"""UI configuration settings."""
from portprotonqt.config.base import BaseConfig, configparser
from portprotonqt.config.validators import validate_string, validate_int, validate_bool


class UIConfig(BaseConfig):
    """UI configuration settings."""

    _section = "Appearance"

    def get_theme(self) -> str:
        """Get the current theme name."""
        return self._get_str("theme", "standart")

    def set_theme(self, theme_name: str):
        """Set the theme name."""
        validate_string(theme_name, "theme", min_len=1, max_len=50)
        self._save_value("theme", theme_name, "str")

    def get_time_detail_level(self) -> str:
        """Get time detail level ('detailed' or 'simple')."""
        cp = self._read_config()
        if cp is None or not cp.has_section("Time"):
            return self._save_time_detail("detailed")
        return cp.get("Time", "detail_level", fallback="detailed").lower()

    def _save_time_detail(self, detail_level: str) -> str:
        """Save time detail level."""
        validate_string(detail_level, "detail_level", min_len=1, max_len=20)
        cp = self._read_config() or configparser.ConfigParser()
        if "Time" not in cp:
            cp["Time"] = {}
        cp["Time"]["detail_level"] = detail_level
        self._save_config(cp)
        return detail_level

    def set_time_detail_level(self, detail_level: str):
        """Set time detail level."""
        self._save_time_detail(detail_level)

    def get_card_width(self) -> int:
        """Get card width for game cards."""
        return self._get_int("card_width", 250)

    def set_card_width(self, width: int):
        """Set card width."""
        validate_int(width, "card_width", min_val=100, max_val=1000)
        self._save_value("card_width", width, "int")

    def get_auto_card_width(self) -> int:
        """Get card width for auto-install."""
        return self._get_int("auto_card_width", 250)

    def set_auto_card_width(self, width: int):
        """Set card width for auto-install."""
        validate_int(width, "auto_card_width", min_val=100, max_val=1000)
        self._save_value("auto_card_width", width, "int")

    def get_hide_autoinstall_tab(self) -> bool:
        """Get hide auto-install tab setting."""
        return self._get_bool("hide_autoinstall_tab", False)

    def set_hide_autoinstall_tab(self, hide: bool):
        """Set hide auto-install tab setting."""
        validate_bool(hide, "hide_autoinstall_tab")
        self._save_value("hide_autoinstall_tab", hide, "bool")
