"""Favorites configuration settings."""
import os
from portprotonqt.config.base import BaseConfig, configparser
from portprotonqt.config.validators import validate_string, validate_path, ValidationError


class FavoritesConfig(BaseConfig):
    """Favorites configuration settings."""

    _section = "Favorites"

    def get_games(self) -> list[str]:
        """Get list of favorite games."""
        cp = self._read_config()
        if cp is None or not cp.has_section(self._section):
            return []

        favs = cp.get(self._section, "games", fallback="").strip()
        if favs.startswith('"') and favs.endswith('"'):
            favs = favs[1:-1]
        return [s.strip() for s in favs.split(",") if s.strip()]

    def set_games(self, games: list[str]):
        """Set list of favorite games."""
        if not isinstance(games, list):
            raise ValidationError("games must be a list", "games", games)
        for game in games:
            validate_string(game, "game", min_len=1, max_len=255)

        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp[self._section] = {}
        fav_str = ", ".join(games)
        cp[self._section]["games"] = f'"{fav_str}"'
        self._save_config(cp)


class FavoritesFoldersConfig(BaseConfig):
    """Favorite folders configuration settings."""

    _section = "FavoritesFolders"

    def get_folders(self) -> list[str]:
        """Get list of favorite folders."""
        cp = self._read_config()
        if cp is None or not cp.has_section(self._section):
            return []

        favs = cp.get(self._section, "folders", fallback="").strip()
        if favs.startswith('"') and favs.endswith('"'):
            favs = favs[1:-1]
        return [
            os.path.normpath(s.strip())
            for s in favs.split(",")
            if s.strip() and os.path.isdir(os.path.normpath(s.strip()))
        ]

    def set_folders(self, folders: list[str]):
        """Set list of favorite folders."""
        if not isinstance(folders, list):
            raise ValidationError("folders must be a list", "folders", folders)
        for folder in folders:
            validate_path(folder, "folder", must_exist=True)

        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp[self._section] = {}
        fav_str = ", ".join([os.path.normpath(f) for f in folders])
        cp[self._section]["folders"] = f'"{fav_str}"'
        self._save_config(cp)


class ExeSettingsFavoritesConfig(BaseConfig):
    """Favorite executable settings configuration."""

    _section = "ExeSettingsFavorites"

    def get_keys(self) -> list[str]:
        """Get list of favorite executable setting keys."""
        cp = self._read_config()
        if cp is None or not cp.has_section(self._section):
            return []

        keys = cp.get(self._section, "keys", fallback="").strip()
        if keys.startswith('"') and keys.endswith('"'):
            keys = keys[1:-1]
        return [key.strip() for key in keys.split(",") if key.strip()]

    def set_keys(self, keys: list[str]) -> None:
        """Set list of favorite executable setting keys."""
        if not isinstance(keys, list):
            raise ValidationError("keys must be a list", "keys", keys)
        for key in keys:
            validate_string(key, "key", min_len=1, max_len=255)

        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp[self._section] = {}
        fav_str = ", ".join(keys)
        cp[self._section]["keys"] = f'"{fav_str}"'
        self._save_config(cp)
