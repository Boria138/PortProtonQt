import sys

from portprotonqt.main_window import MainWindow
from PySide6 import QtWidgets
from portprotonqt.tray import SystemTray
from portprotonqt.config_utils import read_theme_from_config

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    current_theme_name = read_theme_from_config()
    tray = SystemTray(app, current_theme_name)
    tray.show_action.triggered.connect(window.show)
    tray.hide_action.triggered.connect(window.hide)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
