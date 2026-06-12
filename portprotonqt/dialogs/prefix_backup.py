"""Prefix backup progress dialog."""

from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout

from portprotonqt.config import ui_config
from portprotonqt.localization import _
from portprotonqt.scripts_utils.prefix_backup import BackupProgress, create_backup, restore_backup
from portprotonqt.theme_manager import ThemeManager


@dataclass(frozen=True)
class PrefixBackupJob:
    operation: str
    port_data_path: str
    source: str
    target: str = ""


class PrefixBackupThread(QThread):
    """Worker thread for prefix backup operations."""

    progress = Signal(object)
    completed = Signal(bool)

    def __init__(self, job: PrefixBackupJob):
        super().__init__()
        self.job = job
        self.success = False

    def _emit_progress(self, progress: BackupProgress) -> None:
        self.progress.emit(progress)

    def run(self) -> None:
        if self.job.operation == "backup":
            exit_code = create_backup(
                self.job.port_data_path,
                self.job.source,
                self.job.target,
                self._emit_progress,
            )
        else:
            exit_code = restore_backup(self.job.port_data_path, self.job.source, self._emit_progress)
        self.success = exit_code == 0
        self.completed.emit(self.success)


class PrefixBackupDialog(QDialog):
    """Dialog showing prefix backup or restore progress."""

    def __init__(self, parent, worker: PrefixBackupThread, theme=None):
        super().__init__(parent)
        self.theme = theme if theme else ThemeManager().apply_theme(ui_config.get_theme())
        self.worker = worker
        title = _("Prefix backup") if worker.job.operation == "backup" else _("Prefix restore")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(self.theme.MESSAGE_BOX_STYLE)
        self.resize(740, 230)

        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(self.theme.PARAMS_TITLE_STYLE)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(self.theme.PROGRESS_BAR_STYLE)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet(self.theme.CONTENT_STYLE)
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(self.theme.CONTENT_STYLE)
        layout.addWidget(self.stats_label)

        self.worker.progress.connect(self.update_progress)
        self.worker.completed.connect(self.finish)

    def start(self) -> None:
        self.worker.start()
        self.exec()

    def update_progress(self, progress: BackupProgress) -> None:
        self.progress_bar.setValue(progress.percent)
        self.file_label.setText(_("File: {0}").format(progress.path))
        if progress.files_total:
            files_text = _("{0}/{1} files").format(progress.files_done, progress.files_total)
        else:
            files_text = _("{0} files").format(progress.files_done)
        self.stats_label.setText(_("{0}, Speed: {1:.1f} MB/s").format(files_text, progress.speed))

    def finish(self, success: bool) -> None:
        if success:
            self.progress_bar.setValue(100)
        self.accept()
