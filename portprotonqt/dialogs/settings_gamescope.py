"""Gamescope settings support for executable settings dialog."""

import re
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
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.dialogs.settings_mangohud import MANGOHUD_FPS_OPTIONS
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
    ('force_grab_cursor', _("Always use relative mouse mode")),
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
    ('allow_deferred_backend', _("Allow deferred backend")),
    ('keep_alive', _("Keep alive after primary process dies")),
]

GAMESCOPE_VALUE_SPECS = [
    {'key': 'output_width', 'label': _("Output width"), 'type': 'text', 'placeholder': _('e.g., 1920')},
    {'key': 'output_height', 'label': _("Output height"), 'type': 'text', 'placeholder': _('e.g., 1080')},
    {'key': 'nested_width', 'label': _("Game width"), 'type': 'text', 'placeholder': _('e.g., 1280')},
    {'key': 'nested_height', 'label': _("Game height"), 'type': 'text', 'placeholder': _('e.g., 720')},
    {'key': 'nested_refresh', 'label': _("Game refresh rate (Hz)"), 'type': 'combo',
     'options': [''] + MANGOHUD_FPS_OPTIONS},
    {'key': 'max_scale', 'label': _("Maximum scale factor"), 'type': 'text', 'placeholder': _('e.g., 4')},
    {'key': 'scaler', 'label': _("Upscaler type"), 'type': 'combo',
     'options': ['', 'auto', 'integer', 'fit', 'fill', 'stretch']},
    {'key': 'filter', 'label': _("Upscaler filter"), 'type': 'combo',
     'options': ['', 'linear', 'nearest', 'fsr', 'nis', 'pixel']},
    {'key': 'sharpness', 'label': _("Upscaler sharpness (0-20)"), 'type': 'text', 'placeholder': _('e.g., 5')},
    {'key': 'mouse_sensitivity', 'label': _("Mouse sensitivity"), 'type': 'text', 'placeholder': _('e.g., 1.0')},
    {'key': 'backend', 'label': _("Rendering backend"), 'type': 'combo',
     'options': ['', 'auto', 'drm', 'sdl', 'headless', 'wayland']},
    {'key': 'ready_fd', 'label': _("Ready FD"), 'type': 'text', 'placeholder': _('e.g., 3')},
    {'key': 'hide_cursor_delay', 'label': _("Hide cursor delay (ms)"), 'type': 'text', 'placeholder': _('e.g., 5000')},
    {'key': 'xwayland_count', 'label': _("XWayland servers count"), 'type': 'text', 'placeholder': _('e.g., 1')},
    {'key': 'force_orientation', 'label': _("Force orientation"), 'type': 'combo',
     'options': ['', 'left', 'right', 'normal', 'upsidedown']},
    {'key': 'cursor_scale_height', 'label': _("Cursor scale height"), 'type': 'text', 'placeholder': _('e.g., 1080')},
    {'key': 'sdr_gamut_wideness', 'label': _("SDR gamut wideness (0-1)"), 'type': 'text', 'placeholder': _('e.g., 0.5')},
    {'key': 'hdr_sdr_content_nits', 'label': _("HDR SDR content nits"), 'type': 'text', 'placeholder': _('e.g., 400')},
    {'key': 'hdr_itm_sdr_nits', 'label': _("HDR ITM SDR nits"), 'type': 'text', 'placeholder': _('e.g., 100')},
    {'key': 'hdr_itm_target_nits', 'label': _("HDR ITM target nits"), 'type': 'text', 'placeholder': _('e.g., 1000')},
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
    'f': 'fullscreen',
}

GAMESCOPE_SHORT_VALUE_ALIASES = {
    'W': 'output_width',
    'H': 'output_height',
    'w': 'nested_width',
    'h': 'nested_height',
}

GAMESCOPE_TOGGLE_CATEGORIES = {
    _("Window"): [
        'borderless', 'fullscreen', 'grab', 'force_grab_cursor',
        'force_windows_fullscreen',
    ],
    _("Platform"): [
        'expose_wayland', 'backend', 'rt', 'allow_deferred_backend',
        'keep_alive',
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
    'force_grab_cursor': _("Always use relative mouse mode instead of flipping dependent on cursor visibility"),
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
    'allow_deferred_backend': _("Allows initting the backend in a deferred way, if it doesn't work immediately"),
    'keep_alive': _("Keep Gamescope alive even when the primary process has died"),
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
    sender: Any

    def init_gamescope_state(self):
        self.gamescope_widgets = {}
        self.gamescope_original_values = {}
        self.gamescope_toggle_widgets = {}
        self.gamescope_toggle_widget_keys = {}
        self.gamescope_category_groups = {}
        self.gamescope_resolution_widgets = {}

    def setup_gamescope_tab(self):
        """Create Gamescope tab widgets."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setStyleSheet(self.theme.SCROLL_AREA_STYLE)
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
            if spec['key'] not in resolution_keys:
                continue
            self._create_gamescope_text_widget(spec)

        form.addRow(
            f"{_('Output width')} x {_('Output height')}",
            self._create_gamescope_resolution_widget('output'),
        )
        form.addRow(
            f"{_('Game width')} x {_('Game height')}",
            self._create_gamescope_resolution_widget('nested'),
        )

        for spec in GAMESCOPE_VALUE_SPECS:
            if spec['key'] in resolution_keys:
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
        widget.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
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
        widget.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
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
        self.gamescope_category_combo.addItems(list(GAMESCOPE_TOGGLE_CATEGORIES.keys()))
        self.gamescope_category_combo.setStyleSheet(self.theme.SETTINGS_COMBO_STYLE)
        self.gamescope_category_combo.setMinimumHeight(40)
        self.gamescope_category_combo.currentTextChanged.connect(self.on_gamescope_category_changed)
        selector_layout.addWidget(self.gamescope_category_combo)

        self.gamescope_category_stack = QStackedWidget()
        self.gamescope_category_stack.setStyleSheet("background: transparent;")
        selector_layout.addWidget(self.gamescope_category_stack)

        toggle_lookup = dict(GAMESCOPE_TOGGLE_SPECS)
        uncategorized = set(toggle_lookup.keys())

        for category, keys in GAMESCOPE_TOGGLE_CATEGORIES.items():
            category_widget = QWidget()
            layout = QGridLayout(category_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(16)
            layout.setVerticalSpacing(10)

            for index, key in enumerate(keys):
                if key not in toggle_lookup:
                    continue
                label = toggle_lookup[key]
                checkbox = self._create_gamescope_checkbox(key, label)
                row = index // 4
                column = index % 4
                layout.addWidget(checkbox, row, column)
                self.gamescope_toggle_widgets[key] = checkbox
                self.gamescope_toggle_widget_keys[checkbox] = key
                uncategorized.discard(key)

            self.gamescope_category_groups[category] = category_widget
            self.gamescope_category_stack.addWidget(category_widget)

        if uncategorized:
            category_widget = QWidget()
            layout = QGridLayout(category_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(16)
            layout.setVerticalSpacing(10)

            for index, key in enumerate(sorted(uncategorized)):
                label = toggle_lookup[key]
                checkbox = self._create_gamescope_checkbox(key, label)
                row = index // 4
                column = index % 4
                layout.addWidget(checkbox, row, column)
                self.gamescope_toggle_widgets[key] = checkbox
                self.gamescope_toggle_widget_keys[checkbox] = key

            self.gamescope_category_combo.addItem(_("Other"))
            self.gamescope_category_groups[_("Other")] = category_widget
            self.gamescope_category_stack.addWidget(category_widget)

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
        checkbox.setStyleSheet(self.theme.SETTINGS_CHECKBOX_STYLE + """
            QCheckBox {
                spacing: 10px;
                padding: 4px 2px;
            }
        """)
        return checkbox

    def on_gamescope_category_changed(self, category):
        """Handle Gamescope category selection change."""
        widget = self.gamescope_category_groups.get(category)
        if widget:
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
            checkbox = self.gamescope_toggle_widgets[key]
            checkbox.setChecked(key in parsed_args)

        self._sync_gamescope_resolution_combos()
        self.gamescope_extra_edit.setText(parsed_args.get('_extra', ''))
        self.gamescope_original_values = {
            'PW_GAMESCOPE_ARGS_NEW': self.current_settings.get('PW_GAMESCOPE_ARGS_NEW', ''),
        }
        self.gamescope_original_values['extra'] = parsed_args.get('_extra', '')

    def apply_gamescope_button_preset(self, preset_name):
        """Apply a built-in Gamescope preset button."""
        preset = GAMESCOPE_BUTTON_PRESETS[preset_name]
        self._apply_gamescope_args_to_widgets(preset['args'], preset['toggles'])

    def _apply_gamescope_args_to_widgets(self, args_text, forced_toggles=None):
        """Apply Gamescope args text to the tab widgets."""
        parsed_args = self._parse_gamescope_args(args_text)

        for spec in GAMESCOPE_VALUE_SPECS:
            if spec['key'] not in self.gamescope_widgets:
                continue
            self._set_gamescope_value_widget(spec, parsed_args.get(spec['key']))

        enabled_toggles = forced_toggles if forced_toggles is not None else set()
        for key, _label in GAMESCOPE_TOGGLE_SPECS:
            checkbox = self.gamescope_toggle_widgets[key]
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
        known_keys = {key for key, _label in GAMESCOPE_TOGGLE_SPECS}
        known_keys.update(spec['key'] for spec in GAMESCOPE_VALUE_SPECS)
        parsed = {}
        extra_tokens = []
        parsed_resolution_tokens = {
            'output_width': [],
            'output_height': [],
            'nested_width': [],
            'nested_height': [],
        }

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
                    key = key.replace('-', '_')
                    if key in known_keys:
                        parsed[key] = value
                        if key in parsed_resolution_tokens:
                            parsed_resolution_tokens[key] = [token]
                    else:
                        extra_tokens.append(token)
                else:
                    key = token_content.replace('-', '_')
                    if key in known_keys:
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
                        if value_key in parsed_resolution_tokens:
                            parsed_resolution_tokens[value_key] = [token]
                    elif i + 1 < len(tokens):
                        next_token = tokens[i + 1]
                        i += 1
                        parsed[value_key] = tokens[i]
                        if value_key in parsed_resolution_tokens:
                            parsed_resolution_tokens[value_key] = [token, next_token]
                    else:
                        extra_tokens.append(token)
                else:
                    extra_tokens.append(token)
            else:
                extra_tokens.append(token)
            i += 1

        max_width = 0
        max_height = 0
        app_instance = QGuiApplication.instance()
        if isinstance(app_instance, QGuiApplication):
            active_screen = None
            window_method = getattr(self, 'window', None)
            window = window_method() if callable(window_method) else None
            if isinstance(window, QWidget):
                window_handle = window.windowHandle()
                if window_handle is not None:
                    active_screen = window_handle.screen()
            if active_screen is None:
                active_screen = app_instance.primaryScreen()
            if active_screen is not None:
                geometry = active_screen.geometry()
                max_width = geometry.width()
                max_height = geometry.height()
            else:
                for screen in app_instance.screens():
                    geometry = screen.geometry()
                    max_width = max(max_width, geometry.width())
                    max_height = max(max_height, geometry.height())
        if max_width <= 0 or max_height <= 0:
            max_width = 1920
            max_height = 1080

        for width_key, height_key in (('output_width', 'output_height'), ('nested_width', 'nested_height')):
            width_value = parsed.get(width_key)
            height_value = parsed.get(height_key)
            if not (isinstance(width_value, str) and width_value.isdigit()):
                continue
            if not (isinstance(height_value, str) and height_value.isdigit()):
                continue
            if int(width_value) <= max_width and int(height_value) <= max_height:
                continue

            logger.debug(
                "Drop unsupported gamescope resolution for active screen: %sx%s (max %sx%s)",
                width_value,
                height_value,
                max_width,
                max_height,
            )
            parsed.pop(width_key, None)
            parsed.pop(height_key, None)

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
        if self.gamescope_toggle_widgets[key].isChecked():
            key_with_dashes = key.replace('_', '-')
            return f"--{key_with_dashes}"
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

        key_with_dashes = spec['key'].replace('_', '-')
        return f"--{key_with_dashes}={value}"

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

    def _show_gamescope_toggle_tooltip(self, checkbox):
        """Show gamepad tooltip for Gamescope toggle checkbox."""
        key = self.gamescope_toggle_widget_keys.get(checkbox)
        if not key:
            return
        text = GAMESCOPE_TOGGLE_DESCRIPTIONS.get(key, "")
        if not text:
            self.show_gamepad_tooltip(show=False)
            return
        self.show_gamepad_tooltip(show=True, text=text, anchor_widget=checkbox)
