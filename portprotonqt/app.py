import sys
import os
import subprocess
import shutil
from PySide6.QtCore import QTimer, Qt, QThread, Signal
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
from portprotonqt.cli import parse_args, is_portproton_url, parse_portproton_url, is_exe_file, add_steam_compat_tool, parse_resolution
from portprotonqt.portproton_api import PortProtonAPI, set_user_conf_setting
from portprotonqt.downloader import Downloader
from portprotonqt.debug_utils import get_screen_info

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"
__app_version__ = "0.1.11"

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
    # Parse args early to check for force-muvm flag
    parsed_args = parse_args()

    # Handle --add-steam-compat-tool flag
    if parsed_args.add_steam_compat_tool:
        success = add_steam_compat_tool()
        sys.exit(0 if success else 1)

    # Check if running on Apple Silicon/Asahi Linux or if forced to run under muvm, and re-execute under muvm if needed
    should_run_under_muvm = (is_apple_silicon() or parsed_args.force_muvm) and 'PORTPROTONQT_MUVM' not in os.environ
    if should_run_under_muvm:
        muvm_path = shutil.which('muvm')
        if muvm_path:
            env = os.environ.copy()
            args_list = [muvm_path, "-i", "-e", "PORTPROTONQT_MUVM=1", sys.executable, os.path.abspath(__file__)]
            os.execvpe(muvm_path, args_list + sys.argv[1:], env)

    os.environ["PW_CLI"] = "1"
    os.environ["PROCESS_LOG"] = "1"
    os.environ["START_FROM_STEAM"] = "1"

    # Check if running as Steam compatibility tool (STEAM_COMPAT=1)
    # In this mode, launch game immediately without GUI
    is_steam_compat = os.environ.get("STEAM_COMPAT") == "1"

    # Get the PortProton start command
    start_sh = get_portproton_start_command()

    if start_sh is None:
        return

    # Handle Steam compatibility mode - launch game directly without GUI
    if is_steam_compat:
        # In Steam compatibility mode, exe path is passed as first argument
        exe_path = parsed_args.file_or_url if parsed_args.file_or_url else None
        if exe_path and is_exe_file(exe_path):
            exe_path = os.path.abspath(os.path.expanduser(exe_path))
            logger = get_logger(__name__)
            setup_logger(parsed_args.debug_level)
            logger.info("Running in Steam compatibility mode, launching: %s", exe_path)

            # Launch game via PortProton without GUI
            env_vars = os.environ.copy()
            cmd = start_sh + [exe_path]
            try:
                subprocess.run(cmd, env=env_vars)
            except Exception as e:
                logger.error("Failed to launch game in Steam compatibility mode: %s", e)
                sys.exit(1)
            sys.exit(0)
        else:
            # No exe provided, fall back to GUI mode
            is_steam_compat = False

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme(__app_id__))
    app.setDesktopFileName(__app_id__)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__app_version__)

    args = parsed_args
    setup_logger(args.debug_level)
    logger = get_logger(__name__)

    # --- Single-instance logic ---
    server_name = __app_id__
    socket = QLocalSocket()
    socket.connectToServer(server_name)

    if socket.waitForConnected(200):
        # Second instance — send command to the first one
        fullscreen = args.fullscreen or read_fullscreen_config()
        msg = b"show:fullscreen" if fullscreen else b"show"
        socket.write(msg)
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        logger.info("Restored existing instance from tray")
        return

    # Remove old socket if it exists
    QLocalServer.removeServer(server_name)

    local_server = QLocalServer()
    if not local_server.listen(server_name):
        logger.warning(f"Failed to start local server: {local_server.errorString()}")
        return

    # Check if we have a portproton:// URL or exe file to handle
    if args.file_or_url:
        if is_portproton_url(args.file_or_url):
            # Parse the portproton:// URL to get the full download URL
            download_url = parse_portproton_url(args.file_or_url)
            if download_url:

                # Create PortProtonAPI instance to handle the download
                downloader = Downloader(max_workers=4)
                api = PortProtonAPI(downloader=downloader)

                # Perform the PPDB download - user will select the .exe file via FileExplorer
                success = api.download_ppdb_from_url(download_url)
                if success:
                    logger.info(f"Successfully downloaded PPDB from {download_url}")
                else:
                    logger.error(f"Failed to download PPDB from {download_url}")

                # Exit after handling the URL
                return
            else:
                logger.error(f"Failed to parse portproton:// URL: {args.file_or_url}")
                return
        elif is_exe_file(args.file_or_url):
            # Store exe path for later processing after window is created
            exe_path = os.path.abspath(os.path.expanduser(args.file_or_url))
        else:
            logger.warning(f"Unknown file or URL format: {args.file_or_url}")
            exe_path = None
    else:
        exe_path = None

    # --- Main Window ---
    version = get_version()

    # Parse resolution if provided
    window_resolution = None
    if args.resolution:
        window_resolution = parse_resolution(args.resolution)
        if window_resolution is None:
            logger.warning(f"Invalid resolution format: {args.resolution}, expected WIDTHxHEIGHT (e.g., 1920x1080)")

    window = MainWindow(app_name=__app_name__, version=version, launch_exe=exe_path, resolution=window_resolution)

    # Handle exe file if provided
    if exe_path:
        # Defer the call until after the window is shown
        def handle_launch_exe():
            window.handle_launch_exe(exe_path)
        QTimer.singleShot(0, handle_launch_exe)

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

            # Execute in the main thread
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
    elif window_resolution:
        logger.info(f"Launching with resolution: {window_resolution[0]}x{window_resolution[1]}")
        window.resize(window_resolution[0], window_resolution[1])
        window.showNormal()
    else:
        logger.info("Launching in normal mode")
        save_fullscreen_config(False)
        window.showNormal()

    # Execute the initial PortProton command after the UI is set up
    class InitialCommandWorker(QThread):
        """Worker thread to run initial PortProton command without blocking UI."""
        finished = Signal()

        def __init__(self, start_cmd: list[str]):
            super().__init__()
            self.start_cmd = start_cmd

        def run(self):
            try:
                # Get screen information before running the initial command
                # Hack: avoid script from dependency on xorg-xrandr
                from portprotonqt.config_utils import get_portproton_location
                portproton_path = get_portproton_location()

                if portproton_path:
                    screen_resolution, screen_primary = get_screen_info(portproton_path)

                    # Store screen information in user.conf
                    if screen_resolution and '=' in screen_resolution:
                        var_name, var_value = screen_resolution.split('=', 1)
                        set_user_conf_setting(var_name, var_value)

                    if screen_primary and '=' in screen_primary:
                        var_name, var_value = screen_primary.split('=', 1)
                        set_user_conf_setting(var_name, var_value)

                # Run the initial PortProton command
                subprocess.run(self.start_cmd + ["cli", "--initial"], timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Initial PortProton command timed out")
            except Exception as e:
                logger.error(f"Error running initial PortProton command: {e}")
            finally:
                self.finished.emit()

    if start_sh:
        worker = InitialCommandWorker(start_sh)
        worker.start()
    else:
        logger.warning("PortProton start command not available, skipping initial command")

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
