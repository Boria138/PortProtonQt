from portprotonqt.logger import get_logger

logger = get_logger(__name__)


class MainWindowWorkersMixin:
    def _stopBackgroundWorkers(self) -> None:
        worker_timeouts = {
            "networkWorker": 3000,
            "bluetoothWorker": 12000,
            "storageWorker": 3000,
            "audioWorker": 3000,
            "autoInstallLoadThread": 3000,
        }
        for worker_name, timeout_ms in worker_timeouts.items():
            self._stopWorkerThread(worker_name, timeout_ms)
        input_manager = getattr(self, "input_manager", None)
        if input_manager is not None:
            input_manager.cleanup()

    def _stopWorkerThread(self, worker_name: str, timeout_ms: int = 3000) -> None:
        worker = getattr(self, worker_name, None)
        if worker is None:
            return
        request_interruption = getattr(worker, "requestInterruption", None)
        if callable(request_interruption):
            request_interruption()

        is_running = getattr(worker, "isRunning", None)
        wait_method = getattr(worker, "wait", None)
        if callable(is_running) and is_running() and callable(wait_method):
            wait_method(timeout_ms)

        if callable(is_running) and is_running():
            logger.warning("%s is still running during shutdown", worker_name)

        setattr(self, worker_name, None)
