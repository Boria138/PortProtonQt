import sys
from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication
from portprotonqt.main_window import MainWindow
from portprotonqt.tray import SystemTray
from portprotonqt.config_utils import read_theme_from_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

def main():
    app = QApplication(sys.argv)
    system_locale = QLocale.system()
    qt_translator = QTranslator()
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(system_locale, "qtbase", "_", translations_path):
        app.installTranslator(qt_translator)
    else:
        logger.error(f"Qt translations for {system_locale.name()} not found in {translations_path}")

    window = MainWindow()
    current_theme_name = read_theme_from_config()
    tray = SystemTray(app, current_theme_name)
    tray.show_action.triggered.connect(window.show)
    tray.hide_action.triggered.connect(window.hide)
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
