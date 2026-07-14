"""Tests for detail page utilities: gradient stops, wave background."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest import MonkeyPatch
from PySide6.QtWidgets import QWidget

import portprotonqt.detail_pages.utils as detail_utils
from portprotonqt.detail_pages import DetailPageManager
from portprotonqt.detail_pages.utils import (
    _build_palette_stops,
    _resolve_gradient_stops,
    _setup_wave_background,
    _remove_wave_background,
    _wave_states,
)


def test_detail_page_exe_fallback_uses_image_cache(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    exe_path = tmp_path / "game.exe"
    exe_path.write_bytes(b"MZ")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    fallback_exe, fallback_path = DetailPageManager._get_exe_icon_fallback({
        "exec_line": str(exe_path),
        "name": "Game",
    })

    assert fallback_exe == str(exe_path)
    assert fallback_path == str(
        tmp_path / "cache" / "PortProtonQt" / "images" / "exe_icons" / "game.exe.png"
    )


def test_detail_page_loads_exe_fallback_without_cover(monkeypatch: MonkeyPatch) -> None:
    detail_page = MagicMock()
    detail_page.property.side_effect = {
        "fallbackExe": "/games/game.exe",
        "fallbackIconPath": "/cache/images/Game.png",
    }.get
    image_label = MagicMock()
    relay = SimpleNamespace(pixmap_ready=MagicMock())
    load_pixmap = MagicMock()
    monkeypatch.setattr(detail_utils, "_PixmapReadyRelay", lambda _parent: relay)
    monkeypatch.setattr(detail_utils, "_prepare_cover_reveal", MagicMock())
    monkeypatch.setattr(detail_utils, "load_pixmap_async", load_pixmap)

    detail_utils.setup_image_loading(
        detail_page,
        image_label,
        None,
        SimpleNamespace(theme=MagicMock()),
    )

    assert load_pixmap.call_args.args[:3] == ("", 300, 450)
    assert load_pixmap.call_args.kwargs == {
        "fallback_exe": "/games/game.exe",
        "fallback_icon_path": "/cache/images/Game.png",
    }


def test_compact_game_detail_loads_exe_icon_before_cover() -> None:
    manager = DetailPageManager.__new__(DetailPageManager)
    manager.main_window = SimpleNamespace(current_exec_line="")
    manager._get_content_frame_layout = MagicMock(return_value=None)
    manager._get_main_layout = MagicMock(return_value=None)
    manager._setup_detail_page_animation = MagicMock()
    detail_page = MagicMock(spec=QWidget)
    detail_page.property.return_value = "/games/game.exe"
    image_label = MagicMock()

    manager._finalize_compact_game_page(detail_page, {
        "exec_line": "/games/game.exe",
        "image_label": image_label,
        "cover_path": "/covers/game.jpg",
    })

    manager._setup_detail_page_animation.assert_called_once_with(
        detail_page,
        image_label,
        detail_page,
        None,
    )


def test_compact_steam_detail_loads_local_cover_without_exe(monkeypatch: MonkeyPatch) -> None:
    manager = DetailPageManager.__new__(DetailPageManager)
    manager.main_window = SimpleNamespace(current_exec_line="")
    manager._get_content_frame_layout = MagicMock(return_value=None)
    manager._get_main_layout = MagicMock(return_value=None)
    manager._setup_detail_page_animation = MagicMock()
    detail_page = MagicMock(spec=QWidget)
    detail_page.property.return_value = ""
    image_label = MagicMock()
    monkeypatch.setattr(
        "portprotonqt.detail_pages.get_local_steam_cover",
        lambda _appid: "/steam/librarycache/242760/library_600x900.jpg",
    )
    page_data = manager._create_compact_game_data(
        (MagicMock(), image_label),
        {
            "name": "The Forest",
            "description": "",
            "exec_line": "steam://rungameid/242760",
            "cover_path": "/covers/the-forest.jpg",
            "game_source": "steam",
            "appid": 242760,
        },
        MagicMock(),
        MagicMock(),
    )

    manager._finalize_compact_game_page(detail_page, page_data)

    manager._setup_detail_page_animation.assert_called_once_with(
        detail_page,
        image_label,
        detail_page,
        "/steam/librarycache/242760/library_600x900.jpg",
    )


def test_hltb_results_ignored_after_detail_page_replaced(monkeypatch):
    manager = DetailPageManager.__new__(DetailPageManager)
    original_page: QWidget = MagicMock(spec=QWidget)
    manager.main_window = MagicMock()
    manager._current_detail_page = original_page
    manager._is_compact_detail_layout = MagicMock(return_value=False)
    manager._on_hltb_results = MagicMock()
    hltb = MagicMock()
    monkeypatch.setattr("portprotonqt.detail_pages.HowLongToBeat", MagicMock(return_value=hltb))

    manager._setup_hltb_data("Game", MagicMock(), MagicMock())
    callback = hltb.searchCompleted.connect.call_args.args[0]
    manager._current_detail_page = MagicMock(spec=QWidget)
    callback([MagicMock()])

    manager._on_hltb_results.assert_not_called()


def _make_palette(colors):
    """Create mock palette with name() returning hex colors."""
    palette = []
    for c in colors:
        m = MagicMock()
        m.name.return_value = c
        palette.append(m)
    return palette


# === _build_palette_stops ===


class TestBuildPaletteStops:
    def test_even_distribution(self):
        palette = _make_palette(["#aaa", "#bbb", "#ccc"])
        result = _build_palette_stops(palette)
        assert "stop:0.00 #aaa" in result
        assert "stop:0.50 #bbb" in result
        assert "stop:1.00 #ccc" in result

    def test_single_color(self):
        palette = _make_palette(["#fff"])
        result = _build_palette_stops(palette)
        assert "stop:0 #fff" in result


# === _resolve_gradient_stops ===


class TestResolveGradientStops:
    def test_none_returns_palette(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = None
        palette = _make_palette(["#111", "#222"])
        result = _resolve_gradient_stops(theme, palette)
        assert "#111" in result
        assert "#222" in result

    def test_missing_attr_returns_palette(self):
        theme = MagicMock(spec=[])
        palette = _make_palette(["#111", "#222"])
        result = _resolve_gradient_stops(theme, palette)
        assert "#111" in result

    def test_string_passthrough(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = "stop:0 #ff0000, stop:1 #00ff00"
        result = _resolve_gradient_stops(theme, [])
        assert result == "stop:0 #ff0000, stop:1 #00ff00"

    def test_positions_only(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = [0, 0.5, 1]
        palette = _make_palette(["#aaa", "#bbb", "#ccc"])
        result = _resolve_gradient_stops(theme, palette)
        assert "stop:0 #aaa" in result
        assert "stop:0.5 #bbb" in result
        assert "stop:1 #ccc" in result

    def test_positions_fewer_than_palette(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = [0, 1]
        palette = _make_palette(["#aaa", "#bbb", "#ccc"])
        result = _resolve_gradient_stops(theme, palette)
        assert "stop:0 #aaa" in result
        assert "stop:1 #bbb" in result

    def test_positions_more_than_palette(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = [0, 0.33, 0.66, 1]
        palette = _make_palette(["#aaa", "#bbb"])
        result = _resolve_gradient_stops(theme, palette)
        assert "stop:0 #aaa" in result
        assert "stop:0.33 #bbb" in result
        assert "stop:0.66 #bbb" in result
        assert "stop:1 #bbb" in result

    def test_dicts_override_colors(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = [
            {"position": 0, "color": "#ff0000"},
            {"position": 1, "color": "#00ff00"},
        ]
        palette = _make_palette(["#aaa", "#bbb"])
        result = _resolve_gradient_stops(theme, palette)
        assert "stop:0 #ff0000" in result
        assert "stop:1 #00ff00" in result
        assert "#aaa" not in result

    def test_tuples_override_colors(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = (
            (0, "#ff0000"),
            (1, "#00ff00"),
        )
        palette = _make_palette(["#aaa", "#bbb"])
        result = _resolve_gradient_stops(theme, palette)
        assert "stop:0 #ff0000" in result
        assert "stop:1 #00ff00" in result

    def test_string_items_in_list(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_GRADIENT = ["stop:0 #ff0000", "stop:1 #00ff00"]
        palette = _make_palette(["#aaa", "#bbb"])
        result = _resolve_gradient_stops(theme, palette)
        assert "stop:0 #ff0000" in result
        assert "stop:1 #00ff00" in result


# === _setup_wave_background ===


class TestSetupWaveBackground:
    def test_gradient_mode_removes_waves(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_BG_MODE = "gradient"
        page = MagicMock()
        page.width.return_value = 800
        page.height.return_value = 600
        _wave_states[page] = {"timer": MagicMock()}
        _setup_wave_background(page, [], theme)
        assert page not in _wave_states

    def test_static_waves_no_timer(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_BG_MODE = "static_waves"
        theme.DETAIL_PAGE_WAVES = {}
        page = MagicMock()
        page.width.return_value = 800
        page.height.return_value = 600
        _setup_wave_background(page, _make_palette(["#111"]), theme)
        state = _wave_states.get(page)
        assert state is not None
        assert state.get("timer") is None

    def test_waves_creates_timer(self, monkeypatch):
        mock_timer = MagicMock()
        mock_qtimer = MagicMock(return_value=mock_timer)
        monkeypatch.setattr(
            "portprotonqt.detail_pages.utils.QTimer", mock_qtimer,
        )
        theme = MagicMock()
        theme.DETAIL_PAGE_BG_MODE = "waves"
        theme.DETAIL_PAGE_WAVES = {"animation_speed": 0.05, "animation_interval_ms": 50}
        page = MagicMock()
        page.width.return_value = 800
        page.height.return_value = 600
        _setup_wave_background(page, _make_palette(["#111"]), theme)
        state = _wave_states.get(page)
        assert state is not None
        assert state.get("timer") is mock_timer
        mock_timer.setInterval.assert_called_once_with(50)
        mock_timer.timeout.connect.assert_called_once()
        mock_timer.start.assert_called_once()

    def test_called_twice_updates_palette(self):
        theme = MagicMock()
        theme.DETAIL_PAGE_BG_MODE = "static_waves"
        theme.DETAIL_PAGE_WAVES = {}
        page = MagicMock()
        page.width.return_value = 800
        page.height.return_value = 600
        palette1 = _make_palette(["#111"])
        palette2 = _make_palette(["#222"])
        _setup_wave_background(page, palette1, theme)
        _setup_wave_background(page, palette2, theme)
        state = _wave_states.get(page)
        assert state is not None
        assert state["palette"] == palette2
        assert state.get("original_paint") is not None


# === _remove_wave_background ===


class TestRemoveWaveBackground:
    def test_no_state(self):
        page = MagicMock()
        _remove_wave_background(page)

    def test_stops_timer(self):
        page = MagicMock()
        timer = MagicMock()
        _wave_states[page] = {
            "timer": timer,
            "original_paint": MagicMock(),
        }
        _remove_wave_background(page)
        timer.stop.assert_called_once()
        timer.deleteLater.assert_called_once()
        assert page not in _wave_states

    def test_restores_paint_event(self):
        page = MagicMock()
        original = MagicMock()
        _wave_states[page] = {"timer": None, "original_paint": original}
        _remove_wave_background(page)
        assert page.paintEvent == original
