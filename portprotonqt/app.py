import sys

from portprotonqt.main_window import MainWindow
from PySide6 import QtWidgets


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
