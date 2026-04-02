"""Settings dialog for PortProtonQt."""

import os
import re
import shutil
from typing import cast, TYPE_CHECKING

from PySide6.QtCore import Qt, QEvent, QProcess, QTimer, QUrl
from PySide6.QtGui import QColor, QContextMenuEvent, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from portprotonqt.main_window import MainWindow

from portprotonqt.config_utils import (
    get_portproton_location,
    get_portproton_start_command,
    read_theme_from_config,
)
from portprotonqt.custom_widgets import AutoSizeButton
from portprotonqt.dialogs.dialog_utils import create_dialog_hints_widget, update_dialog_hints
from portprotonqt.dialogs.settings_mangohud import MANGOHUD_ENV_KEYS, MangoHudSettingsMixin
from portprotonqt.dialogs.settings_gamescope import GAMESCOPE_ENV_KEYS, GamescopeSettingsMixin
from portprotonqt.localization import _, format_setting_name_for_display
from portprotonqt.logger import get_logger
from portprotonqt.preloader import Preloader
from portprotonqt.settings_manager import ADVANCED_SETTING_KEYS, get_advanced_settings, get_toggle_settings
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.virtual_keyboard import VirtualKeyboard

logger = get_logger(__name__)
theme_manager = ThemeManager()


def _normalize_prefix_directories(prefixes_dir):
    if not os.path.isdir(prefixes_dir):
        return

    for prefix_name in os.listdir(prefixes_dir):
        current_path = os.path.join(prefixes_dir, prefix_name)
        if not os.path.isdir(current_path):
            continue

        normalized_name = re.sub(r"[ \t]", "_", prefix_name).upper()
        if normalized_name == prefix_name:
            continue

        normalized_path = os.path.join(prefixes_dir, normalized_name)
        if os.path.isdir(normalized_path):
            logger.warning(
                "Cannot rename prefix %s to %s: target already exists",
                prefix_name,
                normalized_name
            )
            continue

        try:
            os.rename(current_path, normalized_path)
        except OSError as exc:
            logger.warning("Failed to rename prefix %s: %s", prefix_name, exc)


class ExeSettingsDialog(QDialog, MangoHudSettingsMixin, GamescopeSettingsMixin):
    """Dialog for configuring executable-specific settings."""

    def __init__(self, parent=None, theme=None, exe_path=None, appid=None, game_source=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.exe_path = exe_path
        self.appid = appid
        self.game_source = str(game_source).lower() if game_source else ""
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
                _normalize_prefix_directories(prefixes_dir)
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
        self.init_mangohud_state()
        self.init_gamescope_state()
        self.available_keys = set()
        self.blocked_keys = set()
        self.numa_nodes = {}
        self.locale_options = []
        self.logical_core_options = []
        self._gamepad_tooltip_map = {}

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
        self.tab_widget.setStyleSheet(self.theme.TAB_STYLE)
        self.main_tab = QWidget()
        self.main_tab_layout = QVBoxLayout(self.main_tab)
        self.advanced_tab = QWidget()
        self.advanced_tab_layout = QVBoxLayout(self.advanced_tab)
        self.mangohud_tab = QWidget()
        self.mangohud_tab_layout = QVBoxLayout(self.mangohud_tab)
        self.gamescope_tab = QWidget()
        self.gamescope_tab_layout = QVBoxLayout(self.gamescope_tab)

        self.tab_widget.addTab(self.main_tab, _("Main"))
        self.tab_widget.addTab(self.advanced_tab, _("Advanced"))
        self.tab_widget.addTab(self.mangohud_tab, "MangoHud")
        if self.gamescope_available:
            self.tab_widget.addTab(self.gamescope_tab, "Gamescope")
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
        self.settings_table.setStyleSheet(self.theme.WINETRICKS_TABBLE_STYLE + self.theme.COMBOBOX_STYLE + self.theme.LINE_EDIT_STYLE + self.theme.SCROLL_STYLE)
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
        self.advanced_table.setStyleSheet(self.theme.WINETRICKS_TABBLE_STYLE + self.theme.COMBOBOX_STYLE + self.theme.LINE_EDIT_STYLE + self.theme.SCROLL_STYLE)
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
        if self.gamescope_available:
            self.setup_gamescope_tab()

        self.main_layout.addWidget(self.tab_widget)

        self.gamepad_tooltip = QLabel()
        self.gamepad_tooltip.setWordWrap(True)
        self.gamepad_tooltip.setStyleSheet(self.theme.TOOLTIP_STYLE)
        self.gamepad_tooltip.setVisible(False)
        self.gamepad_tooltip.setParent(self)
        self.gamepad_tooltip.setWindowFlags(Qt.WindowType.ToolTip)
        self.gamepad_tooltip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.gamepad_tooltip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
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
        self._install_line_edit_event_filters()

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
        if self.game_source == "steam":
            self.blocked_keys.update({
                "PW_USE_GSTREAMER",
                "PW_USE_RUNTIME",
                "PW_DGVOODOO2",
                "PW_USE_EAC_AND_BE",
            })

        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            for key in self.toggle_settings:
                self.current_settings[key] = '0'
            for adv_key in ADVANCED_SETTING_KEYS:
                self.current_settings[adv_key] = 'disabled' if any(
                    x in adv_key for x in ['TOPOLOGY', 'SELECT', 'MODE', 'LEVEL', 'GL_VERSION', 'NUMA']
                ) else ''
            for key in MANGOHUD_ENV_KEYS:
                self.current_settings[key] = ''
            for key in GAMESCOPE_ENV_KEYS:
                self.current_settings[key] = ''
        else:
            output = bytes(process.readAllStandardOutput().data()).decode('utf-8', 'ignore').strip()
            self.current_settings = {}
            for line in output.split('\n'):
                line_stripped = line.strip()
                if '=' in line_stripped:
                    try:
                        key, val = line_stripped.split('=', 1)
                        if key in self.toggle_settings or key in ADVANCED_SETTING_KEYS or key in MANGOHUD_ENV_KEYS or key in GAMESCOPE_ENV_KEYS:
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
        if self.gamescope_available:
            self.populate_gamescope()

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

        visible_keys = [
            key for key in self.toggle_settings
            if not self.available_keys or key in self.available_keys
        ]

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
            checkbox_widget = QCheckBox()
            checkbox_widget.setStyleSheet(self.theme.CHECKBOX_STYLE)
            checkbox_widget.setChecked(current_val == '1' and not is_blocked)
            checkbox_widget.setEnabled(not is_blocked)
            checkbox_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            checkbox_container = QWidget()
            checkbox_container.setStyleSheet(self.theme.CHECKBOX_STYLE + self.theme.TRANSPARENT_BACKGROUND_STYLE)
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.addWidget(checkbox_widget)
            checkbox_container.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if is_blocked:
                name_item.setForeground(QColor(self.theme.color_disabled_text))
                checkbox_container.setStyleSheet(f"background-color: {self.theme.color_d};")
            self.settings_table.setItem(row, 1, checkbox_item)
            self.settings_table.setCellWidget(row, 1, checkbox_container)

            desc_item = QTableWidgetItem(description)
            desc_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if is_blocked:
                desc_item.setForeground(QColor(self.theme.color_disabled_text))
            self.settings_table.setItem(row, 2, desc_item)

            self.settings_table.setItem(row, 0, name_item)
            self.value_widgets[(row, 1)] = checkbox_widget

        self.settings_table.resizeRowsToContents()
        if self.settings_table.rowCount() > 0:
            self.settings_table.setCurrentCell(0, 1)
            first_widget = self.value_widgets.get((0, 1))
            if isinstance(first_widget, QCheckBox):
                first_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            else:
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
                if setting['key'] == 'PW_PREFIX_NAME':
                    combo.setEditable(True)
                    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                    prefix_line_edit = combo.lineEdit()
                    if prefix_line_edit is not None:
                        prefix_line_edit.setPlaceholderText(_("Enter prefix name"))

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

                current_val_text = current_val if isinstance(current_val, str) else ''
                if current_val_text and current_val_text not in setting['options']:
                    combo.addItem(current_val_text)
                combo.setCurrentText(current_val_text)

                if setting['key'] in ('PW_PREFIX_NAME', 'PW_VULKAN_USE') and self.game_source == "steam":
                    combo.setEnabled(False)
                    name_item.setForeground(QColor(self.theme.color_disabled_text))
                elif is_blocked:
                    combo.setEnabled(False)
                    name_item.setForeground(QColor(self.theme.color_disabled_text))

                combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

                self.advanced_table.setCellWidget(row, 1, combo)
                self.advanced_widgets[setting['key']] = combo

                if '_value_map' in setting:
                    reverse_map = {v: k for k, v in setting['_value_map'].items()}
                    if current_raw in reverse_map:
                        self.original_display_values[setting['key']] = reverse_map[current_raw]
                    else:
                        self.original_display_values[setting['key']] = current_val_text
                else:
                    self.original_display_values[setting['key']] = current_val_text

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
                if not current_val and not setting['default']:
                    line_edit.setPlaceholderText(_("Default value"))

                if is_blocked:
                    line_edit.setEnabled(False)
                    line_edit.setStyleSheet(self.theme.SETTINGS_DISABLED_INPUT_STYLE)

                if setting['key'] == 'PW_RUN_AFTER_EXE':
                    text_container = QWidget()
                    text_layout = QHBoxLayout(text_container)
                    text_layout.setContentsMargins(0, 0, 0, 0)
                    text_layout.setSpacing(6)
                    text_layout.addWidget(line_edit)

                    browse_button = AutoSizeButton("...", icon=ThemeManager().get_icon("folder"))
                    browse_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
                    browse_button.setFixedWidth(56)
                    browse_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    if is_blocked:
                        browse_button.setEnabled(False)

                    def open_run_after_exe_selector(
                        _checked: bool = False, target_line_edit=line_edit
                    ):
                        from portprotonqt.dialogs.file_explorer import FileExplorer

                        initial_path = os.path.expanduser("~")
                        current_path = target_line_edit.text().strip()
                        if current_path:
                            normalized = os.path.normpath(current_path)
                            if os.path.isfile(normalized):
                                initial_path = os.path.dirname(normalized)
                            elif os.path.isdir(normalized):
                                initial_path = normalized

                        file_explorer = FileExplorer(
                            self,
                            theme=self.theme,
                            file_filter=".exe",
                            initial_path=initial_path,
                        )
                        file_explorer.file_signal.file_selected.connect(
                            lambda file_path, target=target_line_edit: target.setText(os.path.normpath(file_path))
                        )
                        file_explorer.exec()

                    browse_button.clicked.connect(open_run_after_exe_selector)
                    text_layout.addWidget(browse_button)
                    self.advanced_table.setCellWidget(row, 1, text_container)
                else:
                    self.advanced_table.setCellWidget(row, 1, line_edit)
                self.advanced_widgets[setting['key']] = line_edit
                self.original_display_values[setting['key']] = current_val

            desc_item = QTableWidgetItem(setting['description'])
            desc_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if is_blocked:
                desc_item.setForeground(QColor(self.theme.color_disabled_text))
            self.advanced_table.setItem(row, 2, desc_item)

        if self.advanced_table.rowCount() > 0:
            self.on_table_selection_changed()
        self._install_line_edit_event_filters()

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

        self.keyboard.show_for_widget(widget)

    def register_gamepad_tooltip(self, widget: QWidget, text: str) -> None:
        """Register tooltip text for a focusable widget."""
        if text:
            self._gamepad_tooltip_map[widget] = text

    def show_registered_gamepad_tooltip(self, widget: QWidget) -> bool:
        """Show registered tooltip for the provided widget."""
        text = self._gamepad_tooltip_map.get(widget, "")
        if not text:
            return False
        self.show_gamepad_tooltip(show=True, text=text, anchor_widget=widget)
        return True

    def _install_line_edit_event_filters(self) -> None:
        """Install event filter for all line edits in the dialog."""
        for line_edit in self.findChildren(QLineEdit):
            if line_edit.property("ppqt_ctx_menu_filter_installed"):
                continue
            line_edit.setProperty("ppqt_ctx_menu_filter_installed", True)
            line_edit.installEventFilter(self)

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
        self._filter_gamescope_settings(search_text)

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

            widget = self.value_widgets.get((row, 1))
            if not isinstance(widget, QCheckBox):
                continue

            new_val = '1' if widget.isChecked() else '0'
            if new_val != orig_val:
                changes.append(f"{key}={new_val}")
                # Track if PW_MANGOHUD is being enabled
                if key == 'PW_MANGOHUD' and new_val == '1':
                    mangohud_enabled = True

        for key, widget in self.advanced_widgets.items():
            orig_val = self.original_display_values.get(key, '')
            if isinstance(widget, QComboBox):
                new_val = widget.currentText()
                if key in ('PW_PREFIX_NAME', 'PW_VULKAN_USE') and self.game_source == "steam":
                    continue
                if key == 'PW_PREFIX_NAME':
                    new_val = re.sub(r"[ \t]", "_", new_val.strip()).upper()

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

        mangohud_changes = self._collect_mangohud_changes()
        gamescope_changes = []
        if self.gamescope_available:
            gamescope_changes = self._collect_gamescope_changes()
        changes.extend(mangohud_changes)
        changes.extend(gamescope_changes)

        # Check if PW_MANGOHUD or PW_GAMESCOPE toggle changes are already in the list
        has_mangohud_toggle = any(change.startswith("PW_MANGOHUD=") for change in mangohud_changes)
        has_gamescope_toggle = any(change.startswith("PW_GAMESCOPE=") for change in gamescope_changes)

        # Only force-enable if there are other changes but no explicit toggle change
        if mangohud_changes and not has_mangohud_toggle:
            changes = [change for change in changes if not change.startswith("PW_MANGOHUD=")]
            changes.append("PW_MANGOHUD=1")

        if gamescope_changes and not has_gamescope_toggle:
            changes = [change for change in changes if not change.startswith("PW_GAMESCOPE=")]
            changes.append("PW_GAMESCOPE=1")

        # If PW_MANGOHUD is being enabled and MANGOHUD_CONFIG is not in current settings,
        # add it from the var file
        has_mangohud_config_change = any(change.startswith("MANGOHUD_CONFIG=") for change in changes)
        if mangohud_enabled and 'MANGOHUD_CONFIG' not in self.current_settings and not has_mangohud_config_change:
            default_config = self._get_default_mangohud_config()
            if default_config:
                changes.append(f"MANGOHUD_CONFIG={default_config}")
                logger.info("Added MANGOHUD_CONFIG from var file: %s", default_config)

        if not changes:
            QMessageBox.information(self, _("Information"), _("No changes to apply."))
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
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.ContextMenu:
            context_event = cast(QContextMenuEvent, event)
            from portprotonqt.context_menu_manager import show_themed_line_edit_context_menu

            show_themed_line_edit_context_menu(obj, context_event.globalPos(), self.theme)
            return True

        if isinstance(obj, QCheckBox) and obj in self._gamepad_tooltip_map:
            if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self.show_registered_gamepad_tooltip(obj)
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                focused_widget = QApplication.focusWidget()
                if focused_widget not in self._gamepad_tooltip_map:
                    self.show_gamepad_tooltip(show=False)

        return super().eventFilter(obj, event)

    def show_gamepad_tooltip(self, show=True, text="", anchor_widget=None, anchor_global_pos=None):
        """Show or hide the gamepad tooltip with the provided text."""
        if show and text:
            tooltip_x_offset = self.theme.settings_tooltip_offset_x
            tooltip_y_offset = self.theme.settings_tooltip_offset_y
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
                global_pos.setX(global_pos.x() + tooltip_x_offset)
                global_pos.setY(global_pos.y() + tooltip_y_offset)

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
                global_pos.setX(global_pos.x() + tooltip_x_offset)
                global_pos.setY(global_pos.y() + tooltip_y_offset)

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
                global_pos.setX(global_pos.x() + tooltip_x_offset)
                global_pos.setY(global_pos.y() + tooltip_y_offset)

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
