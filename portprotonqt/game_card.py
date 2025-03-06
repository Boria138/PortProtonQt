from PySide6 import QtWidgets, QtCore, QtGui
from portprotonqt.image_utils import load_pixmap, round_corners
import portprotonqt.styles as default_styles

class GameCard(QtWidgets.QFrame):
    def __init__(self, name, description, cover_path, appid, exec_line, select_callback, theme=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.description = description
        self.cover_path = cover_path
        self.appid = appid
        self.exec_line = exec_line
        self.select_callback = select_callback

        # Используем переданную тему или стандартную
        self.theme = theme if theme is not None else default_styles

        self.setFixedSize(250, 400)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.setStyleSheet(self.theme.GAME_CARD_WINDOW_STYLE)

        # Анимация обводки
        self._borderWidth = 1
        self._gradientAngle = 0.0
        self._hovered = False

        self.thickness_anim = QtCore.QPropertyAnimation(self, b"borderWidth")
        self.thickness_anim.setDuration(300)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        coverLabel = QtWidgets.QLabel()
        coverLabel.setFixedSize(250, 300)
        pixmap = load_pixmap(cover_path, 250, 300) if cover_path else load_pixmap("", 250, 300)
        pixmap = round_corners(pixmap, 15)
        coverLabel.setPixmap(pixmap)
        coverLabel.setStyleSheet(self.theme.COVER_LABEL_STYLE)
        layout.addWidget(coverLabel)

        nameLabel = QtWidgets.QLabel(name)
        nameLabel.setAlignment(QtCore.Qt.AlignCenter)
        nameLabel.setStyleSheet(self.theme.GAME_CARD_NAME_LABEL_STYLE)
        layout.addWidget(nameLabel)

    def getBorderWidth(self):
        return self._borderWidth

    def setBorderWidth(self, value):
        self._borderWidth = value
        self.update()

    borderWidth = QtCore.Property(int, getBorderWidth, setBorderWidth)

    def getGradientAngle(self):
        return self._gradientAngle

    def setGradientAngle(self, value):
        self._gradientAngle = value
        self.update()

    gradientAngle = QtCore.Property(float, getGradientAngle, setGradientAngle)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen()
        pen.setWidth(self._borderWidth)
        if self._hovered:
            center = self.rect().center()
            gradient = QtGui.QConicalGradient(center, self._gradientAngle)
            gradient.setColorAt(0, QtGui.QColor("#00fff5"))
            gradient.setColorAt(0.5, QtGui.QColor("#9B59B6"))
            gradient.setColorAt(1, QtGui.QColor("#00fff5"))
            pen.setBrush(QtGui.QBrush(gradient))
        else:
            pen.setColor(QtGui.QColor(0, 0, 0, 0))
        painter.setPen(pen)
        rect = self.rect().adjusted(self._borderWidth / 2, self._borderWidth / 2,
                                    -self._borderWidth / 2, -self._borderWidth / 2)
        painter.drawRoundedRect(rect, 15, 15)

    def enterEvent(self, event):
        self._hovered = True
        self.thickness_anim.stop()
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(4)
        self.thickness_anim.start()
        self.gradient_anim = QtCore.QPropertyAnimation(self, b"gradientAngle")
        self.gradient_anim.setDuration(3000)
        self.gradient_anim.setStartValue(0)
        self.gradient_anim.setEndValue(360)
        self.gradient_anim.setLoopCount(-1)
        self.gradient_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        if hasattr(self, "gradient_anim"):
            self.gradient_anim.stop()
            del self.gradient_anim
        self.thickness_anim.stop()
        self.thickness_anim.setStartValue(self._borderWidth)
        self.thickness_anim.setEndValue(1)
        self.thickness_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.select_callback(self.name, self.description, self.cover_path, self.appid, self.exec_line)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.select_callback(self.name, self.description, self.cover_path, self.appid, self.exec_line)
        else:
            super().keyPressEvent(event)
