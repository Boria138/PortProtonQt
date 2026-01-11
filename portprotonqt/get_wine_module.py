import os
import shutil
import tempfile
import time
import libarchive
import requests
import orjson
from PySide6.QtWidgets import (QDialog, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget, QCheckBox,
                               QPushButton, QHeaderView, QMessageBox,
                               QLabel, QTextEdit, QHBoxLayout, QProgressBar,
                               QFrame, QSizePolicy, QAbstractItemView)
from PySide6.QtCore import Qt, QThread, Signal, QMutex, QWaitCondition, QTimer
import urllib.parse
from portprotonqt.config_utils import read_proxy_config, get_portproton_start_command, read_theme_from_config
from portprotonqt.logger import get_logger
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.localization import _
from portprotonqt.version_utils import version_sort_key
from portprotonqt.dialogs import create_dialog_hints_widget, update_dialog_hints

logger = get_logger(__name__)
theme_manager = ThemeManager()


def get_cpu_level():
    """
    Determine CPU level based on feature flags
    Returns:
        int: CPU level (0-4) based on supported instruction sets
    """
    try:
        with open('/proc/cpuinfo') as f:
            # Read line by line to find flags without loading entire file
            for line in f:
                if line.startswith('flags'):
                    # Extract the actual flags
                    flags = set(line.split(':')[1].strip().split())
                    break
            else:
                # If no flags line found
                logger.warning("Could not find flags in /proc/cpuinfo, defaulting to CPU level 4")
                return 4
    except FileNotFoundError:
        logger.warning("Could not read /proc/cpuinfo, defaulting to CPU level 4")
        return 4  # Default to highest level if we can't read cpuinfo

    # Check for required flags for each level using a more efficient approach
    # Pre-define the flag requirements for each level
    level1_required = {'lm', 'cmov', 'cx8', 'fpu', 'fxsr', 'mmx', 'syscall', 'sse2'}
    if not level1_required.issubset(flags):
        return 0

    level2_required = {'cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2', 'ssse3'}
    if not level2_required.issubset(flags):
        return 1

    level3_required = {'avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'abm', 'movbe', 'xsave'}
    if not level3_required.issubset(flags):
        return 2

    level4_required = {'avx512f', 'avx512bw', 'avx512cd', 'avx512dq', 'avx512vl'}
    if level4_required.issubset(flags):
        return 4

    return 3

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str, bool)
    error = Signal(str)

    def __init__(self, download_url, filename):
        super().__init__()
        self.download_url = download_url
        self.filename = filename
        self._is_running = True
        self._mutex = QMutex()
        self._condition = QWaitCondition()

    def run(self):
        try:
            # Create a session with proxy support
            session = requests.Session()
            proxy = read_proxy_config() or {}
            if proxy:
                session.proxies.update(proxy)
            session.verify = True

            response = session.get(self.download_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(self.filename, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    self._mutex.lock()
                    if not self._is_running:
                        self._mutex.unlock()
                        # Если загрузка отменена, удаляем частично скачанный файл
                        if os.path.exists(self.filename):
                            os.remove(self.filename)
                        return
                    self._mutex.unlock()

                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress.emit(progress)

            self._mutex.lock()
            if self._is_running:
                self._mutex.unlock()
                self.finished.emit(self.filename, True)
            else:
                self._mutex.unlock()
                # Если загрузка отменена в последний момент, удаляем файл
                if os.path.exists(self.filename):
                    os.remove(self.filename)

        except Exception as e:
            self._mutex.lock()
            if self._is_running:
                self._mutex.unlock()
                # Удаляем частично скачанный файл при ошибке
                if os.path.exists(self.filename):
                    try:
                        os.remove(self.filename)
                    except OSError:
                        pass
                self.error.emit(str(e))
            else:
                self._mutex.unlock()

    def stop(self):
        """Безопасная остановка потока"""
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

        if self.isRunning():
            self.quit()
            if not self.wait(1000):  # Ждем до 1 секунды
                logger.warning("Thread did not stop gracefully, but continuing...")


class ExtractionThread(QThread):
    progress = Signal(int)          # %
    speed = Signal(float)           # MB/s
    eta = Signal(int)               # seconds
    finished = Signal(str, bool)    # archive_path, success
    error = Signal(str)

    def __init__(self, archive_path: str, extract_dir: str):
        super().__init__()
        self.archive_path = archive_path
        self.extract_dir = extract_dir

        self._is_running = True
        self._mutex = QMutex()

    # ========================
    # Internal helpers
    # ========================

    def _should_stop(self) -> bool:
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return not running

    # ========================
    # Main logic
    # ========================

    def run(self):
        try:
            self.progress.emit(0)
            self.speed.emit(0.0)
            self.eta.emit(0)

            os.makedirs(self.extract_dir, exist_ok=True)

            archive_size = os.path.getsize(self.archive_path)
            if archive_size <= 0:
                archive_size = 1

            start_time = time.monotonic()
            last_emit_time = start_time
            last_progress = -1
            last_bytes_read = 0

            # Меняем рабочую директорию для корректной распаковки
            original_dir = os.getcwd()
            old_umask = os.umask(0)  # Сохраняем и сбрасываем umask
            os.chdir(self.extract_dir)

            try:
                # Список для отложенной установки времени модификации
                deferred_times = []

                with libarchive.file_reader(self.archive_path) as archive:
                    for entry in archive:
                        if self._should_stop():
                            return

                        entry_path = entry.pathname

                        # Создаём директории
                        if entry.isdir:
                            os.makedirs(entry_path, exist_ok=True)

                            # Права для директорий
                            if entry.mode:
                                try:
                                    os.chmod(entry_path, entry.mode)
                                except (OSError, PermissionError):
                                    pass

                            # Откладываем установку времени для директорий
                            if entry.mtime:
                                deferred_times.append((entry_path, entry.mtime))

                        # Извлекаем файлы
                        elif entry.isfile:
                            parent_dir = os.path.dirname(entry_path)
                            if parent_dir:
                                os.makedirs(parent_dir, exist_ok=True)

                            # Записываем содержимое файла
                            with open(entry_path, 'wb') as f:
                                for block in entry.get_blocks():
                                    if self._should_stop():
                                        return
                                    f.write(block)

                            # Устанавливаем права (включая execute bit)
                            if entry.mode:
                                try:
                                    os.chmod(entry_path, entry.mode)
                                except (OSError, PermissionError):
                                    pass

                            # Устанавливаем время модификации
                            if entry.mtime:
                                try:
                                    os.utime(entry_path, (entry.mtime, entry.mtime))
                                except (OSError, PermissionError):
                                    pass

                        # Символические ссылки
                        elif entry.issym:
                            parent_dir = os.path.dirname(entry_path)
                            if parent_dir:
                                os.makedirs(parent_dir, exist_ok=True)

                            if os.path.lexists(entry_path):
                                os.remove(entry_path)

                            try:
                                os.symlink(entry.linkpath, entry_path)
                            except (OSError, NotImplementedError):
                                pass

                        # Обновляем прогресс
                        bytes_read = archive.bytes_read
                        now = time.monotonic()
                        elapsed = now - start_time

                        if bytes_read != last_bytes_read:
                            last_bytes_read = bytes_read

                            if now - last_emit_time >= 0.1 or elapsed < 0.1:
                                progress = int((bytes_read / archive_size) * 100)
                                if progress != last_progress:
                                    self.progress.emit(min(progress, 99))
                                    last_progress = progress

                                if elapsed > 0:
                                    speed = (bytes_read / (1024 * 1024)) / elapsed
                                    self.speed.emit(round(speed, 2))

                                    if speed > 0:
                                        remaining_mb = (archive_size - bytes_read) / (1024 * 1024)
                                        self.eta.emit(max(0, int(remaining_mb / speed)))
                                    else:
                                        self.eta.emit(0)
                                else:
                                    self.speed.emit(0.0)
                                    self.eta.emit(0)

                                last_emit_time = now

                # Устанавливаем время модификации для директорий в обратном порядке
                # (чтобы родительские директории обновлялись последними)
                for dir_path, mtime in reversed(deferred_times):
                    try:
                        os.utime(dir_path, (mtime, mtime))
                    except (OSError, PermissionError):
                        pass

                self.progress.emit(100)
                self.speed.emit(0.0)
                self.eta.emit(0)
                self.finished.emit(self.archive_path, True)

            finally:
                os.chdir(original_dir)
                os.umask(old_umask)  # Восстанавливаем umask

        except Exception as e:
            if not self._should_stop():
                self.error.emit(str(e))

    # ========================
    # Thread control
    # ========================

    def stop(self):
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

        if self.isRunning():
            self.quit()
            self.wait(1000)



class ProtonManager(QDialog):
    def __init__(self, parent=None, portproton_location=None, theme=None, input_manager=None):
        super().__init__(parent)
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        self.selected_assets = {}  # {unique_id: asset_data}
        self.current_extraction_thread = None
        self.current_download_thread = None  # Still keep this for compatibility with Downloader's thread
        self.is_downloading = False  # Actually extraction in progress now
        self.assets_to_download = []
        self.current_download_index = 0
        self.portproton_location = portproton_location
        self.input_manager = input_manager  # Input manager for gamepad support
        self.initial_command_executed = False  # Track if --initial command has been executed

        # Find main window
        self.main_window = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, 'input_manager'):
                self.main_window = parent_widget
                break
            parent_widget = parent_widget.parent()

        self.initUI()
        self.load_proton_data_from_json()
        self.create_installed_tab()

        # Enable gamepad support if input manager is provided
        if self.input_manager:
            self.enable_proton_manager_mode()

    def initUI(self):
        self.setWindowTitle(_('Manage Wine versions'))
        self.resize(1100, 720)
        self.setStyleSheet(self.theme.MAIN_WINDOW_STYLE + self.theme.MESSAGE_BOX_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Tab widget - основной растягивающийся элемент
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.tab_widget, 1)

        # Инфо-блок для показа выбранного (компактный для информации по выбранным закачкам)
        selection_widget = QWidget()
        selection_layout = QVBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 2, 0, 2)
        selection_layout.setSpacing(2)

        selection_label = QLabel(_("Selected assets:"))
        selection_label.setMaximumHeight(20)
        selection_layout.addWidget(selection_label)

        self.selection_text = QTextEdit()
        self.selection_text.setMaximumHeight(80)
        self.selection_text.setReadOnly(True)
        self.selection_text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.selection_text.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
        self.selection_text.setPlainText(_("No assets selected"))
        selection_layout.addWidget(self.selection_text)

        layout.addWidget(selection_widget)

        # Область прогресса загрузки
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

        # Create hints widget using common function
        if self.input_manager and self.main_window:
            self.current_theme_name = read_theme_from_config()
            self.hints_widget, self.hints_labels = create_dialog_hints_widget(
                self.theme, self.main_window, self.input_manager, context='proton_manager'
            )
            layout.addWidget(self.hints_widget)

        # Кнопки управления
        button_layout = QHBoxLayout()
        self.download_btn = QPushButton(_('Download Selected'))
        self.download_btn.clicked.connect(self.download_selected)
        self.download_btn.setEnabled(False)
        self.download_btn.setMinimumHeight(40)
        self.clear_btn = QPushButton(_('Clear All'))
        self.clear_btn.clicked.connect(self.clear_selection)
        self.clear_btn.setMinimumHeight(40)
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.tab_changed)

        # Connect signals for hints updates
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
            # Initial update
            update_dialog_hints(
                self.hints_labels, self.main_window, self.input_manager,
                theme_manager, self.current_theme_name
            )

    def load_proton_data_from_json(self):
        """Загружаем данные по Протонам из файла JSON"""
        json_url = "https://git.linux-gaming.ru/Boria138/PortProton-Wine-Metadata/raw/branch/main/wine_metadata.json"

        try:
            logger.debug(f"Loading JSON metadata from: {json_url}")
            # Create a session with proxy support
            session = requests.Session()
            proxy = read_proxy_config() or {}
            if proxy:
                session.proxies.update(proxy)
            session.verify = True
            response = session.get(json_url, timeout=30)
            response.raise_for_status()

            metadata = orjson.loads(response.content)
            logger.info(f"Successfully loaded JSON metadata with {len(metadata)} entries")
            self.process_metadata(metadata)


        except requests.exceptions.RequestException as e:
            logger.error(f"Network error loading JSON: {e}")
        except orjson.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")

    def process_metadata(self, metadata):
        """Обработка JSON, создание Табов"""
        successful_tabs = 0

        # Get CPU level to filter incompatible versions
        self.cpu_level = get_cpu_level()
        logger.info(f"Detected CPU level: {self.cpu_level}")

        # Собираем табы в словарь для сортировки
        tabs_dict = {}

        for source_key, entries in metadata.items():
            # Пропускаем таб "gdk_proton" (вроде ненужный протон, скипаем)
            if source_key.lower() == 'gdk_proton':
                logger.debug(f"Skipping tab: {source_key}")
                continue

            # Filter entries based on CPU compatibility
            filtered_entries = self.filter_entries_by_cpu_level(entries, source_key)
            tabs_dict[source_key] = filtered_entries

        # Proton_LG в самое начало кидаем
        if 'proton_lg' in tabs_dict:
            if self.create_tab_from_entries('proton_lg', tabs_dict['proton_lg']):
                successful_tabs += 1
            del tabs_dict['proton_lg']

        # Остальные табы после Proton_LG, сортируем по алфавиту
        for source_key in sorted(tabs_dict.keys()):
            entries = tabs_dict[source_key]
            if self.create_tab_from_entries(source_key, entries):
                successful_tabs += 1

        return successful_tabs

    def filter_entries_by_cpu_level(self, entries, source_name):
        """Filter entries based on CPU compatibility"""
        if self.cpu_level >= 4:
            # If CPU supports all features, return all entries
            return entries

        filtered_entries = []

        for entry in entries:
            # Get the filename from the entry
            url = entry.get('url', '')
            filename = entry.get('name', '')

            if url:
                parsed_url = urllib.parse.urlparse(url)
                url_filename = os.path.basename(parsed_url.path)
                if url_filename:
                    filename = url_filename

            # Check if the filename contains version indicators that require specific CPU levels
            should_include = True

            # Check for v2, v3, v4 indicators in the filename
            if 'v2' in filename and self.cpu_level < 2:
                should_include = False
            elif 'v3' in filename and self.cpu_level < 3:
                should_include = False
            elif 'v4' in filename and self.cpu_level < 4:
                should_include = False

            if should_include:
                filtered_entries.append(entry)

        logger.info(f"Filtered {len(entries)} -> {len(filtered_entries)} entries for {source_name} based on CPU level {self.cpu_level}")
        return filtered_entries


    def create_tab_from_entries(self, source_name, entries):
        """Создаем вкладку с таблицей для источника Proton из записей JSON"""

        try:
            logger.debug(f"Processing {len(entries)} entries for source: {source_name}")

            tab = QWidget()
            tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            layout = QVBoxLayout(tab)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setSpacing(5)

            table = QTableWidget()
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.setColumnCount(2)  # Только Checkbox и Имя
            table.setHorizontalHeaderLabels(['', _('Asset Name')])
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.verticalHeader().setDefaultSectionSize(36)
            table.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)

            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

            # Include all entries (both installed and non-installed)
            all_entries = []
            for entry in entries:
                # Извлекаем имя файла из URL
                url = entry.get('url', '')

                if url:
                    parsed_url = urllib.parse.urlparse(url)
                    url_filename = os.path.basename(parsed_url.path)
                    if url_filename:
                        entry['filename'] = url_filename

                all_entries.append(entry)

            # Sort entries by version before displaying
            all_entries.sort(key=version_sort_key)

            table.setRowCount(len(all_entries))
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.cellClicked.connect(self.on_cell_clicked)

            for row_index, entry in enumerate(all_entries):
                self.add_asset_row_from_json(table, row_index, entry, source_name)

            layout.addWidget(table, 1)

            tab_name = (self.get_short_source_name(source_name) or "UNKNOWN").upper()  # Название для Таба в верхний регистр
            self.tab_widget.addTab(tab, tab_name)

            logger.info(f"Successfully created tab for {source_name} with {len(all_entries)} assets (filtered from {len(entries)})")
            return True

        except Exception as e:
            logger.error(f"Error creating tab for {source_name}: {e}")
            return False

    def get_short_source_name(self, full_name):
        """Получаем короткое имя для вкладки (Таба) из полного имени источника"""
        if full_name is None:
            return "UNKNOWN"

        short_names = {
            'proton_lg': 'PROTON_LG',
            'proton_ge': 'PROTON_GE',
            'wine_kron4ek': 'WINE_KRON4EK',
            'wine_ge': 'WINE_GE',
            'proton_cachyos': 'PROTON_CACHYOS',
            'winepak': 'WINEPAK',
            'proton_sarek': 'PROTON_SAREK',
            'wine_staging': 'WINE_STAGING',
            'wine_valve': 'WINE_VALVE',
            'proton_valve': 'PROTON_VALVE',
            'proton_em': 'PROTON_EM'
        }

        return short_names.get(full_name.lower(), full_name.upper())

    def add_asset_row_from_json(self, table, row_index, entry, source_name):
        """Добавляем строку для определенной позиции из JSON"""
        # Извлекаем имя файла из URL
        url = entry.get('url', '')
        filename = entry.get('name', '')

        if url:
            parsed_url = urllib.parse.urlparse(url)
            url_filename = os.path.basename(parsed_url.path)
            if url_filename:
                filename = url_filename

        # Извлекаем версию для уникального ID
        version_from_name = self.extract_version_from_name(filename)

        # Проверяем, установлен ли уже этот ассет
        uppercase_filename = filename.upper() # Преобразование имени WINE в верхний регистр
        is_installed = self.is_asset_installed(uppercase_filename, source_name)

        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()

        # Создаем структуру для позиции (элемента)
        asset_data = {
            'name': filename,  # имя с расширением
            'browser_download_url': url,
        }

        if is_installed:
            # If asset is already installed, disable the checkbox
            checkbox.setEnabled(False)
            checkbox.setChecked(False)  # Ensure it's not checked
        else:
            # Only connect the signal if the asset is not installed
            checkbox.stateChanged.connect(lambda state, a=asset_data, v=version_from_name,
                                                 s=source_name:
                                          self.on_asset_toggled_json(state, a, v, s))

        checkbox_layout.addWidget(checkbox)

        table.setCellWidget(row_index, 0, checkbox_widget)

        # Remove .tar.xz and .tar.gz extensions completely
        display_name = filename
        if filename.lower().endswith(('.tar.xz', '.tar.gz')):
            display_name = filename[:-7]

        asset_name_item = QTableWidgetItem(display_name)

        if is_installed:
            # Make the item disabled and add "(installed)" suffix
            asset_name_item.setFlags(asset_name_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            # Add "(installed)" suffix to indicate it's already installed
            asset_name_item.setText(_('{display_name} (installed)').format(display_name=display_name))

        table.setItem(row_index, 1, asset_name_item)

        # Собираем метаданные в данных элемента
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
        """Получаем версию из имени элемента"""
        if not name:
            return "N/A"

        # Убираем расширение файла
        basename = os.path.splitext(name)[0]
        basename = os.path.splitext(basename)[0]  # Для двойных расширений .tar.gz

        # Получаем версию по паттернам
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

        # Общий случай для всего
        return basename.split('-')[0] if '-' in basename else basename

    def is_asset_installed(self, asset_filename, source_name):
        """Check if asset is already installed in PortProton data/dist"""
        if not self.portproton_location:
            return False

        # Determine the directory name without extensions
        name_without_ext = asset_filename
        for ext in ['.tar.gz', '.tar.xz']:
            if name_without_ext.lower().endswith(ext):
                name_without_ext = name_without_ext[:-len(ext)]
                break

        # Check if the corresponding directory exists in data/dist
        dist_path = os.path.join(self.portproton_location, "data", "dist")
        expected_dir = os.path.join(dist_path, name_without_ext)

        return os.path.exists(expected_dir)

    def create_installed_tab(self):
        """Create the 'Installed' tab showing installed wine versions with removal option"""
        if not self.portproton_location:
            return

        dist_path = os.path.join(self.portproton_location, "data", "dist")
        if not os.path.exists(dist_path):
            os.makedirs(dist_path, exist_ok=True)

        installed_versions = [d for d in os.listdir(dist_path) if os.path.isdir(os.path.join(dist_path, d))]

        if not installed_versions:
            # Create empty tab with message
            tab = QWidget()
            layout = QVBoxLayout(tab)

            label = QLabel(_("No Wine/Proton versions installed"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 16px; padding: 50px;")
            layout.addWidget(label)

            self.tab_widget.addTab(tab, _("Installed"))
            return

        # Create tab with table for installed versions
        tab = QWidget()
        tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setColumnCount(3)  # Checkbox, Name, Size
        table.setHorizontalHeaderLabels(['', _('Version Name'), _('Size')])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        # Sort installed versions
        installed_versions.sort(key=version_sort_key)
        table.setRowCount(len(installed_versions))
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        for row_index, version_name in enumerate(installed_versions):
            self.add_installed_row(table, row_index, version_name)

        layout.addWidget(table, 1)

        # Настройка выделения строк и обработчика кликов для вкладки Installed
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.cellClicked.connect(self.on_cell_clicked)

        self.tab_widget.addTab(tab, _("Installed"))

    def add_installed_row(self, table, row_index, version_name):
        """Add a row for an installed version with delete option"""
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()
        checkbox_widget.setToolTip(_("Select to remove this version"))
        checkbox.stateChanged.connect(lambda state: self.on_installed_version_toggled(state))
        checkbox_layout.addWidget(checkbox)

        table.setCellWidget(row_index, 0, checkbox_widget)

        # Add version name
        version_item = QTableWidgetItem(version_name)
        version_item.setFlags(version_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row_index, 1, version_item)

        # Calculate and add size
        if self.portproton_location:
            dist_path = os.path.join(self.portproton_location, "data", "dist")
            version_path = os.path.join(dist_path, version_name)
            size_str = self.get_directory_size(version_path)
        else:
            size_str = _("Unknown")
            version_path = ""  # Provide a default value when portproton_location is None
        size_item = QTableWidgetItem(size_str)
        size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row_index, 2, size_item)

        # Store version name in user data for later use
        for col in range(table.columnCount()):
            item = table.item(row_index, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, {
                    'version_name': version_name,
                    'version_path': version_path
                })

    def on_installed_version_toggled(self, state):
        """Handle checkbox state changes in the installed tab"""
        self.update_selection_display()

    def get_directory_size(self, path):
        """Calculate directory size and return human-readable string"""
        try:
            total_size = 0
            for dirpath, _dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            # Convert to human readable format
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024.0:
                    return f"{total_size:.1f} {unit}"
                total_size /= 1024.0
            return f"{total_size:.1f} TB"
        except Exception:
            return _("Unknown")

    def on_cell_clicked(self, row):
        """Обработка клика по ячейке - переключение флажка при клике по любой ячейке в строке"""
        tab = self.tab_widget.currentWidget()
        table = tab.findChild(QTableWidget)
        if table:
            checkbox_widget = table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isEnabled():
                    checkbox.setChecked(not checkbox.isChecked())
                    # Update selection display after clicking
                    self.update_selection_display()

    def on_asset_toggled_json(self, state, asset, version, source_name):
        """Обработка выбора/отмены выбора элемента из данных JSON"""
        # Всегда извлекаем имя файла из URL
        url = asset.get('browser_download_url', '')
        filename = asset.get('name', '')  # Исходное имя из JSON

        # Получаем имя файла из URL (оно всегда с расширением)
        if url:
            parsed_url = urllib.parse.urlparse(url)
            url_filename = os.path.basename(parsed_url.path)
            if url_filename:  # Если удалось получить имя из URL
                filename = url_filename

        unique_id = f"{source_name}_{version}_{filename}"

        if state == Qt.CheckState.Checked.value:
            self.selected_assets[unique_id] = {
                'source_name': source_name,
                'version': version,
                'asset': asset,
                'asset_name': filename,  # Используем имя файла с расширением
                'download_url': asset['browser_download_url']
            }
        else:
            if unique_id in self.selected_assets:
                del self.selected_assets[unique_id]

        self.update_selection_display()

    def update_selection_display(self):
        """Обновляем отображение выбора"""
        current_tab_index = self.tab_widget.currentIndex()
        current_tab_text = self.tab_widget.tabText(current_tab_index)

        if current_tab_text == _("Installed"):
            # Handle installed tab - count selected checkboxes
            current_tab = self.tab_widget.currentWidget()
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
                    selection_text = _('Selected {} assets:\n').format(selected_count)

                    # Add the specific version names that are selected
                    current_tab = self.tab_widget.currentWidget()
                    table = current_tab.findChild(QTableWidget)
                    if table:
                        # Create a counter for numbering the selected items
                        item_number = 1
                        for row in range(table.rowCount()):
                            checkbox_widget = table.cellWidget(row, 0)
                            if checkbox_widget:
                                checkbox = checkbox_widget.findChild(QCheckBox)
                                if checkbox and checkbox.isChecked():
                                    version_item = table.item(row, 1)  # Version name column
                                    if version_item:
                                        version_name = version_item.text()
                                        selection_text += f"{item_number}. {version_name}\n"
                                        item_number += 1

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
            # Handle other tabs - use selected_assets dictionary
            if self.selected_assets:
                selection_text = _('Selected {} assets:\n').format(len(self.selected_assets))

                for i, asset_data in enumerate(self.selected_assets.values(), 1):
                    selection_text += f"{i}. {asset_data['source_name'].upper()} - {asset_data['asset_name']}\n"

                self.selection_text.setPlainText(selection_text)
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(True)
            else:
                self.selection_text.setPlainText(_("No assets selected"))
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(False)

    def tab_changed(self, index):
        """Handle tab change to update button text appropriately"""
        current_tab_text = self.tab_widget.tabText(index)
        if current_tab_text == _("Installed"):
            # Count selected items in installed tab
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
            # For other tabs, use the selected_assets dictionary
            if self.selected_assets:
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(True)
            else:
                self.download_btn.setText(_('Download Selected'))
                self.download_btn.setEnabled(False)

        self.update_selection_display()

    def clear_selection(self):
        """Очищаем (сбрасываем) всё выбранное"""
        if self.is_downloading:
            QMessageBox.warning(self, _("Downloading in Progress"), _("Cannot clear selection while extraction is in progress."))
            return

        # Clear selected assets for download tabs
        self.selected_assets.clear()

        # Clear checkboxes in all tabs
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
        """Handle both downloading new versions and removing installed versions"""
        # Check if we're on the Installed tab
        current_tab_index = self.tab_widget.currentIndex()
        current_tab_text = self.tab_widget.tabText(current_tab_index)

        if current_tab_text == _("Installed"):
            # Handle removal of selected installed versions
            self.remove_selected_installed_versions()
        else:
            # Handle downloading of selected versions (existing functionality)
            if not self.selected_assets:
                QMessageBox.warning(self, _("No Selection"), _("Please select at least one archive to download."))
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
        """Delete selected installed wine/proton versions"""
        # Get the current tab (Installed tab)
        current_tab = self.tab_widget.currentWidget()
        table = current_tab.findChild(QTableWidget)
        if not table:
            return

        # Find all selected versions to remove
        versions_to_remove = []
        for row in range(table.rowCount()):
            checkbox_widget = table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    item = table.item(row, 1)  # Version name column
                    if item:
                        user_data = item.data(Qt.ItemDataRole.UserRole)
                        if user_data:
                            versions_to_remove.append(user_data['version_path'])

        if not versions_to_remove:
            # Temporarily disable proton manager mode to allow gamepad input in QMessageBox
            if self.input_manager:
                self.disable_proton_manager_mode()
            try:
                QMessageBox.warning(self, _("No Selection"), _("Please select at least one version to delete."))
            finally:
                # Re-enable proton manager mode after QMessageBox closes
                if self.input_manager:
                    self.enable_proton_manager_mode()
            return

        # Temporarily disable proton manager mode to allow gamepad input in QMessageBox
        if self.input_manager:
            self.disable_proton_manager_mode()
        try:
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                _("Confirm Deletion"),
                _("Are you sure you want to delete {} selected version(s)?\n\nThis action cannot be undone.").format(len(versions_to_remove)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
        finally:
            # Re-enable proton manager mode after QMessageBox closes
            if self.input_manager:
                self.enable_proton_manager_mode()

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Remove the selected versions
        removed_count = 0
        for version_path in versions_to_remove:
            try:
                if os.path.exists(version_path):
                    import shutil
                    shutil.rmtree(version_path)
                    removed_count += 1
            except Exception as e:
                logger.error(f"Error removing version at {version_path}: {e}")
                QMessageBox.warning(self, _("Error"), _("Failed to remove version at {}: {}").format(version_path, str(e)))

        if removed_count > 0:
            QMessageBox.information(self, _("Success"), _("Successfully removed {} version(s).").format(removed_count))
            # Refresh the installed tab to show updated list
            self.refresh_installed_tab()

    def refresh_installed_tab(self):
        """Refresh the installed tab to show current installed versions"""
        # Find the installed tab index
        installed_tab_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == _("Installed"):
                installed_tab_index = i
                break

        if installed_tab_index != -1:
            # Remove the old installed tab
            self.tab_widget.removeTab(installed_tab_index)
            # Create a new one
            self.create_installed_tab()

    def start_next_download(self):
        """Start extraction of next archive in the list"""
        if self.current_download_index >= len(self.assets_to_download):
            # All extractions completed
            self.download_frame.setVisible(False)
            self.download_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.is_downloading = False

            # Run the initial command after all assets have been processed
            import subprocess
            try:
                # Get the proper PortProton start command
                start_cmd = get_portproton_start_command()
                if start_cmd and not self.initial_command_executed:
                    result = subprocess.run(start_cmd + ["cli", "--initial"], timeout=10)
                    if result.returncode != 0:
                        logger.warning(f"Initial PortProton command returned non-zero exit code: {result.returncode}")
                    else:
                        logger.info("Initial PortProton command executed successfully after all assets processed")
                    self.initial_command_executed = True  # Mark that command has been executed
                elif self.initial_command_executed:
                    logger.debug("Initial PortProton command already executed, skipping")
            except subprocess.TimeoutExpired:
                logger.warning("Initial PortProton command timed out")
            except Exception as e:
                logger.error(f"Error running initial PortProton command: {e}")

            QMessageBox.information(self, _("Downloading Complete"), _("All selected archives have been downloaded!"))
            return

        asset_data = self.assets_to_download[self.current_download_index]
        self.download_asset(asset_data)

    def download_asset(self, asset_data):
        """Download and then extract the archive"""

        # DEBUG FEATURE: Check if proton_downloads folder exists in repo root and contains the file
        # This is a debug feature to use local files instead of downloading - remember to remove for production
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up from portprotonqt/
        proton_downloads_path = os.path.join(repo_root, "proton_downloads")

        local_file_path = None
        if os.path.exists(proton_downloads_path) and os.path.isdir(proton_downloads_path):
            # Look for the asset file in proton_downloads
            for filename in os.listdir(proton_downloads_path):
                if filename == asset_data['asset_name']:
                    local_file_path = os.path.join(proton_downloads_path, filename)
                    logger.info(f"DEBUG: Using local file instead of downloading: {local_file_path}")
                    break

        if local_file_path and os.path.exists(local_file_path):
            # Use local file, skip download
            logger.info(f"DEBUG: Skipping download, using local file: {local_file_path}")
            download_info = f"{asset_data['source_name'].upper()} - {asset_data['asset_name']} (DEBUG: local)"
            if len(download_info) > 80:
                download_info = download_info[:77] + "..."
            self.download_progress.setValue(0)
            self.download_frame.setVisible(True)
            self.download_frame.setStyleSheet(self.theme.GETWINE_WINDOW_STYLE)
            self.download_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)

            # Simulate download completion and start extraction immediately
            QTimer.singleShot(100, lambda: self.start_extraction_for_asset(asset_data, local_file_path))
        else:
            # Normal download process
            # Create a temporary file path for download
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

            # Create and start download thread
            self.current_download_thread = DownloadThread(download_url, filename)

            def update_download_progress(progress):
                self.download_progress.setValue(progress)
                self.download_info_label.setText(_("Downloading: {0} ({1}%)").format(asset_data['asset_name'], progress))

            def download_finished(filepath, success):
                if success:
                    logger.info(f"Successfully downloaded: {filepath}")
                    # Now start extraction
                    self.start_extraction_for_asset(asset_data, filepath)
                else:
                    logger.error(f"Failed to download: {filepath}")
                    # Clean up temp directory
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
                # Clean up temp directory
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
        """Start extraction for a downloaded asset"""
        # Update progress bar to show extraction phase
        self.download_info_label.setText(_("Extracting: {0}").format(asset_data['asset_name']))

        # Extract archive to PortProton data/dist directory using a separate thread
        if self.portproton_location:
            try:
                # Extract directly to dist directory - let the archive create its own folder structure
                dist_path = os.path.join(self.portproton_location, "data", "dist")
                extract_dir = dist_path

                # Create and start extraction thread
                self.current_extraction_thread = ExtractionThread(filepath, extract_dir)

                # Store speed and ETA values to use in the display
                current_speed = 0.0
                current_eta = 0

                def update_extraction_progress(progress):
                    self.download_progress.setValue(progress)
                    # Update the info label to show current progress during extraction
                    eta_text = _(', ETA: {}s').format(current_eta) if current_eta > 0 else ""
                    speed_text = _(', Speed: {:.1f}MB/s').format(current_speed) if current_speed > 0 else ""
                    self.download_info_label.setText(_("Extracting: {0}{1}{2}").format(
                        asset_data['asset_name'], speed_text, eta_text))

                def update_extraction_speed(speed):
                    nonlocal current_speed
                    current_speed = speed

                def update_extraction_eta(eta):
                    # Use ETA to pass actual ETA information during extraction
                    nonlocal current_eta
                    # Now we only use ETA for actual estimated time of arrival
                    current_eta = eta

                def extraction_finished(archive_path, success):
                    if success:
                        logger.info(f"Successfully extracted: {archive_path}")
                    else:
                        logger.error(f"Failed to extract: {archive_path}")
                        QMessageBox.critical(self, _("Extraction Error"), _("Failed to extract archive: {0}").format(archive_path))

                    # Clean up temp directory after extraction
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

                    # Clean up temp directory after error
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
                # Clean up temp directory in case of exception
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
            # Clean up temp directory if portproton location is not provided
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
        """Check if there are active download or extraction processes"""
        extraction_active = (self.current_extraction_thread and
                            self.current_extraction_thread.isRunning())
        download_active = (self.current_download_thread and
                          hasattr(self.current_download_thread, 'isRunning') and
                          self.current_download_thread.isRunning())
        return extraction_active or download_active

    def cancel_current_download(self):
        """Cancel current download or extraction"""
        # Stop extraction thread if running
        if self.current_extraction_thread and self.current_extraction_thread.isRunning():
            self.current_extraction_thread.stop()
            if not self.current_extraction_thread.wait(1000):
                logger.warning("Extraction thread did not stop gracefully")

        # Stop download thread if running
        try:
            if (self.current_download_thread and
                hasattr(self.current_download_thread, 'isRunning') and
                self.current_download_thread.isRunning()):
                if hasattr(self.current_download_thread, 'stop'):
                    self.current_download_thread.stop()
                if not self.current_download_thread.wait(1000):
                    logger.warning("Download thread did not stop gracefully")
        except RuntimeError:
            # Object already deleted, which is fine
            logger.debug("Download thread object already deleted during cancel")

        # Очищаем список загрузок
        self.assets_to_download = []
        self.current_download_index = 0
        self.is_downloading = False
        # Сбрасываем флаг выполнения команды --initial, так как процесс отменен
        self.initial_command_executed = False

        # Сброс/перезапуск UI
        self.download_frame.setVisible(False)
        self.download_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        QMessageBox.information(self, _("Operation Cancelled"), _("Download or extraction has been cancelled."))

    def enable_proton_manager_mode(self):
        """Enable gamepad mode for ProtonManager"""
        if self.input_manager:
            self.input_manager.enable_proton_manager_mode(self)

    def disable_proton_manager_mode(self):
        """Disable gamepad mode for ProtonManager"""
        if self.input_manager:
            self.input_manager.disable_proton_manager_mode()

    def closeEvent(self, event):
        """Проверка, что все потоки останавливаются при закрытии приложения"""
        logger.debug("Closing ProtonManager dialog...")

        # Disable gamepad mode before closing
        if self.input_manager:
            self.disable_proton_manager_mode()

        # Check if there are active processes and cancel them
        if self.has_active_processes():
            logger.debug("Active processes detected, cancelling before close...")
            self.cancel_current_download()
        else:
            # Stop extraction thread if running
            if self.current_extraction_thread and self.current_extraction_thread.isRunning():
                logger.debug("Stopping current extraction thread...")
                self.current_extraction_thread.stop()
                if not self.current_extraction_thread.wait(2000):
                    logger.warning("Extraction thread did not stop gracefully during close")

            # Stop download thread if running
            try:
                if (self.current_download_thread and
                    hasattr(self.current_download_thread, 'isRunning') and
                    self.current_download_thread.isRunning()):
                    logger.debug("Stopping current download thread...")
                    if hasattr(self.current_download_thread, 'stop'):
                        self.current_download_thread.stop()
                    if not self.current_download_thread.wait(2000):
                        logger.warning("Download thread did not stop gracefully during close")
            except RuntimeError:
                # Object already deleted, which is fine
                logger.debug("Download thread object already deleted during close")

            # If we're closing without active processes but haven't completed all downloads,
            # reset the initial command flag so it can run if the dialog is opened again
            if self.is_downloading and self.current_download_index < len(self.assets_to_download):
                self.initial_command_executed = False

        event.accept()

    def reject(self):
        """Override reject to properly cancel active processes before closing"""
        # Disable gamepad mode before rejecting
        if self.input_manager:
            self.disable_proton_manager_mode()

        if self.has_active_processes():
            logger.debug("Active processes detected, cancelling before reject...")
            self.cancel_current_download()
        else:
            # If we're rejecting without active processes but haven't completed all downloads,
            # reset the initial command flag so it can run if the dialog is opened again
            if self.is_downloading and self.current_download_index < len(self.assets_to_download):
                self.initial_command_executed = False
            super().reject()



def show_proton_manager(parent=None, portproton_location=None, input_manager=None):
    """
    Shows the Proton/WINE archive extractor dialog.

    Args:
        parent: Parent widget for the dialog
        portproton_location: Location of PortProton installation
        input_manager: Input manager for gamepad support

    Returns:
        ProtonManager dialog instance
    """
    dialog = ProtonManager(parent, portproton_location, input_manager=input_manager)
    dialog.exec()  # Use exec() for modal dialog
    return dialog
