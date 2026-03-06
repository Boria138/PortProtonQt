"""Proton Manager dialog for PortProtonQt."""

import os
import shutil
import tempfile
import urllib.parse
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QCheckBox, QHeaderView, QMessageBox, QLabel, QTextEdit,
    QHBoxLayout, QProgressBar, QFrame, QSizePolicy, QAbstractItemView,
    QStackedWidget, QPushButton
)
from PySide6.QtCore import Qt, QTimer

from portprotonqt.config_utils import get_portproton_start_command, read_theme_from_config
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.localization import _
from portprotonqt.version_utils import version_sort_key
from portprotonqt.dialogs.dialog_utils import create_dialog_hints_widget, update_dialog_hints
from portprotonqt.dialogs.wine_loader import WineLoadingThread, get_cpu_level
from portprotonqt.dialogs.wine_downloader import DownloadThread
from portprotonqt.dialogs.wine_extractor import ExtractionThread
from portprotonqt.preloader import Preloader

logger = get_logger(__name__)
theme_manager = ThemeManager()


class ProtonManager(QDialog):
    """Dialog for managing Proton/Wine versions."""

    def __init__(self, parent=None, portproton_location=None, theme=None, input_manager=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.selected_assets = {}
        self.current_extraction_thread = None
        self.current_download_thread = None
        self.is_downloading = False
        self.assets_to_download = []
        self.current_download_index = 0
        self.portproton_location = portproton_location
        self.input_manager = input_manager
        self.initial_command_executed = False
        self.wine_loading_thread = None

        self.main_window = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, 'input_manager'):
                self.main_window = parent_widget
                break
            parent_widget = parent_widget.parent()

        self.initUI()
        self.start_loading_wine_data()

        if self.input_manager:
            self.enable_proton_manager_mode()

    def initUI(self):
        self.setWindowTitle(_('Manage Wine versions'))
        self.resize(1133, 720)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.content_stack = QStackedWidget()

        self.preloader_widget = QWidget()
        preloader_layout = QVBoxLayout(self.preloader_widget)
        preloader_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preloader_container = QWidget()
        preloader_container_layout = QVBoxLayout(preloader_container)
        preloader_container_layout.addStretch()
        preloader_hlayout = QHBoxLayout()
        preloader_hlayout.addStretch()
        self.preloader = Preloader()
        preloader_hlayout.addWidget(self.preloader)
        preloader_hlayout.addStretch()
        preloader_container_layout.addLayout(preloader_hlayout)
        preloader_container_layout.addStretch()
        preloader_container_layout.setContentsMargins(0, 0, 0, 0)
        preloader_layout.addWidget(preloader_container)

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(5)

        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(False)
        self.tab_widget.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(self.tab_widget, 1)

        self.content_stack.addWidget(self.preloader_widget)
        self.content_stack.addWidget(self.content_widget)
        self.content_stack.setCurrentIndex(0)

        layout.addWidget(self.content_stack, 1)

        selection_widget = QWidget()
        selection_layout = QVBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 2, 0, 2)
        selection_layout.setSpacing(2)
        selection_label = QLabel(_("Selected WINE/Proton:"))
        selection_label.setMaximumHeight(20)
        selection_layout.addWidget(selection_label)
        self.selection_text = QTextEdit()
        self.selection_text.setMaximumHeight(80)
        self.selection_text.setReadOnly(True)
        self.selection_text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.selection_text.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
        self.selection_text.setPlainText(_("No WINE/Proton selected"))
        selection_layout.addWidget(self.selection_text)
        layout.addWidget(selection_widget)

        self.download_frame = QFrame()
        self.download_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.download_frame.setVisible(False)
        self.download_frame.setMaximumHeight(80)
        download_layout = QVBoxLayout(self.download_frame)
        download_layout.setContentsMargins(10, 5, 10, 5)
        download_layout.setSpacing(5)
        self.download_info_label = QLabel(_("Downloading: "))
        download_layout.addWidget(self.download_info_label)
        progress_layout = QHBoxLayout()
        self.download_progress = QProgressBar()
        self.download_progress.setMinimum(0)
        self.download_progress.setMaximum(100)
        self.cancel_btn = QPushButton(_('Cancel'))
        self.cancel_btn.clicked.connect(self.cancel_current_download)
        progress_layout.addWidget(self.download_progress, 4)
        progress_layout.addWidget(self.cancel_btn, 1)
        download_layout.addLayout(progress_layout)
        layout.addWidget(self.download_frame)

        if self.input_manager and self.main_window:
            self.current_theme_name = read_theme_from_config()
            self.hints_widget, self.hints_labels = create_dialog_hints_widget(
                self.theme, self.main_window, self.input_manager, context='proton_manager'
            )
            layout.addWidget(self.hints_widget)

        button_layout = QHBoxLayout()
        self.download_btn = QPushButton(_('Download Selected'))
        self.download_btn.clicked.connect(self.download_selected)
        self.download_btn.setEnabled(False)
        self.download_btn.setMinimumHeight(40)
        self.clear_btn = QPushButton(_('Clear All'))
        self.clear_btn.clicked.connect(self.clear_selection)
        self.clear_btn.setMinimumHeight(40)
        self.cancel_btn_dialog = QPushButton(_('Cancel'))
        self.cancel_btn_dialog.clicked.connect(self.reject)
        self.cancel_btn_dialog.setMinimumHeight(40)
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.cancel_btn_dialog)
        layout.addLayout(button_layout)

        self.tab_widget.currentChanged.connect(self.tab_changed)

        if self.input_manager and self.main_window:
            self.input_manager.button_event.connect(
                lambda *args: update_dialog_hints(
                    self.hints_labels, self.main_window, self.input_manager,
                    theme_manager, self.current_theme_name
                )
            )
            self.input_manager.dpad_moved.connect(
                lambda *args: update_dialog_hints(
                    self.hints_labels, self.main_window, self.input_manager,
                    theme_manager, self.current_theme_name
                )
            )
            update_dialog_hints(
                self.hints_labels, self.main_window, self.input_manager,
                theme_manager, self.current_theme_name
            )

    def start_loading_wine_data(self):
        self.wine_loading_thread = WineLoadingThread()
        self.wine_loading_thread.loading_complete.connect(self.on_wine_data_loaded)
        self.wine_loading_thread.loading_error.connect(self.on_wine_data_load_error)
        self.wine_loading_thread.start()

    def on_wine_data_loaded(self, metadata):
        self.process_metadata(metadata)
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == _("Installed"):
                self.tab_widget.removeTab(i)
                break
        self.create_installed_tab()
        if hasattr(self, 'content_stack'):
            self.content_stack.setCurrentIndex(1)

    def on_wine_data_load_error(self, error_msg):
        logger.error(f"Wine data loading failed: {error_msg}")
        if hasattr(self, 'content_stack'):
            self.content_stack.setCurrentIndex(1)
        error_label = QLabel(_("Error loading WINE/Proton: {error}").format(error=error_msg))
        error_label.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(self, 'tab_widget'):
            error_tab = QWidget()
            error_layout = QVBoxLayout(error_tab)
            error_layout.addWidget(error_label)
            self.tab_widget.addTab(error_tab, _("Error"))

    def process_metadata(self, metadata):
        self.cpu_level = get_cpu_level()
        logger.info(f"Detected CPU level: {self.cpu_level}")
        tabs_dict = {}
        for source_key, entries in metadata.items():
            filtered_entries = self.filter_entries_by_cpu_level(entries, source_key)
            tabs_dict[source_key] = filtered_entries
        if 'proton_lg' in tabs_dict:
            if self.create_tab_from_entries('proton_lg', tabs_dict['proton_lg']):
                pass
            del tabs_dict['proton_lg']
        for source_key in sorted(tabs_dict.keys()):
            entries = tabs_dict[source_key]
            if self.create_tab_from_entries(source_key, entries):
                pass
        return True

    def filter_entries_by_cpu_level(self, entries, source_name):
        if source_name.lower() != 'proton_cachyos':
            return entries
        if self.cpu_level >= 4:
            return entries
        filtered_entries = []
        for entry in entries:
            url = entry.get('url', '')
            filename = entry.get('name', '')
            if url:
                parsed_url = urllib.parse.urlparse(url)
                url_filename = os.path.basename(parsed_url.path)
                if url_filename:
                    filename = url_filename
            should_include = True
            if 'v2' in filename and self.cpu_level < 2:
                should_include = False
            elif 'v3' in filename and self.cpu_level < 3:
                should_include = False
            elif 'v4' in filename and self.cpu_level < 4:
                should_include = False
            if should_include:
                filtered_entries.append(entry)
        logger.info(f"Filtered {len(entries)} -> {len(filtered_entries)} entries for {source_name}")
        return filtered_entries

    def create_table_widget(self):
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['', _('Version WINE/Proton'), _('Size')])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.cellClicked.connect(self.on_cell_clicked)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def create_tab_from_entries(self, source_name, entries):
        try:
            tab = QWidget()
            tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setSpacing(5)
            table = self.create_table_widget()
            all_entries = []
            for entry in entries:
                url = entry.get('url', '')
                if url:
                    parsed_url = urllib.parse.urlparse(url)
                    url_filename = os.path.basename(parsed_url.path)
                    if url_filename:
                        entry['filename'] = url_filename
                all_entries.append(entry)
            all_entries.sort(key=version_sort_key)
            table.setRowCount(len(all_entries))
            for row_index, entry in enumerate(all_entries):
                self.add_asset_row_from_json(table, row_index, entry, source_name)
            layout.addWidget(table, 1)
            tab_name = (self.get_short_source_name(source_name) or "UNKNOWN").upper()
            self.tab_widget.addTab(tab, tab_name)
            logger.info(f"Successfully created tab for {source_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating tab for {source_name}: {e}")
            return False

    def get_short_source_name(self, full_name):
        if full_name is None:
            return "UNKNOWN"
        return full_name.upper()

    def add_asset_row_from_json(self, table, row_index, entry, source_name):
        url = entry.get('url', '')
        filename = entry.get('name', '')
        size_human = entry.get('size_human', _('Unknown'))
        if url:
            parsed_url = urllib.parse.urlparse(url)
            url_filename = os.path.basename(parsed_url.path)
            if url_filename:
                filename = url_filename
        version_from_name = self.extract_version_from_name(filename)
        uppercase_filename = filename.upper()
        is_installed = self.is_asset_installed(uppercase_filename, source_name)
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox = QCheckBox()
        asset_data = {'name': filename, 'browser_download_url': url}
        if is_installed:
            checkbox.setEnabled(False)
            checkbox.setChecked(False)
        else:
            checkbox.stateChanged.connect(
                lambda state, a=asset_data, v=version_from_name, s=source_name:
                self.on_asset_toggled_json(state, a, v, s)
            )
        checkbox_layout.addWidget(checkbox)
        table.setCellWidget(row_index, 0, checkbox_widget)
        display_name = filename
        if filename.lower().endswith(('.tar.xz', '.tar.gz')):
            display_name = filename[:-7]
        asset_name_item = QTableWidgetItem(display_name)
        if is_installed:
            asset_name_item.setFlags(asset_name_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            asset_name_item.setText(_('{display_name} (installed)').format(display_name=display_name))
        table.setItem(row_index, 1, asset_name_item)
        size_item = QTableWidgetItem(size_human)
        size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row_index, 2, size_item)
        unique_id = f"{source_name}_{version_from_name}_{filename}"
        for col in range(table.columnCount()):
            item = table.item(row_index, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, {
                    'asset': asset_data,
                    'unique_id': unique_id,
                    'json_entry': entry,
                    'source_name': source_name,
                    'version': version_from_name
                })

    def extract_version_from_name(self, name):
        if not name:
            return "N/A"
        basename = os.path.splitext(name)[0]
        basename = os.path.splitext(basename)[0]
        if 'GE-Proton' in basename:
            parts = basename.split('-')
            if len(parts) >= 2:
                return '-'.join(parts[:2])
        elif 'wine-' in basename.lower():
            parts = basename.split('-')
            if len(parts) >= 2:
                return parts[1]
        elif 'proton-' in basename.lower():
            parts = basename.split('-')
            if len(parts) >= 2:
                return parts[1]
        return basename.split('-')[0] if '-' in basename else basename

    def is_asset_installed(self, asset_filename, source_name):
        if not self.portproton_location:
            return False
        name_without_ext = asset_filename
        for ext in ['.tar.gz', '.tar.xz']:
            if name_without_ext.lower().endswith(ext):
                name_without_ext = name_without_ext[:-len(ext)]
                break
        dist_path = os.path.join(self.portproton_location, "data", "dist")
        expected_dir = os.path.join(dist_path, name_without_ext)
        return os.path.exists(expected_dir)

    def create_installed_tab(self):
        if not self.portproton_location:
            return
        dist_path = os.path.join(self.portproton_location, "data", "dist")
        if not os.path.exists(dist_path):
            os.makedirs(dist_path, exist_ok=True)
        installed_versions = [d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))]
        if not installed_versions:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            label = QLabel(_("No Wine/Proton versions installed"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 16px; padding: 50px;")
            layout.addWidget(label)
            self.tab_widget.addTab(tab, _("Installed"))
            return
        tab = QWidget()
        tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        table = self.create_table_widget()
        installed_versions.sort(key=version_sort_key)
        table.setRowCount(len(installed_versions))
        for row_index, version_name in enumerate(installed_versions):
            self.add_installed_row(table, row_index, version_name)
        layout.addWidget(table, 1)
        self.tab_widget.addTab(tab, _("Installed"))

    def add_installed_row(self, table, row_index, version_name):
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox = QCheckBox()
        checkbox_widget.setToolTip(_("Select to remove this WINE/Proton"))
        checkbox.stateChanged.connect(lambda state: self.on_installed_version_toggled(state))
        checkbox_layout.addWidget(checkbox)
        table.setCellWidget(row_index, 0, checkbox_widget)
        version_item = QTableWidgetItem(version_name)
        version_item.setFlags(version_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row_index, 1, version_item)
        if self.portproton_location:
            dist_path = os.path.join(self.portproton_location, "data", "dist")
            version_path = os.path.join(dist_path, version_name)
            size_str = self.get_directory_size(version_path)
        else:
            size_str = _("Unknown")
            version_path = ""
        size_item = QTableWidgetItem(size_str)
        size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row_index, 2, size_item)
        for col in range(table.columnCount()):
            item = table.item(row_index, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, {
                    'version_name': version_name,
                    'version_path': version_path
                })

    def on_installed_version_toggled(self, state):
        self.update_selection_display()

    def get_directory_size(self, path):
        try:
            total_size = 0
            for dirpath, _dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            if total_size == 0:
                return "0 B"
            elif total_size < 1024:
                return f"{total_size}.0 B"
            elif total_size < 1024 * 1024:
                return f"{int(total_size / 1024)}.{int((total_size / 1024 * 10) % 10)} KiB"
            elif total_size < 1024 * 1024 * 1024:
                return f"{int(total_size / (1024 * 1024))}.{int((total_size / (1024 * 1024) * 10) % 10)} MiB"
            elif total_size < 1024 * 1024 * 1024 * 1024:
                return f"{int(total_size / (1024 * 1024 * 1024))}.{int((total_size / (1024 * 1024 * 1024) * 10) % 10)} GiB"
            else:
                return f"{int(total_size / (1024 * 1024 * 1024 * 1024))}.{int((total_size / (1024 * 1024 * 1024 * 1024) * 10) % 10)} TiB"
        except Exception as e:
            logger.debug("Failed to format size: %s", e)
            return _("Unknown")

    def convert_size_to_bytes(self, size_str):
        if not size_str or size_str == _("Unknown"):
            return 0
        size_str = size_str.strip()
        if size_str.endswith("TiB"):
            num = float(size_str[:-3].strip())
            return int(num * 1024 * 1024 * 1024 * 1024)
        elif size_str.endswith("GiB"):
            num = float(size_str[:-3].strip())
            return int(num * 1024 * 1024 * 1024)
        elif size_str.endswith("MiB"):
            num = float(size_str[:-3].strip())
            return int(num * 1024 * 1024)
        elif size_str.endswith("KiB"):
            num = float(size_str[:-3].strip())
            return int(num * 1024)
        elif size_str.endswith("B"):
            num = float(size_str[:-1].strip())
            return int(num)
        return 0

    def format_bytes(self, bytes_value):
        if bytes_value == 0:
            return "0 B"
        elif bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 * 1024:
            kb_value = bytes_value / 1024
            return f"{kb_value:.1f} KiB"
        elif bytes_value < 1024 * 1024 * 1024:
            mb_value = bytes_value / (1024 * 1024)
            return f"{mb_value:.1f} MiB"
        elif bytes_value < 1024 * 1024 * 1024 * 1024:
            gb_value = bytes_value / (1024 * 1024 * 1024)
            return f"{gb_value:.1f} GiB"
        else:
            tb_value = bytes_value / (1024 * 1024 * 1024 * 1024)
            return f"{tb_value:.1f} TiB"

    def on_cell_clicked(self, row):
        tab = self.tab_widget.currentWidget()
        table = tab.findChild(QTableWidget)
        if table:
            checkbox_widget = table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isEnabled():
                    checkbox.setChecked(not checkbox.isChecked())
                    self.update_selection_display()

    def on_asset_toggled_json(self, state, asset, version, source_name):
        url = asset.get('browser_download_url', '')
        filename = asset.get('name', '')
        if url:
            parsed_url = urllib.parse.urlparse(url)
            url_filename = os.path.basename(parsed_url.path)
            if url_filename:
                filename = url_filename
        unique_id = f"{source_name}_{version}_{filename}"
        if state == Qt.CheckState.Checked.value:
            self.selected_assets[unique_id] = {
                'source_name': source_name,
                'version': version,
                'asset': asset,
                'asset_name': filename,
                'download_url': asset['browser_download_url']
            }
        else:
            if unique_id in self.selected_assets:
                del self.selected_assets[unique_id]
        self.update_selection_display()

    def update_selection_display(self):
        current_tab_index = self.tab_widget.currentIndex()
        current_tab_text = self.tab_widget.tabText(current_tab_index)
        if current_tab_text == _("Installed"):
            current_tab = self.tab_widget.currentWidget()
            table = current_tab.findChild(QTableWidget)
            if table:
                selected_count = 0
                total_size = 0
                for row in range(table.rowCount()):
                    checkbox_widget = table.cellWidget(row, 0)
                    if checkbox_widget:
                        checkbox = checkbox_widget.findChild(QCheckBox)
                        if checkbox and checkbox.isChecked():
                            selected_count += 1
                            size_item = table.item(row, 2)
                            if size_item:
                                size_text = size_item.text()
                                size_bytes = self.convert_size_to_bytes(size_text)
                                if size_bytes:
                                    total_size += size_bytes
                if selected_count > 0:
                    selection_text = _('Selected {} WINE/Proton:\n').format(selected_count)
                    current_tab = self.tab_widget.currentWidget()
                    table = current_tab.findChild(QTableWidget)
                    if table:
                        item_number = 1
                        for row in range(table.rowCount()):
                            checkbox_widget = table.cellWidget(row, 0)
                            if checkbox_widget:
                                checkbox = checkbox_widget.findChild(QCheckBox)
                                if checkbox and checkbox.isChecked():
                                    version_item = table.item(row, 1)
                                    if version_item:
                                        version_name = version_item.text()
                                        selection_text += f"{item_number}. {version_name}\n"
                                        item_number += 1
                    total_size_text = self.format_bytes(total_size)
                    selection_text += _("\nTotal size to delete: {}\n").format(total_size_text)
                    self.download_btn.setText(_('Delete Selected'))
                    self.download_btn.setEnabled(True)
                else:
                    selection_text = _("No assets selected")
                    self.download_btn.setText(_('Delete Selected'))
                    self.download_btn.setEnabled(False)
                self.selection_text.setPlainText(selection_text)
            else:
                self.selection_text.setPlainText(_("No assets selected"))
                self.download_btn.setText(_('Delete Selected'))
                self.download_btn.setEnabled(False)
        else:
            if self.selected_assets:
                selection_text = _('Selected {} assets:\n').format(len(self.selected_assets))
                total_size = 0
                for i, asset_data in enumerate(self.selected_assets.values(), 1):
                    selection_text += f"{i}. {asset_data['asset_name']}\n"
                    for tab_index in range(self.tab_widget.count()):
                        tab = self.tab_widget.widget(tab_index)
                        table = tab.findChild(QTableWidget)
                        if table and self.tab_widget.tabText(tab_index) != _("Installed"):
                            for row in range(table.rowCount()):
                                table_item = table.item(row, 1)
                                if table_item:
                                    table_item_name = table_item.text()
                                    for ext in ['.tar.xz', '.tar.gz', '.zip']:
                                        if table_item_name.lower().endswith(ext):
                                            table_item_name = table_item_name[:-len(ext)]
                                            break
                                    asset_name_for_comparison = asset_data['asset_name']
                                    for ext in ['.tar.xz', '.tar.gz', '.zip']:
                                        if asset_name_for_comparison.lower().endswith(ext):
                                            asset_name_for_comparison = asset_name_for_comparison[:-len(ext)]
                                            break
                                    if table_item_name == asset_name_for_comparison:
                                        user_data = table_item.data(Qt.ItemDataRole.UserRole)
                                        if user_data and 'json_entry' in user_data:
                                            json_entry = user_data['json_entry']
                                            size_text = json_entry.get('size_human', 'Unknown')
                                            size_bytes = self.convert_size_to_bytes(size_text)
                                            if size_bytes:
                                                total_size += size_bytes
                                            break
                total_size_text = self.format_bytes(total_size)
                selection_text += _("\nTotal size to download: {}\n").format(total_size_text)
                self.selection_text.setPlainText(selection_text)
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(True)
            else:
                self.selection_text.setPlainText(_("No assets selected"))
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(False)

    def tab_changed(self, index):
        current_tab_text = self.tab_widget.tabText(index)
        if current_tab_text == _("Installed"):
            current_tab = self.tab_widget.widget(index)
            table = current_tab.findChild(QTableWidget)
            if table:
                selected_count = 0
                for row in range(table.rowCount()):
                    checkbox_widget = table.cellWidget(row, 0)
                    if checkbox_widget:
                        checkbox = checkbox_widget.findChild(QCheckBox)
                        if checkbox and checkbox.isChecked():
                            selected_count += 1
                if selected_count > 0:
                    self.download_btn.setText(_('Delete Selected'))
                    self.download_btn.setEnabled(True)
                else:
                    self.download_btn.setText(_('Delete Selected'))
                    self.download_btn.setEnabled(False)
        else:
            if self.selected_assets:
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(True)
            else:
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(False)
        self.update_selection_display()

    def clear_selection(self):
        if self.is_downloading:
            QMessageBox.warning(self, _("Downloading in Progress"), _("Cannot clear selection while extraction is in progress."))
            return
        self.selected_assets.clear()
        for tab_index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(tab_index)
            table = tab.findChild(QTableWidget)
            if table:
                for row in range(table.rowCount()):
                    checkbox_widget = table.cellWidget(row, 0)
                    if checkbox_widget:
                        checkbox = checkbox_widget.findChild(QCheckBox)
                        if checkbox:
                            checkbox.setChecked(False)
        self.update_selection_display()

    def download_selected(self):
        current_tab_index = self.tab_widget.currentIndex()
        current_tab_text = self.tab_widget.tabText(current_tab_index)
        if current_tab_text == _("Installed"):
            self.remove_selected_installed_versions()
        else:
            if not self.selected_assets:
                QMessageBox.warning(self, _("No Selection"), _("Please select at least one WINE/Proton to download."))
                return
            if self.is_downloading:
                QMessageBox.warning(self, _("Downloading in Progress"), _("Please wait for current downloading to complete."))
                return
            downloads_dir = "proton_downloads"
            if not os.path.exists(downloads_dir):
                os.makedirs(downloads_dir)
            self.assets_to_download = list(self.selected_assets.values())
            self.current_download_index = 0
            self.is_downloading = True
            self.start_next_download()

    def remove_selected_installed_versions(self):
        current_tab = self.tab_widget.currentWidget()
        table = current_tab.findChild(QTableWidget)
        if not table:
            return
        versions_to_remove = []
        for row in range(table.rowCount()):
            checkbox_widget = table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    item = table.item(row, 1)
                    if item:
                        user_data = item.data(Qt.ItemDataRole.UserRole)
                        if user_data:
                            versions_to_remove.append(user_data['version_path'])
        if not versions_to_remove:
            if self.input_manager:
                self.disable_proton_manager_mode()
            try:
                QMessageBox.warning(self, _("No Selection"), _("Please select at least one WINE/Proton to delete."))
            finally:
                if self.input_manager:
                    self.enable_proton_manager_mode()
            return
        if self.input_manager:
            self.disable_proton_manager_mode()
        try:
            reply = QMessageBox.question(
                self, _("Confirm Deletion"),
                _("Are you sure you want to delete {} selected WINE/Proton?\n\nThis action cannot be undone.").format(len(versions_to_remove)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
        finally:
            if self.input_manager:
                self.enable_proton_manager_mode()
        if reply != QMessageBox.StandardButton.Yes:
            return
        removed_count = 0
        for version_path in versions_to_remove:
            try:
                if os.path.exists(version_path):
                    shutil.rmtree(version_path)
                    removed_count += 1
            except Exception as e:
                logger.error(f"Error removing version at {version_path}: {e}")
                QMessageBox.warning(self, _("Error"), _("Failed to remove WINE/Proton at {}: {}").format(version_path, str(e)))
        if removed_count > 0:
            QMessageBox.information(self, _("Success"), _("Successfully removed {} WINE/Proton.").format(removed_count))
            self.refresh_installed_tab()

    def refresh_installed_tab(self):
        installed_tab_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == _("Installed"):
                installed_tab_index = i
                break
        if installed_tab_index != -1:
            self.tab_widget.removeTab(installed_tab_index)
            self.create_installed_tab()

    def start_next_download(self):
        if self.current_download_index >= len(self.assets_to_download):
            self.download_frame.setVisible(False)
            self.download_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.is_downloading = False
            self.selected_assets.clear()

            # Сбросить все галочки во всех вкладках
            self.clear_selection()

            # Обновить вкладку установленных версий
            self.refresh_installed_tab()

            import subprocess
            try:
                start_cmd = get_portproton_start_command()
                if start_cmd and not self.initial_command_executed:
                    result = subprocess.run(start_cmd + ["cli", "--initial"], timeout=10)
                    if result.returncode != 0:
                        logger.warning(f"Initial PortProton command returned non-zero exit code: {result.returncode}")
                    else:
                        logger.info("Initial PortProton command executed successfully")
                    self.initial_command_executed = True
                elif self.initial_command_executed:
                    logger.debug("Initial PortProton command already executed, skipping")
            except subprocess.TimeoutExpired:
                logger.warning("Initial PortProton command timed out")
            except Exception as e:
                logger.error(f"Error running initial PortProton command: {e}")
            QMessageBox.information(self, _("Downloading Complete"), _("All selected WINE/Proton have been downloaded!"))
            return
        asset_data = self.assets_to_download[self.current_download_index]
        self.download_asset(asset_data)

    def download_asset(self, asset_data):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proton_downloads_path = os.path.join(repo_root, "proton_downloads")
        local_file_path = None
        if os.path.exists(proton_downloads_path) and os.path.isdir(proton_downloads_path):
            for filename in os.listdir(proton_downloads_path):
                if filename == asset_data['asset_name']:
                    local_file_path = os.path.join(proton_downloads_path, filename)
                    logger.info(f"DEBUG: Using local file: {local_file_path}")
                    break
        if local_file_path and os.path.exists(local_file_path):
            logger.info(f"DEBUG: Skipping download, using local file: {local_file_path}")
            download_info = f"{asset_data['source_name'].upper()} - {asset_data['asset_name']} (DEBUG: local)"
            if len(download_info) > 80:
                download_info = download_info[:77] + "..."
            self.download_progress.setValue(0)
            self.download_frame.setVisible(True)
            self.download_frame.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
            self.download_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            QTimer.singleShot(100, lambda: self.start_extraction_for_asset(asset_data, local_file_path))
        else:
            temp_dir = tempfile.mkdtemp(prefix="portproton_wine_")
            filename = os.path.join(temp_dir, asset_data['asset_name'])
            download_url = asset_data['download_url']
            download_info = f"{asset_data['source_name'].upper()} - {asset_data['asset_name']}"
            if len(download_info) > 80:
                download_info = download_info[:77] + "..."
            self.download_progress.setValue(0)
            self.download_frame.setVisible(True)
            self.download_frame.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
            self.download_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.current_download_thread = DownloadThread(download_url, filename)
            def update_download_progress(progress):
                self.download_progress.setValue(progress)
                self.download_info_label.setText(_("Downloading: {0} ({1}%)").format(asset_data['asset_name'], progress))
            def download_finished(filepath, success):
                if success:
                    logger.info(f"Successfully downloaded: {filepath}")
                    self.start_extraction_for_asset(asset_data, filepath)
                else:
                    logger.error(f"Failed to download: {filepath}")
                    temp_dir = os.path.dirname(filepath)
                    try:
                        shutil.rmtree(temp_dir)
                    except (OSError, FileNotFoundError):
                        pass
                    self.current_download_index += 1
                    QTimer.singleShot(100, self.start_next_download)
            def download_error(error_msg):
                logger.error(f"Download error: {error_msg}")
                QMessageBox.critical(self, "Download Error", f"Failed to download archive: {error_msg}")
                temp_dir = os.path.dirname(filename)
                try:
                    shutil.rmtree(temp_dir)
                except (OSError, FileNotFoundError):
                    pass
                self.current_download_index += 1
                QTimer.singleShot(100, self.start_next_download)
            self.current_download_thread.progress.connect(update_download_progress)
            self.current_download_thread.finished.connect(download_finished)
            self.current_download_thread.error.connect(download_error)
            self.current_download_thread.start()

    def start_extraction_for_asset(self, asset_data, filepath):
        self.download_info_label.setText(_("Extracting: {0}").format(asset_data['asset_name']))
        if self.portproton_location:
            try:
                dist_path = os.path.join(self.portproton_location, "data", "dist")
                extract_dir = dist_path
                self.current_extraction_thread = ExtractionThread(filepath, extract_dir)
                current_speed = [0.0]
                current_eta = [0]
                def update_extraction_progress(progress):
                    self.download_progress.setValue(progress)
                    eta_text = _(', ETA: {}s').format(current_eta[0]) if current_eta[0] > 0 else ""
                    speed_text = _(', Speed: {:.1f}MB/s').format(current_speed[0]) if current_speed[0] > 0 else ""
                    self.download_info_label.setText(_("Extracting: {0}{1}{2}").format(
                        asset_data['asset_name'], speed_text, eta_text))
                def update_extraction_speed(speed):
                    current_speed[0] = speed
                def update_extraction_eta(eta):
                    current_eta[0] = eta
                def extraction_finished(archive_path, success):
                    if success:
                        logger.info(f"Successfully extracted: {archive_path}")
                    else:
                        logger.error(f"Failed to extract: {archive_path}")
                        QMessageBox.critical(self, _("Extraction Error"), _("Failed to extract archive: {0}").format(archive_path))
                    temp_dir = os.path.dirname(filepath)
                    try:
                        shutil.rmtree(temp_dir)
                        logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Could not clean up temporary directory {temp_dir}: {e}")
                    if self.current_extraction_thread and self.current_extraction_thread.isRunning():
                        logger.debug("Waiting for extraction thread to finish...")
                        if not self.current_extraction_thread.wait(500):
                            logger.warning("Extraction thread still running, but continuing...")
                    self.current_download_index += 1
                    QTimer.singleShot(100, self.start_next_download)
                def extraction_error(error_msg):
                    logger.error(f"Extraction error: {error_msg}")
                    QMessageBox.critical(self, "Extraction Error", f"Failed to extract archive: {error_msg}")
                    temp_dir = os.path.dirname(filepath)
                    try:
                        shutil.rmtree(temp_dir)
                        logger.debug(f"Cleaned up temporary directory after error: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Could not clean up temporary directory {temp_dir}: {e}")
                    if self.current_extraction_thread and self.current_extraction_thread.isRunning():
                        logger.debug("Waiting for extraction thread to finish after error...")
                        if not self.current_extraction_thread.wait(500):
                            logger.warning("Extraction thread still running after error, but continuing...")
                    self.current_download_index += 1
                    QTimer.singleShot(100, self.start_next_download)
                self.current_extraction_thread.progress.connect(update_extraction_progress)
                self.current_extraction_thread.speed.connect(update_extraction_speed)
                self.current_extraction_thread.eta.connect(update_extraction_eta)
                self.current_extraction_thread.finished.connect(extraction_finished)
                self.current_extraction_thread.error.connect(extraction_error)
                self.current_extraction_thread.start()
            except Exception as e:
                temp_dir = os.path.dirname(filepath)
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temporary directory after exception: {temp_dir}")
                except Exception as cleanup_error:
                    logger.warning(f"Could not clean up temporary directory {temp_dir}: {cleanup_error}")
                logger.error(f"Error starting extraction thread for {filepath}: {e}")
                QMessageBox.critical(self, "Extraction Error", f"Failed to start extraction: {e}")
                self.current_download_index += 1
                QTimer.singleShot(100, self.start_next_download)
        else:
            temp_dir = os.path.dirname(filepath)
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Could not clean up temporary directory {temp_dir}: {e}")
            logger.warning("PortProton location not provided, skipping extraction")
            self.current_download_index += 1
            QTimer.singleShot(100, self.start_next_download)

    def has_active_processes(self):
        extraction_active = (self.current_extraction_thread and self.current_extraction_thread.isRunning())
        download_active = (self.current_download_thread and hasattr(self.current_download_thread, 'isRunning') and self.current_download_thread.isRunning())
        return extraction_active or download_active

    def cancel_current_download(self):
        if self.current_extraction_thread and self.current_extraction_thread.isRunning():
            self.current_extraction_thread.stop()
            if not self.current_extraction_thread.wait(1000):
                logger.warning("Extraction thread did not stop gracefully")
        try:
            if (self.current_download_thread and hasattr(self.current_download_thread, 'isRunning') and self.current_download_thread.isRunning()):
                if hasattr(self.current_download_thread, 'stop'):
                    self.current_download_thread.stop()
                if not self.current_download_thread.wait(1000):
                    logger.warning("Download thread did not stop gracefully")
        except RuntimeError:
            logger.debug("Download thread object already deleted during cancel")
        self.assets_to_download = []
        self.current_download_index = 0
        self.is_downloading = False
        self.initial_command_executed = False
        self.download_frame.setVisible(False)
        self.download_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        QMessageBox.information(self, _("Operation Cancelled"), _("Download or extraction has been cancelled."))

    def enable_proton_manager_mode(self):
        if self.input_manager:
            self.input_manager.enable_proton_manager_mode(self)

    def disable_proton_manager_mode(self):
        if self.input_manager:
            self.input_manager.disable_proton_manager_mode()

    def closeEvent(self, event):
        logger.debug("Closing ProtonManager dialog...")
        if self.input_manager:
            self.disable_proton_manager_mode()
        if self.has_active_processes():
            logger.debug("Active processes detected, cancelling before close...")
            self.cancel_current_download()
        else:
            if self.current_extraction_thread and self.current_extraction_thread.isRunning():
                logger.debug("Stopping current extraction thread...")
                self.current_extraction_thread.stop()
                if not self.current_extraction_thread.wait(2000):
                    logger.warning("Extraction thread did not stop gracefully during close")
            try:
                if (self.current_download_thread and hasattr(self.current_download_thread, 'isRunning') and self.current_download_thread.isRunning()):
                    logger.debug("Stopping current download thread...")
                    if hasattr(self.current_download_thread, 'stop'):
                        self.current_download_thread.stop()
                    if not self.current_download_thread.wait(2000):
                        logger.warning("Download thread did not stop gracefully during close")
            except RuntimeError:
                logger.debug("Download thread object already deleted during close")
            if self.is_downloading and self.current_download_index < len(self.assets_to_download):
                self.initial_command_executed = False
        event.accept()

    def reject(self):
        if self.input_manager:
            self.disable_proton_manager_mode()
        if self.has_active_processes():
            logger.debug("Active processes detected, cancelling before reject...")
            self.cancel_current_download()
        else:
            if self.is_downloading and self.current_download_index < len(self.assets_to_download):
                self.initial_command_executed = False
            super().reject()


def show_proton_manager(parent=None, portproton_location=None, input_manager=None):
    dialog = ProtonManager(parent, portproton_location, input_manager=input_manager)
    dialog.show()
    return dialog
