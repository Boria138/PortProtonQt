import os
import requests
import orjson
import tarfile
import shutil
from PySide6.QtWidgets import (QDialog, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget, QCheckBox,
                               QPushButton, QHeaderView, QMessageBox,
                               QLabel, QTextEdit, QHBoxLayout, QProgressBar,
                               QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QThread, Signal, QMutex, QWaitCondition, QTimer
import urllib.parse
from portprotonqt.config_utils import read_proxy_config
from portprotonqt.logger import get_logger
from portprotonqt.localization import _

logger = get_logger(__name__)

def get_requests_session():
    """Create a requests session with proxy support"""
    session = requests.Session()
    proxy = read_proxy_config() or {}
    if proxy:
        session.proxies.update(proxy)
    session.verify = True
    return session

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
            session = get_requests_session()
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
    progress = Signal(int)
    finished = Signal(str, bool)  # filename, success
    error = Signal(str)

    def __init__(self, archive_path, extract_dir):
        super().__init__()
        self.archive_path = archive_path
        self.extract_dir = extract_dir
        self._is_running = True
        self._mutex = QMutex()

    def run(self):
        try:
            # Update progress to show extraction is starting
            self.progress.emit(0)

            # Create dist directory if it doesn't exist
            os.makedirs(os.path.dirname(self.extract_dir), exist_ok=True)

            # Remove existing directory if it exists
            if os.path.exists(self.extract_dir):
                shutil.rmtree(self.extract_dir)

            # Extract the archive (only .tar.gz and .tar.xz are supported according to metadata)
            if self.archive_path.lower().endswith(('.tar.gz', '.tar.xz')):
                with tarfile.open(self.archive_path, 'r:*') as tar_ref:
                    # Get total number of members for progress tracking (only once)
                    members = tar_ref.getmembers()
                    total_members = len(members)
                    extracted_count = 0

                    # Extract to a temporary directory first, then move contents to final destination
                    # to avoid nested directory structures
                    import tempfile
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Extract with progress tracking
                        last_progress = -1  # Track last emitted progress to avoid too frequent updates
                        for member in members:
                            self._mutex.lock()
                            if not self._is_running:
                                self._mutex.unlock()
                                return
                            self._mutex.unlock()

                            tar_ref.extract(member, temp_dir)
                            extracted_count += 1

                            # Update progress
                            if total_members > 0:
                                progress = int((extracted_count / total_members) * 100)
                                # Only emit progress if it changed significantly (at least 1%) or at start/end
                                if progress != last_progress:
                                    self.progress.emit(progress)
                                    last_progress = progress
                            else:
                                # If total_members is 0, emit a default progress to show activity
                                if extracted_count == 1:
                                    self.progress.emit(50)  # Show partial progress to indicate activity
                            # Process events to ensure UI updates
                            QThread.yieldCurrentThread()  # Allow other threads to run

                        # Find the actual content directory (often the archive creates a subdirectory)
                        extracted_dirs = os.listdir(temp_dir)
                        if len(extracted_dirs) == 1:
                            # If there's only one directory, move its contents directly to extract_dir
                            content_dir = os.path.join(temp_dir, extracted_dirs[0])
                            if os.path.isdir(content_dir):
                                # Move all contents from content_dir to extract_dir
                                items = os.listdir(content_dir)
                                total_items = len(items)
                                moved_items = 0
                                last_progress = -1  # Track last emitted progress to avoid too frequent updates

                                for item in items:
                                    self._mutex.lock()
                                    if not self._is_running:
                                        self._mutex.unlock()
                                        return
                                    self._mutex.unlock()

                                    source = os.path.join(content_dir, item)
                                    destination = os.path.join(self.extract_dir, item)

                                    if os.path.isdir(source):
                                        shutil.copytree(source, destination)
                                    else:
                                        shutil.copy2(source, destination)

                                    moved_items += 1
                                    # Update progress during file copying (50% to 100% of extraction)
                                    progress = min(100, 50 + int((moved_items / total_items) * 50))
                                    # Only emit progress if it changed significantly (at least 1%)
                                    if progress != last_progress:
                                        self.progress.emit(progress)
                                        last_progress = progress
                                    # Process events to ensure UI updates
                                    QThread.yieldCurrentThread()  # Allow other threads to run
                            else:
                                # If it's just files, move them directly
                                items = os.listdir(temp_dir)
                                total_items = len(items)
                                moved_items = 0
                                last_progress = -1  # Track last emitted progress to avoid too frequent updates

                                for item in items:
                                    self._mutex.lock()
                                    if not self._is_running:
                                        self._mutex.unlock()
                                        return
                                    self._mutex.unlock()

                                    source = os.path.join(temp_dir, item)
                                    destination = os.path.join(self.extract_dir, item)

                                    if os.path.isdir(source):
                                        shutil.copytree(source, destination)
                                    else:
                                        shutil.copy2(source, destination)

                                    moved_items += 1
                                    # Update progress during file copying (50% to 100% of extraction)
                                    progress = min(100, 50 + int((moved_items / total_items) * 50))
                                    # Only emit progress if it changed significantly (at least 1%)
                                    if progress != last_progress:
                                        self.progress.emit(progress)
                                        last_progress = progress
                                    # Process events to ensure UI updates
                                    QThread.yieldCurrentThread()  # Allow other threads to run
                        else:
                            # If multiple top-level items, extract directly to target
                            # This is a simpler case where we extract directly to the target
                            tar_ref.extractall(self.extract_dir)
                            # Set progress to 100% when extraction is complete
                            self.progress.emit(100)
                            QThread.yieldCurrentThread()  # Allow other threads to run
            else:
                raise ValueError(f"Unsupported archive format: {self.archive_path}. Only .tar.gz and .tar.xz are supported.")

            self._mutex.lock()
            if self._is_running:
                self._mutex.unlock()
                self.finished.emit(self.archive_path, True)
            else:
                self._mutex.unlock()

        except Exception as e:
            self._mutex.lock()
            if self._is_running:
                self._mutex.unlock()
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


class ProtonManager(QDialog):
    def __init__(self, parent=None, portproton_location=None):
        super().__init__(parent)
        self.selected_assets = {}  # {unique_id: asset_data}
        self.current_download_thread = None
        self.current_extraction_thread = None
        self.is_downloading = False
        self.assets_to_download = []
        self.current_download_index = 0
        self.portproton_location = portproton_location
        self.initUI()
        self.load_proton_data_from_json()

    def initUI(self):
        self.setWindowTitle(_('Proton | WINE Download Manager'))
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Info label
        self.info_label = QLabel(_("Loading Proton versions from JSON metadata..."))
        self.info_label.setMaximumHeight(20)
        layout.addWidget(self.info_label)

        # Tab widget - основной растягивающийся элемент
        self.tab_widget = QTabWidget()
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

    def load_proton_data_from_json(self):
        """Загружаем данные по Протонам из файла JSON"""
        json_url = "https://git.linux-gaming.ru/Boria138/PortProton-Wine-Metadata/raw/branch/main/wine_metadata.json"

        try:
            logger.debug(f"Loading JSON metadata from: {json_url}")
            session = get_requests_session()
            response = session.get(json_url, timeout=30)
            response.raise_for_status()

            metadata = orjson.loads(response.content)
            logger.info(f"Successfully loaded JSON metadata with {len(metadata)} entries")

            successful_tabs = self.process_metadata(metadata)

            if successful_tabs == 0:
                self.info_label.setText(_("Error: Could not process any data from JSON."))
            else:
                self.info_label.setText(f"Loaded {successful_tabs} Proton/WINE sources from JSON")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error loading JSON: {e}")
            self.info_label.setText(_("Error loading JSON: {0}").format(e))
        except orjson.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            self.info_label.setText(_("Error parsing JSON: {0}").format(e))
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            self.info_label.setText(_("Error: {0}").format(e))

    def process_metadata(self, metadata):
        """Обработка JSON, создание Табов"""
        successful_tabs = 0

        # Собираем табы в словарь для сортировки
        tabs_dict = {}

        for source_key, entries in metadata.items():
            # Пропускаем таб "gdk_proton" (вроде ненужный протон, скипаем)
            if source_key.lower() == 'gdk_proton':
                logger.debug(f"Skipping tab: {source_key}")
                continue

            tabs_dict[source_key] = entries

        # Proton_LG в самое начало кидаем
        if 'proton_lg' in tabs_dict:
            if self.create_tab_from_entries('proton_lg', tabs_dict['proton_lg']):
                successful_tabs += 1
            del tabs_dict['proton_lg']

        # Остальные табы после Proton_LG
        for source_key, entries in tabs_dict.items():
            if self.create_tab_from_entries(source_key, entries):
                successful_tabs += 1

        return successful_tabs

    def create_tab_from_entries(self, source_name, entries):
        """Создаем вкладку с таблицей для источника Proton из записей JSON"""

        try:
            logger.debug(f"Processing {len(entries)} entries for source: {source_name}")

            tab = QWidget()
            tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            layout = QVBoxLayout(tab)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)

            table = QTableWidget()
            table.setColumnCount(2)  # Только Checkbox и Имя
            table.setHorizontalHeaderLabels(['', 'Asset Name'])

            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

            table.setRowCount(len(entries))
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.cellClicked.connect(self.on_cell_clicked)

            for row_index, entry in enumerate(entries):
                self.add_asset_row_from_json(table, row_index, entry, source_name)

            layout.addWidget(table, 1)

            tab_name = (self.get_short_source_name(source_name) or "UNKNOWN").upper()  # Название для Таба в верхний регистр
            self.tab_widget.addTab(tab, tab_name)

            logger.info(f"Successfully created tab for {source_name} with {len(entries)} assets")
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
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()

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

        # Создаем структуру для позиции (элемента)
        asset_data = {
            'name': filename,  # имя с расширением
            'browser_download_url': url,
        }

        # Проверяем, установлен ли уже этот ассет
        is_installed = self.is_asset_installed(filename, source_name)

        checkbox.stateChanged.connect(lambda state, a=asset_data, v=version_from_name,
                                             s=source_name:
                                      self.on_asset_toggled_json(state, a, v, s))
        checkbox_layout.addWidget(checkbox)

        table.setCellWidget(row_index, 0, checkbox_widget)

        # Имя элемента (без расширения для красивого отображения)
        # Remove .tar.xz and .tar.gz extensions completely
        display_name = filename
        if filename.lower().endswith('.tar.xz'):
            display_name = filename[:-7]  # Remove '.tar.xz'
        elif filename.lower().endswith('.tar.gz'):
            display_name = filename[:-7]  # Remove '.tar.gz'
        else:
            # Fallback to removing just the last extension if needed
            display_name = os.path.splitext(filename)[0]
        asset_name_item = QTableWidgetItem(display_name)

        # Если ассет уже установлен, делаем его недоступным для выбора
        if is_installed:
            checkbox.setEnabled(False)
            asset_name_item.setFlags(asset_name_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            # Add "(installed)" suffix to indicate it's already installed
            asset_name_item.setText(f"{display_name} (installed)")

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
        if self.selected_assets:
            selection_text = f"Selected {len(self.selected_assets)} assets:\n"

            for i, asset_data in enumerate(self.selected_assets.values(), 1):
                selection_text += f"{i}. {asset_data['source_name'].upper()} - {asset_data['asset_name']}\n"

            self.selection_text.setPlainText(selection_text)
            self.download_btn.setEnabled(True)
        else:
            self.selection_text.setPlainText(_("No assets selected"))
            self.download_btn.setEnabled(False)

    def clear_selection(self):
        """Очищаем (сбрасываем) всё выбранное"""
        if self.is_downloading:
            QMessageBox.warning(self, _("Download in Progress"), _("Cannot clear selection while downloading."))
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
                        if checkbox and checkbox.isEnabled():
                            checkbox.setChecked(False)

        self.update_selection_display()

    def download_selected(self):
        """Загружаем все выбранные элементы (протоны)"""
        if not self.selected_assets:
            QMessageBox.warning(self, _("No Selection"), _("Please select at least one asset to download."))
            return

        if self.is_downloading:
            QMessageBox.warning(self, _("Download in Progress"), _("Please wait for current download to complete."))
            return

        downloads_dir = "proton_downloads"
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)

        self.assets_to_download = list(self.selected_assets.values())
        self.current_download_index = 0
        self.is_downloading = True
        self.start_next_download()

    def start_next_download(self):
        """Запуск загрузки следующего элемента в списке"""
        if self.current_download_index >= len(self.assets_to_download):
            # Все загрузки завершены
            self.download_frame.setVisible(False)
            self.download_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.is_downloading = False
            QMessageBox.information(self, _("Download Complete"), _("All selected assets have been downloaded!"))
            return

        asset_data = self.assets_to_download[self.current_download_index]
        self.download_asset(asset_data)

    def download_asset(self, asset_data):
        """Загрузка конкретного элемента (протона)"""
        filename = os.path.join("proton_downloads", asset_data['asset_name'])

        download_info = f"{asset_data['source_name'].upper()} - {asset_data['asset_name']}"
        if len(download_info) > 80:
            download_info = download_info[:77] + "..."
        self.download_info_label.setText(f"Downloading: {download_info}")
        self.download_progress.setValue(0)
        self.download_frame.setVisible(True)
        self.download_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        if os.path.exists(filename):
            reply = QMessageBox.question(self, _("File Exists"),
                                         _("File {0} already exists. Overwrite?").format(asset_data['asset_name']),
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                self.current_download_index += 1
                self.start_next_download()
                return

        download_url = asset_data.get('download_url', '')
        if not download_url:
            QMessageBox.critical(self, _("Download Error"), _("No download URL for {0}").format(asset_data['asset_name']))
            self.current_download_index += 1
            self.start_next_download()
            return

        # Проверка, что предыдущий поток завершен
        if self.current_download_thread and self.current_download_thread.isRunning():
            logger.warning("Previous thread still running, waiting...")
            self.current_download_thread.stop()

        self.current_download_thread = DownloadThread(download_url, filename)

        def update_progress(progress):
            self.download_progress.setValue(progress)

        def download_finished(filename, success):
            logger.debug(f"Download finished callback: {filename}, success: {success}")
            if success:
                logger.info(f"Successfully downloaded: {filename}")

                # Update progress bar to show extraction phase
                self.download_info_label.setText(_("Extracting: {0}").format(asset_data['asset_name']))

                # Extract archive to PortProton data/dist directory using a separate thread
                if self.portproton_location:
                    try:
                        # Determine the name for the extraction directory from the asset name
                        asset_name = asset_data['asset_name']

                        # Remove common archive extensions to get the directory name (only .tar.gz and .tar.xz)
                        name_without_ext = asset_name
                        for ext in ['.tar.gz', '.tar.xz']:
                            if name_without_ext.lower().endswith(ext):
                                name_without_ext = name_without_ext[:-len(ext)]
                                break

                        # Create the destination directory in PortProton data/dist
                        dist_path = os.path.join(self.portproton_location, "data", "dist")
                        extract_dir = os.path.join(dist_path, name_without_ext)

                        # Create and start extraction thread
                        self.current_extraction_thread = ExtractionThread(filename, extract_dir)

                        def update_extraction_progress(progress):
                            self.download_progress.setValue(progress)
                            # Update the info label to show current progress percentage during extraction
                            self.download_info_label.setText(_("Extracting: {0} ({1}%)").format(asset_data['asset_name'], progress))

                        def extraction_finished(archive_path, success):
                            if success:
                                logger.info(f"Successfully extracted: {archive_path}")
                            else:
                                logger.error(f"Failed to extract: {archive_path}")
                                QMessageBox.critical(self, _("Extraction Error"), _("Failed to extract archive: {0}").format(archive_path))

                            if self.current_extraction_thread and self.current_extraction_thread.isRunning():
                                logger.debug("Waiting for extraction thread to finish...")
                                if not self.current_extraction_thread.wait(500):
                                    logger.warning("Extraction thread still running, but continuing...")

                            self.current_download_index += 1
                            QTimer.singleShot(100, self.start_next_download)

                        def extraction_error(error_msg):
                            logger.error(f"Extraction error: {error_msg}")
                            QMessageBox.critical(self, "Extraction Error", f"Failed to extract archive: {error_msg}")

                            if self.current_extraction_thread and self.current_extraction_thread.isRunning():
                                logger.debug("Waiting for extraction thread to finish after error...")
                                if not self.current_extraction_thread.wait(500):
                                    logger.warning("Extraction thread still running after error, but continuing...")

                            self.current_download_index += 1
                            QTimer.singleShot(100, self.start_next_download)

                        self.current_extraction_thread.progress.connect(update_extraction_progress)
                        self.current_extraction_thread.finished.connect(extraction_finished)
                        self.current_extraction_thread.error.connect(extraction_error)
                        self.current_extraction_thread.start()

                    except Exception as e:
                        logger.error(f"Error starting extraction thread for {filename}: {e}")
                        QMessageBox.critical(self, "Extraction Error", f"Failed to start extraction: {e}")
                        self.current_download_index += 1
                        QTimer.singleShot(100, self.start_next_download)
                else:
                    logger.warning("PortProton location not provided, skipping extraction")
                    self.current_download_index += 1
                    QTimer.singleShot(100, self.start_next_download)
            else:
                QMessageBox.critical(self, _("Download Failed"),
                                     _("Failed to download:\n{0}").format(filename))

        def download_error(error_msg):
            logger.error(f"Download error: {error_msg}")
            QMessageBox.critical(self, _("Download Error"), error_msg)

            if self.current_download_thread and self.current_download_thread.isRunning():
                if not self.current_download_thread.wait(500):
                    logger.warning("Thread still running after error, but continuing...")

            self.current_download_index += 1
            QTimer.singleShot(100, self.start_next_download)

        self.current_download_thread.progress.connect(update_progress)
        self.current_download_thread.finished.connect(download_finished)
        self.current_download_thread.error.connect(download_error)
        self.current_download_thread.start()

    def cancel_current_download(self):
        """Отмена текущей загрузки"""
        if self.current_download_thread and self.current_download_thread.isRunning():
            self.current_download_thread.stop()
            if not self.current_download_thread.wait(1000):
                logger.warning("Thread did not stop gracefully")

        # Очищаем список загрузок
        self.assets_to_download = []
        self.current_download_index = 0
        self.is_downloading = False

        # Сброс/перезапуск UI
        self.download_frame.setVisible(False)
        self.download_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        QMessageBox.information(self, _("Download Cancelled"), _("Download has been cancelled."))

    def closeEvent(self, event):
        """Проверка, что все потоки останавливаются при закрытии приложения"""
        logger.debug("Closing ProtonManager dialog...")

        # Stop download thread if running
        if self.is_downloading and self.current_download_thread and self.current_download_thread.isRunning():
            logger.debug("Stopping current download thread...")
            self.current_download_thread.stop()
            if not self.current_download_thread.wait(2000):
                logger.warning("Thread did not stop gracefully during close")

        # Stop extraction thread if running
        if self.current_extraction_thread and self.current_extraction_thread.isRunning():
            logger.debug("Stopping current extraction thread...")
            self.current_extraction_thread.stop()
            if not self.current_extraction_thread.wait(2000):
                logger.warning("Extraction thread did not stop gracefully during close")

        event.accept()



def show_proton_manager(parent=None, portproton_location=None):
    """
    Shows the Proton/WINE manager dialog.

    Args:
        parent: Parent widget for the dialog
        portproton_location: Location of PortProton installation

    Returns:
        ProtonManager dialog instance
    """
    dialog = ProtonManager(parent, portproton_location)
    dialog.exec()  # Use exec() for modal dialog
    return dialog
