import sys
from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from portprotonqt.main_window import MainWindow
from portprotonqt.tray import SystemTray
from portprotonqt.config_utils import read_theme_from_config, save_fullscreen_config
from portprotonqt.logger import get_logger
from portprotonqt.cli import parse_args

logger = get_logger(__name__)

__app_id__ = "ru.linux_gaming.PortProtonQt"
__app_name__ = "PortProtonQt"
__app_version__ = "0.1.3"

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme(__app_id__))
    app.setDesktopFileName(__app_id__)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__app_version__)

    system_locale = QLocale.system()
    qt_translator = QTranslator()
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(system_locale, "qtbase", "_", translations_path):
        app.installTranslator(qt_translator)
    else:
        logger.error(f"Qt translations for {system_locale.name()} not found in {translations_path}")

    args = parse_args()

    window = MainWindow()

    if args.fullscreen:
        logger.info("Launching in fullscreen mode due to --fullscreen flag")
        save_fullscreen_config(True)
        window.showFullScreen()

    current_theme_name = read_theme_from_config()
    tray = SystemTray(app, current_theme_name)
    tray.show_action.triggered.connect(window.show)
    tray.hide_action.triggered.connect(window.hide)

    def recreate_tray():
        nonlocal tray
        if tray:
            logger.debug("Recreating system tray")
            tray.cleanup()
            tray = None
        current_theme = read_theme_from_config()
        tray = SystemTray(app, current_theme)
        # Ensure window is not None before connecting signals
        if window:
            tray.show_action.triggered.connect(window.show)
            tray.hide_action.triggered.connect(window.hide)

    def cleanup_on_exit():
        nonlocal tray, window
        app.aboutToQuit.disconnect()
        if tray:
            tray.cleanup()
            tray = None
        if window:
            window.close()
        app.quit()

    window.settings_saved.connect(recreate_tray)
    app.aboutToQuit.connect(cleanup_on_exit)

    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
