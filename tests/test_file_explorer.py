"""Tests for themed file explorer icons."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from pytest import MonkeyPatch
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyleOptionViewItem,
)

import portprotonqt.dialogs.file_explorer as file_explorer_module
from portprotonqt.dialogs.file_explorer import (
    FileExplorer,
    FileIconDelegate,
    THEMED_ICON_ROLE,
)

_application = QApplication.instance() or QApplication([])


class FakeIcon:
    """Record icon files assigned to Qt modes."""

    Mode = QIcon.Mode

    def __init__(self) -> None:
        self.files: dict[QIcon.Mode, str] = {}

    def addFile(self, path: str, _size: QSize, mode: QIcon.Mode) -> None:
        self.files[mode] = path


def test_file_icon_delegate_uses_active_icon_on_hover() -> None:
    list_widget = QListWidget()
    item = QListWidgetItem("folder/")
    normal_pixmap = QPixmap(4, 4)
    normal_pixmap.fill(QColor("#111111"))
    active_pixmap = QPixmap(4, 4)
    active_pixmap.fill(QColor("#222222"))
    icon = QIcon()
    icon.addPixmap(normal_pixmap, QIcon.Mode.Normal)
    icon.addPixmap(active_pixmap, QIcon.Mode.Active)
    item.setIcon(icon)
    item.setData(THEMED_ICON_ROLE, True)
    list_widget.addItem(item)
    option = QStyleOptionViewItem()
    option.state = QStyle.StateFlag.State_MouseOver
    option.decorationSize = QSize(4, 4)

    FileIconDelegate(list_widget).initStyleOption(
        option,
        list_widget.model().index(0, 0),
    )

    rendered = option.icon.pixmap(QSize(4, 4)).toImage()
    assert rendered.pixelColor(0, 0) == QColor("#222222")


def test_list_icon_uses_theme_state_colors(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    icon_path = tmp_path / "folder.svg"
    icon_path.write_text("<svg/>", encoding="utf-8")
    explorer = FileExplorer.__new__(FileExplorer)
    explorer.theme = SimpleNamespace(ICON_COLORS={
        "folder_hover": "#111111",
        "*_focused": "#222222",
        "*_disabled": "#333333",
    })
    monkeypatch.setattr(file_explorer_module, "QIcon", FakeIcon)
    monkeypatch.setattr(
        file_explorer_module.theme_manager,
        "get_icon",
        lambda *_args, **_kwargs: str(icon_path),
    )
    monkeypatch.setattr(
        file_explorer_module.theme_manager,
        "get_colored_icon_path",
        lambda name, color: f"{name}-{color}.svg",
    )

    icon = cast(FakeIcon, explorer._get_list_icon("folder"))

    assert icon.files == {
        QIcon.Mode.Normal: str(icon_path),
        QIcon.Mode.Active: "folder-#111111.svg",
        QIcon.Mode.Selected: "folder-#222222.svg",
        QIcon.Mode.Disabled: "folder-#333333.svg",
    }
