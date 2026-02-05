import sys
import os
import subprocess
import shutil
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from portprotonqt.main_window import MainWindow
from portprotonqt.config_utils import (
    save_fullscreen_config,
    read_fullscreen_config,
    get_portproton_start_command
)
from portprotonqt.logger import get_logger, setup_logger
from portprotonqt.cli import parse_args

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"
__app_version__ = "0.1.10"

def get_version():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return f"{__app_version__} ({commit})"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return __app_version__


def is_apple_silicon():
    path = "/proc/device-tree/compatible"

    if not os.path.exists(path):
        return False

    try:
        with open(path, "rb") as f:
            dtcompat = f.read().decode('utf-8', errors='ignore')

            if "apple,arm-platform" in dtcompat:
                return True
            else:
                return False
    except OSError:
        return False

def main():
    # Check if running on Apple Silicon/Asahi Linux and re-execute under muvm if needed
    if is_apple_silicon() and 'PORTPROTONQT_MUVM' not in os.environ:
        muvm_path = shutil.which('muvm')
        if muvm_path:
            env = os.environ.copy()
            args = [muvm_path, "-i", "-e", "PORTPROTONQT_MUVM=1", sys.executable, os.path.abspath(__file__)]
            os.execvpe(muvm_path, args + sys.argv[1:], env)

    os.environ["PW_CLI"] = "1"
    os.environ["PROCESS_LOG"] = "1"
    os.environ["START_FROM_STEAM"] = "1"

    # Get the PortProton start command
    start_sh = get_portproton_start_command()

    if start_sh is None:
        return

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme(__app_id__))
    app.setDesktopFileName(__app_id__)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__app_version__)

    args = parse_args()
    setup_logger(args.debug_level)
    logger = get_logger(__name__)

    # --- Single-instance logic ---
    server_name = __app_id__
    socket = QLocalSocket()
    socket.connectToServer(server_name)

    if socket.waitForConnected(200):
        # Второй экземпляр — передаём команду первому
        fullscreen = args.fullscreen or read_fullscreen_config()
        msg = b"show:fullscreen" if fullscreen else b"show"
        socket.write(msg)
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        logger.info("Restored existing instance from tray")
        return

    # Если старый сокет остался — удалить
    QLocalServer.removeServer(server_name)

    local_server = QLocalServer()
    if not local_server.listen(server_name):
        logger.warning(f"Failed to start local server: {local_server.errorString()}")
        return

    # --- Main Window ---
    version = get_version()
    window = MainWindow(app_name=__app_name__, version=version)

    # --- Handle incoming connections ---
    def handle_new_connection():
        conn = local_server.nextPendingConnection()
        if not conn:
            return

        if conn.waitForReadyRead(1000):
            data = conn.readAll().data()
            msg = bytes(data).decode("utf-8", errors="ignore")
            logger.info(f"IPC message received: {msg}")

            def restore_window():
                try:
                    if msg.startswith("show"):
                        # Ensure the window is visible and not minimized
                        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
                        window.show()
                        window.raise_()
                        window.activateWindow()

                        # Ensure window is in active state for systems with strict focus policies
                        window.setWindowState(window.windowState() | Qt.WindowState.WindowActive)

                        if ":fullscreen" in msg:
                            logger.info("Switching to fullscreen via IPC")
                            save_fullscreen_config(True)
                            window.showFullScreen()
                        else:
                            logger.info("Switching to normal window via IPC")
                            save_fullscreen_config(False)
                            window.showNormal()
                except Exception as e:
                    logger.warning(f"Failed to restore window: {e}")

            # Выполняем в основном потоке
            QTimer.singleShot(0, restore_window)

        conn.disconnectFromServer()

    local_server.newConnection.connect(handle_new_connection)

    # --- Initial fullscreen state ---
    launch_fullscreen = args.fullscreen or read_fullscreen_config()
    if launch_fullscreen:
        logger.info(
            f"Launching in fullscreen mode ({'--fullscreen' if args.fullscreen else 'config'})"
        )
        save_fullscreen_config(True)
        window.showFullScreen()
    else:
        logger.info("Launching in normal mode")
        save_fullscreen_config(False)
        window.showNormal()

    # Execute the initial PortProton command after the UI is set up
    def run_initial_command():
        nonlocal start_sh
        if start_sh:
            try:
                subprocess.run(start_sh + ["cli", "--initial"], timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Initial PortProton command timed out")
            except Exception as e:
                logger.error(f"Error running initial PortProton command: {e}")
        else:
            logger.warning("PortProton start command not available, skipping initial command")

    # Run the initial command after the UI is displayed
    QTimer.singleShot(100, run_initial_command)

    # --- Cleanup ---
    def cleanup_on_exit():
        try:
            local_server.close()
            QLocalServer.removeServer(server_name)
            if window:
                window.close()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

    app.aboutToQuit.connect(cleanup_on_exit)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
