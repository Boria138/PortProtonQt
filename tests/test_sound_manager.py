"""Tests for UI sound playback and input integration."""

import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QComboBox, QMenu, QPushButton, QWidget
from pytest import MonkeyPatch

import portprotonqt.input_manager as input_manager
import portprotonqt.main_window as main_window
import portprotonqt.tabs.system_tab as system_tab
from portprotonqt.input_manager import InputManager
from portprotonqt.main_window import MainWindow
from portprotonqt.sound_manager import SOUND_EVENTS, SoundManager, _SoundSlot
from portprotonqt.tabs.system_tab import MainWindowSystemTabMixin


def test_sound_manager_resets_slots_when_sound_dirs_change() -> None:
    slots = [Mock(), Mock()]
    manager: Any = object.__new__(SoundManager)
    manager._sounds_dirs = ["old"]
    manager._url_cache = {"click": object()}
    manager._slots = slots

    manager.set_sounds_dirs(["new"])

    assert manager._url_cache == {}
    assert all(slot.reset.called for slot in slots)


def test_sound_manager_reuses_slot_for_same_event() -> None:
    loaded_slot = Mock(_loaded_event="navigate")
    other_slot = Mock(_loaded_event=None)
    manager: Any = object.__new__(SoundManager)
    manager._enabled = True
    manager._slots = [loaded_slot, other_slot]
    manager._slot_index = 1
    manager._get_url = lambda _event: Mock()

    manager.play("navigate")

    loaded_slot.play.assert_called_once()
    other_slot.play.assert_not_called()
    assert manager._slot_index == 1


def test_sound_slot_stops_at_end_of_media() -> None:
    end_of_media = object()
    slot: Any = object.__new__(_SoundSlot)
    slot._player = Mock()
    slot._player.MediaStatus.EndOfMedia = end_of_media

    slot._handle_media_status(end_of_media)

    slot._player.stop.assert_called_once()


def test_sound_manager_skips_unsafe_sound_variant(tmp_path: Path) -> None:
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()
    (sounds_dir / "navigate.ogg").write_bytes(b"not audio")
    safe_sound = sounds_dir / "navigate.wav"
    safe_sound.write_bytes(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 32)
    manager: Any = object.__new__(SoundManager)
    manager._sounds_dirs = [str(sounds_dir)]

    assert manager._find_sound_path("navigate") == safe_sound


def test_standard_theme_provides_all_sound_events() -> None:
    sounds_dir = Path(__file__).parent.parent / "portprotonqt" / "themes" / "standart" / "sounds"
    manager: Any = object.__new__(SoundManager)
    manager._sounds_dirs = [str(sounds_dir)]

    assert all(manager._find_sound_path(event) is not None for event in SOUND_EVENTS)


def test_widget_sound_uses_semantic_event() -> None:
    manager: Any = object.__new__(SoundManager)
    manager.play = Mock()
    widget = types.SimpleNamespace(property=lambda name: "open" if name == "sound_event" else None)

    manager.play_widget_sound(widget)

    manager.play.assert_called_once_with("open")


def test_widget_sound_can_disable_automatic_feedback() -> None:
    manager: Any = object.__new__(SoundManager)
    manager.play = Mock()
    widget = types.SimpleNamespace(property=lambda name: False if name == "sound_event" else None)

    manager.play_widget_sound(widget)

    manager.play.assert_not_called()


def test_combo_box_uses_open_sound() -> None:
    app = QApplication.instance() or QApplication([])
    manager: Any = object.__new__(SoundManager)
    manager.play = Mock()

    manager.play_widget_sound(QComboBox())

    manager.play.assert_called_once_with("open")
    assert app is not None


def test_gamepad_connection_sound_skips_initial_device(monkeypatch: MonkeyPatch) -> None:
    played_events: list[str] = []
    duplicate_closed: list[bool] = []
    gamepads = [
        SimpleNamespace(path="/dev/input/js0", name="Gamepad", close=lambda: None),
        SimpleNamespace(path="/dev/input/js0", name="Gamepad", close=lambda: duplicate_closed.append(True)),
    ]
    manager: Any = InputManager.__new__(InputManager)
    manager._gamepad_polling_suspended = False
    manager._initial_gamepad_check = True
    manager.gamepad = None
    manager.find_gamepad = lambda: gamepads.pop(0)
    manager.detect_gamepad_axes = lambda _gamepad: None
    manager._reset_input_state = lambda: None
    manager._get_effective_gamepad_type = lambda _gamepad: "xbox"
    manager._refresh_gamepad_ui = lambda: None
    monkeypatch.setattr(input_manager, "SoundManager", lambda: SimpleNamespace(play=played_events.append))
    monkeypatch.setattr(input_manager.display_config, "get_auto_fullscreen_gamepad", lambda: False)

    manager.check_gamepad()
    manager._initial_gamepad_check = False
    manager.check_gamepad()

    assert played_events == []
    assert duplicate_closed == [True]


def test_gamepad_connection_sound_plays_after_startup(monkeypatch: MonkeyPatch) -> None:
    played_events: list[str] = []
    manager: Any = InputManager.__new__(InputManager)
    manager._gamepad_polling_suspended = False
    manager._initial_gamepad_check = False
    manager.gamepad = None
    manager.find_gamepad = lambda: SimpleNamespace(path="/dev/input/js0", name="Gamepad", close=lambda: None)
    manager.detect_gamepad_axes = lambda _gamepad: None
    manager._reset_input_state = lambda: None
    manager._get_effective_gamepad_type = lambda _gamepad: "xbox"
    manager._refresh_gamepad_ui = lambda: None
    monkeypatch.setattr(input_manager, "SoundManager", lambda: SimpleNamespace(play=played_events.append))
    monkeypatch.setattr(input_manager.display_config, "get_auto_fullscreen_gamepad", lambda: False)

    manager.check_gamepad()

    assert played_events == ["gamepad_connect"]


def test_menu_navigation_plays_sound(monkeypatch: MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    menu = QMenu()
    first_action = menu.addAction("First")
    second_action = menu.addAction("Second")
    menu.setActiveAction(first_action)
    played_events: list[str] = []
    manager: Any = InputManager.__new__(InputManager)
    monkeypatch.setattr(input_manager, "SoundManager", lambda: SimpleNamespace(play=played_events.append))

    manager._navigate_menu_actions(menu, direction_down=True)

    assert menu.activeAction() is second_action
    assert played_events == ["navigate"]
    assert app is not None


def test_menu_show_plays_open_sound(monkeypatch: MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    played_events: list[str] = []
    manager = InputManager.__new__(InputManager)
    QObject.__init__(manager)
    monkeypatch.setattr(input_manager, "SoundManager", lambda: SimpleNamespace(play=played_events.append))

    manager.eventFilter(QMenu(), QEvent(QEvent.Type.Show))

    assert played_events == ["open"]
    assert app is not None


def test_combo_popup_show_plays_open_sound(monkeypatch: MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    played_events: list[str] = []
    manager = InputManager.__new__(InputManager)
    QObject.__init__(manager)
    combo = QComboBox()
    popup = QWidget(combo, Qt.WindowType.Popup)
    monkeypatch.setattr(input_manager, "SoundManager", lambda: SimpleNamespace(play=played_events.append))

    manager.eventFilter(popup, QEvent(QEvent.Type.Show))

    assert played_events == ["open"]
    assert app is not None


def test_combo_show_does_not_play_open_sound(monkeypatch: MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    played_events: list[str] = []
    manager = InputManager.__new__(InputManager)
    QObject.__init__(manager)
    monkeypatch.setattr(input_manager, "SoundManager", lambda: SimpleNamespace(play=played_events.append))

    manager.eventFilter(QComboBox(), QEvent(QEvent.Type.Show))

    assert played_events == []
    assert app is not None


def test_right_mouse_button_does_not_play_widget_sound(monkeypatch: MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    played_widgets: list[object] = []
    manager = InputManager.__new__(InputManager)
    QObject.__init__(manager)
    sound_manager = SimpleNamespace(play_widget_sound=played_widgets.append)
    monkeypatch.setattr(input_manager, "SoundManager", lambda: sound_manager)
    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(),
        QPointF(),
        QPointF(),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    manager.eventFilter(QPushButton(), event)

    assert played_widgets == []
    assert app is not None


def test_system_section_change_plays_tab_sound(monkeypatch: MonkeyPatch) -> None:
    played_events: list[str] = []
    section_stack = SimpleNamespace(
        count=lambda: 2,
        currentIndex=lambda: 0,
        setCurrentIndex=lambda _index: None,
    )
    buttons = [
        SimpleNamespace(isVisible=lambda: True, setChecked=lambda _checked: None),
        SimpleNamespace(isVisible=lambda: True, setChecked=lambda _checked: None),
    ]
    window = SimpleNamespace(
        systemSectionStack=section_stack,
        systemSectionButtons=buttons,
        _focusCurrentSystemSection=lambda _index: None,
    )
    monkeypatch.setattr(system_tab, "SoundManager", lambda: SimpleNamespace(play=played_events.append))

    changed = MainWindowSystemTabMixin.switchSystemSection(cast(Any, window), 1)

    assert changed is True
    assert played_events == ["tab_switch"]


def test_autoinstall_tab_defers_loading_until_after_sound(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []
    scheduled: list[object] = []
    button = SimpleNamespace(isVisible=lambda: True, setChecked=lambda _checked: None)
    stack = SimpleNamespace(setCurrentIndex=lambda _index: None, currentIndex=lambda: 1)
    window = SimpleNamespace(
        tabButtons={1: button},
        stackedWidget=stack,
        auto_install_tab_index=1,
        system_tab_index=-1,
        _start_autoinstall_load=lambda: calls.append("load"),
        _close_library_controls=lambda: None,
    )
    monkeypatch.setattr(main_window, "SoundManager", lambda: SimpleNamespace(play=calls.append))
    monkeypatch.setattr(main_window.QTimer, "singleShot", lambda _delay, callback: scheduled.append(callback))

    MainWindow.switchTab(cast(Any, window), 1)

    assert calls == ["tab_switch"]
    assert scheduled == [window._start_autoinstall_load]
