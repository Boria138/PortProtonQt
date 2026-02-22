"""Debug log manager for game launch and output capture."""

import os
import queue
import signal
import subprocess
import threading
import time

from portprotonqt.logger import get_logger
from portprotonqt.config_utils import get_portproton_location

from portprotonqt.debug_utils.system_info import generate_system_info
from portprotonqt.debug_utils.log_processor import process_portproton_log

logger = get_logger(__name__)


class DebugLogManager:
    """Manages debug log creation with game launch and Wine output capture."""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.exe_path: str | None = None
        self.start_command: list[str] | None = None
        self.wine_output: list[str] = []
        self.is_running = False
        self.output_queue = queue.Queue()
        self.output_thread = None
        self._stop_event = threading.Event()

    def start(self, exe_path: str, start_command: list[str]) -> bool:
        """Start game with PW_LOG=1 and capture output."""
        if self.is_running:
            return False

        self.exe_path = exe_path
        self.start_command = start_command
        self.wine_output = []
        self._stop_event.clear()

        portproton_path = get_portproton_location()
        if portproton_path:
            portproton_log_path = os.path.join(portproton_path, "PortProton.log")
            try:
                if os.path.exists(portproton_log_path):
                    os.remove(portproton_log_path)
                    logger.debug(
                        "Deleted existing PortProton.log at %s",
                        portproton_log_path
                    )
            except OSError as e:
                logger.debug(
                    "Could not delete PortProton.log at %s: %s",
                    portproton_log_path, e
                )

        env_vars = os.environ.copy()
        env_vars["PW_LOG"] = "1"

        cmd = start_command + [exe_path]

        try:
            self.process = subprocess.Popen(
                cmd,
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid
            )

            self.output_thread = threading.Thread(
                target=self._read_output, daemon=True
            )
            self.output_thread.start()

            self.is_running = True
            logger.info("Started debug session for %s", exe_path)
            return True
        except Exception as e:
            logger.error("Failed to start debug session: %s", e)
            return False

    def _read_output(self):
        """Read output from subprocess in a separate thread."""
        if self.process and self.process.stdout:
            try:
                for line in iter(self.process.stdout.readline, ''):
                    if self._stop_event.is_set():
                        break
                    self.output_queue.put(line)
            except Exception as e:
                logger.debug("Error reading output: %s", e)

    def stop(self) -> str | None:
        """Stop game and save debug log with captured Wine output."""
        self._stop_event.set()

        if self.is_running and self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                try:
                    time.sleep(0.1)

                    if self.process.poll() is None:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            except Exception as e:
                logger.debug("Error terminating process: %s", e)

        try:
            while True:
                line = self.output_queue.get_nowait()
                self.wine_output.append(line)
        except queue.Empty:
            pass

        log_file = self._save_log()

        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except (AttributeError, OSError):
                pass
        self.process = None
        self.is_running = False

        return log_file

    def check_running(self) -> bool:
        """Check if process is still running."""
        if self.process is None:
            self.is_running = False
            return False

        poll = self.process.poll()
        if poll is not None:
            self.is_running = False
            return False

        return True

    def _save_log(self) -> str | None:
        """Save complete debug log to file."""
        portproton_path = get_portproton_location()
        if not portproton_path:
            return None

        system_info = generate_system_info(self.exe_path, self.start_command)

        lines = [system_info]

        portproton_log_content = ""

        if portproton_path:
            portproton_log_path = os.path.join(portproton_path, "PortProton.log")

            if os.path.exists(portproton_log_path):
                try:
                    with open(
                        portproton_log_path,
                        encoding="utf-8",
                        errors="ignore"
                    ) as f:
                        portproton_log_content = f.read()
                except OSError as e:
                    logger.debug(
                        "Could not read PortProton log file %s: %s",
                        portproton_log_path, e
                    )

        if portproton_log_content.strip():
            lines.append(portproton_log_content)

        log_content = "\n".join(lines)

        log_content = process_portproton_log(log_content)

        if self.exe_path and os.path.exists(self.exe_path):
            game_dir = os.path.dirname(self.exe_path)
            log_file = os.path.join(game_dir, "PortProtonQt.log")
        else:
            log_file = os.path.join(portproton_path, "PortProtonQt.log")

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(log_content)
            logger.info("Debug log saved to %s", log_file)
            return log_file
        except OSError as e:
            logger.error("Failed to save debug log: %s", e)
            return None

    def cleanup_on_exit(self):
        """Clean up resources and save log when application exits."""
        if self.is_running:
            logger.info("Cleaning up debug log manager on application exit...")
            self.stop()
