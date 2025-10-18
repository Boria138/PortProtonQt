import sys
import os
import subprocess
from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from portprotonqt.main_window import MainWindow
from portprotonqt.config_utils import save_fullscreen_config, get_portproton_location
from portprotonqt.logger import get_logger, setup_logger
from portprotonqt.cli import parse_args

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"
__app_version__ = "0.1.8"

def get_version():
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        return f"{__app_version__} ({commit})"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return __app_version__

def main():
    os.environ['PW_CLI'] = '1'
    os.environ['PROCESS_LOG'] = '1'
    os.environ['START_FROM_STEAM'] = '1'

    portproton_path = get_portproton_location()

    if portproton_path is None:
        return

    script_path = os.path.join(portproton_path, 'data', 'scripts', 'start.sh')
    subprocess.run([script_path, 'cli', '--initial'])

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme(__app_id__))
    app.setDesktopFileName(__app_id__)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__app_version__)

    args = parse_args()

    # Setup logger with specified debug level
    setup_logger(args.debug_level)

    # Reinitialize logger after setup to ensure it uses the new configuration
    logger = get_logger(__name__)

    system_locale = QLocale.system()
    qt_translator = QTranslator()
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(system_locale, "qtbase", "_", translations_path):
        app.installTranslator(qt_translator)
    else:
        logger.warning(f"Qt translations for {system_locale.name()} not found in {translations_path}, using english language")

    version = get_version()
    window = MainWindow(app_name=__app_name__, version=version)

    if args.fullscreen:
        logger.info("Launching in fullscreen mode due to --fullscreen flag")
        save_fullscreen_config(True)
        window.showFullScreen()

    def cleanup_on_exit():
        nonlocal window
        app.aboutToQuit.disconnect()
        if window:
            window.close()
        app.quit()

    app.aboutToQuit.connect(cleanup_on_exit)

    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
