import argparse
import sys
import os
import importlib
import subprocess
import threading
import urllib.error
import urllib.request
from urllib.parse import quote, unquote
from logging import Logger

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"

try:
    version_module = importlib.import_module("portprotonqt._version")
    APP_COMMIT = version_module.APP_COMMIT
    APP_VERSION = version_module.APP_VERSION
except ImportError:
    APP_COMMIT = ""
    APP_VERSION = "1.2.0"

__app_version__ = APP_VERSION

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PySide6.QtGui import QAction, QIcon

from portprotonqt.config import (
    consume_download_counter_skip,
    display_config,
    get_portproton_start_command,
    get_portproton_location,
    save_portdata_path_to_config,
    ui_config,
    update_app_version,
    window_config,
)
from portprotonqt.logger import get_logger, setup_logger
from portprotonqt.cli import (
    parse_args,
    is_portproton_url,
    parse_portproton_url,
    is_launch_file,
    is_prefix_backup_file,
    normalize_launch_path,
    add_steam_compat_tool,
    reinstall_steam_compat_tool,
    remove_steam_compat_tool,
    clear_cache,
    reset_settings,
    parse_resolution,
)
from portprotonqt.localization import _, get_steam_language

COUNTER_DOWNLOAD_URL = "http://cloud.linux-gaming.ru:8081/api/download/{version}"

def get_version():
    if APP_COMMIT:
        return f"{__app_version__} ({APP_COMMIT})"

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return f"{__app_version__} ({commit})"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return __app_version__


def stop_portproton_game(start_sh: list[str], logger: Logger) -> None:
    try:
        subprocess.run(
            start_sh + ["cli", "--stop"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("Failed to execute PortProton stop command: %s", e)


def get_portproton_tray_icon() -> QIcon:
    from portprotonqt.theme_manager import ThemeManager

    icon = ThemeManager().get_icon("tray_portproton", ui_config.get_theme())
    if isinstance(icon, QIcon):
        return icon
    return QIcon()


def run_silent_tray(app: QApplication, start_sh: list[str], exe_path: str) -> None:
    """Launch a game with a minimal tray stop action."""
    logger = get_logger(__name__)
    app.setQuitOnLastWindowClosed(False)
    tray_icon = QSystemTrayIcon(get_portproton_tray_icon(), app)
    tray_icon.setToolTip(__app_name__)

    from datetime import datetime
    from portprotonqt.time_utils import save_last_launch, save_playtime
    save_last_launch(os.path.splitext(os.path.basename(exe_path))[0], datetime.now())
    start_time = datetime.now()

    process = subprocess.Popen(start_sh + [exe_path], env=os.environ.copy(), shell=False)
    tray_menu = QMenu()

    def end_silent_run():
        monitor_timer.stop()
        elapsed = int((datetime.now() - start_time).total_seconds())
        if elapsed > 0:
            save_playtime(exe_path, elapsed)
        tray_icon.hide()
        app.quit()

    def stop_game() -> None:
        stop_portproton_game(start_sh, logger)
        end_silent_run()

    def close_when_game_exits(_tray_menu: QMenu = tray_menu) -> None:
        if process.poll() is not None:
            end_silent_run()

    stop_action = QAction(_("Stop Game"), tray_menu)
    stop_action.triggered.connect(stop_game)
    tray_menu.addAction(stop_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    monitor_timer = QTimer(app)
    monitor_timer.timeout.connect(close_when_game_exits)
    monitor_timer.start(1000)


def restore_prefix_backup(start_sh: list[str], backup_path: str) -> int:
    """Restore a PortProton prefix backup."""
    logger = get_logger(__name__)
    path = normalize_launch_path(backup_path)
    cmd = start_sh + ["--restore-prefix", path]
    try:
        process = subprocess.Popen(
            cmd,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return process.wait()
    except (OSError, subprocess.SubprocessError) as e:
        logger.error("Failed to restore prefix backup %s: %s", path, e)
        return 1


def notify_download_counter(app_version: str, logger: Logger) -> None:
    url = COUNTER_DOWNLOAD_URL.format(version=quote(app_version, safe=""))

    def send_request() -> None:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=10):
                pass
        except urllib.error.URLError as e:
            logger.debug("Failed to notify download counter: %s", e)
        except OSError as e:
            logger.debug("Failed to notify download counter: %s", e)

    threading.Thread(target=send_request, daemon=True).start()


def create_prefix_backup(start_sh: list[str], prefix_name: str, backup_dir: str) -> int:
    """Create a PortProton prefix backup."""
    logger = get_logger(__name__)
    path = os.path.abspath(os.path.expanduser(backup_dir))
    cmd = start_sh + ["--backup-prefix", prefix_name, path]
    try:
        process = subprocess.run(cmd, env=os.environ.copy(), check=False)
    except (OSError, subprocess.SubprocessError) as e:
        logger.error("Failed to create prefix backup %s: %s", prefix_name, e)
        return 1
    return process.returncode


def is_restore_prefix_request(args: argparse.Namespace) -> bool:
    if args.restore_prefix:
        return bool(args.file_or_url)
    return bool(args.file_or_url and is_prefix_backup_file(args.file_or_url))


def main():
    parsed_args = parse_args()

    # Handle --reinstall-steam-compat-tool flag
    if parsed_args.reinstall_steam_compat_tool:
        success = reinstall_steam_compat_tool()
        sys.exit(0 if success else 1)

    # Handle --add-steam-compat-tool flag
    if parsed_args.add_steam_compat_tool:
        success = add_steam_compat_tool()
        sys.exit(0 if success else 1)

    # Handle --remove-steam-compat-tool flag
    if parsed_args.remove_steam_compat_tool:
        success = remove_steam_compat_tool()
        sys.exit(0 if success else 1)

    if parsed_args.clear_cache:
        success = clear_cache()
        sys.exit(0 if success else 1)

    if parsed_args.reset_settings:
        success = reset_settings()
        sys.exit(0 if success else 1)

    os.environ["FULL_LN"] = get_steam_language()
    portproton_location = get_portproton_location()
    if portproton_location:
        os.environ["PORT_DATA_PATH"] = portproton_location
    ui_config.get_disable_runtime_download()

    # Check if running as Steam compatibility tool (STEAM_COMPAT=1).
    is_steam_compat = os.environ.get("STEAM_COMPAT") == "1"
    is_silent_launch = parsed_args.silent

    # Get the PortProton start command
    start_sh = get_portproton_start_command()

    if start_sh is None:
        return

    if parsed_args.restore_prefix and not parsed_args.file_or_url:
        setup_logger(parsed_args.debug_level)
        sys.exit(1)

    # Handle Steam compatibility mode - launch game directly without GUI.
    if is_steam_compat:
        exe_path = parsed_args.file_or_url if parsed_args.file_or_url else None
        can_launch_without_gui = bool(exe_path and is_launch_file(exe_path))

        if can_launch_without_gui and isinstance(exe_path, str):
            exe_path = normalize_launch_path(exe_path)
            logger = get_logger(__name__)
            setup_logger(parsed_args.debug_level)
            logger.info("Running in Steam compatibility mode, launching: %s", exe_path)
            logger.info("Steam compatibility launch arguments: %s", parsed_args.launch_args)

            # Launch game via PortProton without GUI
            env_vars = os.environ.copy()
            cmd = start_sh + [exe_path] + parsed_args.launch_args
            try:
                subprocess.run(cmd, env=env_vars)
            except Exception as e:
                logger.error("Failed to launch game in Steam compatibility mode: %s", e)
                sys.exit(1)
            sys.exit(0)
        else:
            # No launch file provided, fall back to GUI mode
            is_steam_compat = False

    from PySide6.QtCore import Qt
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme(__app_id__))
    app.setDesktopFileName(__app_id__)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__app_version__)

    args = parsed_args
    setup_logger(args.debug_level)
    logger = get_logger(__name__)
    if consume_download_counter_skip():
        update_app_version(__app_version__)
    elif update_app_version(__app_version__):
        notify_download_counter(__app_version__, logger)

    fullscreen = args.fullscreen or display_config.get_fullscreen()
    ipc_message = "show:fullscreen" if fullscreen else "show"
    backup_request = None
    restore_prefix_path = None
    resolution_from_args = None
    if args.resolution:
        resolution_from_args = parse_resolution(args.resolution)
        if resolution_from_args is None:
            logger.warning(f"Invalid resolution format: {args.resolution}, expected WIDTHxHEIGHT (e.g., 1920x1080)")
        else:
            window_config.set_geometry(resolution_from_args[0], resolution_from_args[1])
            logger.info("Saved window resolution: %sx%s", resolution_from_args[0], resolution_from_args[1])
            ipc_message = "noop"
    if args.create_backup:
        prefix_name, backup_dir = args.create_backup
        backup_request = (prefix_name, os.path.abspath(os.path.expanduser(backup_dir)))
        ipc_message = "backup:{}:{}".format(quote(prefix_name, safe=""), quote(backup_request[1], safe=""))
    elif is_silent_launch and args.file_or_url and is_launch_file(args.file_or_url):
        run_silent_tray(app, start_sh, normalize_launch_path(args.file_or_url))
        sys.exit(app.exec())
    elif is_restore_prefix_request(args):
        restore_prefix_path = normalize_launch_path(args.file_or_url)
        ipc_message = f"restore:{quote(restore_prefix_path, safe='')}"
    elif args.file_or_url and is_launch_file(args.file_or_url):
        ipc_message = f"open:{normalize_launch_path(args.file_or_url)}"

    from PySide6.QtCore import QThread, Signal
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from portprotonqt.main_window import MainWindow
    from portprotonqt.port_data_path_selector import ask_portdata_path, is_portdata_path_read_write
    from portprotonqt.portproton_api import (
        PortProtonAPI,
        get_user_conf_setting,
        set_user_conf_setting,
    )
    from portprotonqt.downloader import Downloader
    from portprotonqt.debug_utils import (
        get_selectable_gpu_entries,
    )
    from portprotonqt.qt_utils import get_screen_info, get_system_dpi_for_wine

    # --- Single-instance logic ---
    server_name = __app_id__
    socket = QLocalSocket()
    socket.connectToServer(server_name)

    if socket.waitForConnected(200):
        # Second instance — send command to the first one
        socket.write(ipc_message.encode("utf-8"))
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

    portdata_warning = None
    if portproton_location and not is_portdata_path_read_write(portproton_location):
        logger.warning("PORT_DATA_PATH is not readable/writable: %s", portproton_location)
        portdata_warning = _("PortProton data folder is not readable and writable. Choose another folder for PortProton data.")
        portproton_location = None

    if not portproton_location:
        portproton_location = ask_portdata_path(portdata_warning, bool(portdata_warning))
        if not portproton_location:
            logger.error("PORT_DATA_PATH is not configured, startup aborted")
            return
        os.environ["PORT_DATA_PATH"] = portproton_location
        if not save_portdata_path_to_config(portproton_location):
            logger.warning("Failed to persist PORT_DATA_PATH in PortProtonQt config")

    # Check if we have a portproton:// URL or launch file to handle
    if args.file_or_url and not restore_prefix_path:
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
        elif is_launch_file(args.file_or_url):
            # Store launch file path for later processing after window is created
            exe_path = normalize_launch_path(args.file_or_url)
        else:
            logger.warning(f"Unknown file or URL format: {args.file_or_url}")
            exe_path = None
    else:
        exe_path = None

    # --- Main Window ---
    version = get_version()

    # Parse resolution if provided
    window_resolution = None
    if args.resolution and resolution_from_args is None:
        logger.warning(f"Invalid resolution format: {args.resolution}, expected WIDTHxHEIGHT (e.g., 1920x1080)")

    window = MainWindow(app_name=__app_name__, version=version, launch_exe=exe_path, resolution=window_resolution, show_system_tab=args.ppqtos)

    # Handle launch file if provided
    if exe_path:
        # Defer the call until after the window is shown
        def handle_launch_exe():
            window.handle_launch_exe(exe_path)
        QTimer.singleShot(0, handle_launch_exe)
    elif backup_request:
        def handle_create_backup():
            window._perform_backup(backup_request[1], backup_request[0])
        QTimer.singleShot(0, handle_create_backup)
    elif restore_prefix_path:
        def handle_restore_prefix():
            window._perform_restore(restore_prefix_path)
        QTimer.singleShot(0, handle_restore_prefix)

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
                    if (
                        msg.startswith("show")
                        or msg.startswith("open:")
                        or msg.startswith("restore:")
                        or msg.startswith("backup:")
                    ):
                        # Ensure the window is visible and not minimized
                        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
                        window.show()
                        window.raise_()
                        window.activateWindow()

                        # Ensure window is in active state for systems with strict focus policies
                        window.setWindowState(window.windowState() | Qt.WindowState.WindowActive)

                        if ":fullscreen" in msg:
                            logger.info("Switching to fullscreen via IPC")
                            display_config.set_fullscreen(True)
                            window.showFullScreen()
                        else:
                            if msg.startswith("show"):
                                logger.info("Switching to normal window via IPC")
                                display_config.set_fullscreen(False)
                                window.showNormal()

                        if msg.startswith("open:"):
                            launch_path = msg[5:].strip()
                            if launch_path and is_launch_file(launch_path):
                                logger.info("Opening launch file via IPC: %s", launch_path)
                                window.handle_launch_exe(launch_path)
                            else:
                                logger.warning("Invalid launch file via IPC: %s", launch_path)
                        elif msg.startswith("restore:"):
                            backup_path = unquote(msg[8:].strip())
                            if backup_path and is_prefix_backup_file(backup_path):
                                logger.info("Restoring prefix backup via IPC: %s", backup_path)
                                window._perform_restore(backup_path)
                            else:
                                logger.warning("Invalid prefix backup via IPC: %s", backup_path)
                        elif msg.startswith("backup:"):
                            parts = msg.split(":", 2)
                            if len(parts) == 3:
                                prefix_name = unquote(parts[1])
                                backup_dir = unquote(parts[2])
                                logger.info("Creating prefix backup via IPC: %s", prefix_name)
                                window._perform_backup(backup_dir, prefix_name)
                            else:
                                logger.warning("Invalid prefix backup request via IPC: %s", msg)
                except Exception as e:
                    logger.warning(f"Failed to restore window: {e}")

            # Execute in the main thread
            QTimer.singleShot(0, restore_window)

        conn.disconnectFromServer()

    local_server.newConnection.connect(handle_new_connection)

    # --- Initial fullscreen state ---
    launch_fullscreen = args.fullscreen or display_config.get_fullscreen()
    launch_auto_fullscreen = (
        display_config.get_auto_fullscreen_gamepad()
        and not launch_fullscreen
        and getattr(window.input_manager, "gamepad", None) is not None
    )
    launch_minimized = (
        display_config.get_start_minimized()
        and not args.fullscreen
        and not launch_auto_fullscreen
        and window_resolution is None
        and exe_path is None
        and backup_request is None
        and restore_prefix_path is None
    )
    if launch_minimized:
        logger.info("Launching in tray")
        window.hide()
    elif launch_fullscreen:
        logger.info(
            f"Launching in fullscreen mode ({'--fullscreen' if args.fullscreen else 'config'})"
        )
        display_config.set_fullscreen(True)
        window.showFullScreen()
    elif launch_auto_fullscreen:
        logger.info("Launching in fullscreen mode (gamepad)")
        window.input_manager.handle_fullscreen_slot(True)
        window.updateControlHints("force")
    elif window_resolution:
        logger.info(f"Launching with resolution: {window_resolution[0]}x{window_resolution[1]}")
        window.resize(window_resolution[0], window_resolution[1])
        window.showNormal()
    else:
        logger.info("Launching in normal mode")
        display_config.set_fullscreen(False)
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
                wine_dpi_value = "96"
                # Get screen information before running the initial command
                from portprotonqt.config import get_portproton_location
                portproton_path = get_portproton_location()

                if portproton_path:
                    screen_resolution, screen_primary = get_screen_info()

                    if screen_resolution and '=' in screen_resolution:
                        var_name, var_value = screen_resolution.split('=', 1)
                        if var_value:
                            set_user_conf_setting(var_name, var_value)
                            wine_dpi_value = get_system_dpi_for_wine()

                    if screen_primary and '=' in screen_primary:
                        var_name, var_value = screen_primary.split('=', 1)
                        if var_value:
                            set_user_conf_setting(var_name, var_value)

                set_user_conf_setting("PW_WINE_DPI_VALUE", wine_dpi_value)

                current_gpu_use = get_user_conf_setting("PW_GPU_USE")
                selectable_gpu_entries = get_selectable_gpu_entries()
                if len(selectable_gpu_entries) > 1:
                    selected_entry = None
                    for entry in selectable_gpu_entries:
                        if entry["device_name"] == current_gpu_use:
                            selected_entry = entry
                            break
                    if selected_entry is None:
                        selected_entry = selectable_gpu_entries[0]
                    if selected_entry is not None:
                        selected_gpu = selected_entry["device_name"]
                        if set_user_conf_setting("PW_GPU_USE", selected_gpu):
                            logger.info("Set PW_GPU_USE in user.conf via vk_gpu_info: %s", selected_gpu)
                        if selected_entry["vendor_id"]:
                            set_user_conf_setting("PW_vendorID", selected_entry["vendor_id"])
                        if selected_entry["device_id"]:
                            set_user_conf_setting("PW_deviceID", selected_entry["device_id"])
                elif current_gpu_use and current_gpu_use != "disabled":
                    set_user_conf_setting("PW_GPU_USE", None)
                    set_user_conf_setting("PW_vendorID", None)
                    set_user_conf_setting("PW_deviceID", None)

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
