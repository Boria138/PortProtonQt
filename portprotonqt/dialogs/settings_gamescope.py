"""Gamescope settings support for executable settings dialog."""

import configparser
import re
import shutil
import subprocess
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.dialogs.settings_mangohud import MANGOHUD_FPS_OPTIONS
from portprotonqt.config import CONFIG_FILE
from portprotonqt.localization import _
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

GAMESCOPE_ENV_KEYS = [
    'PW_GAMESCOPE_ARGS_NEW',
]

COMMON_GAMESCOPE_RESOLUTIONS = [
    (3840, 2160),
    (3440, 1440),
    (2560, 1600),
    (2560, 1440),
    (2048, 1536),
    (1920, 1200),
    (1920, 1080),
    (1680, 1050),
    (1600, 1200),
    (1600, 900),
    (1440, 1080),
    (1440, 900),
    (1400, 1050),
    (1368, 768),
    (1366, 768),
    (1280, 1024),
    (1280, 960),
    (1280, 800),
    (1280, 720),
    (1152, 864),
    (1152, 720),
    (1024, 768),
    (1024, 576),
    (960, 600),
    (928, 580),
    (864, 486),
    (800, 600),
]

GAMESCOPE_TOGGLE_SPECS = [
    ('borderless', _("Borderless window")),
    ('fullscreen', _("Fullscreen window")),
    ('grab', _("Grab keyboard")),
    ('force_grab_cursor', _("Force grab cursor (always relative mouse mode)")),
    ('expose_wayland', _("Expose Wayland")),
    ('rt', _("Use realtime scheduling")),
    ('force_windows_fullscreen', _("Force windows fullscreen")),
    ('hdr_enabled', _("Enable HDR output")),
    ('hdr_itm_enabled', _("Enable SDR→HDR inverse tone mapping")),
    ('hdr_debug_force_support', _("Force HDR support")),
    ('hdr_debug_force_output', _("Force HDR10 PQ output")),
    ('hdr_debug_heatmap', _("HDR luminance heatmap")),
    ('mangoapp', _("Enable mangoapp overlay")),
    ('adaptive_sync', _("Enable adaptive sync")),
]

GAMESCOPE_VALUE_SPECS = [
    {'key': 'output_width', 'label': _("Output width"), 'type': 'text', 'placeholder': 'E.g., 1920'},
    {'key': 'output_height', 'label': _("Output height"), 'type': 'text', 'placeholder': 'E.g., 1080'},
    {'key': 'nested_width', 'label': _("Game width"), 'type': 'text', 'placeholder': 'E.g., 1280'},
    {'key': 'nested_height', 'label': _("Game height"), 'type': 'text', 'placeholder': 'E.g., 720'},
    {'key': 'nested_refresh', 'label': _("Game refresh rate (Hz)"), 'type': 'combo',
     'options': [''] + MANGOHUD_FPS_OPTIONS},
    {'key': 'max_scale', 'label': _("Maximum scale factor"), 'type': 'text', 'placeholder': _('E.g., 5')},
    {'key': 'scaler', 'label': _("Upscaler type"), 'type': 'combo',
     'options': ['', 'auto', 'integer', 'fit', 'fill', 'stretch']},
    {'key': 'filter', 'label': _("Upscaler filter"), 'type': 'combo',
     'options': ['', 'linear', 'nearest', 'fsr', 'nis', 'pixel']},
    {'key': 'sharpness', 'label': _("Upscaler sharpness (0-20)"), 'type': 'text', 'placeholder': _('E.g., 5')},
    {'key': 'mouse_sensitivity', 'label': _("Mouse sensitivity"), 'type': 'text', 'placeholder': _('E.g., 0.5')},
    {'key': 'backend', 'label': _("Rendering backend"), 'type': 'combo',
     'options': ['', 'auto', 'drm', 'sdl', 'headless', 'wayland']},
    {'key': 'ready_fd', 'label': _("Ready FD"), 'type': 'text', 'placeholder': _('E.g., 3')},
    {'key': 'hide_cursor_delay', 'label': _("Hide cursor delay (ms)"), 'type': 'text', 'placeholder': _('E.g., 1000')},
    {'key': 'xwayland_count', 'label': _("XWayland servers count"), 'type': 'text', 'placeholder': _('E.g., 1')},
    {'key': 'force_orientation', 'label': _("Force orientation"), 'type': 'combo',
     'options': ['', 'left', 'right', 'normal', 'upsidedown']},
    {'key': 'cursor_scale_height', 'label': _("Cursor scale height"), 'type': 'text', 'placeholder': _('E.g., 1000')},
    {'key': 'sdr_gamut_wideness', 'label': _("SDR gamut wideness (0-1)"), 'type': 'text', 'placeholder': _('E.g., 0.5')},
    {'key': 'hdr_sdr_content_nits', 'label': _("HDR SDR content nits"), 'type': 'text', 'placeholder': _('E.g., 400')},
    {'key': 'hdr_itm_sdr_nits', 'label': _("HDR ITM SDR nits"), 'type': 'text', 'placeholder': _('E.g., 400')},
    {'key': 'hdr_itm_target_nits', 'label': _("HDR ITM target nits"), 'type': 'text', 'placeholder': _('E.g., 1000')},
    {'key': 'framerate_limit', 'label': _("Framerate limit"), 'type': 'combo',
     'options': [''] + MANGOHUD_FPS_OPTIONS},
    {'key': 'nested_unfocused_refresh', 'label': _("Unfocused refresh rate (Hz)"), 'type': 'combo',
     'options': [''] + MANGOHUD_FPS_OPTIONS},
]

GAMESCOPE_VALUE_DEFAULTS = {
    'output_width': '',
    'output_height': '',
    'nested_width': '',
    'nested_height': '',
    'nested_refresh': '',
    'max_scale': '',
    'scaler': '',
    'filter': '',
    'sharpness': '',
    'mouse_sensitivity': '',
    'backend': '',
    'ready_fd': '',
    'hide_cursor_delay': '',
    'xwayland_count': '',
    'force_orientation': '',
    'cursor_scale_height': '',
    'sdr_gamut_wideness': '',
    'hdr_sdr_content_nits': '',
    'hdr_itm_sdr_nits': '',
    'hdr_itm_target_nits': '',
    'framerate_limit': '',
    'nested_unfocused_refresh': '',
}

GAMESCOPE_SHORT_TOGGLE_ALIASES = {
    'b': 'borderless',
    'f': 'fullscreen',
    'g': 'grab',
}

GAMESCOPE_SHORT_VALUE_ALIASES = {
    'F': 'filter',
    'S': 'scaler',
    'W': 'output_width',
    'H': 'output_height',
    'm': 'max_scale',
    'r': 'framerate_limit',
    's': 'mouse_sensitivity',
    'w': 'nested_width',
    'h': 'nested_height',
}

GAMESCOPE_SHORT_TOGGLE_TOKENS = {
    'borderless': '-b',
    'fullscreen': '-f',
    'grab': '-g',
}

GAMESCOPE_SHORT_VALUE_TOKENS = {
    'filter': '-F',
    'scaler': '-S',
    'output_width': '-W',
    'output_height': '-H',
    'max_scale': '-m',
    'framerate_limit': '-r',
    'mouse_sensitivity': '-s',
    'nested_width': '-w',
    'nested_height': '-h',
}

GAMESCOPE_OPTION_ALIASES = {
    'hdr_itm_enabled': ('hdr-itm-enabled', 'hdr-itm-enable'),
}

GAMESCOPE_OPTION_ALIAS_TO_KEY = {
    alias.replace('-', '_'): key
    for key, aliases in GAMESCOPE_OPTION_ALIASES.items()
    for alias in aliases
}

GAMESCOPE_TOGGLE_CATEGORIES = {
    _("Window"): [
        'borderless', 'fullscreen', 'grab', 'force_grab_cursor',
        'force_windows_fullscreen',
    ],
    _("Platform"): [
        'expose_wayland', 'backend', 'rt',
    ],
    _("HDR"): [
        'hdr_enabled', 'hdr_itm_enabled', 'hdr_debug_force_support',
        'hdr_debug_force_output', 'hdr_debug_heatmap',
    ],
    _("Overlay"): [
        'mangoapp', 'adaptive_sync',
    ],
}

GAMESCOPE_TOGGLE_DESCRIPTIONS = {
    'borderless': _("Make the window borderless"),
    'fullscreen': _("Make the window fullscreen"),
    'grab': _("Grab the keyboard"),
    'force_grab_cursor': _("Force grab cursor: always use relative mouse mode instead of switching with cursor visibility"),
    'expose_wayland': _("Support Wayland clients using xdg-shell"),
    'rt': _("Use realtime scheduling"),
    'force_windows_fullscreen': _("Force windows inside of gamescope to be the size of the nested display (fullscreen)"),
    'hdr_enabled': _("Enable HDR output (needs Gamescope WSI layer enabled for support from clients)"),
    'hdr_itm_enabled': _("Enable SDR->HDR inverse tone mapping. only works for SDR input"),
    'hdr_debug_force_support': _("Force support for HDR even if the display doesn't support it"),
    'hdr_debug_force_output': _("Force output to HDR10 PQ even if unsupported (will look wrong)"),
    'hdr_debug_heatmap': _("Display heatmap-style debug view of HDR luminance in nits"),
    'mangoapp': _("Launch with the mangoapp (mangohud) performance overlay enabled"),
    'adaptive_sync': _("Enable adaptive sync if available (variable rate refresh)"),
}

GAMESCOPE_BUTTON_PRESETS = {
    'default': {
        'args': '',
        'toggles': set(),
    },
    'fsr_upscaling': {
        'args': '--scaler=fsr --filter=fsr',
        'toggles': set(),
    },
    'hdr_setup': {
        'args': '--hdr-enabled --hdr-itm-enabled --hdr-itm-sdr-nits=100 --hdr-sdr-content-nits=400 --hdr-itm-target-nits=1000',
        'toggles': set(),
    },
    'performance': {
        'args': '--rt --mangoapp',
        'toggles': {'adaptive_sync'},
    },
    'clear': {
        'args': '',
        'toggles': set(),
    },
    'custom': {
        'args': '',
        'toggles': set(),
    },
}


class GamescopeSettingsMixin:
    """Mixin with Gamescope settings UI and serialization logic."""
    theme: Any
    tab_widget: Any
    portproton_path: str | None
    current_settings: dict[str, str]
    gamescope_tab: QWidget
    gamescope_tab_layout: QVBoxLayout
    show_gamepad_tooltip: Any
    register_gamepad_tooltip: Any
    sender: Any

    def init_gamescope_state(self):
        self.gamescope_widgets = {}
        self.gamescope_original_values = {}
        self.gamescope_toggle_widgets = {}
        self.gamescope_toggle_widget_keys = {}
        self.gamescope_category_groups = {}
        self.gamescope_resolution_widgets = {}
        self.gamescope_path = shutil.which('gamescope')
        self.gamescope_available = bool(self.gamescope_path)
        self.gamescope_supported_options = None
        self.gamescope_supported_toggle_keys = {key for key, _label in GAMESCOPE_TOGGLE_SPECS}
        self.gamescope_supported_value_keys = {spec['key'] for spec in GAMESCOPE_VALUE_SPECS}
        if self.gamescope_available:
            self._detect_gamescope_supported_options()

    def _detect_gamescope_supported_options(self) -> None:
        """Read gamescope --help and cache supported long options."""
        if not self.gamescope_path:
            return
        try:
            result = subprocess.run(
                [self.gamescope_path, '--help'],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Failed to detect gamescope options: %s", exc)
            return

        help_text = f"{result.stdout}\n{result.stderr}"
        options = set(re.findall(r'--([a-z0-9][a-z0-9-]*)', help_text))
        if not options:
            return

        self.gamescope_supported_options = options
        self.gamescope_supported_toggle_keys = {
            key for key, _label in GAMESCOPE_TOGGLE_SPECS if self._is_gamescope_option_supported(key)
        }
        self.gamescope_supported_value_keys = {
            spec['key'] for spec in GAMESCOPE_VALUE_SPECS if self._is_gamescope_option_supported(spec['key'])
        }

    def _is_gamescope_option_supported(self, option_key: str) -> bool:
        """Check if gamescope supports a long option from key name."""
        if self.gamescope_supported_options is None:
            return True
        if option_key in GAMESCOPE_SHORT_TOGGLE_TOKENS or option_key in GAMESCOPE_SHORT_VALUE_TOKENS:
            return True
        aliases = GAMESCOPE_OPTION_ALIASES.get(option_key, (option_key.replace('_', '-'),))
        return any(alias in self.gamescope_supported_options for alias in aliases)

    def _normalize_gamescope_option_key(self, option_key: str) -> str:
        """Normalize long-option key aliases to a canonical setting key."""
        return GAMESCOPE_OPTION_ALIAS_TO_KEY.get(option_key, option_key)

    def _get_gamescope_option_name(self, option_key: str) -> str:
        """Get long option name for serialization, preferring supported aliases."""
        aliases = GAMESCOPE_OPTION_ALIASES.get(option_key)
        if not aliases:
            return option_key.replace('_', '-')
        if self.gamescope_supported_options is None:
            return aliases[0]
        for alias in aliases:
            if alias in self.gamescope_supported_options:
                return alias
        return aliases[0]

    def setup_gamescope_tab(self):
        """Create Gamescope tab widgets."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setStyleSheet(self.theme.SCROLL_STYLE + self.theme.TRANSPARENT_BACKGROUND_STYLE)
        container = QWidget()
        container.setStyleSheet(self.theme.TRANSPARENT_BACKGROUND_STYLE)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._add_gamescope_presets_group(layout)
        self._add_gamescope_toggle_group(layout)
        self._add_gamescope_value_group(layout)
        self._add_gamescope_extra_group(layout)
        layout.addStretch()

        scroll.setWidget(container)

        self.gamescope_tab_layout.addWidget(scroll)

    def _add_gamescope_value_group(self, parent_layout):
        """Add Gamescope value controls."""
        group = QGroupBox(_("Resolution and scaling"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        form = QFormLayout(group)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        resolution_keys = {
            'output_width', 'output_height', 'nested_width', 'nested_height',
        }
        for spec in GAMESCOPE_VALUE_SPECS:
            if (
                spec['key'] not in resolution_keys
                or spec['key'] not in self.gamescope_supported_value_keys
            ):
                continue
            self._create_gamescope_text_widget(spec)

        output_resolution_supported = (
            'output_width' in self.gamescope_widgets and 'output_height' in self.gamescope_widgets
        )
        nested_resolution_supported = (
            'nested_width' in self.gamescope_widgets and 'nested_height' in self.gamescope_widgets
        )

        if output_resolution_supported:
            form.addRow(
                f"{_('Output width')} x {_('Output height')}",
                self._create_gamescope_resolution_widget('output'),
            )
        if nested_resolution_supported:
            form.addRow(
                f"{_('Game width')} x {_('Game height')}",
                self._create_gamescope_resolution_widget('nested'),
            )

        for spec in GAMESCOPE_VALUE_SPECS:
            if (
                spec['key'] in resolution_keys
                or spec['key'] not in self.gamescope_supported_value_keys
            ):
                continue
            if spec['type'] == 'text':
                form.addRow(spec['label'], self._create_gamescope_text_widget(spec))
            elif spec['type'] == 'combo':
                form.addRow(spec['label'], self._create_gamescope_value_widget(spec))

        parent_layout.addWidget(group)

    def _create_gamescope_resolution_widget(self, target):
        """Create a resolution combo widget and bind it to width/height fields."""
        widget = QComboBox()
        widget.addItem(_("Default value"), '')
        for resolution in self._get_gamescope_resolution_options():
            widget.addItem(resolution, resolution)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.setMinimumHeight(40)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        widget.currentTextChanged.connect(
            lambda value, name=target: self._on_gamescope_resolution_changed(name, value)
        )
        self.gamescope_resolution_widgets[target] = widget
        return widget

    def _get_gamescope_resolution_options(self):
        """Collect sorted resolution options based on current Qt screens."""
        screen_sizes = set()
        max_width = 0
        max_height = 0

        app_instance = QGuiApplication.instance()
        if isinstance(app_instance, QGuiApplication):
            for screen in app_instance.screens():
                geometry = screen.geometry()
                width = geometry.width()
                height = geometry.height()
                if width <= 0 or height <= 0:
                    continue
                screen_sizes.add((width, height))
                max_width = max(max_width, width)
                max_height = max(max_height, height)

        if max_width <= 0 or max_height <= 0:
            max_width = 1920
            max_height = 1080

        for width, height in COMMON_GAMESCOPE_RESOLUTIONS:
            if width <= max_width and height <= max_height:
                screen_sizes.add((width, height))

        sorted_sizes = sorted(
            screen_sizes,
            key=lambda size: (size[0] * size[1], size[0], size[1]),
            reverse=True,
        )
        return [f"{width}x{height}" for width, height in sorted_sizes]

    def _on_gamescope_resolution_changed(self, target, resolution):
        """Apply selected resolution to underlying width/height fields."""
        text = resolution.strip()
        sender = self.sender()
        if isinstance(sender, QComboBox):
            current_data = sender.currentData()
            if isinstance(current_data, str) and current_data.strip():
                text = current_data.strip()
            elif current_data == '':
                text = ''

        if not text:
            if target == 'output':
                self.gamescope_widgets['output_width'].clear()
                self.gamescope_widgets['output_height'].clear()
                return
            self.gamescope_widgets['nested_width'].clear()
            self.gamescope_widgets['nested_height'].clear()
            return

        match = re.fullmatch(r'(\d+)x(\d+)', text)
        if not match:
            return
        width, height = match.groups()
        if target == 'output':
            self.gamescope_widgets['output_width'].setText(width)
            self.gamescope_widgets['output_height'].setText(height)
            return
        self.gamescope_widgets['nested_width'].setText(width)
        self.gamescope_widgets['nested_height'].setText(height)

    def _sync_gamescope_resolution_combos(self):
        """Sync resolution combo values with width/height text fields."""
        combo_map = {
            'output': ('output_width', 'output_height'),
            'nested': ('nested_width', 'nested_height'),
        }
        for target, (width_key, height_key) in combo_map.items():
            widget = self.gamescope_resolution_widgets.get(target)
            if widget is None:
                continue
            width = self.gamescope_widgets[width_key].text().strip()
            height = self.gamescope_widgets[height_key].text().strip()
            resolution = f"{width}x{height}" if width and height else ''
            index = widget.findData(resolution)
            if index < 0 and resolution:
                widget.addItem(resolution, resolution)
                index = widget.findData(resolution)
            if index >= 0:
                widget.setCurrentIndex(index)
            else:
                widget.setCurrentIndex(0)

    def _create_gamescope_text_widget(self, spec):
        """Create a Gamescope text input widget."""
        widget = QLineEdit()
        widget.setPlaceholderText(spec.get('placeholder', ''))
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.setMinimumHeight(40)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        self.gamescope_widgets[spec['key']] = widget
        return widget

    def _create_gamescope_value_widget(self, spec):
        """Create a Gamescope value widget."""
        widget = QComboBox()
        options = spec['options']
        placeholder_text = _("Default value")
        for option in options:
            display_text = placeholder_text if option == '' else option
            widget.addItem(display_text, option)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.setMinimumHeight(40)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        default_value = GAMESCOPE_VALUE_DEFAULTS.get(spec['key'], '')
        default_index = widget.findData(default_value)
        if default_value and default_index >= 0:
            widget.setCurrentIndex(default_index)
        else:
            widget.setCurrentIndex(0)
        self.gamescope_widgets[spec['key']] = widget
        return widget

    def _add_gamescope_presets_group(self, parent_layout):
        """Add preset buttons for common Gamescope layouts."""
        group = QGroupBox(_("Quick presets"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QGridLayout(group)
        layout.setSpacing(10)
        columns = 2

        buttons = [
            (_("Default"), lambda: self.apply_gamescope_button_preset('default')),
            (_("FSR upscaling"), lambda: self.apply_gamescope_button_preset('fsr_upscaling')),
            (_("HDR setup"), lambda: self.apply_gamescope_button_preset('hdr_setup')),
            (_("Performance"), lambda: self.apply_gamescope_button_preset('performance')),
            (_("Custom"), lambda: self.apply_gamescope_button_preset('custom')),
            (_("Save custom"), self.save_custom_gamescope_preset),
            (_("Clear"), lambda: self.apply_gamescope_button_preset('clear')),
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

    def _add_gamescope_toggle_group(self, parent_layout):
        """Add categorized Gamescope toggle checkboxes."""
        selector_group = QGroupBox(_("Gamescope switches"))
        selector_group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        selector_layout = QVBoxLayout(selector_group)

        self.gamescope_category_combo = QComboBox()
        self.gamescope_category_combo.setStyleSheet(self.theme.COMBOBOX_STYLE + self.theme.SCROLL_STYLE)
        self.gamescope_category_combo.setMinimumHeight(40)
        selector_layout.addWidget(self.gamescope_category_combo)

        self.gamescope_category_stack = QStackedWidget()
        self.gamescope_category_stack.setStyleSheet("background: transparent;")
        selector_layout.addWidget(self.gamescope_category_stack)

        toggle_lookup = dict(GAMESCOPE_TOGGLE_SPECS)
        uncategorized = set(toggle_lookup.keys())
        columns = 2

        for category, keys in GAMESCOPE_TOGGLE_CATEGORIES.items():
            supported_keys = [key for key in keys if key in self.gamescope_supported_toggle_keys]
            if not supported_keys:
                continue
            category_widget = QWidget()
            layout = QGridLayout(category_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(16)
            layout.setVerticalSpacing(10)
            for column in range(columns):
                layout.setColumnStretch(column, 1)

            for index, key in enumerate(supported_keys):
                if key not in toggle_lookup:
                    continue
                label = toggle_lookup[key]
                checkbox = self._create_gamescope_checkbox(key, label)
                row = index // columns
                column = index % columns
                layout.addWidget(checkbox, row, column)
                self.gamescope_toggle_widgets[key] = checkbox
                self.gamescope_toggle_widget_keys[checkbox] = key
                self.register_gamepad_tooltip(checkbox, GAMESCOPE_TOGGLE_DESCRIPTIONS.get(key, ""))
                uncategorized.discard(key)

            self.gamescope_category_groups[category] = category_widget
            self.gamescope_category_stack.addWidget(category_widget)
            self.gamescope_category_combo.addItem(category)

        uncategorized &= self.gamescope_supported_toggle_keys
        if uncategorized:
            category_widget = QWidget()
            layout = QGridLayout(category_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(16)
            layout.setVerticalSpacing(10)
            for column in range(columns):
                layout.setColumnStretch(column, 1)

            for index, key in enumerate(sorted(uncategorized)):
                label = toggle_lookup[key]
                checkbox = self._create_gamescope_checkbox(key, label)
                row = index // columns
                column = index % columns
                layout.addWidget(checkbox, row, column)
                self.gamescope_toggle_widgets[key] = checkbox
                self.gamescope_toggle_widget_keys[checkbox] = key
                self.register_gamepad_tooltip(checkbox, GAMESCOPE_TOGGLE_DESCRIPTIONS.get(key, ""))

            self.gamescope_category_combo.addItem(_("Other"))
            self.gamescope_category_groups[_("Other")] = category_widget
            self.gamescope_category_stack.addWidget(category_widget)

        if not self.gamescope_category_groups:
            return

        self.gamescope_category_combo.currentTextChanged.connect(self.on_gamescope_category_changed)
        self._update_gamescope_category_stack_height()
        parent_layout.addWidget(selector_group)

    def _add_gamescope_extra_group(self, parent_layout):
        """Add raw args field for unsupported Gamescope parameters."""
        group = QGroupBox(_("Extra args"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QVBoxLayout(group)
        label = QLabel(_("Additional Gamescope options not covered by the GUI."))
        label.setWordWrap(True)
        layout.addWidget(label)
        self.gamescope_extra_edit = QLineEdit()
        self.gamescope_extra_edit.setPlaceholderText(_("Example: --cursor-scale-height=1080 --force-orientation=left"))
        self.gamescope_extra_edit.setMinimumHeight(40)
        self.gamescope_extra_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.gamescope_extra_edit.installEventFilter(cast(QWidget, self))
        self.gamescope_extra_edit.setStyleSheet(self.theme.ADDGAME_INPUT_STYLE)
        layout.addWidget(self.gamescope_extra_edit)
        parent_layout.addWidget(group)

    def _create_gamescope_checkbox(self, _key, label):
        """Create a Gamescope checkbox with description support."""
        checkbox = QCheckBox(label)
        checkbox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        checkbox.setMinimumHeight(36)
        checkbox.installEventFilter(cast(QWidget, self))
        checkbox.setStyleSheet(self.theme.CHECKBOX_STYLE + """
            QCheckBox {
                spacing: 10px;
                padding: 4px 2px;
            }
        """)
        return checkbox

    def on_gamescope_category_changed(self, category):
        """Handle Gamescope category selection change."""
        widget = self.gamescope_category_groups.get(category)
        if widget and self.gamescope_category_stack.indexOf(widget) >= 0:
            self.gamescope_category_stack.setCurrentWidget(widget)
            self._update_gamescope_category_stack_height()

    def _update_gamescope_category_stack_height(self):
        """Update Gamescope category block height to current visible page."""
        current_widget = self.gamescope_category_stack.currentWidget()
        if not current_widget:
            return
        target_height = current_widget.sizeHint().height()
        if target_height > 0:
            self.gamescope_category_stack.setMinimumHeight(target_height)
            self.gamescope_category_stack.setMaximumHeight(target_height)

    def populate_gamescope(self):
        """Populate Gamescope tab from current settings."""
        parsed_args = self._parse_gamescope_args(
            self.current_settings.get('PW_GAMESCOPE_ARGS_NEW', '')
        )

        for spec in GAMESCOPE_VALUE_SPECS:
            if spec['key'] not in self.gamescope_widgets:
                continue
            self._set_gamescope_value_widget(spec, parsed_args.get(spec['key']))

        for key, _label in GAMESCOPE_TOGGLE_SPECS:
            checkbox = self.gamescope_toggle_widgets.get(key)
            if checkbox is None:
                continue
            checkbox.setChecked(key in parsed_args)

        self._sync_gamescope_resolution_combos()
        self.gamescope_extra_edit.setText(parsed_args.get('_extra', ''))
        self.gamescope_original_values = {
            'PW_GAMESCOPE_ARGS_NEW': self.current_settings.get('PW_GAMESCOPE_ARGS_NEW', ''),
        }
        self.gamescope_original_values['extra'] = parsed_args.get('_extra', '')

    def apply_gamescope_button_preset(self, preset_name):
        """Apply a built-in Gamescope preset button."""
        if preset_name == 'custom':
            preset = self._load_custom_gamescope_preset()
            if preset is None:
                QMessageBox.information(cast(QWidget, self), _("Information"), _("Custom preset is empty. Save one first."))
                return
            self._apply_gamescope_args_to_widgets(preset['args'])
            return
        preset = GAMESCOPE_BUTTON_PRESETS[preset_name]
        self._apply_gamescope_args_to_widgets(preset['args'], preset['toggles'])

    def save_custom_gamescope_preset(self):
        """Save current Gamescope settings as custom preset."""
        cp = configparser.ConfigParser()
        try:
            if CONFIG_FILE.exists():
                cp.read(CONFIG_FILE, encoding='utf-8')
            if 'GamescopePresets' not in cp:
                cp['GamescopePresets'] = {}
            cp['GamescopePresets']['custom_args'] = self._build_gamescope_args()
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                cp.write(f)
            QMessageBox.information(cast(QWidget, self), _("Success"), _("Custom preset saved."))
        except Exception as e:
            logger.warning("Failed to save custom Gamescope preset: %s", e)
            QMessageBox.warning(cast(QWidget, self), _("Error"), _("Failed to save custom preset."))

    def _load_custom_gamescope_preset(self):
        """Load custom Gamescope preset from config file."""
        cp = configparser.ConfigParser()
        try:
            if not CONFIG_FILE.exists():
                return None
            cp.read(CONFIG_FILE, encoding='utf-8')
            if not cp.has_section('GamescopePresets'):
                return None
            custom_args = cp.get('GamescopePresets', 'custom_args', fallback='').strip()
            if not custom_args:
                return None
            return {'args': custom_args}
        except Exception as e:
            logger.warning("Failed to load custom Gamescope preset: %s", e)
            return None

    def _apply_gamescope_args_to_widgets(self, args_text, forced_toggles=None):
        """Apply Gamescope args text to the tab widgets."""
        parsed_args = self._parse_gamescope_args(args_text)

        for spec in GAMESCOPE_VALUE_SPECS:
            if spec['key'] not in self.gamescope_widgets:
                continue
            self._set_gamescope_value_widget(spec, parsed_args.get(spec['key']))

        enabled_toggles = forced_toggles if forced_toggles is not None else set()
        for key, _label in GAMESCOPE_TOGGLE_SPECS:
            checkbox = self.gamescope_toggle_widgets.get(key)
            if checkbox is None:
                continue
            checkbox.setChecked(key in enabled_toggles or key in parsed_args)

        self._sync_gamescope_resolution_combos()
        self.gamescope_extra_edit.setText(parsed_args.get('_extra', ''))

    def _set_gamescope_value_widget(self, spec, value):
        """Apply parsed value to a Gamescope value widget."""
        widget = self.gamescope_widgets.get(spec['key'])
        if widget is None:
            return

        if spec['type'] == 'text':
            widget.setText(value if isinstance(value, str) else '')
        elif spec['type'] == 'combo':
            text = value if isinstance(value, str) else ''
            index = widget.findData(text)
            if text and index < 0:
                widget.addItem(text, text)
                index = widget.findData(text)
            if text:
                widget.setCurrentIndex(index)
            else:
                default_value = GAMESCOPE_VALUE_DEFAULTS.get(spec['key'], '')
                default_index = widget.findData(default_value)
                if default_value and default_index >= 0:
                    widget.setCurrentIndex(default_index)
                else:
                    widget.setCurrentIndex(0)

    def _parse_gamescope_args(self, args_text):
        """Parse PW_GAMESCOPE_ARGS_NEW into known values and raw tokens.

        Args format: ' --flag --key=value --another-flag'
        Note: Leading space is required in the stored format.
        """
        known_toggle_keys = set(self.gamescope_supported_toggle_keys)
        known_value_keys = set(self.gamescope_supported_value_keys)
        known_keys = known_toggle_keys | known_value_keys
        parsed = {}
        extra_tokens = []

        args_text = args_text.strip()
        if not args_text:
            return parsed

        tokens = args_text.split()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.startswith('--'):
                token_content = token[2:]
                if '=' in token_content:
                    key, value = token_content.split('=', 1)
                    key = self._normalize_gamescope_option_key(key.replace('-', '_'))
                    if key in known_keys:
                        parsed[key] = value
                    else:
                        extra_tokens.append(token)
                else:
                    key = self._normalize_gamescope_option_key(token_content.replace('-', '_'))
                    if key in known_value_keys and i + 1 < len(tokens):
                        i += 1
                        parsed[key] = tokens[i]
                    elif key in known_toggle_keys:
                        parsed[key] = True
                    else:
                        extra_tokens.append(token)
            elif token.startswith('-') and len(token) > 1:
                short_key = token[1:2]
                toggle_key = GAMESCOPE_SHORT_TOGGLE_ALIASES.get(short_key)
                value_key = GAMESCOPE_SHORT_VALUE_ALIASES.get(short_key)
                if toggle_key and toggle_key in known_keys and len(token) == 2:
                    parsed[toggle_key] = True
                elif value_key and value_key in known_keys:
                    inline_value = token[2:]
                    if inline_value:
                        parsed[value_key] = inline_value
                    elif i + 1 < len(tokens):
                        i += 1
                        parsed[value_key] = tokens[i]
                    else:
                        extra_tokens.append(token)
                else:
                    extra_tokens.append(token)
            else:
                extra_tokens.append(token)
            i += 1

        if extra_tokens:
            parsed['_extra'] = ' ' + ' '.join(extra_tokens)
        return parsed

    def _build_gamescope_args(self):
        """Build PW_GAMESCOPE_ARGS_NEW from the Gamescope tab.

        Returns format: ' --flag --key=value' (with leading space for +=)
        """
        tokens = []

        for spec in GAMESCOPE_VALUE_SPECS:
            if spec['key'] not in self.gamescope_widgets:
                continue
            token = self._build_gamescope_value_token(spec)
            if token:
                tokens.append(token)

        for key, _label in GAMESCOPE_TOGGLE_SPECS:
            token = self._build_gamescope_toggle_token(key)
            if token:
                tokens.append(token)

        extra_text = self.gamescope_extra_edit.text().strip()
        if extra_text:
            tokens.append(extra_text)

        if tokens:
            return ' ' + ' '.join(tokens)
        return ''

    def _build_gamescope_toggle_token(self, key):
        """Build one Gamescope toggle token from a checkbox."""
        checkbox = self.gamescope_toggle_widgets.get(key)
        if checkbox is None:
            return ''
        if checkbox.isChecked():
            short_token = GAMESCOPE_SHORT_TOGGLE_TOKENS.get(key)
            if short_token:
                return short_token
            option_name = self._get_gamescope_option_name(key)
            return f"--{option_name}"
        return ''

    def _build_gamescope_value_token(self, spec):
        """Build one Gamescope value token."""
        widget = self.gamescope_widgets.get(spec['key'])
        if widget is None:
            return ''

        if spec['type'] == 'text':
            value = widget.text().strip()
        elif spec['type'] == 'combo':
            current_data = widget.currentData()
            value = '' if current_data is None else str(current_data).strip()
            if not value and current_data is None:
                value = widget.currentText().strip()
        else:
            value = ''

        if not value:
            return ''

        short_token = GAMESCOPE_SHORT_VALUE_TOKENS.get(spec['key'])
        if short_token:
            return f"{short_token} {value}"

        option_name = self._get_gamescope_option_name(spec['key'])
        return f"--{option_name}={value}"

    def _collect_gamescope_changes(self):
        """Collect Gamescope-specific changes."""
        changes = []
        args_value = self._build_gamescope_args()
        if args_value != self.gamescope_original_values.get('PW_GAMESCOPE_ARGS_NEW', ''):
            changes.append(f"PW_GAMESCOPE_ARGS_NEW={args_value}")

        return changes

    def _filter_gamescope_settings(self, search_text):
        """Filter Gamescope groups based on search text."""
        for group_box in self.gamescope_tab.findChildren(QGroupBox):
            if not search_text:
                group_box.setVisible(True)
                continue
            group_text = group_box.title().lower()
            label_text = ' '.join(widget.text().lower() for widget in group_box.findChildren(QLabel))
            checkbox_text = ' '.join(widget.text().lower() for widget in group_box.findChildren(QCheckBox))
            content_text = f"{label_text} {checkbox_text}"
            group_box.setVisible(search_text in group_text or search_text in content_text)
