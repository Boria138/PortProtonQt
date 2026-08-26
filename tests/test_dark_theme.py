"""Tests for config/ui.py — dark theme detection logic."""
from unittest.mock import patch, MagicMock

from portprotonqt.config.ui import (
    UIConfig,
    _is_gsettings_dark_theme,
    THEME_VARIANTS,
)
from portprotonqt.theme_manager import SystemThemeWatcher


class TestIsGsettingsDarkTheme:
    def test_xfce_dark_theme(self):
        env = {"XDG_SESSION_DESKTOP": "Xubuntu"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'Xfce-dark'\n")
            assert _is_gsettings_dark_theme() is True

    def test_xfce_light_theme(self):
        env = {"XDG_SESSION_DESKTOP": "Xubuntu"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'Xfce'\n")
            assert _is_gsettings_dark_theme() is False

    def test_mate_dark_theme(self):
        env = {"XDG_SESSION_DESKTOP": "MATE"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'Yaru-dark'\n")
            assert _is_gsettings_dark_theme() is True

    def test_mate_light_theme(self):
        env = {"XDG_SESSION_DESKTOP": "MATE"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'Yaru'\n")
            assert _is_gsettings_dark_theme() is False

    def test_cinnamon_dark_via_color_scheme(self):
        env = {"XDG_SESSION_DESKTOP": "Cinnamon"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'prefer-dark'\n")
            assert _is_gsettings_dark_theme() is True

    def test_cinnamon_light_via_color_scheme(self):
        env = {"XDG_SESSION_DESKTOP": "Cinnamon"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'prefer-light'\n")
            assert _is_gsettings_dark_theme() is False

    def test_cinnamon_fallback_to_gtk_theme(self):
        env = {"XDG_SESSION_DESKTOP": "Cinnamon"}
        call_count = 0

        def mock_subprocess_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(returncode=1, stdout="")
            return MagicMock(returncode=0, stdout="'Mint-Y-Dark'\n")

        with (
            patch.dict("os.environ", env),
            patch("subprocess.run", side_effect=mock_subprocess_run),
        ):
            assert _is_gsettings_dark_theme() is True

    def test_gnome_dark_via_color_scheme(self):
        env = {"XDG_SESSION_DESKTOP": "gnome"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'prefer-dark'\n")
            assert _is_gsettings_dark_theme() is True

    def test_gnome_light_via_color_scheme(self):
        env = {"XDG_SESSION_DESKTOP": "gnome"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'default'\n")
            assert _is_gsettings_dark_theme() is False

    def test_gnome_fallback_to_gtk_theme(self):
        env = {"XDG_SESSION_DESKTOP": "gnome"}
        call_count = 0

        def mock_subprocess_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(returncode=1, stdout="")
            return MagicMock(returncode=0, stdout="'Adwaita-dark'\n")

        with (
            patch.dict("os.environ", env),
            patch("subprocess.run", side_effect=mock_subprocess_run),
        ):
            assert _is_gsettings_dark_theme() is True

    def test_unknown_de_falls_through_to_gnome(self):
        env = {"XDG_SESSION_DESKTOP": "unknown_de"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'prefer-dark'\n")
            assert _is_gsettings_dark_theme() is True

    def test_subprocess_error_returns_none(self):
        env = {"XDG_SESSION_DESKTOP": "XFCE"}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run", side_effect=OSError("fail")),
        ):
            assert _is_gsettings_dark_theme() is None

    def test_empty_session_desktop_falls_through_to_gnome(self):
        env = {"XDG_SESSION_DESKTOP": ""}
        with (
            patch.dict("os.environ", env),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'prefer-dark'\n")
            assert _is_gsettings_dark_theme() is True

    def test_xdg_session_desktop_missing_falls_through_to_gnome(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'prefer-dark'\n")
            assert _is_gsettings_dark_theme() is True


class TestThemeVariants:
    def test_theme_variants_values(self):
        assert set(THEME_VARIANTS) == {"dark", "light", "auto"}

    def test_get_theme_caches_resolved_theme(self, tmp_path):
        config = UIConfig(tmp_path / "PortProtonQt.conf")
        config.set_theme("classic")
        config.set_theme_variant("auto")

        with patch("portprotonqt.config.ui._resolve_theme_name", return_value="classic") as resolve:
            assert config.get_theme() == "classic"
            assert config.get_theme() == "classic"

        assert resolve.call_count == 1

    def test_set_theme_variant_clears_resolved_theme_cache(self, tmp_path):
        config = UIConfig(tmp_path / "PortProtonQt.conf")
        config.set_theme("classic")
        config.set_theme_variant("auto")

        with patch("portprotonqt.config.ui._resolve_theme_name", return_value="classic") as resolve:
            assert config.get_theme() == "classic"
            config.set_theme_variant("dark")
            assert config.get_theme() == "classic"

        assert resolve.call_count == 2


def test_system_theme_watcher_emits_change(monkeypatch):
    watcher = SystemThemeWatcher(initial_light=False)
    detected = []
    watcher.theme_changed.connect(detected.append)
    interruptions = iter((False, True))
    monkeypatch.setattr(watcher, "isInterruptionRequested", lambda: next(interruptions))
    monkeypatch.setattr(watcher, "msleep", lambda _milliseconds: None)
    monkeypatch.setattr("portprotonqt.theme_manager._is_system_light_theme", lambda: True)

    watcher._poll_system_theme()

    assert detected == [True]


def test_system_theme_watcher_emits_portal_change() -> None:
    watcher = SystemThemeWatcher(initial_light=False)
    detected = []
    watcher.theme_changed.connect(detected.append)

    watcher._on_portal_setting_changed(
        "org.freedesktop.appearance",
        "color-scheme",
        2,
    )

    assert detected == [True]
