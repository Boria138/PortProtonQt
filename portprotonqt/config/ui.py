"""UI configuration settings."""
import os
from portprotonqt.config.base import BaseConfig, configparser, THEMES_DIRS
from portprotonqt.config.validators import validate_string, validate_int, validate_bool
from portprotonqt.localization import get_theme_translations


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

    def get_badge_view_mode(self) -> str:
        """Get badge view mode ('detailed' or 'compact')."""
        mode = self._get_str("badge_view_mode", "detailed")
        return mode if mode in ("detailed", "compact", "hidden") else "detailed"

    def set_badge_view_mode(self, mode: str):
        """Set badge view mode."""
        validate_string(mode, "badge_view_mode", min_len=1, max_len=20)
        self._save_value("badge_view_mode", mode, "str")

    def get_economy_mode(self) -> bool:
        """Get economy mode setting."""
        return self._get_bool("economy_mode", False)

    def set_economy_mode(self, enabled: bool):
        """Set economy mode setting."""
        validate_bool(enabled, "economy_mode")
        self._save_value("economy_mode", enabled, "bool")


def load_theme_metainfo(theme_name: str) -> dict:
    """Load theme metadata from metainfo.ini."""
    meta: dict[str, str] = {}
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        metainfo_file = os.path.join(theme_folder, "metainfo.ini")
        if os.path.exists(metainfo_file):
            theme_translations = get_theme_translations(metainfo_file)
            cp = configparser.ConfigParser()
            cp.read(metainfo_file, encoding="utf-8")
            if "Metainfo" in cp:
                meta["author"] = cp.get("Metainfo", "author", fallback="Unknown")
                meta["author_link"] = cp.get("Metainfo", "author_link", fallback="")
                meta["name"] = theme_translations.get("name", theme_name)
                meta["description"] = theme_translations.get("description", "")
            break
    return meta
