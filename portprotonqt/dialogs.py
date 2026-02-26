"""Backward compatibility module for dialogs.

This module re-exports all dialog classes from the dialogs package for backward compatibility.
New code should import directly from portprotonqt.dialogs package.
"""

# Re-export all dialog classes for backward compatibility
from portprotonqt.dialogs.base import (
    GameLaunchDialog,
    AddGameDialog,
    generate_thumbnail,
    FileSelectedSignal,
)
from portprotonqt.dialogs.file_explorer import FileExplorer
from portprotonqt.dialogs.winetricks_dialog import WinetricksDialog
from portprotonqt.dialogs.settings_dialog import ExeSettingsDialog
from portprotonqt.dialogs.proton_manager import ProtonManager
from portprotonqt.dialogs.dialog_utils import create_dialog_hints_widget, update_dialog_hints

__all__ = [
    'GameLaunchDialog',
    'AddGameDialog',
    'generate_thumbnail',
    'FileSelectedSignal',
    'FileExplorer',
    'WinetricksDialog',
    'ExeSettingsDialog',
    'ProtonManager',
    'create_dialog_hints_widget',
    'update_dialog_hints',
]
