import sys
import os
import subprocess
import shutil
from logging import Logger

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"
__app_version__ = "0.1.12"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PySide6.QtGui import QAction, QIcon

from portprotonqt.config import (
    display_config,
    get_portproton_start_command,
    get_portproton_location,
    save_portdata_path_to_config,
    ui_config,
    window_config,
)
from portprotonqt.logger import get_logger, setup_logger
from portprotonqt.cli import (
    parse_args,
    is_portproton_url,
    parse_portproton_url,
    is_launch_file,
    is_exe_file,
    normalize_launch_path,
    add_steam_compat_tool,
    reinstall_steam_compat_tool,
    remove_steam_compat_tool,
    parse_resolution,
)
from portprotonqt.localization import _, get_steam_language

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

    icon = ThemeManager().get_icon("badge_portproton", ui_config.get_theme())
    if isinstance(icon, QIcon):
        return icon
    return QIcon()


def run_silent_tray(app: QApplication, start_sh: list[str], exe_path: str) -> None:
    """Launch a game with a minimal tray stop action."""
    logger = get_logger(__name__)
    app.setQuitOnLastWindowClosed(False)
    tray_icon = QSystemTrayIcon(get_portproton_tray_icon(), app)
    tray_icon.setToolTip(__app_name__)

    process = subprocess.Popen(
        start_sh + [exe_path],
        env=os.environ.copy(),
        shell=False,
    )
    tray_menu = QMenu()

    def stop_game() -> None:
        monitor_timer.stop()
        stop_portproton_game(start_sh, logger)
        tray_icon.hide()
        app.quit()

    def close_when_game_exits(_tray_menu: QMenu = tray_menu) -> None:
        if process.poll() is None:
            return
        monitor_timer.stop()
        tray_icon.hide()
        app.quit()

    stop_action = QAction(_("Stop Game"), tray_menu)
    stop_action.triggered.connect(stop_game)
    tray_menu.addAction(stop_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    monitor_timer = QTimer(app)
    monitor_timer.timeout.connect(close_when_game_exits)
    monitor_timer.start(1000)


def main():
    # Parse args early to check for force-muvm flag
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

    # Check if running on Apple Silicon/Asahi Linux or if forced to run under muvm, and re-execute under muvm if needed
    should_run_under_muvm = (is_apple_silicon() or parsed_args.force_muvm) and 'PORTPROTONQT_MUVM' not in os.environ
    if should_run_under_muvm:
        muvm_path = shutil.which('muvm')
        if muvm_path:
            env = os.environ.copy()
            args_list = [muvm_path, "-i", "-e", "PORTPROTONQT_MUVM=1", sys.executable, os.path.abspath(__file__)]
            os.execvpe(muvm_path, args_list + sys.argv[1:], env)

    os.environ["FULL_LN"] = get_steam_language()
    portproton_location = get_portproton_location()
    if portproton_location:
        os.environ["PORT_DATA_PATH"] = portproton_location

    # Check if running as Steam compatibility tool (STEAM_COMPAT=1).
    is_steam_compat = os.environ.get("STEAM_COMPAT") == "1"
    is_silent_launch = parsed_args.silent

    # Get the PortProton start command
    start_sh = get_portproton_start_command()

    if start_sh is None:
        return

    # Handle Steam compatibility mode - launch game directly without GUI.
    if is_steam_compat:
        exe_path = parsed_args.file_or_url if parsed_args.file_or_url else None
        can_launch_without_gui = bool(exe_path and is_launch_file(exe_path))

        if can_launch_without_gui and isinstance(exe_path, str):
            exe_path = normalize_launch_path(exe_path)
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

    fullscreen = args.fullscreen or display_config.get_fullscreen()
    ipc_message = "show:fullscreen" if fullscreen else "show"
    resolution_from_args = None
    if args.resolution:
        resolution_from_args = parse_resolution(args.resolution)
        if resolution_from_args is None:
            logger.warning(f"Invalid resolution format: {args.resolution}, expected WIDTHxHEIGHT (e.g., 1920x1080)")
        else:
            window_config.set_geometry(resolution_from_args[0], resolution_from_args[1])
            logger.info("Saved window resolution: %sx%s", resolution_from_args[0], resolution_from_args[1])
            ipc_message = "noop"
    if is_silent_launch and args.file_or_url and is_exe_file(args.file_or_url):
        run_silent_tray(app, start_sh, normalize_launch_path(args.file_or_url))
        sys.exit(app.exec())
    elif args.file_or_url and is_launch_file(args.file_or_url):
        ipc_message = f"open:{normalize_launch_path(args.file_or_url)}"

    from PySide6.QtCore import QThread, Signal
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from portprotonqt.main_window import MainWindow
    from portprotonqt.port_data_path_selector import ask_portdata_path
    from portprotonqt.portproton_api import (
        PortProtonAPI,
        get_user_conf_setting,
        set_user_conf_setting,
    )
    from portprotonqt.downloader import Downloader
    from portprotonqt.debug_utils import (
        get_screen_info,
        get_selectable_gpu_entries,
        get_system_dpi_for_wine,
    )

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

    if not portproton_location:
        portproton_location = ask_portdata_path()
        if not portproton_location:
            logger.error("PORT_DATA_PATH is not configured, startup aborted")
            return
        os.environ["PORT_DATA_PATH"] = portproton_location
        if not save_portdata_path_to_config(portproton_location):
            logger.warning("Failed to persist PORT_DATA_PATH in PortProtonQt config")

    # Check if we have a portproton:// URL or launch file to handle
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
                    if msg.startswith("show") or msg.startswith("open:"):
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
                except Exception as e:
                    logger.warning(f"Failed to restore window: {e}")

            # Execute in the main thread
            QTimer.singleShot(0, restore_window)

        conn.disconnectFromServer()

    local_server.newConnection.connect(handle_new_connection)

    # --- Initial fullscreen state ---
    launch_fullscreen = args.fullscreen or display_config.get_fullscreen()
    launch_minimized = (
        (
            display_config.get_start_minimized()
            and window_resolution is None
        )
        or resolution_from_args is not None
    ) and not args.fullscreen and exe_path is None
    if launch_minimized:
        logger.info("Launching in tray")
        window.hide()
    elif launch_fullscreen:
        logger.info(
            f"Launching in fullscreen mode ({'--fullscreen' if args.fullscreen else 'config'})"
        )
        display_config.set_fullscreen(True)
        window.showFullScreen()
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
                    screen_resolution, screen_primary = get_screen_info(portproton_path)

                    if screen_resolution and '=' in screen_resolution:
                        var_name, var_value = screen_resolution.split('=', 1)
                        if var_value:
                            set_user_conf_setting(var_name, var_value)
                            wine_dpi_value = get_system_dpi_for_wine(var_value)

                    if screen_primary and '=' in screen_primary:
                        var_name, var_value = screen_primary.split('=', 1)
                        if var_value:
                            set_user_conf_setting(var_name, var_value)

                set_user_conf_setting("PW_WINE_DPI_VALUE", wine_dpi_value)

                current_gpu_use = get_user_conf_setting("PW_GPU_USE")
                selectable_gpu_entries = get_selectable_gpu_entries()
                if selectable_gpu_entries:
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
