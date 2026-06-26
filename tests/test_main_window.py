"""Tests for main window library data processing."""

from pathlib import Path
from typing import Any

from portprotonqt.main_window import MainWindow
from portprotonqt.tabs import (
    MainWindowAutoInstallTabMixin,
    MainWindowLibraryTabMixin,
    MainWindowSettingsTabMixin,
    MainWindowThemeTabMixin,
    MainWindowWineTabMixin,
)
from portprotonqt.tabs.autoinstall_tab import MainWindowAutoInstallTabMixin as AutoInstallMixin
from portprotonqt.tabs.library_tab import MainWindowLibraryTabMixin as LibraryMixin
from portprotonqt.tabs.settings_tab import MainWindowSettingsTabMixin as SettingsMixin
from portprotonqt.tabs.theme_tab import (
    THEME_STORE_ITEM,
    MainWindowThemeTabMixin as ThemeMixin,
)
from portprotonqt.tabs.wine_tab import MainWindowWineTabMixin as WineMixin


TAB_METHODS = {
    AutoInstallMixin: (
        "createAutoInstallTab",
        "_open_autoinstall_card_after_script_download",
        "_setup_autoinstall_search_animation",
        "_wrap_autoinstall_search_focus_event",
        "_wrap_autoinstall_search_resize_event",
        "_center_collapsed_autoinstall_search_icon",
        "_start_autoinstall_load",
        "_refresh_autoinstall_games",
        "on_auto_slider_released",
        "filterAutoInstallGames",
    ),
    LibraryMixin: (
        "_load_empty_library_on_tab_enter",
        "_set_combo_current_key",
        "_create_library_combo",
        "_on_library_sort_changed",
        "_on_library_filter_changed",
        "_on_library_badge_view_changed",
        "_toggle_library_controls",
        "_create_library_controls_widget",
        "_add_library_action_buttons",
        "_add_library_search",
        "_add_library_refresh_button",
        "_add_library_controls_button",
        "_setup_library_search_animation",
        "_wrap_search_focus_event",
        "_wrap_search_resize_event",
        "_center_collapsed_search_icon",
        "_add_library_filter_controls",
        "_delay_library_controls_hover_close",
        "_allow_library_controls_hover_close",
        "createSearchWidget",
        "refreshGames",
        "quickLaunch",
        "on_search_text_changed",
        "on_search_changed",
        "startSearchDebounce",
        "createInstalledTab",
        "resizeEvent",
        "dragEnterEvent",
        "dropEvent",
        "openAddGameDialog",
        "_sync_game_shortcuts_from_dialog",
    ),
    WineMixin: (
        "createWineTab",
        "save_wine_defaults",
        "launch_generic_tool",
        "_start_wine_process_monitor",
        "_check_wine_process",
        "_on_wine_tool_finished",
        "_on_wine_tool_error",
        "show_proton_manager",
        "clear_prefix",
        "_on_clear_prefix_finished",
        "_on_clear_prefix_error",
        "create_prefix_backup",
        "_perform_backup",
        "load_prefix_backup",
        "_perform_restore",
        "_perform_legacy_restore",
        "_on_backup_finished",
        "_on_restore_finished",
        "delete_prefix",
        "refresh_wine_combo",
        "refresh_prefix_combo",
        "_normalize_prefix_directories",
        "open_winetricks",
    ),
    SettingsMixin: (
        "createPortProtonTab",
        "resetSettings",
        "migrateLegacyShortcuts",
        "clearCache",
        "applySettingsDelayed",
        "_format_game_tuple_playtime",
        "_refresh_loaded_playtime_format",
        "_refresh_current_detail_time",
        "savePortProtonSettings",
        "_apply_gamepad_type_setting",
    ),
    ThemeMixin: (
        "createThemeTab",
        "_refresh_theme_store_visibility",
        "restart_application",
        "restore_state",
    ),
}


def test_main_window_inherits_all_tab_mixins() -> None:
    expected_mixins = (
        MainWindowAutoInstallTabMixin,
        MainWindowLibraryTabMixin,
        MainWindowSettingsTabMixin,
        MainWindowThemeTabMixin,
        MainWindowWineTabMixin,
    )

    for mixin in expected_mixins:
        assert issubclass(MainWindow, mixin)


def test_tab_methods_resolve_from_expected_modules() -> None:
    for mixin, method_names in TAB_METHODS.items():
        for method_name in method_names:
            assert getattr(MainWindow, method_name) is getattr(mixin, method_name)
            assert method_name not in MainWindow.__dict__


def test_tabs_package_exports_tab_mixins() -> None:
    import portprotonqt.tabs as tabs

    for mixin in TAB_METHODS:
        assert getattr(tabs, mixin.__name__) is mixin


def test_meson_installs_tab_modules() -> None:
    meson_build = Path("portprotonqt/meson.build").read_text(encoding="utf-8")
    expected_files = (
        "tabs/autoinstall_tab.py",
        "tabs/library_tab.py",
        "tabs/settings_tab.py",
        "tabs/theme_tab.py",
        "tabs/wine_tab.py",
    )

    for file_name in expected_files:
        assert file_name in meson_build


class FakeComboBox:
    def __init__(self, items: list[tuple[str, object]], current_index: int = 0) -> None:
        self.items = items
        self.current_index = current_index

    def findData(self, value: object) -> int:
        return next(
            (index for index, item in enumerate(self.items) if item[1] == value),
            -1,
        )

    def addItem(self, text: str, data: object) -> None:
        self.items.append((text, data))

    def currentIndex(self) -> int:
        return self.current_index

    def setCurrentIndex(self, index: int) -> None:
        self.current_index = index

    def removeItem(self, index: int) -> None:
        self.items.pop(index)


def test_refresh_theme_store_visibility_adds_store(monkeypatch: Any) -> None:
    window: Any = MainWindow.__new__(MainWindow)
    window.themesCombo = FakeComboBox([("Standard", None)])
    monkeypatch.setattr(
        "portprotonqt.tabs.theme_tab.ui_config.get_enable_theme_store",
        lambda: True,
    )

    window._refresh_theme_store_visibility()

    assert window.themesCombo.findData(THEME_STORE_ITEM) == 1


def test_refresh_theme_store_visibility_removes_selected_store(monkeypatch: Any) -> None:
    window: Any = MainWindow.__new__(MainWindow)
    window.themesCombo = FakeComboBox(
        [("Standard", None), (THEME_STORE_ITEM, THEME_STORE_ITEM)],
        current_index=1,
    )
    monkeypatch.setattr(
        "portprotonqt.tabs.theme_tab.ui_config.get_enable_theme_store",
        lambda: False,
    )

    window._refresh_theme_store_visibility()

    assert window.themesCombo.findData(THEME_STORE_ITEM) == -1
    assert window.themesCombo.currentIndex() == 0


def test_process_portproton_desktop_calls_callback_without_asset_download(
    tmp_config_dir: Path,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    exe_path = tmp_path / "Game.exe"
    exe_path.write_text("", encoding="utf-8")
    desktop_path = tmp_path / "Game.desktop"
    desktop_path.write_text(
        "[Desktop Entry]\n"
        "Name=Test Game\n"
        f"Exec=portproton {exe_path}\n"
        "Icon=\n",
        encoding="utf-8",
    )

    window = MainWindow.__new__(MainWindow)
    window.portproton_location = str(tmp_path)
    results: list[tuple | None] = []

    def fake_steam_info(_name: str, _exec_line: str, callback: Any) -> None:
        callback({})

    monkeypatch.setattr(
        "portprotonqt.main_window.generate_thumbnail",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr("portprotonqt.main_window.get_steam_game_info_async", fake_steam_info)
    monkeypatch.setattr("portprotonqt.main_window.get_last_launch", lambda _exe_name: "Never")
    monkeypatch.setattr(
        "portprotonqt.main_window.get_last_launch_timestamp",
        lambda _exe_name: 0,
    )
    monkeypatch.setattr("portprotonqt.main_window.get_playtime_for_exe", lambda *_args: None)
    monkeypatch.setattr("portprotonqt.main_window.ui_config.get_economy_mode", lambda: False)

    window._process_desktop_file_async(str(desktop_path), results.append)

    assert len(results) == 1
    assert results[0] is not None
    assert results[0][0] == "Test Game"
    assert results[0][5] == f"portproton {exe_path}"
