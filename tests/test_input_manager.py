"""Tests for gamepad input navigation."""

import os
from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QStackedWidget, QWidget
from pytest import MonkeyPatch

import portprotonqt.input_manager as input_manager
from portprotonqt.input_manager import InputManager, MainWindowProtocol, PAD_DPAD_X

FIRST_CARD_X = 0
HIDDEN_CARD_X = 20
NEXT_CARD_X = 40


class DummyCard(QFrame):
    def __init__(self, parent: QWidget, x_pos: int) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(x_pos, 0, 10, 10)


def test_game_card_navigation_skips_hidden_cards(monkeypatch: MonkeyPatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    container = QWidget()
    container.show()

    first_card = DummyCard(container, FIRST_CARD_X)
    hidden_card = DummyCard(container, HIDDEN_CARD_X)
    next_card = DummyCard(container, NEXT_CARD_X)
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


def test_library_toolbar_navigation_includes_delete_missing_button() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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
