"""Main window tab-related mixins."""

from portprotonqt.tabs.autoinstall_tab import MainWindowAutoInstallTabMixin
from portprotonqt.tabs.control_hints import MainWindowControlHintsMixin
from portprotonqt.tabs.library_tab import MainWindowLibraryTabMixin
from portprotonqt.tabs.settings_tab import MainWindowSettingsTabMixin
from portprotonqt.tabs.system_tab import MainWindowSystemTabMixin
from portprotonqt.tabs.theme_tab import MainWindowThemeTabMixin
from portprotonqt.tabs.wine_tab import MainWindowWineTabMixin
from portprotonqt.tabs.workers import MainWindowWorkersMixin

__all__ = [
    "MainWindowAutoInstallTabMixin",
    "MainWindowControlHintsMixin",
    "MainWindowLibraryTabMixin",
    "MainWindowSettingsTabMixin",
    "MainWindowSystemTabMixin",
    "MainWindowThemeTabMixin",
    "MainWindowWineTabMixin",
    "MainWindowWorkersMixin",
]
