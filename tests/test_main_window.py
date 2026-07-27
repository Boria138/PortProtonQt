"""Tests for main window library data processing."""

import shlex
from collections.abc import Callable
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

from pytest import MonkeyPatch
from PySide6.QtCore import Qt

from portprotonqt.animations.library_controls import _animation_duration
from portprotonqt.detail_pages import DetailPageManager
from portprotonqt.game_library_manager import GameLibraryManager
from portprotonqt.gog_api import GOGAPI
from portprotonqt.main_window import MainWindow
from portprotonqt.portproton_api import remove_empty_custom_data_dirs
import portprotonqt.tabs.autoinstall_tab as autoinstall_tab_module
import portprotonqt.tabs.gog_tab as gog_tab_module
import portprotonqt.tabs.library_tab as library_tab_module
from portprotonqt.tabs import (
    MainWindowAutoInstallTabMixin,
    MainWindowLibraryTabMixin,
    MainWindowSettingsTabMixin,
    MainWindowThemeTabMixin,
    MainWindowWineTabMixin,
)
from portprotonqt.tabs.autoinstall_tab import MainWindowAutoInstallTabMixin as AutoInstallMixin
from portprotonqt.tabs.gog_tab import MainWindowGOGTabMixin as GOGMixin
from portprotonqt.tabs.library_tab import MainWindowLibraryTabMixin as LibraryMixin
from portprotonqt.tabs.settings_tab import MainWindowSettingsTabMixin as SettingsMixin
from portprotonqt.tabs.theme_store import THEME_STORE_ITEM, ThemeStoreMixin
from portprotonqt.tabs.theme_tab import (
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
        "_close_library_controls",
        "_create_library_controls_widget",
        "_add_library_action_buttons",
        "_add_library_search",
        "_add_library_refresh_button",
        "_add_library_delete_missing_button",
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
        "_get_games_without_exe",
        "updateDeleteMissingExeButton",
        "deleteMissingExeCards",
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

THEME_STORE_METHODS = (
    "_create_theme_store_page",
    "_show_theme_store",
    "_load_theme_store",
    "_on_theme_store_slider_released",
    "_set_theme_store_preview_variant",
    "_download_current_store_theme",
)


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


def test_gog_account_state_detects_saved_auth(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    class Control:
        def __init__(self) -> None:
            self.text = ""
            self.enabled = False

        def setText(self, text: str) -> None:
            self.text = text

        def setEnabled(self, enabled: bool) -> None:
            self.enabled = enabled

    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}")
    window = SimpleNamespace(
        gog_api=SimpleNamespace(
            auth_path=auth_path,
            get_account_name=lambda: "gog-user",
        ),
        gogAccountStatus=Control(),
        gogLoginButton=Control(),
    )
    monkeypatch.setattr(gog_tab_module, "_", lambda text: text)

    GOGMixin._update_gog_account_state(cast(Any, window))

    assert window.gogAccountStatus.text == "gog-user"
    assert window.gogLoginButton.text == "Log out"


def test_gog_account_action_logs_out_and_reloads_library(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}")
    calls = []

    def logout() -> bool:
        calls.append("logout")
        auth_path.unlink()
        return True

    window = SimpleNamespace(
        gog_api=SimpleNamespace(
            auth_path=auth_path,
            get_account_name=lambda: "",
            logout=logout,
        ),
        gogAccountStatus=SimpleNamespace(setText=lambda text: calls.append(text)),
        gogLoginButton=SimpleNamespace(
            setEnabled=lambda enabled: calls.append(("enabled", enabled)),
            setText=lambda text: calls.append(("button", text)),
        ),
        loadGames=lambda **kwargs: calls.append(("load", kwargs)),
    )
    window._update_gog_account_state = lambda: GOGMixin._update_gog_account_state(
        cast(Any, window)
    )
    monkeypatch.setattr(gog_tab_module, "_", lambda text: text)

    GOGMixin._handle_gog_account_action(cast(Any, window))

    assert "logout" in calls
    assert ("button", "Open login page") in calls
    assert ("load", {"force_load": True}) in calls


def test_gog_logout_removes_credentials_and_library_cache(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    api = GOGAPI()
    api.data_dir.mkdir(parents=True)
    api.auth_path.write_text("{}")
    api.account_path.write_text('{"username": "gog-user"}')
    api.library_path.write_text("[]")

    assert api.get_account_name() == "gog-user"
    assert api.logout() is True
    assert not api.auth_path.exists()
    assert not api.account_path.exists()
    assert not api.library_path.exists()


def test_gog_account_name_callback_updates_status() -> None:
    values = []
    window = SimpleNamespace(
        gogAccountStatus=SimpleNamespace(setText=values.append),
    )

    GOGMixin._on_gog_account_name_loaded(cast(Any, window), "gog-user")

    assert values == ["gog-user"]


def test_gog_library_refresh_restores_account_status() -> None:
    calls = []
    window = SimpleNamespace(
        _update_gog_account_state=lambda: calls.append("account"),
        loadGames=lambda **kwargs: calls.append(("load", kwargs)),
    )

    GOGMixin._on_gog_library_loaded(cast(Any, window), [])

    assert calls == ["account", ("load", {"force_load": True})]


def test_library_refresh_updates_connected_gog_library(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.touch()
    calls = []
    refresh_button = MagicMock()
    refresh_button.setEnabled.side_effect = lambda enabled: calls.append(enabled)
    window = SimpleNamespace(
        _refresh_in_progress=False,
        searchEdit=SimpleNamespace(clear=lambda: calls.append("clear")),
        refreshButton=refresh_button,
        _gamepad_tooltip_map={},
        game_library_manager=None,
        gog_api=SimpleNamespace(auth_path=auth_path),
        gog_library_worker=None,
        _refresh_gog_library=lambda: calls.append("gog"),
    )

    LibraryMixin.refreshGames(cast(Any, window))

    assert calls == ["clear", False, "gog"]


def test_gog_library_refresh_failure_reloads_cached_games(
    monkeypatch: MonkeyPatch,
) -> None:
    calls = []
    window = SimpleNamespace(
        gogAccountStatus=SimpleNamespace(setText=lambda text: calls.append(text)),
        loadGames=lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(gog_tab_module, "_", lambda text: text)

    GOGMixin._on_gog_library_failed(cast(Any, window), "network error")

    assert calls == [
        "Failed to refresh GOG library: network error",
        {"force_load": True},
    ]


def test_gog_login_shows_cached_games_before_refresh(monkeypatch: MonkeyPatch) -> None:
    calls = []
    window = SimpleNamespace(
        gog_api=SimpleNamespace(get_account_name=lambda: "gog-user"),
        gogAccountStatus=SimpleNamespace(setText=lambda text: calls.append(text)),
        loadGames=lambda **kwargs: calls.append(("load", kwargs)),
        _refresh_gog_library=lambda: calls.append("refresh"),
    )
    monkeypatch.setattr(gog_tab_module, "_", lambda text: text)

    GOGMixin._on_gog_authenticated(cast(Any, window), True, "")

    assert calls == [
        "gog-user",
        ("load", {"force_load": True}),
        "refresh",
    ]


def test_gog_support_removes_finished_process_before_launching_game() -> None:
    process = SimpleNamespace(poll=lambda: 0)
    launches = []
    window = SimpleNamespace(
        game_processes=[process],
        _launch_gog_game=lambda *args: launches.append(args),
    )

    GOGMixin._launch_after_gog_support(cast(Any, window), "123", "button")

    assert window.game_processes == []
    assert launches == [("123", "button")]


def test_repair_gog_game_uses_repair_command(tmp_path: Path) -> None:
    install_path = tmp_path / "Game"
    started: list[tuple] = []
    api = SimpleNamespace(
        config_dir=tmp_path / "gogdl",
        get_installed_path=lambda _app_id: install_path,
        build_command=lambda arguments: ["gogdl", *arguments],
    )
    window = SimpleNamespace(
        gog_process=None,
        gog_api=api,
        gogAccountStatus=SimpleNamespace(setText=lambda _text: None),
        _start_gog_download=lambda *arguments: started.append(arguments),
    )

    GOGMixin._repair_gog_game(cast(Any, window), {"app_id": "123", "title": "Game"})

    assert started[0][2] == [
        "gogdl", "repair", "123", "--path", str(install_path),
        "--support", str(tmp_path / "gogdl/heroic_gogdl/gog-support/123"),
        "--platform", "windows",
    ]


def test_install_gog_game_uses_support_path(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    selected_path = tmp_path / "Games"
    started: list[tuple] = []
    explorer = MagicMock()
    explorer.file_signal.file_selected.connect.side_effect = (
        lambda callback: callback(str(selected_path))
    )
    monkeypatch.setattr(gog_tab_module, "FileExplorer", lambda *_args, **_kwargs: explorer)
    api = SimpleNamespace(
        config_dir=tmp_path / "gogdl",
        get_install_path=lambda _app_id, _title: selected_path,
        is_game_installed=lambda _app_id: False,
        build_command=lambda arguments: ["gogdl", *arguments],
    )
    window = SimpleNamespace(
        gog_process=None, gog_download_queue=[], theme=object(), gog_api=api,
        _start_gog_download=lambda *arguments: started.append(arguments),
    )

    GOGMixin._install_gog_game(cast(Any, window), {"app_id": "123", "title": "Game"})

    assert started[0][2] == [
        "gogdl", "download", "123", "--path", str(selected_path),
        "--support", str(tmp_path / "gogdl/heroic_gogdl/gog-support/123"),
        "--platform", "windows",
    ]


def test_cancel_gog_download_terminates_then_kills(monkeypatch: MonkeyPatch) -> None:
    process = SimpleNamespace(
        terminate=MagicMock(),
        kill=MagicMock(),
        state=lambda: gog_tab_module.QProcess.ProcessState.Running,
    )
    window = SimpleNamespace(
        gog_process=process,
        downloadCancelButton=SimpleNamespace(setEnabled=MagicMock()),
        downloadActiveDetails=SimpleNamespace(setText=MagicMock()),
        _kill_gog_process=lambda active: GOGMixin._kill_gog_process(
            cast(Any, window), active
        ),
    )
    monkeypatch.setattr(gog_tab_module.QTimer, "singleShot", lambda _delay, callback: callback())

    GOGMixin._cancel_gog_download(cast(Any, window))

    process.terminate.assert_called_once()
    process.kill.assert_called_once()


def test_import_gog_game_saves_selected_installation(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    selected_path = tmp_path / "Selected"
    game_path = selected_path / "Game"
    saved: list[tuple] = []

    class Explorer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.callback: Callable[[str], None] = lambda _path: None
            self.file_signal = SimpleNamespace(
                file_selected=SimpleNamespace(connect=self._connect)
            )

        def _connect(self, callback: Callable[[str], None]) -> None:
            self.callback = callback

        def setWindowTitle(self, _title: str) -> None:
            return

        def exec(self) -> None:
            self.callback(str(selected_path))

    api = SimpleNamespace(
        find_install_path=lambda _app_id, _path: game_path,
        save_installed_game=lambda *arguments: saved.append(arguments),
        ensure_launch_parameters=lambda _app_id: None,
    )
    window = SimpleNamespace(
        theme=object(),
        gog_api=api,
        gogAccountStatus=SimpleNamespace(setText=lambda _text: None),
        loadGames=lambda **_kwargs: None,
    )
    monkeypatch.setattr(gog_tab_module, "FileExplorer", Explorer)

    GOGMixin._import_gog_game(cast(Any, window), {"app_id": "123", "title": "Game"})

    assert saved == [("123", {"install_path": str(game_path), "title": "Game"})]


def test_downloads_tab_is_hidden_without_downloads() -> None:
    tab_button = SimpleNamespace(setVisible=MagicMock())
    window = SimpleNamespace(
        downloadActiveCard=SimpleNamespace(isHidden=lambda: True),
        downloadQueuedTable=SimpleNamespace(rowCount=lambda: 0),
        downloadCompletedTable=SimpleNamespace(rowCount=lambda: 0),
        tabButtons={6: tab_button},
        stackedWidget=SimpleNamespace(currentIndex=lambda: 0),
        switchTab=MagicMock(),
    )

    GOGMixin._update_downloads_tab_visibility(cast(Any, window))

    tab_button.setVisible.assert_called_once_with(False)


def test_downloads_tab_is_visible_with_completed_download() -> None:
    tab_button = SimpleNamespace(setVisible=MagicMock())
    window = SimpleNamespace(
        downloadActiveCard=SimpleNamespace(isHidden=lambda: True),
        downloadQueuedTable=SimpleNamespace(rowCount=lambda: 0),
        downloadCompletedTable=SimpleNamespace(rowCount=lambda: 1),
        tabButtons={6: tab_button},
        stackedWidget=SimpleNamespace(currentIndex=lambda: 0),
        switchTab=MagicMock(),
    )

    GOGMixin._update_downloads_tab_visibility(cast(Any, window))

    tab_button.setVisible.assert_called_once_with(True)


def test_library_controls_animation_ignores_game_card_scale_duration() -> None:
    theme = SimpleNamespace(GAME_CARD_ANIMATION={"scale_anim_duration": 10})

    assert _animation_duration(theme, 150) == 150


def test_library_controls_animation_uses_own_duration() -> None:
    theme = SimpleNamespace(
        GAME_CARD_ANIMATION={
            "library_controls_anim_duration": 220,
            "scale_anim_duration": 10,
        },
    )

    assert _animation_duration(theme, 150) == 220


def test_switch_tab_closes_library_controls_when_leaving_library() -> None:
    class Button:
        def __init__(self) -> None:
            self.checked = False

        def isVisible(self) -> bool:
            return True

        def setChecked(self, checked: bool) -> None:
            self.checked = checked

    class Stack:
        def __init__(self) -> None:
            self.index = 0

        def setCurrentIndex(self, index: int) -> None:
            self.index = index

        def currentIndex(self) -> int:
            return self.index

    window = SimpleNamespace(
        tabButtons={0: Button(), 1: Button()},
        stackedWidget=Stack(),
        auto_install_tab_index=-1,
        system_tab_index=-1,
        library_controls_closed=False,
    )
    window._close_library_controls = lambda: setattr(
        window,
        "library_controls_closed",
        True,
    )

    MainWindow.switchTab(cast(Any, window), 1)

    assert window.library_controls_closed is True


def test_library_search_keeps_expanded_for_active_virtual_keyboard(monkeypatch: MonkeyPatch) -> None:
    class Window(LibraryMixin):
        pass

    search_edit = object()
    animation = SimpleNamespace(expanded=False, collapsed=False)
    keyboard = SimpleNamespace(
        current_input_widget=search_edit,
        isVisible=lambda: True,
    )
    window: Any = Window()
    window.searchEdit = search_edit
    window.searchAnimation = animation
    window.keyboard = keyboard
    window._center_collapsed_search_icon = lambda: None
    animation.expand = lambda: setattr(animation, "expanded", True)
    animation.collapse = lambda: setattr(animation, "collapsed", True)
    monkeypatch.setattr(library_tab_module.QTimer, "singleShot", lambda _ms, callback: callback())

    handler = window._wrap_search_focus_event(lambda _event: None, False)
    handler(object())

    assert animation.collapsed is False


def test_autoinstall_search_keeps_expanded_for_active_virtual_keyboard(monkeypatch: MonkeyPatch) -> None:
    class Window(AutoInstallMixin):
        pass

    search_edit = object()
    animation = SimpleNamespace(expanded=False, collapsed=False)
    keyboard = SimpleNamespace(
        current_input_widget=search_edit,
        isVisible=lambda: True,
    )
    window: Any = Window()
    window.autoInstallSearchLineEdit = search_edit
    window.autoInstallSearchAnimation = animation
    window.keyboard = keyboard
    window._center_collapsed_autoinstall_search_icon = lambda: None
    animation.expand = lambda: setattr(animation, "expanded", True)
    animation.collapse = lambda: setattr(animation, "collapsed", True)
    monkeypatch.setattr(autoinstall_tab_module.QTimer, "singleShot", lambda _ms, callback: callback())

    handler = window._wrap_autoinstall_search_focus_event(lambda _event: None, False)
    handler(object())

    assert animation.collapsed is False


def test_autoinstall_search_uses_card_names() -> None:
    class Window(AutoInstallMixin):
        pass

    class FakeSearchEdit:
        def __init__(self, text: str) -> None:
            self._text = text

        def text(self) -> str:
            return self._text

    class FakeCard:
        def __init__(self, name: str, description: str) -> None:
            self.name = name
            self.description = description
            self.visible = False

        def setVisible(self, visible: bool) -> None:
            self.visible = visible

    window: Any = Window()
    target_card = FakeCard("VK Play", "Launcher for the VK Play game library.")
    other_card = FakeCard("Another Game", "Different installer.")
    window.allAutoInstallCards = [target_card, other_card]
    window.autoInstallSearchLineEdit = FakeSearchEdit("vk")
    window.autoInstallContainerLayout = SimpleNamespace(invalidate=lambda: None)
    window.autoInstallContainer = SimpleNamespace(updateGeometry=lambda: None)
    window.autoInstallScrollArea = SimpleNamespace(updateGeometry=lambda: None)

    window.filterAutoInstallGames()

    assert target_card.visible is True
    assert other_card.visible is False


def test_tab_methods_resolve_from_expected_modules() -> None:
    for mixin, method_names in TAB_METHODS.items():
        for method_name in method_names:
            assert getattr(MainWindow, method_name) is getattr(mixin, method_name)
            assert method_name not in MainWindow.__dict__


def test_theme_store_methods_resolve_from_store_mixin() -> None:
    assert issubclass(ThemeMixin, ThemeStoreMixin)
    for method_name in THEME_STORE_METHODS:
        assert getattr(MainWindow, method_name) is getattr(ThemeStoreMixin, method_name)
        assert method_name not in ThemeMixin.__dict__


def test_tabs_package_exports_tab_mixins() -> None:
    import portprotonqt.tabs as tabs

    for mixin in TAB_METHODS:
        assert getattr(tabs, mixin.__name__) is mixin


def test_autoinstall_script_name_supports_spaced_paths(tmp_path: Path) -> None:
    script_path = tmp_path / "Game Installer.ppai"
    script_path.touch()
    manager = DetailPageManager.__new__(DetailPageManager)

    script_name = manager._extract_script_name(f"autoinstall:{shlex.quote(str(script_path))}")

    assert script_name == str(script_path)


def test_open_local_autoinstall_card_uses_autoinstall_page(tmp_path: Path) -> None:
    script_path = tmp_path / "Game Installer.ppai"
    script_path.touch()
    opened = []

    class FakePortProtonAPI:
        def read_local_autoinstall_metadata(self, path: str) -> dict[str, str]:
            assert path == str(script_path)
            return {"name": "Game", "description": "Description"}

    class FakeThemeManager:
        def get_icon(self, *args: Any, **kwargs: Any) -> str:
            return ""

    class FakeDetailPageManager:
        def openAutoInstallDetailPage(self, game_data: dict, return_tab_index: int = 1) -> None:
            opened.append((game_data, return_tab_index))

    window: Any = MainWindow.__new__(MainWindow)
    window.portproton_api = FakePortProtonAPI()
    window.theme_manager = FakeThemeManager()
    window.detail_page_manager = FakeDetailPageManager()

    window.open_local_autoinstall_card(str(script_path))

    game_data, return_tab_index = opened[0]
    assert game_data["name"] == "Game"
    assert game_data["exec_line"] == f"autoinstall:{shlex.quote(str(script_path))}"
    assert return_tab_index == 0


def test_open_game_detail_starts_pending_log(tmp_path: Path) -> None:
    exe_path = tmp_path / "Game.exe"
    exe_path.touch()
    started = []

    class FakeDetailPageManager:
        _debug_log_button = object()

        def openGameDetailPage(self, _game_data: dict) -> None:
            return

        def _start_debug_log(self, path: str, button: object) -> None:
            started.append((path, button))

    class FakeStackedWidget:
        def currentIndex(self) -> int:
            return 0

        def currentWidget(self) -> None:
            return None

    window: Any = MainWindow.__new__(MainWindow)
    window.detail_page_manager = FakeDetailPageManager()
    window.stackedWidget = FakeStackedWidget()
    window.currentDetailPage = None
    window._pending_log_exe = str(exe_path)

    window.openGameDetailPage({"name": "Game", "exec_line": str(exe_path)})

    assert started == [(str(exe_path), window.detail_page_manager._debug_log_button)]
    assert window._pending_log_exe is None


def test_launch_exe_skips_library_load_for_ppai() -> None:
    window: Any = MainWindow.__new__(MainWindow)
    window._loading_games = False
    window.launch_exe = "/tmp/Game Installer.ppai"

    window.loadGames()

    assert window._loading_games is False


def test_meson_installs_tab_modules() -> None:
    meson_build = Path("portprotonqt/meson.build").read_text(encoding="utf-8")
    expected_files = (
        "tabs/autoinstall_tab.py",
        "tabs/library_tab.py",
        "tabs/settings_tab.py",
        "tabs/theme_store.py",
        "tabs/theme_store_workers.py",
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


class FakeInputManager:
    def __init__(self) -> None:
        self.suspended = False

    def suspend_gamepad_polling(self) -> None:
        self.suspended = True


class FakeButton:
    def __init__(self) -> None:
        self.text = ""
        self.icon = None

    def setText(self, text: str) -> None:
        self.text = text

    def setIcon(self, icon: object) -> None:
        self.icon = icon


class FakeThemeManager:
    def get_icon(self, _name: str, as_path: bool = False) -> str:
        return "icon.svg"


class FakeTimer:
    def __init__(self, _parent: object) -> None:
        self.interval = 0

    @property
    def timeout(self) -> "FakeTimer":
        return self

    def connect(self, _callback: object) -> None:
        pass

    def start(self, interval: int) -> None:
        self.interval = interval


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def emit(self) -> None:
        for callback in self._callbacks:
            callback()


class FakeWorker:
    def __init__(self) -> None:
        self.finished = FakeSignal()


class FakeDetailPageManager:
    def __init__(self) -> None:
        self.opened_data: dict | None = None

    def openAutoInstallDetailPage(self, game_data: dict) -> None:
        self.opened_data = dict(game_data)


def test_stop_running_game_analyzes_before_stop_command_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    window: Any = MainWindow.__new__(MainWindow)
    analyzed = []
    window.current_running_button = None
    monkeypatch.setattr(window, "_analyze_short_launch", lambda: analyzed.append(True))
    monkeypatch.setattr(window, "_run_portproton_stop_command", lambda: False)

    assert window.stop_running_game() is False
    assert analyzed == [True]


def test_show_compatibility_report_uses_report_dialog(monkeypatch: MonkeyPatch) -> None:
    calls = []
    window: Any = MainWindow.__new__(MainWindow)
    window.theme = object()

    class ReportDialog:
        def __init__(self, parent: object, theme: object, report: str) -> None:
            calls.append((parent, theme, report))

        def exec(self) -> None:
            calls.append("exec")

    monkeypatch.setattr("portprotonqt.main_window.CompatibilityReportDialog", ReportDialog)

    window._show_compatibility_report("report text")

    assert calls == [(window, window.theme, "report text"), "exec"]


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


def test_autoinstall_script_thread_reference_clears_after_thread_finished() -> None:
    class FakePortProtonAPI:
        def __init__(self) -> None:
            self.script_callback: Any = None
            self.script_worker = FakeWorker()
            self.custom_data_worker = FakeWorker()

        def start_autoinstall_script_download(
            self,
            _url: str,
            callback: Any,
        ) -> FakeWorker:
            self.script_callback = callback
            return self.script_worker

        def start_autoinstall_custom_data_write(
            self,
            _path: str,
            _game_data: dict,
        ) -> FakeWorker:
            return self.custom_data_worker

    api = FakePortProtonAPI()
    window: Any = MainWindow.__new__(MainWindow)
    window.portproton_api = api
    window.detail_page_manager = FakeDetailPageManager()
    game_data = {"exec_line": "autoinstall:https://example.org/game.ppai"}

    window._open_autoinstall_card_after_script_download(
        game_data,
        "https://example.org/game.ppai",
    )
    api.script_callback("/tmp/game.ppai")

    assert window.autoInstallScriptLoadThread is api.script_worker
    assert window.detail_page_manager.opened_data == {
        "exec_line": "autoinstall:/tmp/game.ppai",
    }
    assert window.autoInstallCustomDataThread is api.custom_data_worker

    api.script_worker.finished.emit()
    api.custom_data_worker.finished.emit()

    assert window.autoInstallScriptLoadThread is None
    assert window.autoInstallCustomDataThread is None


def test_launch_autoinstall_checks_alt_i586_dependencies() -> None:
    window: Any = MainWindow.__new__(MainWindow)
    window.installing = False
    window._check_alt_i586_dependencies_before_launch = lambda: False

    window.launch_autoinstall("/tmp/game.ppai")

    assert window.installing is False


def test_initial_library_card_focus_does_not_use_navigation_reason() -> None:
    focus_reasons: list[Qt.FocusReason] = []
    card = SimpleNamespace(
        isVisible=lambda: True,
        isEnabled=lambda: True,
        setFocus=lambda reason: focus_reasons.append(reason),
    )
    manager: Any = GameLibraryManager.__new__(GameLibraryManager)
    manager.main_window = SimpleNamespace(
        stackedWidget=SimpleNamespace(currentIndex=lambda: 0),
    )
    manager.gamesListWidget = SimpleNamespace(findChildren=lambda _type: [card])
    manager.gamesScrollArea = None
    manager._focus_first_card_after_update = True

    manager._focus_first_visible_card()

    assert focus_reasons == [Qt.FocusReason.ActiveWindowFocusReason]


def test_launch_dependency_percent_updates_button_before_status() -> None:
    window: Any = MainWindow.__new__(MainWindow)
    button = FakeButton()
    window.current_running_button = button
    window.theme_manager = FakeThemeManager()
    window.launch_output_queue = Queue()
    window.launch_output_queue.put((None, 0.1, False))
    window.wine_download_seen = False
    window.wine_download_percent = 0.0
    window.wine_download_status = "Downloading Wine…"
    window.game_launch_started = False

    assert window._drain_launch_output_progress()
    window._set_running_button_progress()

    assert button.text == "Downloading Wine… 0.1%"


def test_toggle_game_replaces_invalid_launch_output_bytes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    exe_path = tmp_path / "Game.exe"
    exe_path.write_text("", encoding="utf-8")
    process = object()
    popen_kwargs: dict[str, object] = {}
    launch_events: list[str] = []
    window: Any = MainWindow.__new__(MainWindow)
    window.start_sh = ["portproton"]
    window.game_processes = []
    window.target_exe = None
    window.current_play_button = None
    window.input_manager = FakeInputManager()
    window.games = []

    def fake_popen(_command: list[str], **kwargs: object) -> object:
        launch_events.append("popen")
        popen_kwargs.update(kwargs)
        return process

    monkeypatch.setattr("portprotonqt.main_window.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "portprotonqt.main_window.SoundManager",
        lambda: SimpleNamespace(play=launch_events.append),
    )
    monkeypatch.setattr("portprotonqt.main_window.QTimer", FakeTimer)
    monkeypatch.setattr("portprotonqt.main_window.save_last_launch", lambda *_args: None)
    monkeypatch.setattr(window, "_check_alt_i586_dependencies_before_launch", lambda: True)
    monkeypatch.setattr(window, "_check_missing_prefix_before_launch", lambda *_args: None)
    monkeypatch.setattr(window, "_start_launch_output_reader", lambda _process: None)
    monkeypatch.setattr(window, "_update_last_launch_after_start", lambda *_args: None)

    window.toggleGame(str(exe_path))

    assert window.game_processes == [process]
    assert popen_kwargs["text"] is True
    assert popen_kwargs["errors"] == "replace"
    assert window.input_manager.suspended
    assert launch_events == ["popen", "game_launch"]


def test_steam_launch_plays_game_launch_sound(monkeypatch: MonkeyPatch) -> None:
    launch_events: list[str] = []
    window: Any = MainWindow.__new__(MainWindow)
    monkeypatch.setattr(
        "portprotonqt.main_window.get_steam_launch_commands",
        lambda _appid: [["steam", "-applaunch", "1"]],
    )
    monkeypatch.setattr(
        "portprotonqt.main_window.subprocess.Popen",
        lambda _command: launch_events.append("popen"),
    )
    monkeypatch.setattr(
        "portprotonqt.main_window.SoundManager",
        lambda: SimpleNamespace(play=launch_events.append),
    )

    window._launch_steam_game("steam://rungameid/1")

    assert launch_events == ["popen", "game_launch"]


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
    custom_data_path = tmp_config_dir.parent / "data" / "PortProtonQt" / "custom_data"
    assert not custom_data_path.exists()


def test_load_gog_games_includes_compatibility_metadata(monkeypatch: MonkeyPatch) -> None:
    window = MainWindow.__new__(MainWindow)
    test_window = cast(Any, window)
    test_window.gog_api = SimpleNamespace(
        load_installed=lambda: {},
        load_library=lambda: [
            {"app_id": "gog-1", "title": "Game", "steam_appid": "123"}
        ],
        is_game_installed=lambda _app_id, _installed: True,
    )
    steam_info = {
        "appid": 123,
        "controller_support": "full",
        "protondb_tier": "gold",
        "anticheat_status": "Supported",
        "anticheat_slug": "game",
        "ppdb_id": "456",
        "ppdb_rating": "good",
    }
    get_steam_info = MagicMock(
        side_effect=lambda _appid, callback, fallback_name: callback(steam_info)
    )
    monkeypatch.setattr(
        "portprotonqt.main_window.get_full_steam_game_info_async", get_steam_info
    )
    results = []

    MainWindow._load_gog_games_async(window, results.append)

    assert len(results) == 1
    game = results[0][0]
    assert game[3] == "gog-1"
    assert game[4] == "full"
    assert game[8:10] == ("gold", "Supported")
    assert game[13:17] == ("game", "456", "good", 123)
    assert get_steam_info.call_args.args[0] == 123
    assert get_steam_info.call_args.kwargs == {"fallback_name": "Game"}


def test_legacy_gog_library_refreshes_metadata(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    window = MainWindow.__new__(MainWindow)
    test_window = cast(Any, window)
    test_window._load_gog_games_async = MagicMock()
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}", encoding="utf-8")
    worker = SimpleNamespace(
        loaded=MagicMock(), failed=MagicMock(), finished=MagicMock(), start=MagicMock()
    )
    monkeypatch.setattr(
        "portprotonqt.main_window.GOGLibraryWorker", lambda _api: worker
    )
    callback = MagicMock()

    started = MainWindow._upgrade_legacy_gog_library(
        window, cast(Any, SimpleNamespace(auth_path=auth_path)),
        [{"app_id": "1"}], callback
    )

    assert started is True
    worker.start.assert_called_once_with()
    worker.loaded.connect.call_args.args[0]([])
    test_window._load_gog_games_async.assert_called_once_with(callback)


def test_gog_metadata_search_ignores_uri_components(monkeypatch: MonkeyPatch) -> None:
    from portprotonqt.steam_api import get_steam_game_info_async

    searched_candidates = []
    monkeypatch.setattr(
        "portprotonqt.steam_api.api.ui_config.get_economy_mode", lambda: False
    )
    monkeypatch.setattr(
        "portprotonqt.steam_api.api.get_steam_apps_and_index_async",
        lambda callback: callback(([{"appid": 1}], {"game": [{"appid": 1}]})),
    )
    monkeypatch.setattr(
        "portprotonqt.steam_api.api.search_app",
        lambda candidate, _index: searched_candidates.append(candidate),
    )
    fetch_sgdb_cover = MagicMock()
    monkeypatch.setattr(
        "portprotonqt.steam_api.api.fetch_sgdb_cover_async", fetch_sgdb_cover
    )
    monkeypatch.setattr(
        "portprotonqt.steam_api.api.get_weanticheatyet_info_async",
        lambda _name, callback: callback({}),
    )
    monkeypatch.setattr(
        "portprotonqt.steam_api.api._add_ppdb_info",
        lambda result, _name, callback: callback(result),
    )
    results = []

    get_steam_game_info_async("Unknown GOG Game", "gog://launch/123", results.append)

    assert searched_candidates == ["Unknown GOG Game"]
    assert len(results) == 1
    fetch_sgdb_cover.assert_not_called()


def test_remove_empty_custom_data_dirs_keeps_non_empty_dirs(tmp_config_dir: Path) -> None:
    custom_data_path = tmp_config_dir.parent / "data" / "PortProtonQt" / "custom_data"
    (custom_data_path / "praest").mkdir(parents=True)
    (custom_data_path / "Akalabeth - World of Doom").mkdir()
    kept_dir = custom_data_path / "Edited Game"
    kept_dir.mkdir()
    (kept_dir / "metadata.txt").write_text("name=Edited Game\n", encoding="utf-8")

    remove_empty_custom_data_dirs(str(custom_data_path))

    assert not (custom_data_path / "praest").exists()
    assert not (custom_data_path / "Akalabeth - World of Doom").exists()
    assert kept_dir.exists()


def test_get_games_without_exe_only_includes_portproton(tmp_path: Path) -> None:
    exe_path = tmp_path / "Game.exe"
    exe_path.write_text("", encoding="utf-8")
    window = MainWindow.__new__(MainWindow)
    test_window = cast(Any, window)
    test_window.game_library_manager = SimpleNamespace(
        games=[
            ("Existing", "", "", "", "", str(exe_path), "", "", "", "", 0, 0, "portproton"),
            (
                "Missing",
                "",
                "",
                "",
                "",
                str(tmp_path / "Missing.exe"),
                "",
                "",
                "",
                "",
                0,
                0,
                "portproton",
            ),
            ("Steam", "", "", "", "", "steam://rungameid/1", "", "", "", "", 0, 0, "steam"),
            ("GOG", "", "", "", "", "gog://install/1", "", "", "", "", 0, 0, "gog"),
        ]
    )

    missing_games = MainWindowLibraryTabMixin._get_games_without_exe(window)

    assert [game[0] for game in missing_games] == ["Missing"]


def test_update_delete_missing_exe_button_visibility(tmp_path: Path) -> None:
    exe_path = tmp_path / "Game.exe"
    exe_path.write_text("", encoding="utf-8")
    window = MainWindow.__new__(MainWindow)
    test_window = cast(Any, window)
    button = SimpleNamespace(visible=None)
    button.setVisible = lambda visible: setattr(button, "visible", visible)
    test_window.deleteMissingExeButton = button
    test_window.game_library_manager = SimpleNamespace(
        games=[
            ("Existing", "", "", "", "", str(exe_path), "", "", "", "", 0, 0, "portproton"),
            ("Steam", "", "", "", "", "steam://rungameid/1", "", "", "", "", 0, 0, "steam"),
        ]
    )

    MainWindowLibraryTabMixin.updateDeleteMissingExeButton(window)
    assert button.visible is False

    test_window.game_library_manager.games.append(
        (
            "Missing",
            "",
            "",
            "",
            "",
            str(tmp_path / "Missing.exe"),
            "",
            "",
            "",
            "",
            0,
            0,
            "portproton",
        )
    )
    MainWindowLibraryTabMixin.updateDeleteMissingExeButton(window)

    assert button.visible is True
