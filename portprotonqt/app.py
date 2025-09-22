import sys
from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from portprotonqt.main_window import MainWindow
from portprotonqt.config_utils import save_fullscreen_config
from portprotonqt.logger import get_logger, setup_logger
from portprotonqt.cli import parse_args

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"
__app_version__ = "0.1.5"

def main():
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

    window = MainWindow(app_name=__app_name__)

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
