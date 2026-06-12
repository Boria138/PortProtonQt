"""Wine downloader for PortProtonQt."""

import os

from PySide6.QtCore import QThread, Signal, QMutex

from portprotonqt.downloader import get_requests_session
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


class DownloadThread(QThread):
    """Thread for downloading Wine/Proton archives."""

    progress = Signal(int)
    finished = Signal(str, bool)
    error = Signal(str)

    def __init__(self, download_url: str, filename: str):
        super().__init__()
        self.download_url = download_url
        self.filename = filename
        self._is_running = True
        self._mutex = QMutex()

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
                if os.path.exists(self.filename):
                    os.remove(self.filename)

        except Exception as e:
            self._mutex.lock()
            if self._is_running:
                self._mutex.unlock()
                if os.path.exists(self.filename):
                    try:
                        os.remove(self.filename)
                    except OSError:
                        pass
                self.error.emit(str(e))
            else:
                self._mutex.unlock()

    def stop(self):
        """Safe thread stop."""
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                logger.warning("Thread did not stop gracefully, but continuing...")
