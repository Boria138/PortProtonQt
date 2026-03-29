import time

from PySide6.QtCore import QRect
from PySide6.QtGui import QPainter, QPen, QBrush, Qt, QColor, QConicalGradient
from PySide6.QtWidgets import QWidget

class Preloader(QWidget):
    def __init__(self, speed=180.0, line_line_width=20, color=QColor(0, 120, 215), parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self._speed = speed
        self._line_width = line_line_width
        self._color1 = color
        self._color2 = QColor(color.red(), color.green(), color.blue(), 0)
        self._start_time = time.time()

    def showEvent(self, event):
        self._start_time = time.time()

    def paintEvent(self, event):
        rect = self._get_preloader_rect()
        center = rect.center()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self._get_pen())
        painter.translate(center)
        painter.rotate(self._get_angle())
        painter.translate(-center)
        painter.drawArc(rect, 0, 270 * 16)
        self.update()

    def _get_pen(self) -> QPen:
        gradient = QConicalGradient()
        gradient.setCenter(self.rect().center())
        gradient.setColorAt(0, self._color1)
        gradient.setColorAt(1, self._color2)
        pen = QPen(QBrush(gradient), self._line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def _get_angle(self) -> float:
        duration = time.time() - self._start_time
        return (self._speed * duration) % 360.0

    def _get_preloader_rect(self) -> QRect:
        size = self._line_width // 2
        rect = self.rect()
        rect.adjust(size, size, -size, -size)
        return rect
