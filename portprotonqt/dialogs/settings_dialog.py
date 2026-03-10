"""Settings dialog for PortProtonQt."""

import os
import re
import shutil
import configparser
from typing import cast, TYPE_CHECKING
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTabWidget,
    QTableWidget, QHeaderView, QTableWidgetItem, QAbstractItemView,
    QStackedWidget, QWidget, QMessageBox, QComboBox, QApplication,
    QCheckBox, QGroupBox, QScrollArea, QFormLayout,
    QGridLayout, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QEvent, QProcess, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

from portprotonqt.config_utils import (
    get_portproton_location,
    read_theme_from_config,
    get_portproton_start_command,
)
from portprotonqt.settings_manager import get_toggle_settings, get_advanced_settings, ADVANCED_SETTING_KEYS
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.preloader import Preloader
from portprotonqt.virtual_keyboard import VirtualKeyboard
from portprotonqt.localization import _, format_setting_name_for_display
from portprotonqt.dialogs.dialog_utils import create_dialog_hints_widget, update_dialog_hints
from portprotonqt.config import CONFIG_FILE
from portprotonqt.debug_utils import get_cached_vk_gpu_info

logger = get_logger(__name__)
theme_manager = ThemeManager()

MANGOHUD_ENV_KEYS = [
    'MANGOHUD_CONFIG',
    'FPS_LIMIT',
]

MANGOHUD_TOGGLE_SPECS = [
    ('arch', _("Arch")),
    ('battery', _("Battery")),
    ('battery_icon', _("Battery icon")),
    ('battery_time', _("Battery time")),
    ('battery_watt', _("Battery watt")),
    ('bicubic', _("Bicubic")),
    ('core_bars', _("Core bars")),
    ('core_load', _("Core load")),
    ('core_load_change', _("Core load change")),
    ('core_type', _("Core type")),
    ('cpu_efficiency', _("CPU efficiency")),
    ('cpu_load_change', _("CPU load change")),
    ('cpu_mhz', _("CPU MHz")),
    ('cpu_power', _("CPU power")),
    ('cpu_temp', _("CPU temperature")),
    ('debug', _("Debug")),
    ('device_battery_icon', _("Device battery icon")),
    ('display_server', _("Display server")),
    ('dynamic_frame_timing', _("Dynamic frame timing")),
    ('engine_short_names', _("Short engine names")),
    ('engine_version', _("Engine version")),
    ('exec_name', _("Executable name")),
    ('fan', _("Fan")),
    ('fcat', _("FCAT")),
    ('flip_efficiency', _("Flip efficiency")),
    ('fps_color_change', _("FPS color change")),
    ('fps_metrics', _("FPS metrics")),
    ('fps_only', _("FPS only")),
    ('frame_count', _("Frame count")),
    ('frametime', _("Frametime")),
    ('frame_timing_detailed', _("Detailed frametime")),
    ('fsr', _("FSR status")),
    ('full', _("Full preset")),
    ('gamemode', _("GameMode")),
    ('gpu_core_clock', _("GPU core clock")),
    ('gpu_efficiency', _("GPU efficiency")),
    ('gpu_fan', _("GPU fan")),
    ('gpu_junction_temp', _("GPU junction temp")),
    ('gpu_load_change', _("GPU load change")),
    ('gpu_mem_clock', _("GPU memory clock")),
    ('gpu_mem_temp', _("GPU memory temp")),
    ('gpu_name', _("GPU name")),
    ('gpu_power', _("GPU power")),
    ('gpu_power_limit', _("GPU power limit")),
    ('gpu_temp', _("GPU temperature")),
    ('gpu_voltage', _("GPU voltage")),
    ('hdr', _("HDR status")),
    ('hide_fsr_sharpness', _("Hide FSR sharpness")),
    ('histogram', _("Histogram")),
    ('horizontal', _("Horizontal")),
    ('horizontal_stretch', _("Horizontal stretch")),
    ('hud_compact', _("Compact HUD")),
    ('hud_no_margin', _("No margins")),
    ('io_read', _("IO read")),
    ('io_write', _("IO write")),
    ('log_versioning', _("Log versioning")),
    ('media_player', _("Media player")),
    ('no_display', _("Hidden by default")),
    ('no_small_font', _("No small font")),
    ('permit_upload', _("Permit upload")),
    ('present_mode', _("Present mode")),
    ('proc_vram', _("Process VRAM")),
    ('procmem', _("Process memory")),
    ('procmem_shared', _("Shared memory")),
    ('procmem_virt', _("Virtual memory")),
    ('ram', _("RAM")),
    ('ram_temp', _("RAM temperature")),
    ('read_cfg', _("Read config")),
    ('refresh_rate', _("Refresh rate")),
    ('resolution', _("Resolution")),
    ('retro', _("Retro")),
    ('show_fps_limit', _("Show FPS limit")),
    ('swap', _("Swap")),
    ('temp_fahrenheit', _("Fahrenheit")),
    ('text_outline', _("Text outline")),
    ('throttling_status', _("Throttling status")),
    ('throttling_status_graph', _("Throttling graph")),
    ('time', _("Time")),
    ('time_no_label', _("Time without label")),
    ('trilinear', _("Trilinear")),
    ('upload_logs', _("Upload logs")),
    ('version', _("Version")),
    ('vkbasalt', _("vkBasalt")),
    ('vram', _("VRAM")),
    ('vulkan_driver', _("Vulkan driver")),
    ('wine', _("Wine")),
    ('winesync', _("Wine sync")),
]

MANGOHUD_FPS_OPTIONS = ['30', '40', '45', '48', '60', '75', '90', '120', '144', '165', '175', '240']

MANGOHUD_VALUE_SPECS = [
    {'key': 'position', 'label': _("Overlay position"), 'type': 'combo',
     'options': ['top-left', 'top-right', 'middle-left', 'middle-right',
                 'bottom-left', 'bottom-right', 'top-center', 'bottom-center']},
    {'key': 'device_battery', 'label': _("Device battery"), 'type': 'combo',
     'options': ['', 'gamepad', 'mouse', 'gamepad,mouse']},
    {'key': 'fps_limit_method', 'label': _("FPS limit method"), 'type': 'combo',
     'options': ['late', 'early']},
    {'key': 'af', 'label': _("Anisotropic filtering"), 'type': 'combo',
     'options': [str(value) for value in range(17)]},
    {'key': 'fcat_screen_edge', 'label': _("FCAT screen edge"), 'type': 'combo',
     'options': ['1', '2', '3', '4']},
    {'key': 'table_columns', 'label': _("Table columns"), 'type': 'combo',
     'options': ['1', '2', '3', '4', '5', '6']},
    {'key': 'network', 'label': _("Network (tx/rx kb/s)"), 'type': 'combo',
     'options': ['']},
    {'key': 'gpu_list', 'label': _("GPU list"), 'type': 'combo',
     'options': ['']},
    {'key': 'background_alpha', 'label': _("Background opacity"), 'type': 'combo',
     'options': [f'{i / 10:.1f}' for i in range(11)]},
    {'key': 'round_corners', 'label': _("Round corners (px)"), 'type': 'combo',
     'options': [str(i) for i in range(16)]},
]

MANGOHUD_VALUE_OPTION_TRANSLATIONS = {
    'position': {
        'top-left': _("Top-left"),
        'top-right': _("Top-right"),
        'middle-left': _("Middle-left"),
        'middle-right': _("Middle-right"),
        'bottom-left': _("Bottom-left"),
        'bottom-right': _("Bottom-right"),
        'top-center': _("Top-center"),
        'bottom-center': _("Bottom-center"),
    },
    'device_battery': {
        'gamepad': _("Gamepad"),
        'mouse': _("Mouse"),
        'gamepad,mouse': _("Gamepad, mouse"),
    },
    'fps_limit_method': {
        'late': _("Late"),
        'early': _("Early"),
    },
}

MANGOHUD_VALUE_DEFAULTS = {
    'position': 'top-left',
    'device_battery': '',
    'fps_limit_method': 'late',
    'af': '0',
    'fcat_screen_edge': '1',
    'table_columns': '3',
    'network': '',
    'gpu_list': '',
    'background_alpha': '0.5',
    'round_corners': '0',
}

MANGOHUD_HIDDEN_EXTRA_KEYS = {
    'font_size',
}

MANGOHUD_BUTTON_PRESETS = {
    'fps_only': {
        'config': 'position=top-left',
        'fps_limit': '',
        'toggles': {'show_fps_limit'},
    },
    'compact': {
        'config': 'position=top-right,hud_compact',
        'fps_limit': '',
        'toggles': {'frametime', 'cpu_temp', 'gpu_temp', 'ram', 'vram', 'wine', 'winesync'},
    },
    'extended': {
        'config': 'position=top-left',
        'fps_limit': '',
        'toggles': {
            'frametime', 'frame_count', 'cpu_mhz', 'cpu_power', 'cpu_temp',
            'gpu_power', 'gpu_temp', 'ram', 'vram', 'io_read', 'io_write',
            'resolution', 'engine_version', 'vulkan_driver', 'wine', 'winesync', 'gamemode'
        },
    },
    'clear': {
        'config': '',
        'fps_limit': '',
        'toggles': set(),
    },
    'custom': {
        'config': '',
        'fps_limit': '',
        'toggles': set(),
    },
}

MANGOHUD_TOGGLE_CATEGORIES = {
    _("General"): [
        'arch', 'battery', 'battery_icon', 'battery_time', 'battery_watt',
        'device_battery_icon', 'display_server', 'exec_name', 'gamemode',
        'media_player', 'time', 'time_no_label', 'version', 'vkbasalt',
        'wine', 'winesync',
    ],
    _("Performance"): [
        'bicubic', 'dynamic_frame_timing', 'flip_efficiency', 'fps_color_change',
        'fps_metrics', 'fps_only', 'frametime', 'frame_timing_detailed',
        'full', 'hide_fsr_sharpness', 'histogram', 'present_mode',
        'read_cfg', 'retro', 'show_fps_limit', 'trilinear',
    ],
    _("CPU / GPU"): [
        'core_bars', 'core_load', 'core_load_change', 'core_type',
        'cpu_efficiency', 'cpu_load_change', 'cpu_mhz', 'cpu_power', 'cpu_temp',
        'gpu_core_clock', 'gpu_efficiency', 'gpu_fan', 'gpu_junction_temp',
        'gpu_load_change', 'gpu_mem_clock', 'gpu_mem_temp', 'gpu_name',
        'gpu_power', 'gpu_power_limit', 'gpu_temp', 'gpu_voltage',
        'ram', 'ram_temp', 'swap', 'vram',
    ],
    _("Overlay"): [
        'debug', 'engine_short_names', 'engine_version', 'fan', 'fcat', 'fsr',
        'frame_count', 'hdr', 'horizontal', 'horizontal_stretch', 'hud_compact',
        'hud_no_margin', 'io_read', 'io_write', 'log_versioning', 'no_display',
        'no_small_font', 'permit_upload', 'proc_vram', 'procmem',
        'procmem_shared', 'procmem_virt', 'refresh_rate', 'resolution',
        'temp_fahrenheit', 'text_outline', 'throttling_status',
        'throttling_status_graph', 'upload_logs', 'vulkan_driver',
    ],
}

MANGOHUD_TOGGLE_DESCRIPTIONS = {
    'arch': _("Application architecture (32/64-bit)"),
    'battery': _("Battery percent and energy consumption"),
    'battery_icon': _("Battery icon instead of percent"),
    'battery_time': _("Remaining battery time"),
    'battery_watt': _("Battery wattage"),
    'bicubic': _("Force bicubic filtering"),
    'core_bars': _("Core load as vertical bars"),
    'core_load': _("Per-core load and frequency"),
    'core_load_change': _("Core load color change"),
    'core_type': _("CPU core type (P/E/ARM)"),
    'cpu_efficiency': _("CPU efficiency (frames/joule)"),
    'cpu_load_change': _("CPU load color change"),
    'cpu_mhz': _("CPU frequency in MHz"),
    'cpu_power': _("CPU power draw (watts)"),
    'cpu_temp': _("CPU temperature"),
    'debug': _("Gamescope frametime graphs"),
    'device_battery_icon': _("Wireless device battery icon"),
    'display_server': _("Display server type (X11/Wayland)"),
    'dynamic_frame_timing': _("Dynamic frametime Y-axis"),
    'engine_short_names': _("Short engine names"),
    'engine_version': _("Engine version (OpenGL/Vulkan)"),
    'exec_name': _("Executable name"),
    'fan': _("Steam Deck fan RPM"),
    'fcat': _("Frame capture analysis"),
    'flip_efficiency': _("Flip efficiency (joules/frame)"),
    'fps_color_change': _("FPS text color by value"),
    'fps_metrics': _("FPS percentiles"),
    'fps_only': _("Show FPS only"),
    'frame_count': _("Frame counter"),
    'frametime': _("Frametime next to FPS"),
    'frame_timing_detailed': _("Detailed frame timing chart"),
    'fsr': _("FSR status (gamescope)"),
    'full': _("Enable most parameters"),
    'gamemode': _("GameMode status"),
    'gpu_core_clock': _("GPU core frequency"),
    'gpu_efficiency': _("GPU efficiency (frames/joule)"),
    'gpu_fan': _("GPU fan (RPM/%)"),
    'gpu_junction_temp': _("GPU junction temperature"),
    'gpu_load_change': _("GPU load color change"),
    'gpu_mem_clock': _("GPU memory frequency"),
    'gpu_mem_temp': _("GPU memory temperature"),
    'gpu_name': _("GPU name from pci.ids"),
    'gpu_power': _("GPU power draw (watts)"),
    'gpu_power_limit': _("GPU power limit"),
    'gpu_temp': _("GPU temperature"),
    'gpu_voltage': _("GPU voltage"),
    'hdr': _("HDR status (gamescope)"),
    'hide_fsr_sharpness': _("Hide FSR sharpness info"),
    'histogram': _("FPS histogram"),
    'horizontal': _("Horizontal HUD layout"),
    'horizontal_stretch': _("Stretch background horizontally"),
    'hud_compact': _("Compact HUD mode"),
    'hud_no_margin': _("Remove HUD margins"),
    'io_read': _("IO read rate (MiB/s)"),
    'io_write': _("IO write rate (MiB/s)"),
    'log_versioning': _("Add versioning to logs"),
    'media_player': _("Media player metadata"),
    'no_display': _("Hide HUD by default"),
    'no_small_font': _("Use primary font size"),
    'permit_upload': _("Allow log uploads"),
    'present_mode': _("Vulkan present mode"),
    'proc_vram': _("Process VRAM usage"),
    'procmem': _("Process memory (resident)"),
    'procmem_shared': _("Process shared memory"),
    'procmem_virt': _("Process virtual memory"),
    'ram': _("System RAM usage"),
    'ram_temp': _("RAM temperature (DDR5)"),
    'read_cfg': _("Load config file"),
    'refresh_rate': _("Refresh rate (gamescope)"),
    'resolution': _("Current resolution"),
    'retro': _("Retro filtering (unfiltered)"),
    'show_fps_limit': _("Show FPS limit"),
    'swap': _("Swap usage"),
    'temp_fahrenheit': _("Temperature in Fahrenheit"),
    'text_outline': _("Text outline"),
    'throttling_status': _("GPU throttling status"),
    'throttling_status_graph': _("Throttling in frame graph"),
    'time': _("Local time"),
    'time_no_label': _("Time without label"),
    'trilinear': _("Force trilinear filtering"),
    'upload_logs': _("Automatic log uploads"),
    'version': _("MangoHud version"),
    'vkbasalt': _("vkBasalt status"),
    'vulkan_driver': _("Vulkan driver (radv/amdvlk)"),
    'wine': _("Wine/Proton version"),
    'winesync': _("Wine sync method"),
    'vram': _("VRAM usage"),
}

class ExeSettingsDialog(QDialog):
    """Dialog for configuring executable-specific settings."""

    def __init__(self, parent=None, theme=None, exe_path=None, appid=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.exe_path = exe_path
        self.appid = appid
        if not self.exe_path and not self.appid:
            return
        self.portproton_path = get_portproton_location()
        if self.portproton_path is None:
            logger.error("PortProton location not found")
            return
        self.start_sh = get_portproton_start_command()
        if self.start_sh is None:
            logger.error("PortProton start command not found")
            return

        self.dist_options = []
        self.prefix_options = []
        if self.portproton_path:
            dist_dir = os.path.join(self.portproton_path, "data", 'dist')
            if os.path.exists(dist_dir):
                self.dist_options = sorted(
                    [f for f in os.listdir(dist_dir) if os.path.isdir(os.path.join(dist_dir, f))],
                    key=lambda x: x.lower()
                )
            prefixes_dir = os.path.join(self.portproton_path, 'prefixes')
            if os.path.exists(prefixes_dir):
                self.prefix_options = sorted(
                    [f for f in os.listdir(prefixes_dir) if os.path.isdir(os.path.join(prefixes_dir, f))],
                    key=lambda x: x.lower()
                )

        if shutil.which('wine'):
            if _('System WINE') not in self.dist_options:
                self.dist_options.append(_('System WINE'))

        self.current_settings = {}
        self.value_widgets = {}
        self.original_values = {}
        self.advanced_widgets = {}
        self.original_display_values = {}
        self.mangohud_widgets = {}
        self.mangohud_original_values = {}
        self.mangohud_hidden_extra_tokens = []
        self.mangohud_toggle_widgets = {}
        self.mangohud_toggle_widget_keys = {}
        self.mangohud_fps_widgets = {}
        self.mangohud_category_groups = {}
        self.available_keys = set()
        self.blocked_keys = set()
        self.numa_nodes = {}
        self.locale_options = []
        self.logical_core_options = []

        self.setWindowTitle(_("Exe Settings"))
        self.setModal(True)
        self.resize(1100, 720)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.toggle_settings = get_toggle_settings()

        self.setup_ui()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._on_focus_changed)

        self.input_manager = None
        self.main_window = None
        parent_obj = self.parent()
        while parent_obj:
            if hasattr(parent_obj, 'input_manager'):
                self.input_manager = cast("MainWindow", parent_obj).input_manager
                self.main_window = parent_obj
            parent_obj = parent_obj.parent()

        self.current_theme_name = read_theme_from_config()

        if self.input_manager:
            self.input_manager.enable_settings_mode(self)

        self.hints_widget, self.hints_labels = create_dialog_hints_widget(
            self.theme, self.main_window, self.input_manager, context='settings'
        )
        self.main_layout.addWidget(self.hints_widget)

        if self.input_manager:
            self.input_manager.button_event.connect(
                lambda *args: update_dialog_hints(self.hints_labels, self.main_window, self.input_manager, theme_manager, self.current_theme_name)
            )
            self.input_manager.dpad_moved.connect(
                lambda *args: update_dialog_hints(self.hints_labels, self.main_window, self.input_manager, theme_manager, self.current_theme_name)
            )
            update_dialog_hints(self.hints_labels, self.main_window, self.input_manager, theme_manager, self.current_theme_name)

        self.init_virtual_keyboard()
        self.load_current_settings()

    def _get_process_args(self, subcommand_args):
        """Get the full arguments for QProcess.start, handling flatpak format."""
        if self.start_sh and self.start_sh[0] == "flatpak":
            return self.start_sh + subcommand_args
        return self.start_sh + subcommand_args

    def setup_ui(self):
        """Set up the user interface."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        search_layout = QHBoxLayout()
        self.search_label = QLabel(_("Search:"))
        self.search_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.search_edit = QLineEdit()
        self.search_edit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        self.search_edit.setPlaceholderText(_("Search settings..."))
        self.search_edit.textChanged.connect(self.filter_settings)
        self.search_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.search_edit.installEventFilter(self)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_edit)
        self.main_layout.addLayout(search_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self.theme.WINETRICKS_TAB_STYLE)
        self.main_tab = QWidget()
        self.main_tab_layout = QVBoxLayout(self.main_tab)
        self.advanced_tab = QWidget()
        self.advanced_tab_layout = QVBoxLayout(self.advanced_tab)
        self.mangohud_tab = QWidget()
        self.mangohud_tab_layout = QVBoxLayout(self.mangohud_tab)

        self.tab_widget.addTab(self.main_tab, _("Main"))
        self.tab_widget.addTab(self.advanced_tab, _("Advanced"))
        self.tab_widget.addTab(self.mangohud_tab, _("MangoHud"))
        self.tab_widget.currentChanged.connect(self.on_table_selection_changed)

        self.settings_table = QTableWidget()
        self.settings_table.setAlternatingRowColors(True)
        self.settings_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.settings_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.settings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.settings_table.setColumnCount(3)
        self.settings_table.setHorizontalHeaderLabels([_("Setting"), _("Value"), _("Description")])
        self.settings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.settings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.settings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.settings_table.horizontalHeader().resizeSection(1, 100)
        self.settings_table.setWordWrap(True)
        self.settings_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.settings_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.settings_table.setStyleSheet(self.theme.WINETRICKS_TABBLE_STYLE)
        self.settings_table.setMouseTracking(True)

        self.settings_preloader = Preloader()
        settings_preloader_container = QWidget()
        settings_preloader_layout = QVBoxLayout(settings_preloader_container)
        settings_preloader_layout.addStretch()
        settings_preloader_hlayout = QHBoxLayout()
        settings_preloader_hlayout.addStretch()
        settings_preloader_hlayout.addWidget(self.settings_preloader)
        settings_preloader_hlayout.addStretch()
        settings_preloader_layout.addLayout(settings_preloader_hlayout)
        settings_preloader_layout.addStretch()
        settings_preloader_layout.setContentsMargins(0, 0, 0, 0)
        settings_preloader_layout.setSpacing(0)

        self.settings_container = QStackedWidget()
        self.settings_container.addWidget(settings_preloader_container)
        self.settings_container.addWidget(self.settings_table)
        self.main_tab_layout.addWidget(self.settings_container)
        self.settings_table.currentCellChanged.connect(self.on_table_selection_changed)
        self.settings_table.cellEntered.connect(self.on_table_cell_hovered)
        self.settings_table.installEventFilter(self)

        self.advanced_table = QTableWidget()
        self.advanced_table.setAlternatingRowColors(True)
        self.advanced_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.advanced_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.advanced_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.advanced_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.advanced_table.setColumnCount(3)
        self.advanced_table.setHorizontalHeaderLabels([_("Setting"), _("Value"), _("Description")])
        self.advanced_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.advanced_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.advanced_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.advanced_table.horizontalHeader().resizeSection(1, 230)
        self.advanced_table.setWordWrap(True)
        self.advanced_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.advanced_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.advanced_table.setStyleSheet(self.theme.WINETRICKS_TABBLE_STYLE)
        self.advanced_table.setMouseTracking(True)

        self.advanced_preloader = Preloader()
        advanced_preloader_container = QWidget()
        advanced_preloader_layout = QVBoxLayout(advanced_preloader_container)
        advanced_preloader_layout.addStretch()
        advanced_preloader_hlayout = QHBoxLayout()
        advanced_preloader_hlayout.addStretch()
        advanced_preloader_hlayout.addWidget(self.advanced_preloader)
        advanced_preloader_hlayout.addStretch()
        advanced_preloader_layout.addLayout(advanced_preloader_hlayout)
        advanced_preloader_layout.addStretch()
        advanced_preloader_layout.setContentsMargins(0, 0, 0, 0)
        advanced_preloader_layout.setSpacing(0)

        self.advanced_container = QStackedWidget()
        self.advanced_container.addWidget(advanced_preloader_container)
        self.advanced_container.addWidget(self.advanced_table)
        self.advanced_tab_layout.addWidget(self.advanced_container)
        self.advanced_table.currentCellChanged.connect(self.on_table_selection_changed)
        self.advanced_table.cellEntered.connect(self.on_table_cell_hovered)
        self.advanced_table.installEventFilter(self)

        self.setup_mangohud_tab()

        self.main_layout.addWidget(self.tab_widget)

        self.gamepad_tooltip = QLabel()
        self.gamepad_tooltip.setWordWrap(True)
        self.gamepad_tooltip.setStyleSheet(self.theme.SETTINGS_TOOLTIP_STYLE)
        self.gamepad_tooltip.setVisible(False)
        self.gamepad_tooltip.setParent(self)
        self.gamepad_tooltip.setWindowFlags(Qt.WindowType.ToolTip)
        self.gamepad_tooltip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.gamepad_tooltip_timer = QTimer(self)
        self.gamepad_tooltip_timer.setSingleShot(True)
        self.gamepad_tooltip_timer.timeout.connect(lambda: self.gamepad_tooltip.setVisible(False))

        button_layout = QHBoxLayout()
        self.apply_button = AutoSizeButton(_("Apply"), icon=ThemeManager().get_icon("apply"))
        self.cancel_button = AutoSizeButton(_("Cancel"), icon=ThemeManager().get_icon("cancel"))
        self.open_ppdb_button = AutoSizeButton(_("Open PPDB"), icon=ThemeManager().get_icon("folder"))
        self.apply_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.cancel_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.open_ppdb_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.open_ppdb_button)
        self.main_layout.addLayout(button_layout)

        self.apply_button.clicked.connect(self.apply_changes)
        self.cancel_button.clicked.connect(self.reject)
        self.open_ppdb_button.clicked.connect(self.open_ppdb_file)

    def load_current_settings(self):
        """Load available toggles first, then current settings."""
        self.settings_container.setCurrentIndex(0)
        self.advanced_container.setCurrentIndex(0)

        process = QProcess(self)
        process.finished.connect(self.on_list_db_finished)
        args = self._get_process_args(["cli", "--list-db"])
        process.start(args[0], args[1:])

    def on_list_db_finished(self, exit_code, exit_status):
        """Handle --list-db output and extract available keys and system info."""
        process = cast(QProcess, self.sender())
        self.available_keys = set()
        self.blocked_keys = set()
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            output = bytes(process.readAllStandardOutput().data()).decode('utf-8', 'ignore')
            lines = output.splitlines()
            self.numa_nodes = {}
            self.logical_core_options = []
            self.locale_options = []
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if re.match(r'^[A-Z_0-9]+=[^=]+$', line_stripped) and not line_stripped.startswith('PW_'):
                    k, v = line_stripped.split('=', 1)
                    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
                        v = v[1:-1]
                    if k.startswith('NUMA_NODE_'):
                        node_id = k[10:]
                        self.numa_nodes[node_id] = v
                    elif k == 'IS_AMD':
                        self.is_amd = v.lower() == 'true'
                    elif k == 'LOGICAL_CORE_OPTIONS':
                        self.logical_core_options = v.split('!') if v else []
                    elif k == 'LOCALE_LIST':
                        self.locale_options = v.split('!') if v else []
                    continue
                if line_stripped.startswith('PW_'):
                    parts = line_stripped.split(maxsplit=1)
                    key = parts[0]
                    self.available_keys.add(key)
                    if len(parts) > 1 and 'blocked' in parts[1]:
                        self.blocked_keys.add(key)

            self.available_keys &= set(self.toggle_settings.keys())

        process = QProcess(self)
        process.finished.connect(self.on_show_ppdb_finished)
        args = self._get_process_args(["cli", "--show-ppdb", f"{self.exe_path}"])
        process.start(args[0], args[1:])

    def on_show_ppdb_finished(self, exit_code, exit_status):
        """Handle --show-ppdb output."""
        process = cast(QProcess, self.sender())
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            for key in self.toggle_settings:
                self.current_settings[key] = '0'
            for adv_key in ADVANCED_SETTING_KEYS:
                self.current_settings[adv_key] = 'disabled' if any(
                    x in adv_key for x in ['TOPOLOGY', 'SELECT', 'MODE', 'LEVEL', 'GL_VERSION', 'NUMA']
                ) else ''
            for key in MANGOHUD_ENV_KEYS:
                self.current_settings[key] = ''
        else:
            output = bytes(process.readAllStandardOutput().data()).decode('utf-8', 'ignore').strip()
            self.current_settings = {}
            for line in output.split('\n'):
                line_stripped = line.strip()
                if '=' in line_stripped:
                    try:
                        key, val = line_stripped.split('=', 1)
                        if key in self.toggle_settings or key in ADVANCED_SETTING_KEYS or key in MANGOHUD_ENV_KEYS:
                            if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                                val = val[1:-1]
                            self.current_settings[key] = val
                    except ValueError:
                        continue

        for key in self.blocked_keys:
            self.current_settings[key] = '0'

        current_wine_version = self.current_settings.get('PW_WINE_USE')
        if current_wine_version and current_wine_version not in self.dist_options:
            self.dist_options.append(current_wine_version)

        self.original_values = self.current_settings.copy()
        for key in set(self.toggle_settings.keys()):
            self.original_values.setdefault(key, '0')

        self.populate_table()
        self.populate_advanced()
        self.populate_mangohud()

        self.settings_container.setCurrentIndex(1)
        self.advanced_container.setCurrentIndex(1)

    def open_ppdb_file(self):
        """Open the PPDB file for the current executable."""
        if not self.exe_path:
            QMessageBox.critical(self, _("Error"), _("Executable path is not available."))
            return

        db_path = self.exe_path + ".ppdb"

        if not os.path.exists(db_path):
            QMessageBox.critical(self, _("Error"), _("PPDB file does not exist at: ") + db_path)
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(db_path)):
            QMessageBox.critical(self, _("Error"), _("Failed to open PPDB file:\n") + db_path)

    def populate_table(self):
        """Populate the table with settings."""
        self.settings_table.setRowCount(0)
        self.value_widgets.clear()
        self.settings_table.verticalHeader().setVisible(False)

        visible_keys = sorted(self.available_keys) if self.available_keys else sorted(self.toggle_settings.keys())

        for toggle in visible_keys:
            description = self.toggle_settings.get(toggle)
            if not description:
                continue

            row = self.settings_table.rowCount()
            self.settings_table.insertRow(row)

            name_item = QTableWidgetItem(format_setting_name_for_display(toggle))
            name_item.setData(Qt.ItemDataRole.UserRole, toggle)
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            current_val = self.current_settings.get(toggle, '0')
            is_blocked = toggle in self.blocked_keys
            checkbox = QTableWidgetItem()
            check_state = Qt.CheckState.Checked if current_val == '1' and not is_blocked else Qt.CheckState.Unchecked
            checkbox.setCheckState(check_state)
            if is_blocked:
                checkbox.setFlags(checkbox.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                checkbox.setBackground(QColor(240, 240, 240))
                name_item.setForeground(QColor(128, 128, 128))
            self.settings_table.setItem(row, 1, checkbox)

            desc_item = QTableWidgetItem(description)
            desc_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if is_blocked:
                desc_item.setForeground(QColor(128, 128, 128))
            self.settings_table.setItem(row, 2, desc_item)

            self.settings_table.setItem(row, 0, name_item)
            self.value_widgets[(row, 1)] = checkbox

        self.settings_table.resizeRowsToContents()
        if self.settings_table.rowCount() > 0:
            self.settings_table.setCurrentCell(0, 0)
            self.settings_table.setFocus(Qt.FocusReason.OtherFocusReason)

        self.on_table_selection_changed()

    def populate_advanced(self):
        """Populate the advanced tab with table format."""
        self.advanced_table.setRowCount(0)
        self.advanced_widgets.clear()
        self.original_display_values = {}
        self.value_mapping = {}
        self.advanced_table.verticalHeader().setVisible(False)

        current = self.current_settings
        disabled_text = _('disabled')

        advanced_settings = get_advanced_settings(
            disabled_text=disabled_text,
            logical_core_options=self.logical_core_options,
            locale_options=self.locale_options,
            numa_nodes=self.numa_nodes,
            dist_options=self.dist_options,
            prefix_options=self.prefix_options
        )

        for setting in advanced_settings:
            row = self.advanced_table.rowCount()
            self.advanced_table.insertRow(row)
            is_blocked = setting.get("type") == "combo" and len(setting.get("options", [])) == 1

            name_item = QTableWidgetItem(setting['name'])
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.advanced_table.setItem(row, 0, name_item)

            if setting['type'] == 'combo':
                combo = QComboBox()
                combo.addItems(setting['options'])

                current_raw = current.get(setting['key'], setting['default'])
                if setting['key'] == 'PW_WINE_CPU_TOPOLOGY':
                    current_val = disabled_text if current_raw == 'disabled' else (
                        current_raw.split(':')[0] if isinstance(current_raw, str) and ':' in current_raw else current_raw
                    )
                elif setting['key'] == 'PW_WINE_USE':
                    current_val = _('System WINE') if current_raw == 'USE_SYSTEM_WINE' else current_raw
                else:
                    current_val = disabled_text if current_raw == 'disabled' else current_raw

                if '_value_map' in setting:
                    reverse_map = {v: k for k, v in setting['_value_map'].items()}
                    if current_raw in reverse_map:
                        current_val = reverse_map[current_raw]

                if current_val and current_val not in setting['options']:
                    combo.addItem(current_val)
                combo.setCurrentText(current_val)

                if is_blocked:
                    combo.setEnabled(False)
                    name_item.setForeground(QColor(128, 128, 128))

                combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

                self.advanced_table.setCellWidget(row, 1, combo)
                self.advanced_widgets[setting['key']] = combo

                if '_value_map' in setting:
                    reverse_map = {v: k for k, v in setting['_value_map'].items()}
                    if current_raw in reverse_map:
                        self.original_display_values[setting['key']] = reverse_map[current_raw]
                    else:
                        self.original_display_values[setting['key']] = current_val
                else:
                    self.original_display_values[setting['key']] = current_val

                if '_value_map' in setting:
                    reverse_map = {v: k for k, v in setting['_value_map'].items()}
                    self.value_mapping[setting['key']] = {
                        'forward': setting['_value_map'],
                        'reverse': reverse_map
                    }

            elif setting['type'] == 'text':
                line_edit = QLineEdit()
                current_val = current.get(setting['key'], setting['default'])
                line_edit.setText(current_val)

                if is_blocked:
                    line_edit.setEnabled(False)
                    line_edit.setStyleSheet("background-color: #f0f0f0;")

                self.advanced_table.setCellWidget(row, 1, line_edit)
                self.advanced_widgets[setting['key']] = line_edit
                self.original_display_values[setting['key']] = current_val

            desc_item = QTableWidgetItem(setting['description'])
            desc_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if is_blocked:
                desc_item.setForeground(QColor(128, 128, 128))
            self.advanced_table.setItem(row, 2, desc_item)

        if self.advanced_table.rowCount() > 0:
            self.on_table_selection_changed()

    def setup_mangohud_tab(self):
        """Create MangoHud tab widgets."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._add_mangohud_values_group(layout)
        self._add_mangohud_presets_group(layout)
        self._add_mangohud_toggle_group(layout)
        self._add_mangohud_fps_group(layout)
        self._add_mangohud_extra_group(layout)
        layout.addStretch()

        scroll.setWidget(container)

        self.mangohud_tab_layout.addWidget(scroll)

    def _add_mangohud_values_group(self, parent_layout):
        """Add MangoHud value controls."""
        group = QGroupBox(_("Layout and limiter"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        form = QFormLayout(group)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for spec in MANGOHUD_VALUE_SPECS:
            if spec['key'] == 'fps_limit_method':
                continue
            form.addRow(spec['label'], self._create_mangohud_value_widget(spec))

        parent_layout.addWidget(group)

    def _create_mangohud_value_widget(self, spec):
        """Create a MangoHud value widget."""
        widget = QComboBox()
        options = spec['options']
        if spec['key'] == 'network':
            options = self._get_mangohud_network_options()
        if spec['key'] == 'gpu_list':
            for text, value in self._get_mangohud_gpu_options():
                widget.addItem(text, value)
        else:
            value_translations = MANGOHUD_VALUE_OPTION_TRANSLATIONS.get(spec['key'], {})
            for option in options:
                widget.addItem(value_translations.get(option, option), option)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.setMinimumHeight(40)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        default_value = MANGOHUD_VALUE_DEFAULTS.get(spec['key'], '')
        default_index = widget.findData(default_value)
        if default_value and default_index >= 0:
            widget.setCurrentIndex(default_index)
        else:
            widget.setCurrentIndex(0)
        self.mangohud_widgets[spec['key']] = widget
        return widget

    def _add_mangohud_presets_group(self, parent_layout):
        """Add preset buttons for common MangoHud layouts."""
        group = QGroupBox(_("Quick presets"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QGridLayout(group)
        layout.setSpacing(10)
        columns = 2

        buttons = [
            (_("PortProton default"), self.apply_portproton_default_mangohud),
            (_("FPS only"), lambda: self.apply_mangohud_button_preset('fps_only')),
            (_("Compact"), lambda: self.apply_mangohud_button_preset('compact')),
            (_("Extended"), lambda: self.apply_mangohud_button_preset('extended')),
            (_("Custom"), lambda: self.apply_mangohud_button_preset('custom')),
            (_("Save custom"), self.save_custom_mangohud_preset),
            (_("Clear"), lambda: self.apply_mangohud_button_preset('clear')),
        ]

        for index, (label, handler) in enumerate(buttons):
            button = QPushButton(label)
            button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
            button.setMinimumHeight(44)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(handler)
            row = index // columns
            column = index % columns
            layout.addWidget(button, row, column)

        parent_layout.addWidget(group)

    def _add_mangohud_toggle_group(self, parent_layout):
        """Add categorized MangoHud toggle checkboxes."""
        selector_group = QGroupBox(_("MangoHud switches"))
        selector_group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        selector_layout = QVBoxLayout(selector_group)

        self.mangohud_category_combo = QComboBox()
        self.mangohud_category_combo.addItems(list(MANGOHUD_TOGGLE_CATEGORIES.keys()))
        self.mangohud_category_combo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.mangohud_category_combo.setMinimumHeight(40)
        self.mangohud_category_combo.currentTextChanged.connect(self.on_mangohud_category_changed)
        selector_layout.addWidget(self.mangohud_category_combo)

        self.mangohud_category_stack = QStackedWidget()
        self.mangohud_category_stack.setStyleSheet("background: transparent;")
        selector_layout.addWidget(self.mangohud_category_stack)

        toggle_lookup = dict(MANGOHUD_TOGGLE_SPECS)
        uncategorized = set(toggle_lookup.keys())

        for category, keys in MANGOHUD_TOGGLE_CATEGORIES.items():
            category_widget = QWidget()
            layout = QGridLayout(category_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(16)
            layout.setVerticalSpacing(10)

            for index, key in enumerate(keys):
                if key not in toggle_lookup:
                    continue
                label = toggle_lookup[key]
                checkbox = self._create_mangohud_checkbox(label)
                row = index // 4
                column = index % 4
                layout.addWidget(checkbox, row, column)
                self.mangohud_toggle_widgets[key] = checkbox
                self.mangohud_toggle_widget_keys[checkbox] = key
                uncategorized.discard(key)

            self.mangohud_category_groups[category] = category_widget
            self.mangohud_category_stack.addWidget(category_widget)

        if uncategorized:
            category_widget = QWidget()
            layout = QGridLayout(category_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(16)
            layout.setVerticalSpacing(10)

            for index, key in enumerate(sorted(uncategorized)):
                label = toggle_lookup[key]
                checkbox = self._create_mangohud_checkbox(label)
                row = index // 4
                column = index % 4
                layout.addWidget(checkbox, row, column)
                self.mangohud_toggle_widgets[key] = checkbox
                self.mangohud_toggle_widget_keys[checkbox] = key

            self.mangohud_category_combo.addItem(_("Other"))
            self.mangohud_category_groups[_("Other")] = category_widget
            self.mangohud_category_stack.addWidget(category_widget)

        self._update_mangohud_category_stack_height()
        parent_layout.addWidget(selector_group)

    def _add_mangohud_fps_group(self, parent_layout):
        """Add FPS limit presets."""
        group = QGroupBox(_("FPS limit"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        fps_limit_method_spec = next(
            (spec for spec in MANGOHUD_VALUE_SPECS if spec['key'] == 'fps_limit_method'),
            None,
        )
        if fps_limit_method_spec:
            form = QFormLayout()
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            form.addRow(
                fps_limit_method_spec['label'],
                self._create_mangohud_value_widget(fps_limit_method_spec),
            )
            layout.addLayout(form)

        label = QLabel(_(
            "Select one or more FPS presets. The values are saved into FPS_LIMIT "
            "and MangoHud will also show the active FPS limit."
        ))
        label.setWordWrap(True)
        layout.addWidget(label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        for index, fps in enumerate(MANGOHUD_FPS_OPTIONS):
            checkbox = QCheckBox(fps)
            checkbox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            checkbox.setMinimumHeight(36)
            checkbox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE + """
                QCheckBox {
                    spacing: 10px;
                    padding: 4px 2px;
                }
            """)
            row = index // 4
            column = index % 4
            grid.addWidget(checkbox, row, column)
            self.mangohud_fps_widgets[fps] = checkbox

        layout.addLayout(grid)
        parent_layout.addWidget(group)

    def _add_mangohud_extra_group(self, parent_layout):
        """Add raw config field for unsupported MangoHud parameters."""
        group = QGroupBox(_("Extra config"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QVBoxLayout(group)
        label = QLabel(_("Additional comma-separated MangoHud options not covered by the GUI."))
        label.setWordWrap(True)
        # label.setStyleSheet("background: transparent; color: inherit;")
        layout.addWidget(label)
        self.mangohud_extra_edit = QLineEdit()
        self.mangohud_extra_edit.setPlaceholderText(_("Example: battery,gpu_junction_temp,fps_color=39f900"))
        self.mangohud_extra_edit.setMinimumHeight(40)
        self.mangohud_extra_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mangohud_extra_edit.installEventFilter(self)
        self.mangohud_extra_edit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        layout.addWidget(self.mangohud_extra_edit)
        parent_layout.addWidget(group)

    def _get_mangohud_network_options(self) -> list[str]:
        """Get available network interfaces for MangoHud network option."""
        options = ['']
        net_class_path = '/sys/class/net'
        try:
            if not os.path.isdir(net_class_path):
                return options

            interfaces = sorted(
                iface for iface in os.listdir(net_class_path)
                if iface and iface != 'lo'
            )
            options.extend(interfaces)
        except OSError as e:
            logger.warning("Failed to read network interfaces: %s", e)

        if len(options) == 1:
            options.append('eth0')
        return options

    def _get_mangohud_gpu_options(self) -> list[tuple[str, str]]:
        """Get available GPU options for MangoHud gpu_list value."""
        options = [('', '')]
        vk_gpu_info_output = get_cached_vk_gpu_info()
        if not vk_gpu_info_output:
            return options

        gpu_entries = []
        for gpu_block in vk_gpu_info_output.split("GPU #")[1:]:
            lines = [line.strip() for line in gpu_block.splitlines() if line.strip()]
            if not lines:
                continue
            gpu_id = lines[0].rstrip(':')
            if not gpu_id.isdigit():
                continue
            gpu_props = {
                key.strip(): value.strip()
                for line in lines[1:] if ':' in line
                for key, value in [line.split(':', 1)]
            }
            device_name = gpu_props.get('device_name', '').strip()
            device_type = gpu_props.get('device_type', '').strip()
            if device_type in {'CPU', 'VIRTUAL_GPU'}:
                continue
            if not device_name:
                continue
            gpu_entries.append((gpu_id, device_name))

        if not gpu_entries:
            return options

        all_gpu_ids = ','.join(gpu_id for gpu_id, _name in gpu_entries)
        options.append((_("All GPUs"), all_gpu_ids))
        for gpu_id, device_name in gpu_entries:
            options.append((device_name, gpu_id))

        return options

    def _create_mangohud_checkbox(self, label):
        """Create a styled MangoHud checkbox."""
        checkbox = QCheckBox(label)
        checkbox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        checkbox.setMinimumHeight(36)
        checkbox.installEventFilter(self)
        checkbox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE + """
            QCheckBox {
                spacing: 10px;
                padding: 4px 2px;
            }
        """)
        return checkbox

    def on_mangohud_category_changed(self, category):
        """Switch visible MangoHud toggle category."""
        widget = self.mangohud_category_groups.get(category)
        if widget:
            self.mangohud_category_stack.setCurrentWidget(widget)
            self._update_mangohud_category_stack_height()

    def _show_mangohud_toggle_tooltip(self, checkbox):
        """Show gamepad tooltip for MangoHud toggle checkbox."""
        key = self.mangohud_toggle_widget_keys.get(checkbox)
        if not key:
            return
        text = MANGOHUD_TOGGLE_DESCRIPTIONS.get(key, "")
        if not text:
            self.show_gamepad_tooltip(show=False)
            return
        self.show_gamepad_tooltip(show=True, text=text, anchor_widget=checkbox)

    def _on_focus_changed(self, _old, new):
        """Track focused MangoHud toggle checkbox and show tooltip."""
        if isinstance(new, QCheckBox) and new in self.mangohud_toggle_widget_keys:
            self._show_mangohud_toggle_tooltip(new)
            return
        if self.tab_widget.currentIndex() == 2:
            self.show_gamepad_tooltip(show=False)

    def _update_mangohud_category_stack_height(self):
        """Update MangoHud category block height to current visible page."""
        current_widget = self.mangohud_category_stack.currentWidget()
        if not current_widget:
            return
        target_height = current_widget.sizeHint().height()
        if target_height > 0:
            self.mangohud_category_stack.setMinimumHeight(target_height)
            self.mangohud_category_stack.setMaximumHeight(target_height)


    def populate_mangohud(self):
        """Populate MangoHud tab from current settings."""
        parsed_config, raw_tokens = self._parse_mangohud_config(
            self.current_settings.get('MANGOHUD_CONFIG', '')
        )
        visible_raw_tokens, hidden_raw_tokens = self._split_mangohud_extra_tokens(raw_tokens)

        for spec in MANGOHUD_VALUE_SPECS:
            self._set_mangohud_value_widget(spec, parsed_config.get(spec['key']))

        for key, _label in MANGOHUD_TOGGLE_SPECS:
            checkbox = self.mangohud_toggle_widgets[key]
            checkbox.setChecked(self._mangohud_bool_value(parsed_config.get(key), False))

        fps_limit_values = self._get_mangohud_fps_values(parsed_config)
        for fps, checkbox in self.mangohud_fps_widgets.items():
            checkbox.setChecked(fps in fps_limit_values)

        self.mangohud_hidden_extra_tokens = hidden_raw_tokens
        self.mangohud_extra_edit.setText(', '.join(visible_raw_tokens))
        self.mangohud_original_values = {
            'MANGOHUD_CONFIG': self.current_settings.get('MANGOHUD_CONFIG', ''),
            'FPS_LIMIT': self.current_settings.get('FPS_LIMIT', ''),
        }
        self.mangohud_original_values['extra'] = ', '.join(visible_raw_tokens)

    def apply_portproton_default_mangohud(self):
        """Apply MangoHud defaults from PortProton var file."""
        default_config = self._get_default_mangohud_config()
        if default_config is None:
            QMessageBox.warning(self, _("Error"), _("Failed to read default MangoHud config."))
            return
        self._apply_mangohud_config_to_widgets(default_config, '')

    def apply_mangohud_button_preset(self, preset_name):
        """Apply a built-in MangoHud preset button."""
        if preset_name == 'custom':
            preset = self._load_custom_mangohud_preset()
            if preset is None:
                QMessageBox.information(self, _("Info"), _("Custom preset is empty. Save one first."))
                return
            self._apply_mangohud_config_to_widgets(preset['config'], preset['fps_limit'])
            return
        preset = MANGOHUD_BUTTON_PRESETS[preset_name]
        self._apply_mangohud_config_to_widgets(preset['config'], preset['fps_limit'], preset['toggles'])

    def save_custom_mangohud_preset(self):
        """Save current MangoHud settings as custom preset."""
        preset = {
            'config': self._build_mangohud_config(),
            'fps_limit': '+'.join(
                fps for fps, checkbox in self.mangohud_fps_widgets.items() if checkbox.isChecked()
            ),
        }
        cp = configparser.ConfigParser()
        try:
            if CONFIG_FILE.exists():
                cp.read(CONFIG_FILE, encoding='utf-8')
            if 'MangoHudPresets' not in cp:
                cp['MangoHudPresets'] = {}
            cp['MangoHudPresets']['custom_config'] = preset['config']
            cp['MangoHudPresets']['custom_fps_limit'] = preset['fps_limit']
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                cp.write(f)
            QMessageBox.information(self, _("Success"), _("Custom preset saved."))
        except Exception as e:
            logger.warning("Failed to save custom MangoHud preset: %s", e)
            QMessageBox.warning(self, _("Error"), _("Failed to save custom preset."))

    def _load_custom_mangohud_preset(self):
        """Load custom MangoHud preset from config file."""
        cp = configparser.ConfigParser()
        try:
            if not CONFIG_FILE.exists():
                return None
            cp.read(CONFIG_FILE, encoding='utf-8')
            if not cp.has_section('MangoHudPresets'):
                return None
            custom_config = cp.get('MangoHudPresets', 'custom_config', fallback='').strip()
            custom_fps_limit = cp.get('MangoHudPresets', 'custom_fps_limit', fallback='').strip()
            if not custom_config and not custom_fps_limit:
                return None
            return {
                'config': custom_config,
                'fps_limit': custom_fps_limit,
            }
        except Exception as e:
            logger.warning("Failed to load custom MangoHud preset: %s", e)
            return None

    def _apply_mangohud_config_to_widgets(self, config_text, fps_limit, forced_toggles=None):
        """Apply MangoHud config text to the tab widgets."""
        parsed_config, raw_tokens = self._parse_mangohud_config(config_text)
        visible_raw_tokens, hidden_raw_tokens = self._split_mangohud_extra_tokens(raw_tokens)

        for spec in MANGOHUD_VALUE_SPECS:
            self._set_mangohud_value_widget(spec, parsed_config.get(spec['key']))

        enabled_toggles = forced_toggles if forced_toggles is not None else set()
        for key, _label in MANGOHUD_TOGGLE_SPECS:
            checkbox = self.mangohud_toggle_widgets[key]
            checkbox.setChecked(
                key in enabled_toggles or self._mangohud_bool_value(parsed_config.get(key), False)
            )

        fps_values = {value.strip() for value in fps_limit.replace('+', ',').split(',') if value.strip()}
        for fps, checkbox in self.mangohud_fps_widgets.items():
            checkbox.setChecked(fps in fps_values)

        self.mangohud_hidden_extra_tokens = hidden_raw_tokens
        self.mangohud_extra_edit.setText(', '.join(visible_raw_tokens))

    def _split_mangohud_extra_tokens(self, raw_tokens):
        """Split hidden MangoHud extra tokens from visible ones."""
        visible_tokens = []
        hidden_tokens = []
        for token in raw_tokens:
            key = token.split('=', 1)[0].strip()
            if key in MANGOHUD_HIDDEN_EXTRA_KEYS:
                hidden_tokens.append(token)
            else:
                visible_tokens.append(token)
        return visible_tokens, hidden_tokens

    def _set_mangohud_value_widget(self, spec, value):
        """Apply parsed value to a MangoHud value widget."""
        widget = self.mangohud_widgets[spec['key']]
        text = value if isinstance(value, str) else ''
        index = widget.findData(text)
        if text and index < 0:
            widget.addItem(text, text)
            index = widget.findData(text)
        if text:
            widget.setCurrentIndex(index)
        else:
            default_value = MANGOHUD_VALUE_DEFAULTS.get(spec['key'], '')
            default_index = widget.findData(default_value)
            if default_value and default_index >= 0:
                widget.setCurrentIndex(default_index)
            else:
                widget.setCurrentIndex(0)

    def _mangohud_bool_value(self, value, default_enabled):
        """Convert a MangoHud token to checkbox state."""
        if value is None:
            return default_enabled
        if value is True:
            return True
        return str(value).lower() not in {'0', 'false', 'no', 'off', 'disabled'}

    def _parse_mangohud_config(self, config_text):
        """Parse MANGOHUD_CONFIG into known values and raw tokens."""
        known_keys = {key for key, label in MANGOHUD_TOGGLE_SPECS}
        known_keys.update(spec['key'] for spec in MANGOHUD_VALUE_SPECS)
        known_keys.add('fps_limit')
        bool_keys = {key for key, label in MANGOHUD_TOGGLE_SPECS}
        parsed = {}
        raw_tokens = []
        current_key = None
        current_value = None

        for part in [token.strip() for token in config_text.split(',') if token.strip()]:
            if '=' in part:
                if current_key is not None:
                    self._store_mangohud_token(current_key, current_value, known_keys, parsed, raw_tokens)
                current_key, current_value = self._split_mangohud_token(part)
                continue

            if current_key is not None and part not in bool_keys:
                current_value = f"{current_value},{part}"
                continue

            if current_key is not None:
                self._store_mangohud_token(current_key, current_value, known_keys, parsed, raw_tokens)
                current_key = None
                current_value = None

            self._store_mangohud_token(part, True, known_keys, parsed, raw_tokens)

        if current_key is not None:
            self._store_mangohud_token(current_key, current_value, known_keys, parsed, raw_tokens)

        return parsed, raw_tokens

    def _split_mangohud_token(self, token):
        """Split a MangoHud token into key and value."""
        if '=' not in token:
            return token, True
        key, value = token.split('=', 1)
        return key.strip(), value.strip()

    def _store_mangohud_token(self, key, value, known_keys, parsed, raw_tokens):
        """Store a parsed MangoHud token in known or raw collections."""
        if key in known_keys:
            parsed[key] = value
            return
        raw_tokens.append(key if value is True else f"{key}={value}")

    def _build_mangohud_config(self):
        """Build MANGOHUD_CONFIG from the MangoHud tab."""
        tokens = []
        for spec in MANGOHUD_VALUE_SPECS:
            token = self._build_mangohud_value_token(spec)
            if token:
                tokens.append(token)

        for key, _label in MANGOHUD_TOGGLE_SPECS:
            token = self._build_mangohud_toggle_token(key)
            if token:
                tokens.append(token)

        fps_limit = '+'.join(
            fps for fps, checkbox in self.mangohud_fps_widgets.items() if checkbox.isChecked()
        )
        if fps_limit:
            if 'show_fps_limit' not in [key for key, label in MANGOHUD_TOGGLE_SPECS if self.mangohud_toggle_widgets[key].isChecked()]:
                tokens.append('show_fps_limit')
            tokens.append(f'fps_limit={fps_limit}')

        extra_text = self.mangohud_extra_edit.text().strip(' ,')
        if extra_text:
            tokens.append(extra_text)
        if self.mangohud_hidden_extra_tokens:
            tokens.extend(self.mangohud_hidden_extra_tokens)
        return ','.join(tokens)

    def _build_mangohud_toggle_token(self, key):
        """Build one MangoHud toggle token from a checkbox."""
        if self.mangohud_toggle_widgets[key].isChecked():
            return key
        return ''

    def _build_mangohud_value_token(self, spec):
        """Build one MangoHud value token."""
        widget = self.mangohud_widgets[spec['key']]
        value = str(widget.currentData()).strip()
        if not value:
            value = widget.currentText().strip()
        if not value:
            return ''
        parsed_original, _raw_tokens = self._parse_mangohud_config(
            self.mangohud_original_values.get('MANGOHUD_CONFIG', '')
        )
        key = spec['key']
        default_value = MANGOHUD_VALUE_DEFAULTS.get(key, '')
        if key not in parsed_original and default_value and value == default_value:
            return ''
        return f"{spec['key']}={value}"

    def _get_mangohud_fps_values(self, parsed_config):
        """Get FPS limit values from settings."""
        fps_limit = self.current_settings.get('FPS_LIMIT', '').strip()
        if not fps_limit:
            fps_limit = parsed_config.get('fps_limit', '')
        return {value.strip() for value in fps_limit.replace('+', ',').split(',') if value.strip()}

    def _collect_mangohud_changes(self):
        """Collect MangoHud-specific changes."""
        changes = []
        config_value = self._build_mangohud_config()
        if config_value != self.mangohud_original_values.get('MANGOHUD_CONFIG', ''):
            changes.append(f"MANGOHUD_CONFIG={config_value}")

        fps_limit = '+'.join(fps for fps, checkbox in self.mangohud_fps_widgets.items() if checkbox.isChecked())
        if fps_limit != self.mangohud_original_values.get('FPS_LIMIT', ''):
            changes.append(f"FPS_LIMIT={fps_limit}")

        return changes

    def init_virtual_keyboard(self):
        """Initialize virtual keyboard."""
        self.keyboard = VirtualKeyboard(self, theme=self.theme, button_width=50)
        self.keyboard.hide()
        self.keyboard.current_input_widget = None

    def show_virtual_keyboard(self, widget=None):
        """Show virtual keyboard for search or text input."""
        if not widget:
            widget = self.search_edit

        if not widget or not widget.isVisible():
            return

        self.keyboard.current_input_widget = widget

        keyboard_height = 220
        self.keyboard.setFixedWidth(self.width())
        self.keyboard.setFixedHeight(keyboard_height)
        self.keyboard.move(0, self.height() - keyboard_height)

        self.keyboard.setParent(self)
        self.keyboard.show()
        self.keyboard.raise_()

        first_button = self.keyboard.findFirstFocusableButton()
        if first_button:
            focused_widget = QApplication.focusWidget()
            if focused_widget and focused_widget != self.keyboard:
                focused_widget.clearFocus()
            QTimer.singleShot(50, lambda: first_button.setFocus())

    def filter_settings(self, text):
        """Filter settings based on search text."""
        search_text = text.lower()
        for row in range(self.settings_table.rowCount()):
            name_item = self.settings_table.item(row, 0)
            desc_item = self.settings_table.item(row, 2)
            should_show = False

            if name_item and search_text in name_item.text().lower():
                should_show = True
            elif desc_item and search_text in desc_item.text().lower():
                should_show = True

            self.settings_table.setRowHidden(row, not should_show)

        for row in range(self.advanced_table.rowCount()):
            name_item = self.advanced_table.item(row, 0)
            desc_item = self.advanced_table.item(row, 2)
            should_show = False

            if name_item and search_text in name_item.text().lower():
                should_show = True
            elif desc_item and search_text in desc_item.text().lower():
                should_show = True

            self.advanced_table.setRowHidden(row, not should_show)

        self._filter_mangohud_settings(search_text)

    def _filter_mangohud_settings(self, search_text):
        """Filter MangoHud groups based on search text."""
        for group_box in self.mangohud_tab.findChildren(QGroupBox):
            if not search_text:
                group_box.setVisible(True)
                continue
            group_text = group_box.title().lower()
            label_text = ' '.join(widget.text().lower() for widget in group_box.findChildren(QLabel))
            checkbox_text = ' '.join(widget.text().lower() for widget in group_box.findChildren(QCheckBox))
            content_text = f"{label_text} {checkbox_text}"
            group_box.setVisible(search_text in group_text or search_text in content_text)

    def _get_default_mangohud_config(self) -> str | None:
        """Read DEFAULT_MANGOHUD_CONFIG from portproton_path/data/scripts/var.

        Returns:
            The value of DEFAULT_MANGOHUD_CONFIG without the 'DEFAULT_' prefix,
            or None if not found.
        """
        if not self.portproton_path:
            logger.warning("PortProton path not set")
            return None

        var_path = os.path.join(self.portproton_path, "data", "scripts", "var")
        if not os.path.exists(var_path):
            logger.warning("var file not found: %s", var_path)
            return None

        try:
            with open(var_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export DEFAULT_MANGOHUD_CONFIG="):
                        # Extract value: export DEFAULT_MANGOHUD_CONFIG="value"
                        match = re.match(r'^export DEFAULT_MANGOHUD_CONFIG=(.*)$', line)
                        if match:
                            value = match.group(1).strip().strip('"\'')
                            # Remove 'DEFAULT_' prefix from the value if present
                            if value.startswith("DEFAULT_"):
                                value = value[8:]
                            return value
        except Exception as e:
            logger.warning("Failed to read var file: %s", e)

        return None

    def apply_changes(self):
        """Apply changes by collecting diffs from both main and advanced tabs."""
        changes = []
        mangohud_enabled = False

        for key, orig_val in self.original_values.items():
            if key in self.blocked_keys:
                continue
            row = -1
            for r in range(self.settings_table.rowCount()):
                item0 = self.settings_table.item(r, 0)
                if item0 and item0.data(Qt.ItemDataRole.UserRole) == key:
                    row = r
                    break
            if row == -1:
                continue

            item = self.settings_table.item(row, 1)
            if not item:
                continue

            new_val = '1' if item.checkState() == Qt.CheckState.Checked else '0'
            if new_val != orig_val:
                changes.append(f"{key}={new_val}")
                # Track if PW_MANGOHUD is being enabled
                if key == 'PW_MANGOHUD' and new_val == '1':
                    mangohud_enabled = True

        for key, widget in self.advanced_widgets.items():
            orig_val = self.original_display_values.get(key, '')
            if isinstance(widget, QComboBox):
                new_val = widget.currentText()

                if key in self.value_mapping and 'forward' in self.value_mapping[key]:
                    value_map = self.value_mapping[key]['forward']
                    has_changed = (new_val != orig_val)
                    if new_val in value_map:
                        new_val = value_map[new_val]
                else:
                    has_changed = (new_val != orig_val)

                if key == 'PW_WINE_USE' and new_val == _('System WINE'):
                    new_val = 'USE_SYSTEM_WINE'

                if new_val.lower() == _('disabled').lower():
                    new_val = 'disabled'

                if has_changed:
                    changes.append(f"{key}={new_val}")

            elif isinstance(widget, QLineEdit):
                new_val = widget.text().strip()
                if new_val != orig_val:
                    changes.append(f"{key}={new_val}")
            else:
                continue

        changes.extend(self._collect_mangohud_changes())

        # If PW_MANGOHUD is being enabled and MANGOHUD_CONFIG is not in current settings,
        # add it from the var file
        has_mangohud_config_change = any(change.startswith("MANGOHUD_CONFIG=") for change in changes)
        if mangohud_enabled and 'MANGOHUD_CONFIG' not in self.current_settings and not has_mangohud_config_change:
            default_config = self._get_default_mangohud_config()
            if default_config:
                changes.append(f"MANGOHUD_CONFIG={default_config}")
                logger.info("Added MANGOHUD_CONFIG from var file: %s", default_config)

        if not changes:
            QMessageBox.information(self, _("Info"), _("No changes to apply."))
            return

        process = QProcess(self)
        process.finished.connect(self.on_edit_db_finished)
        process_args = ["cli", "--edit-db", self.exe_path] + changes
        args = self._get_process_args(process_args)
        process.start(args[0], args[1:])
        self.apply_button.setEnabled(False)

    def on_edit_db_finished(self, exit_code, exit_status):
        """Handle --edit-db output."""
        process = cast(QProcess, self.sender())
        self.apply_button.setEnabled(True)
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            error_output = bytes(process.readAllStandardError().data()).decode('utf-8', 'ignore')
            QMessageBox.warning(self, _("Error"), _("Failed to apply changes. Check logs."))
            logger.error(f"Failed to apply changes: {error_output}")
        else:
            self.load_current_settings()
            QMessageBox.information(self, _("Success"), _("Settings updated successfully."))

    def keyPressEvent(self, event):
        """Override key press event to handle combo box interaction properly."""
        focused_widget = QApplication.focusWidget()
        if (event.key() == Qt.Key.Key_Escape and
            isinstance(focused_widget, QComboBox) and
            focused_widget.view().isVisible()):
            focused_widget.hidePopup()
            self.advanced_table.setFocus()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if hasattr(self, 'keyboard') and self.keyboard.isVisible():
            self.keyboard.hide()
        if self.input_manager:
            self.input_manager.disable_settings_mode()
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        mangohud_toggle_widget_keys = getattr(self, 'mangohud_toggle_widget_keys', {})

        if isinstance(obj, QCheckBox) and obj in mangohud_toggle_widget_keys:
            if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self._show_mangohud_toggle_tooltip(obj)
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                focused_widget = QApplication.focusWidget()
                if not (isinstance(focused_widget, QCheckBox) and focused_widget in mangohud_toggle_widget_keys):
                    self.show_gamepad_tooltip(show=False)
        return super().eventFilter(obj, event)

    def show_gamepad_tooltip(self, show=True, text="", anchor_widget=None, anchor_global_pos=None):
        """Show or hide the gamepad tooltip with the provided text."""
        if show and text:
            tooltip_timeout_ms = max(2500, min(12000, 1500 + len(text) * 30))
            self.gamepad_tooltip.setText(text)
            self.gamepad_tooltip.setFixedSize(500, 300)

            font_metrics = self.gamepad_tooltip.fontMetrics()
            max_width = 500

            text_rect = font_metrics.boundingRect(
                0, 0, max_width - 20, 1000,
                Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextExpandTabs,
                text
            )

            required_width = min(max_width, text_rect.width() + 25)
            required_height = min(300, text_rect.height() + 25)

            if anchor_global_pos is not None:
                global_pos = anchor_global_pos
                global_pos.setY(global_pos.y() + 4)

                screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
                if screen:
                    available_rect = screen.availableGeometry()
                    if global_pos.x() + required_width > available_rect.right():
                        global_pos.setX(max(available_rect.left(), available_rect.right() - required_width))
                    if global_pos.x() < available_rect.left():
                        global_pos.setX(available_rect.left())
                    if global_pos.y() + required_height > available_rect.bottom():
                        global_pos.setY(max(available_rect.top(), available_rect.bottom() - required_height))

                self.gamepad_tooltip.setFixedSize(required_width, required_height)
                self.gamepad_tooltip.move(global_pos.x(), global_pos.y())
                self.gamepad_tooltip.setVisible(True)
                self.gamepad_tooltip_timer.start(tooltip_timeout_ms)
                return

            if anchor_widget and anchor_widget.isVisible():
                widget_rect = anchor_widget.rect()
                global_pos = anchor_widget.mapToGlobal(widget_rect.bottomLeft())
                global_pos.setY(global_pos.y() + 4)

                screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
                if screen:
                    available_rect = screen.availableGeometry()
                    if global_pos.x() + required_width > available_rect.right():
                        global_pos.setX(max(available_rect.left(), available_rect.right() - required_width))
                    if global_pos.x() < available_rect.left():
                        global_pos.setX(available_rect.left())
                    if global_pos.y() + required_height > available_rect.bottom():
                        global_pos.setY(max(available_rect.top(), available_rect.bottom() - required_height))

                self.gamepad_tooltip.setFixedSize(required_width, required_height)
                self.gamepad_tooltip.move(global_pos.x(), global_pos.y())
                self.gamepad_tooltip.setVisible(True)
                self.gamepad_tooltip_timer.start(tooltip_timeout_ms)
                return

            current_table = self.advanced_table if self.tab_widget.currentIndex() == 1 else self.settings_table
            if current_table and current_table.currentRow() >= 0 and current_table.currentColumn() >= 0:
                row = current_table.currentRow()
                col = current_table.currentColumn()
                item_rect = current_table.visualRect(current_table.model().index(row, col))
                global_pos = current_table.mapToGlobal(item_rect.bottomLeft())
                global_pos.setY(global_pos.y() + 4)

                screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
                if screen:
                    available_rect = screen.availableGeometry()
                    if global_pos.x() + required_width > available_rect.right():
                        global_pos.setX(max(available_rect.left(), available_rect.right() - required_width))
                    if global_pos.x() < available_rect.left():
                        global_pos.setX(available_rect.left())
                    if global_pos.y() + required_height > available_rect.bottom():
                        global_pos.setY(max(available_rect.top(), available_rect.bottom() - required_height))

                self.gamepad_tooltip.setFixedSize(required_width, required_height)
                self.gamepad_tooltip.move(global_pos.x(), global_pos.y())
                self.gamepad_tooltip.setVisible(True)
                self.gamepad_tooltip_timer.start(tooltip_timeout_ms)
            else:
                self.gamepad_tooltip_timer.stop()
                self.gamepad_tooltip.setVisible(False)
        else:
            self.gamepad_tooltip_timer.stop()
            self.gamepad_tooltip.setVisible(False)

    def get_current_description(self):
        """Get the description text for the currently selected row."""
        current_table = self.advanced_table if self.tab_widget.currentIndex() == 1 else self.settings_table
        if self.tab_widget.currentIndex() == 2:
            return ""
        current_row = current_table.currentRow()
        if current_row >= 0:
            desc_item = current_table.item(current_row, 2)
            if desc_item:
                return desc_item.text()
        return ""

    def on_table_selection_changed(self):
        """Called when table selection changes to update the gamepad tooltip."""
        if self.tab_widget.currentIndex() == 2:
            self.show_gamepad_tooltip(show=False)
            return

        current_table = self.advanced_table if self.tab_widget.currentIndex() == 1 else self.settings_table
        current_column = current_table.currentColumn() if current_table else -1
        if current_column != 2:
            self.show_gamepad_tooltip(show=False)
            return

        description = self.get_current_description()
        if description:
            self.show_gamepad_tooltip(show=True, text=description)
        else:
            self.show_gamepad_tooltip(show=False)

    def on_table_cell_hovered(self, row, column):
        """Show custom tooltip on hover for description cells."""
        if self.tab_widget.currentIndex() == 2 or column != 2:
            self.show_gamepad_tooltip(show=False)
            return

        table = cast(QTableWidget | None, self.sender())
        if table is None:
            self.show_gamepad_tooltip(show=False)
            return

        desc_item = table.item(row, 2)
        description = desc_item.text() if desc_item else ""
        if description:
            item_rect = table.visualRect(table.model().index(row, 2))
            cell_pos = table.mapToGlobal(item_rect.bottomLeft())
            self.show_gamepad_tooltip(show=True, text=description, anchor_global_pos=cell_pos)
        else:
            self.show_gamepad_tooltip(show=False)

    def reject(self):
        if hasattr(self, 'keyboard') and self.keyboard.isVisible():
            self.keyboard.hide()
        self.gamepad_tooltip.setVisible(False)
        if self.input_manager:
            self.input_manager.disable_settings_mode()
        super().reject()

    def accept(self):
        if hasattr(self, 'keyboard') and self.keyboard.isVisible():
            self.keyboard.hide()
        self.gamepad_tooltip.setVisible(False)
        if self.input_manager:
            self.input_manager.disable_settings_mode()
        super().accept()
