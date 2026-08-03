"""Tests for gamepad input navigation."""

from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QFrame, QStackedWidget, QWidget
from pytest import MonkeyPatch

import portprotonqt.input_manager as input_manager
from portprotonqt.gamepad_backend import (
    SDL_GAMEPAD_BUTTON_DPAD_DOWN,
    SDL_GAMEPAD_BUTTON_DPAD_UP,
    SDLGamepad,
)
from portprotonqt.input_manager import InputManager, MainWindowProtocol, PAD_DPAD_X, PAD_DPAD_Y

FIRST_CARD_X = 0
HIDDEN_CARD_X = 20
NEXT_CARD_X = 40


def test_qt_event_to_input_key_supports_cyrillic() -> None:
    event = cast(
        QEvent,
        SimpleNamespace(
            nativeScanCode=lambda: 0,
            text=lambda: "Я",
            key=lambda: 0,
        ),
    )
    manager = InputManager.__new__(InputManager)

    assert manager._qt_event_to_input_key(event) == ord("я")


def test_sdl_dpad_vertical_directions() -> None:
    emitted: list[tuple[int, int, float]] = []
    pressed_button = SDL_GAMEPAD_BUTTON_DPAD_UP
    gamepad = cast(
        SDLGamepad,
        SimpleNamespace(get_button=lambda button: int(button == pressed_button)),
    )
    manager = InputManager.__new__(InputManager)
    QObject.__init__(manager)
    manager._hat_states = {}
    manager.mouse_emulation_enabled = False
    manager.emulation_active = False
    manager.emulation_triggered = False
    manager.dpad_moved.connect(lambda code, value, now: emitted.append((code, value, now)))

    InputManager._poll_hat_events(manager, gamepad, 1.0)
    pressed_button = SDL_GAMEPAD_BUTTON_DPAD_DOWN
    InputManager._poll_hat_events(manager, gamepad, 2.0)

    assert emitted == [(PAD_DPAD_Y, -1, 1.0), (PAD_DPAD_Y, 1, 2.0)]


class DummyCard(QFrame):
    def __init__(self, parent: QWidget, x_pos: int) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(x_pos, 0, 10, 10)


def test_game_card_navigation_skips_hidden_cards(monkeypatch: MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    container = QWidget()
    container.show()

    next_card = DummyCard(container, NEXT_CARD_X)
    hidden_card = DummyCard(container, HIDDEN_CARD_X)
    first_card = DummyCard(container, FIRST_CARD_X)
    first_card.show()
    hidden_card.hide()
    next_card.show()
    app.processEvents()

    monkeypatch.setattr(input_manager, "GameCard", DummyCard)
    manager = InputManager.__new__(InputManager)
    manager._parent = cast(MainWindowProtocol, SimpleNamespace(tabButtons={0: QWidget()}))

    first_card.setFocus(Qt.FocusReason.OtherFocusReason)
    manager._navigate_game_cards(container, 0, PAD_DPAD_X, 1)

    assert QApplication.focusWidget() is next_card

    manager._navigate_game_cards(container, 0, PAD_DPAD_X, -1)

    assert QApplication.focusWidget() is first_card


def test_card_grid_navigation_uses_visual_rows() -> None:
    app = QApplication.instance() or QApplication([])
    container = QWidget()
    container.show()

    bottom_right = DummyCard(container, NEXT_CARD_X)
    bottom_right.move(NEXT_CARD_X, 20)
    top_left = DummyCard(container, FIRST_CARD_X)
    bottom_left = DummyCard(container, FIRST_CARD_X)
    bottom_left.move(FIRST_CARD_X, 20)
    top_right = DummyCard(container, NEXT_CARD_X)
    for card in (bottom_right, top_left, bottom_left, top_right):
        card.show()
    app.processEvents()

    manager = InputManager.__new__(InputManager)
    top_left.setFocus(Qt.FocusReason.OtherFocusReason)

    assert manager._navigate_card_grid(
        [bottom_right, top_left, bottom_left, top_right], PAD_DPAD_X, 1
    )
    assert QApplication.focusWidget() is top_right

    assert manager._navigate_card_grid(
        [bottom_right, top_left, bottom_left, top_right], PAD_DPAD_Y, 1
    )
    assert QApplication.focusWidget() is bottom_right


def test_library_toolbar_navigation_includes_delete_missing_button() -> None:
    app = QApplication.instance() or QApplication([])
    toolbar = QWidget()
    toolbar.show()

    widgets = []
    for _index in range(5):
        widget = QWidget(toolbar)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.show()
        widgets.append(widget)
    app.processEvents()

    parent = SimpleNamespace(
        quickLaunchButton=widgets[0],
        addGameButton=widgets[1],
        searchEdit=widgets[2],
        refreshButton=widgets[3],
        deleteMissingExeButton=widgets[4],
        libraryControlsButton=QWidget(toolbar),
        stackedWidget=QStackedWidget(),
        tabButtons={0: QWidget()},
    )
    parent.stackedWidget.addWidget(QWidget())
    manager = InputManager.__new__(InputManager)
    manager._parent = cast(MainWindowProtocol, parent)

    widgets[3].setFocus(Qt.FocusReason.OtherFocusReason)
    handled = manager._handle_toolbar_navigation(PAD_DPAD_X, 1)

    assert handled is True
    assert QApplication.focusWidget() is widgets[4]
