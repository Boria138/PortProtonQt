import sys
from PySide6 import QtWidgets
from portprotonqt.main_window import MainWindow
from portprotonqt.styles import load_custom_fonts

def main():
    app = QtWidgets.QApplication(sys.argv)
    load_custom_fonts()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
