"""Common utilities for dialogs."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from portprotonqt.localization import _
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config_utils import read_theme_from_config

theme_manager = ThemeManager()


def create_dialog_hints_widget(theme, main_window, input_manager, context='default'):
    """
    Common function to create hints widget for all dialogs.
    Uses main_window for get_button_icon/get_nav_icon, input_manager for gamepad detection.
    """
    current_theme_name = read_theme_from_config()

    hintsWidget = QWidget()
    hintsWidget.setStyleSheet(theme.STATUS_BAR_STYLE)
    hintsLayout = QHBoxLayout(hintsWidget)
    hintsLayout.setContentsMargins(10, 0, 10, 0)
    hintsLayout.setSpacing(20)

    dialog_actions = []

    if context == 'file_explorer':
        dialog_actions = [
            ("confirm", _("Open")),
            ("add_game", _("Select Dir")),
            ("prev_dir", _("Prev Dir")),
            ("back", _("Cancel")),
            ("context_menu", _("Menu")),
        ]
    elif context == 'winetricks':
        dialog_actions = [
            ("confirm", _("Toggle")),
            ("add_game", _("Install")),
            ("prev_dir", _("Force Install")),
            ("back", _("Cancel")),
            ("prev_tab", _("Prev Tab")),
            ("next_tab", _("Next Tab")),
        ]
    elif context == 'settings':
        dialog_actions = [
            ("confirm", _("Toggle")),
            ("add_game", _("Save")),
            ("prev_dir", _("Search")),
            ("back", _("Cancel")),
            ("prev_tab", _("Prev Tab")),
            ("next_tab", _("Next Tab")),
        ]
    elif context == 'proton_manager':
        dialog_actions = [
            ("confirm", _("Toggle")),
            ("add_game", _("Apply")),
            ("prev_dir", _("Clear All")),
            ("back", _("Cancel")),
            ("prev_tab", _("Prev Tab")),
            ("next_tab", _("Next Tab")),
        ]

    hints_labels = []

    def make_hint(icon_name, text, action=None):
        container = QWidget()
        hlayout = QHBoxLayout(container)
        hlayout.setContentsMargins(0, 5, 0, 0)
        hlayout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setFixedSize(26, 26)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap()
        icon_path = theme_manager.get_theme_image(icon_name, current_theme_name)
        if icon_path:
            pixmap.load(str(icon_path))
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        hlayout.addWidget(icon_label)

        text_label = QLabel(text)
        text_label.setStyleSheet(theme.LAST_LAUNCH_VALUE_STYLE)
        text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        hlayout.addWidget(text_label)

        container.setVisible(False)
        hints_labels.append((container, icon_label, action))

        hintsLayout.addWidget(container)

    for action, text in dialog_actions:
        make_hint("placeholder", text, action)

    hintsLayout.addStretch()

    return hintsWidget, hints_labels


def update_dialog_hints(hints_labels, main_window, input_manager, theme_manager, current_theme_name):
    """
    Common function to update hints for any dialog.
    """
    if not input_manager or not main_window:
        for container, _, _ in hints_labels:
            container.setVisible(False)
        return

    is_gamepad = input_manager.gamepad is not None
    if not is_gamepad:
        for container, _, _ in hints_labels:
            container.setVisible(False)
        return

    gtype = input_manager.gamepad_type
    gamepad_actions = ['confirm', 'back', 'context_menu', 'add_game', 'prev_dir', 'prev_tab', 'next_tab']

    for container, icon_label, action in hints_labels:
        if action and action in gamepad_actions:
            container.setVisible(True)
            if action in ['confirm', 'back', 'context_menu', 'add_game', 'prev_dir']:
                icon_name = main_window.get_button_icon(action, gtype)
            else:
                direction = 'left' if action == 'prev_tab' else 'right'
                icon_name = main_window.get_nav_icon(direction, gtype)
            icon_path = theme_manager.get_theme_image(icon_name, current_theme_name)
            pixmap = QPixmap()
            if icon_path:
                pixmap.load(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(
                    26, 26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                placeholder = theme_manager.get_theme_image("placeholder", current_theme_name)
                if placeholder:
                    pixmap.load(str(placeholder))
                    icon_label.setPixmap(pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            container.setVisible(False)
