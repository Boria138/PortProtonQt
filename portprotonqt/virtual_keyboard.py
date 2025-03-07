from PySide6 import QtWidgets, QtCore
import portprotonqt.themes.standart_lite.styles as default_styles

class VirtualKeyboard(QtWidgets.QWidget):
    def __init__(self, parent=None, target_widget=None, theme=None):
        super().__init__(parent)
        self.theme = theme if theme is not None else default_styles
        self.target_widget = target_widget  # куда отправлять вводимые символы
        self.current_layout = "EN"  # "EN" или "RU"
        self.dragging = False
        self.drag_start_pos = QtCore.QPoint()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(800, 300)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(40)
        self.header.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_HEADER_STYLE)
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_label = QtWidgets.QLabel("Виртуальная клавиатура")
        header_label.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_HEADER_LABEL_STYLE)
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        main_layout.addWidget(self.header)
        self.header.installEventFilter(self)

        self.keyboard_area = QtWidgets.QWidget()
        self.keyboard_area.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_AREA_STYLE)
        main_layout.addWidget(self.keyboard_area)

        self.keys_layout = QtWidgets.QVBoxLayout(self.keyboard_area)
        self.keys_layout.setSpacing(10)
        self.keys_layout.setContentsMargins(20, 20, 20, 20)

        self.createKeys()

    def getLayouts(self):
        return {
            "EN": [
                ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
                ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
                ["Z", "X", "C", "V", "B", "N", "M"],
                ["Toggle", "Space", "Backspace", "Enter"]
            ],
            "RU": [
                ["Й", "Ц", "У", "К", "Е", "Н", "Г", "Ш", "Щ", "З"],
                ["Ф", "Ы", "В", "А", "П", "Р", "О", "Л", "Д", "Ж"],
                ["Я", "Ч", "С", "М", "И", "Т", "Ь"],
                ["Toggle", "Space", "Backspace", "Enter"]
            ]
        }

    def createKeys(self):
        while self.keys_layout.count():
            child = self.keys_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        layouts = self.getLayouts()[self.current_layout]
        for row_keys in layouts:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(10)
            for key in row_keys:
                btn = QtWidgets.QPushButton(key)
                btn.setMinimumHeight(60)
                btn.setMinimumWidth(60)
                btn.setStyleSheet(self.theme.VIRTUAL_KEYBORD_AREA_KEYS_STYLE)
                btn.clicked.connect(lambda checked, k=key: self.handleKey(k))
                row.addWidget(btn)
            self.keys_layout.addLayout(row)

    def handleKey(self, key):
        if key == "Toggle":
            self.current_layout = "RU" if self.current_layout == "EN" else "EN"
            self.createKeys()
        elif key == "Space":
            self.insertText(" ")
        elif key == "Backspace":
            self.deleteText()
        elif key == "Enter":
            self.insertText("\n")
        else:
            self.insertText(key)

    def insertText(self, text):
        widget = self.target_widget or QtWidgets.QApplication.focusWidget()
        if widget and isinstance(widget, QtWidgets.QLineEdit):
            widget.insert(text)
        elif widget and isinstance(widget, QtWidgets.QTextEdit):
            widget.insertPlainText(text)

    def deleteText(self):
        widget = self.target_widget or QtWidgets.QApplication.focusWidget()
        if widget and isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(widget.text()[:-1])
        elif widget and isinstance(widget, QtWidgets.QTextEdit):
            cursor = widget.textCursor()
            if cursor.position() > 0:
                cursor.deletePreviousChar()
                widget.setTextCursor(cursor)

    def eventFilter(self, obj, event):
        if obj == self.header:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton:
                    self.dragging = True
                    self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif event.type() == QtCore.QEvent.MouseMove:
                if self.dragging:
                    self.move(event.globalPosition().toPoint() - self.drag_start_pos)
                    return True
            elif event.type() == QtCore.QEvent.MouseButtonRelease:
                self.dragging = False
                return True
        return super().eventFilter(obj, event)
