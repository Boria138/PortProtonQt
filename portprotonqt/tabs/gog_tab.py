"""Shared download manager with GOG download support."""

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QProcess, QProcessEnvironment, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from portprotonqt.dialogs.file_explorer import FileExplorer
from portprotonqt.gog_api import GOGAPI, GOG_LOGIN_URL
from portprotonqt.image_utils import load_pixmap_async
from portprotonqt.localization import _
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
GOG_CANCEL_KILL_TIMEOUT_MS = 3000
GOG_LOGIN_TIMEOUT_MS = 300000

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

    _MainWindowTypingBase = QMainWindow
else:
    _MainWindowTypingBase = object


class GOGLibraryWorker(QThread):
    """Refresh the GOG library outside the UI thread."""

    loaded = Signal(list)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, api: GOGAPI) -> None:
        super().__init__()
        self.api = api

    def run(self) -> None:
        try:
            self.loaded.emit(self.api.refresh_library(self.progress.emit))
        except Exception as error:
            logger.exception("Failed to refresh GOG library")
            self.failed.emit(str(error))


class GOGAuthWorker(QThread):
    """Exchange the GOG OAuth code outside the UI thread."""

    authenticated = Signal(bool, str)

    def __init__(self, api: GOGAPI, code: str) -> None:
        super().__init__()
        self.api = api
        self.code = code

    def run(self) -> None:
        try:
            authenticated, error = self.api.authenticate(self.code)
            self.authenticated.emit(authenticated, error)
        except Exception as error:
            logger.exception("Failed to authenticate with GOG: %s", error)
            self.authenticated.emit(False, str(error))


class GOGAccountWorker(QThread):
    """Load the GOG account name outside the UI thread."""

    loaded = Signal(str)

    def __init__(self, api: GOGAPI) -> None:
        super().__init__()
        self.api = api

    def run(self) -> None:
        try:
            self.loaded.emit(self.api.refresh_account_name())
        except Exception:
            logger.exception("Failed to refresh GOG account name")
            self.loaded.emit("")


class GOGSupportWorker(QThread):
    """Install GOG support instructions outside the UI thread."""

    failed = Signal(str)
    launched = Signal(object)
    succeeded = Signal()

    def __init__(self, api: GOGAPI, app_id: str, start_command: list[str]) -> None:
        super().__init__()
        self.api = api
        self.app_id = app_id
        self.start_command = start_command
        self.error = ""

    def run(self) -> None:
        try:
            self.api.install_support(
                self.app_id, self.start_command, self.launched.emit
            )
            self.succeeded.emit()
        except (OSError, subprocess.SubprocessError) as error:
            logger.exception("Failed to install GOG support for %s", self.app_id)
            self.error = str(error)
            self.failed.emit(self.error)


class MainWindowGOGTabMixin(_MainWindowTypingBase):
    """Add account actions and the shared downloads page."""

    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def createGOGDownloadsTab(self) -> None:
        self.gog_process = None
        self.gog_download_queue = []
        self.gog_download_output = ""
        self.gog_support_workers = []
        self.downloadTableHeadings = {}
        page = QWidget()
        page.setStyleSheet(self.theme.OTHER_PAGES_WIDGET_STYLE)
        layout = QVBoxLayout(page)
        layout.setSpacing(self.theme.downloadsSectionSpacing)
        title = QLabel(_("Downloads"))
        title.setStyleSheet(self.theme.TAB_TITLE_STYLE)
        layout.addWidget(title)
        self._create_active_download_card(layout)
        self.downloadQueuedTable = self._create_download_table(_("Queued"), layout)
        completed_header = QHBoxLayout()
        completed_header.addWidget(QLabel(_("Completed")))
        clear_button = QPushButton(_("Clear List"))
        clear_button.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        clear_button.clicked.connect(self._clear_completed_downloads)
        completed_header.addWidget(clear_button)
        completed_header.addStretch()
        layout.addLayout(completed_header)
        self.downloadCompletedTable = self._create_download_table("", layout)
        layout.addStretch()
        self.stackedWidget.addWidget(page)
        self._update_downloads_tab_visibility()

    def _update_downloads_tab_visibility(self) -> None:
        has_downloads = (
            not self.downloadActiveCard.isHidden()
            or self.downloadQueuedTable.rowCount() > 0
            or self.downloadCompletedTable.rowCount() > 0
        )
        self.tabButtons[6].setVisible(has_downloads)
        if not has_downloads and self.stackedWidget.currentIndex() == 6:
            self.switchTab(0)

    def _create_active_download_card(self, layout: QVBoxLayout) -> None:
        self.downloadActiveHeading = QLabel(_("Now Downloading"))
        self.downloadActiveHeading.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        layout.addWidget(self.downloadActiveHeading)
        self.downloadActiveCard = QFrame()
        self.downloadActiveCard.setObjectName("downloadsActiveCard")
        self.downloadActiveCard.setStyleSheet(self.theme.DOWNLOADS_ACTIVE_STYLE)
        self.downloadActiveCard.setFixedHeight(self.theme.downloadsActiveCardHeight)
        card_layout = QVBoxLayout(self.downloadActiveCard)
        card_layout.setContentsMargins(*self.theme.downloadsActiveCardMargins)
        card_layout.setSpacing(self.theme.downloadsActiveCardSpacing)
        content = QHBoxLayout()
        content.setSpacing(self.theme.downloadsActiveCardSpacing)
        self.downloadActiveCover = QLabel()
        self.downloadActiveCover.setFixedSize(*self.theme.downloadsActiveCoverSize)
        content.addWidget(self.downloadActiveCover)
        info = QVBoxLayout()
        header = QHBoxLayout()
        self.downloadActiveTitle = QLabel()
        self.downloadActiveTitle.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
        header.addWidget(self.downloadActiveTitle)
        header.addStretch()
        self.downloadCancelButton = QPushButton(_("Cancel"))
        self.downloadCancelButton.setStyleSheet(self.theme.ACTION_BUTTON_STYLE)
        self.downloadCancelButton.clicked.connect(self._cancel_gog_download)
        header.addWidget(self.downloadCancelButton)
        info.addLayout(header)
        self.downloadActiveDetails = QLabel(_("Waiting…"))
        self.downloadActiveDetails.setStyleSheet(self.theme.CONTENT_STYLE)
        info.addWidget(self.downloadActiveDetails)
        metrics = QHBoxLayout()
        self.downloadSpeedLabel = QLabel(_("Downloading: ") + "\u2014")
        self.diskSpeedLabel = QLabel(_("Disk: ") + "\u2014")
        metrics.addWidget(self.downloadSpeedLabel)
        metrics.addWidget(self.diskSpeedLabel)
        metrics.addStretch()
        info.addLayout(metrics)
        content.addLayout(info, stretch=1)
        card_layout.addLayout(content)
        self.downloadOverallProgress = QProgressBar()
        self.downloadOverallProgress.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        card_layout.addWidget(self.downloadOverallProgress)
        layout.addWidget(self.downloadActiveCard)
        self.downloadActiveHeading.setVisible(False)
        self.downloadActiveCard.setVisible(False)

    def _create_download_table(self, heading: str, layout: QVBoxLayout) -> QTableWidget:
        label = None
        if heading:
            label = QLabel(heading)
            label.setStyleSheet(self.theme.SETTINGS_TITLE_STYLE)
            layout.addWidget(label)
        columns = (_("Game Title"), _("Started at"), _("Type"), _("Store"))
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setStyleSheet(self.theme.DOWNLOADS_TABLE_STYLE)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setFixedHeight(self.theme.downloadsTableHeaderHeight)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(columns)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        self._update_download_table_height(table)
        layout.addWidget(table)
        if label is not None:
            self.downloadTableHeadings[table] = label
            label.setVisible(False)
        table.setVisible(False)
        return table

    def _update_download_table_height(self, table: QTableWidget) -> None:
        rows = max(1, table.rowCount())
        height = self.theme.downloadsTableHeaderHeight + rows * self.theme.downloadsTableRowHeight
        table.setFixedHeight(height)
        has_rows = table.rowCount() > 0
        table.setVisible(has_rows)
        heading = self.downloadTableHeadings.get(table)
        if heading is not None:
            heading.setVisible(has_rows)

    def _clear_completed_downloads(self) -> None:
        self.downloadCompletedTable.setRowCount(0)
        self._update_download_table_height(self.downloadCompletedTable)
        self._update_downloads_tab_visibility()

    def _start_gog_login(self) -> None:
        if getattr(self, "gog_auth_worker", None) is not None:
            return
        clipboard = QApplication.clipboard()
        if not getattr(self, "gog_auth_clipboard_connected", False):
            clipboard.dataChanged.connect(self._check_gog_login_clipboard)
            self.gog_auth_clipboard_connected = True
        self.gog_auth_timer = QTimer(self)
        self.gog_auth_timer.setSingleShot(True)
        self.gog_auth_timer.timeout.connect(self._cancel_gog_login)
        self.gog_auth_timer.start(GOG_LOGIN_TIMEOUT_MS)
        self.gogLoginButton.setEnabled(False)
        self.gogAccountStatus.setText(_("Copy the link to clipboard"))
        if not QDesktopServices.openUrl(QUrl(GOG_LOGIN_URL)):
            self._stop_gog_login_clipboard()
            self.gogLoginButton.setEnabled(True)
            self._update_gog_account_state()

    def _handle_gog_account_action(self) -> None:
        if not self.gog_api.auth_path.is_file():
            self._start_gog_login()
            return
        if not self.gog_api.logout():
            self.gogAccountStatus.setText(_("Failed to log out of GOG account"))
            return
        self._update_gog_account_state()
        self.loadGames(force_load=True)

    def _check_gog_login_clipboard(self) -> None:
        code = self.gog_api.extract_auth_code(QApplication.clipboard().text().strip())
        if not code:
            return
        self._stop_gog_login_clipboard()
        self.gogAccountStatus.setText(_("Refreshing…"))
        worker = GOGAuthWorker(self.gog_api, code)
        worker.authenticated.connect(self._on_gog_authenticated)
        worker.finished.connect(self._on_gog_auth_worker_finished)
        self.gog_auth_worker = worker
        worker.start()

    def _stop_gog_login_clipboard(self) -> None:
        timer = getattr(self, "gog_auth_timer", None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
            self.gog_auth_timer = None
        if not getattr(self, "gog_auth_clipboard_connected", False):
            return
        QApplication.clipboard().dataChanged.disconnect(
            self._check_gog_login_clipboard
        )
        self.gog_auth_clipboard_connected = False

    def _cancel_gog_login(self) -> None:
        self._stop_gog_login_clipboard()
        self.gogLoginButton.setEnabled(True)
        self._update_gog_account_state()

    def _on_gog_authenticated(self, authenticated: bool, error: str) -> None:
        if not authenticated:
            message = error or _("Unknown error")
            self.gogAccountStatus.setText(_("GOG login failed: {0}").format(message))
            return
        account_name = self.gog_api.get_account_name()
        self.gogAccountStatus.setText(
            account_name or _("GOG account connected")
        )
        self.loadGames(force_load=True)
        self._refresh_gog_library()

    def _on_gog_auth_worker_finished(self) -> None:
        self.gogLoginButton.setEnabled(True)
        button_text = (
            _("Log out")
            if self.gog_api.auth_path.is_file() else _("Open login page")
        )
        self.gogLoginButton.setText(button_text)
        self.gog_auth_worker = None

    def _update_gog_account_state(self) -> None:
        connected = self.gog_api.auth_path.is_file()
        account_name = self.gog_api.get_account_name() if connected else ""
        status = (
            account_name or _("GOG account connected")
            if connected else _("GOG account not connected")
        )
        self.gogAccountStatus.setText(status)
        self.gogLoginButton.setEnabled(True)
        self.gogLoginButton.setText(
            _("Log out") if connected else _("Open login page")
        )
        if connected and not account_name:
            self._refresh_gog_account_name()

    def _refresh_gog_account_name(self) -> None:
        if getattr(self, "gog_account_worker", None) is not None:
            return
        worker = GOGAccountWorker(self.gog_api)
        worker.loaded.connect(self._on_gog_account_name_loaded)
        worker.finished.connect(self._on_gog_account_worker_finished)
        self.gog_account_worker = worker
        worker.start()

    def _on_gog_account_name_loaded(self, account_name: str) -> None:
        if account_name:
            self.gogAccountStatus.setText(account_name)

    def _on_gog_account_worker_finished(self) -> None:
        self.gog_account_worker = None

    def _refresh_gog_library(self) -> None:
        if not self.gog_api.auth_path.is_file():
            self.loadGames(force_load=True)
            return
        if getattr(self, "gog_library_worker", None) is not None:
            return
        self.gogAccountStatus.setText(_("Refreshing…"))
        worker = GOGLibraryWorker(self.gog_api)
        worker.loaded.connect(self._on_gog_library_loaded)
        worker.failed.connect(self._on_gog_library_failed)
        worker.progress.connect(self._on_gog_library_progress)
        worker.finished.connect(self._on_gog_library_worker_finished)
        self.gog_library_worker = worker
        worker.start()

    def _on_gog_library_progress(self, completed: int, total: int) -> None:
        self.gogAccountStatus.setText(
            _("Refreshing GOG library… {0}/{1}").format(completed, total)
        )

    def _on_gog_library_loaded(self, _games: list) -> None:
        self._update_gog_account_state()
        self.loadGames(force_load=True)

    def _on_gog_library_failed(self, message: str) -> None:
        self.gogAccountStatus.setText(_("Failed to refresh GOG library: {0}").format(message))
        self.loadGames(force_load=True)

    def _on_gog_library_worker_finished(self) -> None:
        self.gog_library_worker = None

    def _install_gog_game(self, game: dict) -> None:
        if self.gog_process is not None:
            self.gog_download_queue.append(game)
            self._append_download_row(self.downloadQueuedTable, game, _("Install"))
            self.switchTab(6)
            return
        app_id = str(game["app_id"])
        install_path = self.gog_api.get_install_path(app_id, str(game["title"]))
        install_path.mkdir(parents=True, exist_ok=True)
        selected_paths: list[str] = []
        file_explorer = FileExplorer(
            self,
            theme=self.theme,
            initial_path=str(install_path),
            directory_only=True,
        )
        file_explorer.setWindowTitle(_("Select installation folder"))
        file_explorer.file_signal.file_selected.connect(selected_paths.append)
        file_explorer.exec()
        if not selected_paths:
            return
        install_path = Path(selected_paths[0])
        manifest_path = (
            self.gog_api.config_dir / "heroic_gogdl" / "manifests" / app_id
        )
        if manifest_path.is_file() and not self.gog_api.is_game_installed(app_id):
            try:
                manifest_path.unlink()
            except OSError as error:
                logger.error("Failed to reset incomplete GOG download: %s", error)
                self.gogAccountStatus.setText(str(error))
                return
        support_path = (
            self.gog_api.config_dir / "heroic_gogdl" / "gog-support" / app_id
        )
        try:
            command = self.gog_api.build_command(
                [
                    "download", app_id, "--path", str(install_path),
                    "--support", str(support_path), "--platform", "windows",
                ]
            )
        except FileNotFoundError as error:
            self.gogAccountStatus.setText(str(error))
            return
        self._start_gog_download(game, install_path, command, _("Install"))

    def _repair_gog_game(self, game: dict) -> None:
        if self.gog_process is not None:
            self.gogAccountStatus.setText(_("Another GOG operation is already running"))
            return
        app_id = str(game["app_id"])
        install_path = self.gog_api.get_installed_path(app_id)
        if install_path is None:
            self.gogAccountStatus.setText(_("GOG installation not found"))
            return
        support_path = (
            self.gog_api.config_dir / "heroic_gogdl" / "gog-support" / app_id
        )
        try:
            command = self.gog_api.build_command(
                [
                    "repair", app_id, "--path", str(install_path),
                    "--support", str(support_path), "--platform", "windows",
                ]
            )
        except FileNotFoundError as error:
            self.gogAccountStatus.setText(str(error))
            return
        self._start_gog_download(game, install_path, command, _("Repair"))

    def _import_gog_game(self, game: dict) -> None:
        selected_paths: list[str] = []
        file_explorer = FileExplorer(
            self, theme=self.theme, initial_path=str(Path.home() / "Games"),
            directory_only=True,
        )
        file_explorer.setWindowTitle(_("Select GOG game folder"))
        file_explorer.file_signal.file_selected.connect(selected_paths.append)
        file_explorer.exec()
        if not selected_paths:
            return
        app_id = str(game["app_id"])
        game_path = self.gog_api.find_install_path(app_id, Path(selected_paths[0]))
        if game_path is None:
            self.gogAccountStatus.setText(_("Selected folder is not this GOG game"))
            return
        self.gog_api.save_installed_game(
            app_id, {"install_path": str(game_path), "title": str(game["title"])}
        )
        self.gog_api.ensure_launch_parameters(app_id)
        self.loadGames(force_load=True)

    def _delete_gog_game(self, game: dict) -> None:
        app_id = str(game["app_id"])
        install_path = self.gog_api.get_installed_path(app_id)
        if install_path is None:
            self.gogAccountStatus.setText(_("GOG installation not found"))
            return
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle(_("Confirm Deletion"))
        message_box.setText(
            _("Delete '{0}' and all files in its installation folder?").format(
                game["title"]
            )
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.No)
        message_box.setButtonText(QMessageBox.StandardButton.Yes, _("Yes"))
        message_box.setButtonText(QMessageBox.StandardButton.No, _("No"))
        if message_box.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(install_path)
        except OSError as error:
            logger.error("Failed to delete GOG game %s: %s", app_id, error)
            self.gogAccountStatus.setText(str(error))
            return
        manifest_path = (
            self.gog_api.config_dir / "heroic_gogdl" / "manifests" / app_id
        )
        try:
            manifest_path.unlink(missing_ok=True)
        except OSError as error:
            logger.warning("Failed to delete GOG manifest %s: %s", app_id, error)
        self.gog_api.remove_installed_game(app_id)
        self.context_menu_manager.remove_gog_shortcuts(str(game["title"]))
        self.loadGames(force_load=True)

    def _start_gog_download(
        self, game: dict, install_path: Path, command: list[str], action: str
    ) -> None:
        app_id = str(game["app_id"])
        self.downloadActiveTitle.setText(str(game["title"]))
        self.downloadActiveDetails.setText(_("Starting"))
        cover_width, cover_height = self.theme.downloadsActiveCoverSize
        load_pixmap_async(
            str(game.get("cover", "")), cover_width, cover_height,
            self.downloadActiveCover.setPixmap,
            app_name=f"download-active-{app_id}",
        )
        self.downloadActiveHeading.setVisible(True)
        self.downloadActiveCard.setVisible(True)
        self._update_downloads_tab_visibility()
        process = QProcess(self)
        process.setProgram(command[0])
        process.setArguments(command[1:])
        process.setProcessEnvironment(self._gog_process_environment())
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_gog_download_output)
        process.finished.connect(self._on_gog_download_finished)
        self.gog_process = process
        self.gog_active_app_id = app_id
        self.gog_active_game = game
        self.gog_active_install_path = install_path
        self.gog_active_action = action
        self.gog_download_output = ""
        self.downloadOverallProgress.setValue(0)
        self.downloadCancelButton.setEnabled(True)
        self.switchTab(6)
        process.start()

    def _cancel_gog_download(self) -> None:
        if self.gog_process is None:
            return
        process = self.gog_process
        self.downloadCancelButton.setEnabled(False)
        self.downloadActiveDetails.setText(_("Cancel"))
        process.terminate()
        QTimer.singleShot(
            GOG_CANCEL_KILL_TIMEOUT_MS,
            lambda: self._kill_gog_process(process),
        )

    def _kill_gog_process(self, process: QProcess) -> None:
        if process.state() != QProcess.ProcessState.NotRunning:
            logger.warning("gogdl did not terminate after cancellation; killing it")
            process.kill()

    def _append_download_row(
        self, table: QTableWidget, game: dict, action: str
    ) -> tuple[int, QLabel]:
        row = table.rowCount()
        table.insertRow(row)
        game_cell, details_label = self._create_download_game_cell(game)
        table.setCellWidget(row, 0, game_cell)
        values = (datetime.now().strftime("%H:%M:%S"), action, "GOG")
        for column, value in enumerate(values, 1):
            table.setItem(row, column, QTableWidgetItem(value))
        table.setRowHeight(row, self.theme.downloadsTableRowHeight)
        if table is self.downloadQueuedTable:
            details_label.setText(_("Queued"))
        else:
            details_label.setText(action)
        self._update_download_table_height(table)
        self._update_downloads_tab_visibility()
        return row, details_label

    def _create_download_game_cell(self, game: dict) -> tuple[QWidget, QLabel]:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(*self.theme.downloadsCellMargins)
        layout.setSpacing(self.theme.downloadsCellSpacing)
        cover = QLabel()
        cover_width, cover_height = self.theme.downloadsCoverSize
        cover.setFixedSize(cover_width, cover_height)
        layout.addWidget(cover)
        text_layout = QVBoxLayout()
        title = QLabel(str(game["title"]))
        details = QLabel(_("Waiting…"))
        details.setStyleSheet(self.theme.CONTENT_STYLE)
        text_layout.addWidget(title)
        text_layout.addWidget(details)
        layout.addLayout(text_layout)
        load_pixmap_async(
            str(game.get("cover", "")), cover_width, cover_height, cover.setPixmap,
            app_name=f"download-{game['app_id']}",
        )
        return widget, details

    def _gog_process_environment(self) -> QProcessEnvironment:
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("GOGDL_CONFIG_PATH", str(self.gog_api.config_dir))
        return environment

    def _read_gog_download_output(self) -> None:
        if self.gog_process is None:
            return
        output = bytes(
            self.gog_process.readAllStandardOutput().data()
        ).decode(errors="replace")
        self.gog_download_output = (self.gog_download_output + output)[-4096:]
        percentages = re.findall(
            r"Progress:\s+(\d{1,3}(?:\.\d+)?)", self.gog_download_output
        )
        if percentages:
            self.downloadOverallProgress.setValue(int(float(percentages[-1])))
        download_speeds = re.findall(
            r"Download\t-\s+(\S+)\s+MiB", self.gog_download_output
        )
        disk_speeds = re.findall(
            r"Disk\t-\s+(\S+)\s+MiB", self.gog_download_output
        )
        downloaded = re.findall(
            r"Downloaded:\s+([\d.]+\s+MiB)", self.gog_download_output
        )
        eta = re.findall(r"ETA:\s+(\d{2}:\d{2}:\d{2})", self.gog_download_output)
        if download_speeds:
            self.downloadSpeedLabel.setText(
                _("Download: {0} MiB/s").format(download_speeds[-1])
            )
        if disk_speeds:
            self.diskSpeedLabel.setText(
                _("Disk: {0} MiB/s").format(disk_speeds[-1])
            )
        details = []
        if downloaded:
            details.append(downloaded[-1])
        if download_speeds:
            details.append(f"{download_speeds[-1]} MiB/s")
        if eta:
            details.append(_("ETA: {0}").format(eta[-1]))
        if details:
            self._update_active_download_details(details)

    def _update_active_download_details(self, details: list[str]) -> None:
        self.downloadActiveDetails.setText("  ·  ".join(details))

    def _on_gog_download_finished(
        self, code: int, _status: QProcess.ExitStatus
    ) -> None:
        game = self.gog_active_game
        install_path = self.gog_active_install_path
        app_id = str(game["app_id"])
        self.downloadActiveHeading.setVisible(False)
        self.downloadActiveCard.setVisible(False)
        game_path = self.gog_api.find_install_path(app_id, install_path)
        if code == 0 and game_path is None:
            code = 1
        completed_action = _("Failed")
        if code == 0:
            completed_action = (
                _("Repaired") if self.gog_active_action == _("Repair")
                else _("Installed")
            )
        _completed_row, completed_details = self._append_download_row(
            self.downloadCompletedTable, game, completed_action,
        )
        if code == 0:
            self.gog_api.save_installed_game(
                app_id, {"install_path": str(game_path), "title": game["title"]}
            )
            self._update_installed_gog_detail(app_id)
            self.loadGames(force_load=True)
        else:
            error = self._get_gog_download_error()
            completed_details.setText(error)
            logger.error("GOG download failed for %s: %s", app_id, error)
        self.gog_process = None
        self.downloadOverallProgress.setValue(0)
        self.downloadSpeedLabel.setText(_("Downloading: ") + "\u2014")
        self.diskSpeedLabel.setText(_("Disk: ") + "\u2014")
        if self.gog_download_queue:
            next_game = self.gog_download_queue.pop(0)
            self.downloadQueuedTable.removeRow(0)
            self._update_download_table_height(self.downloadQueuedTable)
            self._install_gog_game(next_game)

    def _start_gog_support_setup(self, app_id: str, button=None) -> None:
        if getattr(self, "gog_support_workers", []):
            return
        start_command = getattr(self, "start_sh", None)
        if not start_command:
            logger.warning("PortProton is unavailable for GOG support setup")
            return
        self.downloadActiveTitle.setText("GOG Redist")
        self.downloadActiveDetails.setText(_("Starting"))
        self.downloadActiveCover.clear()
        self.downloadActiveHeading.setVisible(True)
        self.downloadActiveCard.setVisible(True)
        self._update_downloads_tab_visibility()
        self.downloadCancelButton.setEnabled(False)
        self.downloadOverallProgress.setValue(0)
        worker = GOGSupportWorker(self.gog_api, app_id, start_command)
        worker.failed.connect(self.gogAccountStatus.setText)
        worker.launched.connect(
            lambda process: self._track_gog_support_process(
                app_id, process, button
            )
        )
        worker.succeeded.connect(
            lambda: self._launch_after_gog_support(app_id, button)
        )
        worker.finished.connect(lambda: self._finish_gog_support_setup(worker))
        self.gog_support_workers.append(worker)
        worker.start()

    def _track_gog_support_process(
        self, app_id: str, process: subprocess.Popen, button=None
    ) -> None:
        target = self.gog_api.get_launch_target(app_id)
        self.game_processes.append(process)
        self.target_exe = os.path.basename(target or app_id)
        self.current_running_button = button
        self.input_manager.suspend_gamepad_polling()
        self._set_running_button_stop()

    def _launch_after_gog_support(self, app_id: str, button=None) -> None:
        self.game_processes = [
            process for process in self.game_processes
            if process.poll() is None
        ]
        self._launch_gog_game(app_id, button)

    def _finish_gog_support_setup(self, worker: GOGSupportWorker) -> None:
        workers = getattr(self, "gog_support_workers", [])
        if worker in workers:
            workers.remove(worker)
        self.downloadActiveHeading.setVisible(False)
        self.downloadActiveCard.setVisible(False)
        action = _("Failed") if worker.error else _("Installed")
        redist = {"app_id": "gog-redist", "title": "GOG Redist", "cover": ""}
        _row, details = self._append_download_row(
            self.downloadCompletedTable, redist, action
        )
        if worker.error:
            details.setText(worker.error)
            self.resetPlayButton()

    def _get_gog_download_error(self) -> str:
        lines = [line.strip() for line in self.gog_download_output.splitlines()]
        error_lines = [line for line in lines if "ERROR" in line.upper()]
        if error_lines:
            return error_lines[-1]
        useful = [line for line in lines if line and "[PROGRESS]" not in line]
        return useful[-1] if useful else _("Download process failed")

    def _update_installed_gog_detail(self, app_id: str) -> None:
        install_uri = f"gog://install/{app_id}"
        if self.current_exec_line != install_uri:
            return
        if self.stackedWidget.currentWidget() is not self.currentDetailPage:
            return
        source = self.detail_page_manager._current_detail_source
        if source is None or source[0] != "game":
            return
        source[1]["exec_line"] = f"gog://launch/{app_id}"
        self.current_exec_line = source[1]["exec_line"]
        self.detail_page_manager._reopen_current_detail_page()
