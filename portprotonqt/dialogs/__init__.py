"""Dialogs package for PortProtonQt."""

from portprotonqt.dialogs.dialog_utils import create_dialog_hints_widget, update_dialog_hints
from portprotonqt.dialogs.file_explorer import FileExplorer
from portprotonqt.dialogs.winetricks_dialog import WinetricksDialog
from portprotonqt.dialogs.settings_dialog import ExeSettingsDialog
from portprotonqt.dialogs.proton_manager import ProtonManager
from portprotonqt.icon_extractor import generate_thumbnail
from portprotonqt.dialogs.base import GameLaunchDialog, AddGameDialog, FileSelectedSignal

__all__ = [
    'create_dialog_hints_widget',
    'update_dialog_hints',
    'FileExplorer',
    'WinetricksDialog',
    'ExeSettingsDialog',
    'ProtonManager',
    'GameLaunchDialog',
    'AddGameDialog',
    'generate_thumbnail',
    'FileSelectedSignal',
]
