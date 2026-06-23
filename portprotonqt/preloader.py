import time
import re

from PySide6.QtCore import QRect
from PySide6.QtGui import QPainter, QPen, QBrush, Qt, QColor, QConicalGradient
from PySide6.QtWidgets import QWidget
from portprotonqt.config import ui_config
from portprotonqt.theme_manager import ThemeManager, load_theme

class Preloader(QWidget):
    def __init__(self, speed=180.0, line_line_width=20, color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self._speed = speed
        self._line_width = line_line_width
        self._color1 = self._resolve_color(color)
        self._color2 = QColor(self._color1.red(), self._color1.green(), self._color1.blue(), 0)
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

    def _resolve_color(self, color):
        if isinstance(color, QColor) and color.isValid():
            return color
        if isinstance(color, str):
            parsed = self._parse_color_string(color)
            if parsed.isValid():
                return parsed

        fallback = QColor(0, 120, 215)
        theme_manager = ThemeManager()
        theme = theme_manager.current_theme_module
        if theme is None:
            try:
                theme = load_theme(ui_config.get_theme())
            except FileNotFoundError:
                theme = load_theme("standart")

        for attr_name in ("color_preloader", "color_accent_blue", "color_accent"):
            if not hasattr(theme, attr_name):
                continue
            parsed = self._parse_color_string(getattr(theme, attr_name))
            if parsed.isValid():
                return parsed
        return fallback

    def _parse_color_string(self, value):
        if isinstance(value, QColor):
            return value

        color_str = str(value).strip()
        rgba_match = re.match(r"^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$", color_str)
        if rgba_match:
            red = int(rgba_match.group(1))
            green = int(rgba_match.group(2))
            blue = int(rgba_match.group(3))
            alpha_value = float(rgba_match.group(4))
            alpha = int(alpha_value * 255) if alpha_value <= 1 else int(alpha_value)
            alpha = max(0, min(255, alpha))
            return QColor(red, green, blue, alpha)

        rgb_match = re.match(r"^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", color_str)
        if rgb_match:
            return QColor(int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))

        return QColor(color_str)
