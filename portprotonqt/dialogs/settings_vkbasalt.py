"""vkBasalt settings support for executable settings dialog."""

import os
from typing import Any, cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.localization import _
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

VKBASALT_ENV_KEYS = [
    'PW_PLUGINS_VER',
    'PW_VKBASALT_EFFECTS',
    'PW_VKBASALT_FFX_CAS',
    'PW_VKBASALT_TOOGLE_KEY',
]


class VkBasaltSettingsMixin:
    """Mixin with vkBasalt settings UI and serialization logic."""
    theme: Any
    current_settings: dict[str, str]
    original_values: dict[str, str]
    portproton_path: str | None
    vkbasalt_tab: QWidget
    vkbasalt_tab_layout: QVBoxLayout
    sender: Any

    def init_vkbasalt_state(self) -> None:
        self.vkbasalt_shader_widgets = {}
        self.vkbasalt_original_values = {}
        self.vkbasalt_actions_group = None
        self.vkbasalt_shaders_group = None
        self.vkbasalt_shaders_layout = None
        self.vkbasalt_cas_group = None
        self.vkbasalt_cas_label = None
        self.vkbasalt_toggle_key_button = None
        self.vkbasalt_toggle_key_waiting = False

    def setup_vkbasalt_tab(self) -> None:
        """Create vkBasalt tab widgets."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setStyleSheet(self.theme.SCROLL_STYLE + self.theme.TRANSPARENT_BACKGROUND_STYLE)
        container = QWidget()
        container.setStyleSheet(self.theme.TRANSPARENT_BACKGROUND_STYLE)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme.exeSettingsGroupBoxBlockSpacing)

        self._add_vkbasalt_actions_group(layout)
        self._add_vkbasalt_shaders_group(layout)
        self._add_vkbasalt_cas_group(layout)
        layout.addStretch()

        scroll.setWidget(container)
        self.vkbasalt_tab_layout.addWidget(scroll)

    def _add_vkbasalt_actions_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox(_("Actions"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QGridLayout(group)
        layout.setVerticalSpacing(self.theme.exeSettingsGroupBoxElementVerticalSpacing)
        layout.setHorizontalSpacing(self.theme.exeSettingsGroupBoxElementHorizontalSpacing)
        self.vkbasalt_actions_group = group

        self.vkbasalt_enable_button = self._create_vkbasalt_button(_("Enable {0}").format("vkBasalt"))
        self.vkbasalt_enable_button.clicked.connect(self.toggle_vkbasalt_enable)
        self.vkbasalt_user_conf_button = self._create_vkbasalt_button(_("Use system config"))
        self.vkbasalt_user_conf_button.clicked.connect(self.toggle_vkbasalt_user_conf)
        layout.addWidget(self.vkbasalt_enable_button, 0, 0)
        layout.addWidget(self.vkbasalt_user_conf_button, 0, 1)

        parent_layout.addWidget(group)

    def _add_vkbasalt_shaders_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox(_("ReShade shaders"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        self.vkbasalt_shaders_layout = QGridLayout(group)
        self.vkbasalt_shaders_layout.setContentsMargins(0, 8, 0, 8)
        self.vkbasalt_shaders_layout.setHorizontalSpacing(0)
        self.vkbasalt_shaders_layout.setVerticalSpacing(self.theme.mangoHudSwitchesVerticalSpacing)
        self.vkbasalt_shaders_group = group

        columns = self.theme.mangoHudSwitchesColumns
        for col in range(columns * 2 + 1):
            self.vkbasalt_shaders_layout.setColumnStretch(col, 1 if col % 2 == 0 else 0)

        parent_layout.addWidget(group)

    def _add_vkbasalt_cas_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox(_("AMD FidelityFX - Contrast Adaptive Sharpening"))
        group.setStyleSheet(self.theme.QGROUP_BOX_STYLE)
        layout = QVBoxLayout(group)
        layout.setSpacing(self.theme.exeSettingsGroupBoxElementHorizontalSpacing)
        self.vkbasalt_cas_group = group
        self.vkbasalt_cas_label = QLabel()
        self.vkbasalt_cas_label.setWordWrap(True)
        layout.addWidget(self.vkbasalt_cas_label)

        self.vkbasalt_cas_slider = QSlider(Qt.Orientation.Horizontal)
        self.vkbasalt_cas_slider.setRange(0, 100)
        self.vkbasalt_cas_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.vkbasalt_cas_slider.setStyleSheet(self.theme.SLIDER_SIZE_STYLE)
        self.vkbasalt_cas_slider.valueChanged.connect(self._update_vkbasalt_cas_label)
        layout.addWidget(self.vkbasalt_cas_slider)

        toggle_key_label = QLabel(_("Toggle key"))
        toggle_key_label.setWordWrap(True)
        layout.addWidget(toggle_key_label)
        self.vkbasalt_toggle_key_button = self._create_vkbasalt_button("")
        self.vkbasalt_toggle_key_button.clicked.connect(self._start_vkbasalt_toggle_key_capture)
        self.vkbasalt_toggle_key_button.installEventFilter(cast(QWidget, self))
        layout.addWidget(self.vkbasalt_toggle_key_button)
        parent_layout.addWidget(group)

    def _create_vkbasalt_button(self, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    def _create_vkbasalt_checkbox(self, label: str) -> QCheckBox:
        checkbox = QCheckBox(label)
        checkbox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        checkbox.installEventFilter(cast(QWidget, self))
        checkbox.setStyleSheet(self.theme.CHECKBOX_STYLE)
        return checkbox

    def _get_vkbasalt_shader_names(self) -> list[str]:
        shaders = self._get_vkbasalt_plugins_shader_names()
        if shaders:
            return shaders
        logger.warning("vkBasalt ReShade shaders not found for PW_PLUGINS_VER")
        return []

    def _get_vkbasalt_plugins_shader_names(self) -> list[str]:
        if not self.portproton_path:
            return []

        tmp_path = os.path.join(self.portproton_path, "data", "tmp")
        plugins_ver = self.current_settings.get('PW_PLUGINS_VER', '').strip()
        if not plugins_ver:
            return []

        shader_dirs = [os.path.join(tmp_path, f"plugins{plugins_ver}", "reshade", "shaders")]
        for shader_dir in shader_dirs:
            shaders = self._read_vkbasalt_shader_dir(shader_dir)
            if shaders:
                return shaders
        return []

    def _read_vkbasalt_shader_dir(self, shader_dir: str) -> list[str]:
        try:
            shader_files = os.listdir(shader_dir)
        except OSError:
            return []
        shaders = [
            os.path.splitext(name)[0]
            for name in shader_files
            if name.endswith(".fx") and os.path.isfile(os.path.join(shader_dir, name))
        ]
        return sorted(shaders, key=str.casefold)

    def populate_vkbasalt(self) -> None:
        """Populate vkBasalt tab from current settings."""
        self._populate_vkbasalt_shader_widgets()
        effects = self._parse_vkbasalt_effects(
            self.current_settings.get('PW_VKBASALT_EFFECTS', 'Curves:cas')
        )
        for shader, checkbox in self.vkbasalt_shader_widgets.items():
            checkbox.setChecked(shader in effects)

        cas_value = self._parse_vkbasalt_cas(self.current_settings.get('PW_VKBASALT_FFX_CAS', '0.50'))
        self.vkbasalt_cas_slider.setValue(cas_value)
        toggle_key = self.current_settings.get('PW_VKBASALT_TOOGLE_KEY', 'Home')
        self._set_vkbasalt_toggle_key(toggle_key)
        self.vkbasalt_original_values = {
            'PW_VKBASALT_EFFECTS': self.current_settings.get('PW_VKBASALT_EFFECTS', 'Curves:cas'),
            'PW_VKBASALT_FFX_CAS': self.current_settings.get('PW_VKBASALT_FFX_CAS', '0.50'),
            'PW_VKBASALT_TOOGLE_KEY': toggle_key,
        }
        self._update_vkbasalt_toggle_buttons()

    def _populate_vkbasalt_shader_widgets(self) -> None:
        if self.vkbasalt_shader_widgets or self.vkbasalt_shaders_layout is None:
            return

        columns = self.theme.mangoHudSwitchesColumns
        shader_names = self._get_vkbasalt_shader_names()
        for index, shader in enumerate([*shader_names, 'cas']):
            checkbox = self._create_vkbasalt_checkbox(shader)
            row = index // columns
            real_col = (index % columns) * 2 + 1
            self.vkbasalt_shaders_layout.addWidget(checkbox, row, real_col)
            self.vkbasalt_shader_widgets[shader] = checkbox

    def _parse_vkbasalt_effects(self, effects_text: str) -> set[str]:
        return {effect.strip() for effect in effects_text.split(':') if effect.strip()}

    def _parse_vkbasalt_cas(self, value: str) -> int:
        try:
            return max(0, min(100, round(float(value) * 100)))
        except ValueError:
            return 50

    def _update_vkbasalt_cas_label(self) -> None:
        if self.vkbasalt_cas_label is None:
            return
        self.vkbasalt_cas_label.setText(_("Sharpness: {0}").format(self.vkbasalt_cas_slider.value()))

    def _update_vkbasalt_toggle_buttons(self) -> None:
        vkbasalt_enabled = self.current_settings.get('PW_VKBASALT') == '1'
        user_conf_enabled = self.current_settings.get('PW_VKBASALT_USER_CONF') == '1'
        config_visible = vkbasalt_enabled and not user_conf_enabled

        self._update_vkbasalt_button(self.vkbasalt_enable_button, vkbasalt_enabled)
        self.vkbasalt_enable_button.setText(
            _("Disable {0}").format("vkBasalt") if vkbasalt_enabled else _("Enable {0}").format("vkBasalt")
        )
        self.vkbasalt_user_conf_button.setVisible(vkbasalt_enabled)
        self._update_vkbasalt_button(self.vkbasalt_user_conf_button, user_conf_enabled)
        self.vkbasalt_user_conf_button.setText(
            _("Don't use system config") if user_conf_enabled else _("Use system config")
        )
        for group in (self.vkbasalt_shaders_group, self.vkbasalt_cas_group):
            if group is not None:
                group.setVisible(config_visible)

    def _update_vkbasalt_button(self, button: QPushButton, active: bool) -> None:
        style = self.theme.ACTION_BUTTON_ACTIVE_STYLE if active else self.theme.ACTION_BUTTON_STYLE
        button.setStyleSheet(style)

    def _start_vkbasalt_toggle_key_capture(self) -> None:
        self.vkbasalt_toggle_key_waiting = True
        if self.vkbasalt_toggle_key_button is None:
            return
        self.vkbasalt_toggle_key_button.setText(_("Press a button to choose"))
        self.vkbasalt_toggle_key_button.grabKeyboard()

    def _set_vkbasalt_toggle_key(self, key_name: str) -> None:
        self.current_settings['PW_VKBASALT_TOOGLE_KEY'] = key_name or 'Home'
        if self.vkbasalt_toggle_key_button is not None:
            self.vkbasalt_toggle_key_button.setText(self.current_settings['PW_VKBASALT_TOOGLE_KEY'])

    def _handle_vkbasalt_key_button_event(self, obj: QWidget, event: QEvent) -> bool:
        button = self.vkbasalt_toggle_key_button
        if button is None or obj is not button:
            return False
        if event.type() != QEvent.Type.KeyPress or not self.vkbasalt_toggle_key_waiting:
            return False

        key_event = cast(QKeyEvent, event)
        key_name = QKeySequence(key_event.key()).toString()
        if key_name:
            self._set_vkbasalt_toggle_key(key_name)
        self.vkbasalt_toggle_key_waiting = False
        button.releaseKeyboard()
        return True

    def toggle_vkbasalt_enable(self) -> None:
        current_val = self.current_settings.get('PW_VKBASALT', '0')
        self.current_settings['PW_VKBASALT'] = '0' if current_val == '1' else '1'
        self._update_vkbasalt_toggle_buttons()

    def toggle_vkbasalt_user_conf(self) -> None:
        current_val = self.current_settings.get('PW_VKBASALT_USER_CONF', '0')
        self.current_settings['PW_VKBASALT_USER_CONF'] = '0' if current_val == '1' else '1'
        self._update_vkbasalt_toggle_buttons()

    def _build_vkbasalt_effects(self) -> str:
        return ':'.join(
            shader for shader, checkbox in self.vkbasalt_shader_widgets.items()
            if checkbox.isChecked()
        )

    def _collect_vkbasalt_changes(self) -> list[str]:
        changes = []
        original_values = cast(dict[str, str], getattr(self, 'original_values', {}))
        for key in ('PW_VKBASALT', 'PW_VKBASALT_USER_CONF'):
            new_val = '1' if self.current_settings.get(key) == '1' else '0'
            orig_val = '1' if original_values.get(key) == '1' else '0'
            if new_val != orig_val:
                changes.append(f"{key}={new_val}")

        effects = self._build_vkbasalt_effects()
        if effects != self.vkbasalt_original_values.get('PW_VKBASALT_EFFECTS', ''):
            changes.append(f"PW_VKBASALT_EFFECTS={effects}")
        cas_value = f"{self.vkbasalt_cas_slider.value() / 100:.2f}"
        if cas_value != self.vkbasalt_original_values.get('PW_VKBASALT_FFX_CAS', ''):
            changes.append(f"PW_VKBASALT_FFX_CAS={cas_value}")
        toggle_key = self.current_settings.get('PW_VKBASALT_TOOGLE_KEY', 'Home')
        if toggle_key != self.vkbasalt_original_values.get('PW_VKBASALT_TOOGLE_KEY', ''):
            changes.append(f"PW_VKBASALT_TOOGLE_KEY={toggle_key}")
        return changes

    def _filter_vkbasalt_settings(self, search_text: str) -> None:
        vkbasalt_enabled = self.current_settings.get('PW_VKBASALT') == '1'
        user_conf_enabled = self.current_settings.get('PW_VKBASALT_USER_CONF') == '1'
        config_visible = vkbasalt_enabled and not user_conf_enabled
        for group_box in self.vkbasalt_tab.findChildren(QGroupBox):
            if not config_visible:
                group_box.setVisible(group_box is self.vkbasalt_actions_group)
                continue
            if not search_text:
                group_box.setVisible(True)
                continue
            content_text = self._get_vkbasalt_group_text(group_box)
            group_box.setVisible(search_text in group_box.title().lower() or search_text in content_text)

    def _get_vkbasalt_group_text(self, group_box: QGroupBox) -> str:
        label_text = ' '.join(widget.text().lower() for widget in group_box.findChildren(QLabel))
        checkbox_text = ' '.join(widget.text().lower() for widget in group_box.findChildren(QCheckBox))
        return f"{label_text} {checkbox_text}"
