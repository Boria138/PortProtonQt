"""Wine archive extractor for PortProtonQt."""

import os
import time
import libarchive
from PySide6.QtCore import QThread, Signal, QMutex
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


class ExtractionThread(QThread):
    """Thread for extracting Wine/Proton archives."""

    progress = Signal(int)
    speed = Signal(float)
    eta = Signal(int)
    finished = Signal(str, bool)
    error = Signal(str)

    def __init__(self, archive_path: str, extract_dir: str):
        super().__init__()
        self.archive_path = archive_path
        self.extract_dir = extract_dir
        self._is_running = True
        self._mutex = QMutex()

    def _should_stop(self) -> bool:
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return not running

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

            original_dir = os.getcwd()
            old_umask = os.umask(0)
            os.chdir(self.extract_dir)

            try:
                deferred_times = []

                with libarchive.file_reader(self.archive_path) as archive:
                    for entry in archive:
                        if self._should_stop():
                            return

                        entry_path = entry.pathname
                        if entry_path is None:
                            continue

                        if entry.isdir:
                            os.makedirs(entry_path, exist_ok=True)
                            if entry.mode:
                                try:
                                    os.chmod(entry_path, entry.mode)
                                except (OSError, PermissionError):
                                    pass
                            if entry.mtime:
                                deferred_times.append((entry_path, entry.mtime))

                        elif entry.isfile:
                            parent_dir = os.path.dirname(entry_path)
                            if parent_dir:
                                os.makedirs(parent_dir, exist_ok=True)

                            with open(entry_path, 'wb') as f:
                                for block in entry.get_blocks():
                                    if self._should_stop():
                                        return
                                    f.write(block)

                            if entry.mode:
                                try:
                                    os.chmod(entry_path, entry.mode)
                                except (OSError, PermissionError):
                                    pass

                            if entry.mtime:
                                try:
                                    os.utime(entry_path, (entry.mtime, entry.mtime))
                                except (OSError, PermissionError):
                                    pass

                        elif entry.issym:
                            parent_dir = os.path.dirname(entry_path)
                            if parent_dir:
                                os.makedirs(parent_dir, exist_ok=True)

                            if os.path.lexists(entry_path):
                                os.remove(entry_path)

                            link_path = entry.linkpath
                            if link_path is not None:
                                try:
                                    os.symlink(link_path, entry_path)
                                except (OSError, NotImplementedError):
                                    pass

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
                os.umask(old_umask)

        except Exception as e:
            if not self._should_stop():
                self.error.emit(str(e))

    def stop(self):
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

        if self.isRunning():
            self.quit()
            self.wait(1000)
