import time
import re
import math

from PySide6.QtCore import QRect, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, Qt, QColor, QConicalGradient, QPainterPath,
)
from PySide6.QtWidgets import QWidget
from portprotonqt.config import ui_config
from portprotonqt.theme_manager import ThemeManager, load_theme

PRELOADER_DEFAULT = {
    "style": "default",
    "speed": 180.0,
    "line_width": 20,
    "bat_size": 80,
    "bat_flap_speed": 3.0,
    "bat_alpha": 220,
    "bat_color": "#bd93f9",
    "bat_eye_color": "#282a36",
    "bat_fang_color": "#f8f8f2",
    "pulse_count": 3,
    "pulse_max_radius": 40,
    "pulse_speed": 2.0,
    "pulse_color": "#bd93f9",
    "dots_count": 8,
    "dots_radius": 38,
    "dots_dot_size": 5,
    "dots_speed": 3.0,
    "dots_color": "#bd93f9",
    "wave_width": 80,
    "wave_amplitude": 15,
    "wave_speed": 3.0,
    "wave_line_width": 3,
    "wave_color": "#bd93f9",
}


def _load_preloader_config() -> dict:
    theme_manager = ThemeManager()
    theme = theme_manager.current_theme_module
    if theme is None:
        try:
            theme = load_theme(ui_config.get_theme())
        except FileNotFoundError:
            theme = load_theme("standart")
    return PRELOADER_DEFAULT | getattr(theme, "PRELOADER", {})


class Preloader(QWidget):
    def __init__(self, speed=180.0, line_line_width=20, color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self._config = _load_preloader_config()
        self._style = self._config.get("style", "default")
        self._speed = self._config.get("speed", speed)
        self._line_width = self._config.get("line_width", line_line_width)
        self._color1 = self._resolve_color(color)
        self._color2 = QColor(self._color1.red(), self._color1.green(), self._color1.blue(), 0)
        self._start_time = time.time()
        self._pulse_start = time.time()
        self._bat_color = QColor(self._config.get("bat_color", str(self._color1.name())))

    def showEvent(self, event):
        self._start_time = time.time()
        self._pulse_start = time.time()

    def paintEvent(self, event):
        style = self._style
        if style == "bat":
            self._paint_bat()
        elif style == "pulse":
            self._paint_pulse()
        elif style == "dots":
            self._paint_dots()
        elif style == "wave":
            self._paint_wave()
        else:
            self._paint_default()
        self.update()

    def _paint_default(self):
        rect = self._get_preloader_rect()
        center = rect.center()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self._get_pen())
        painter.translate(center)
        painter.rotate(self._get_angle())
        painter.translate(-center)
        painter.drawArc(rect, 0, 270 * 16)

    def _paint_bat(self):
        speed = self._config.get("bat_flap_speed", 3.0)
        t = time.time() - self._pulse_start
        flap = math.sin(t * speed)
        bob = math.sin(t * speed * 0.6) * 4
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2 + bob)
        painter.translate(center)
        size = self._config.get("bat_size", 80)
        alpha = self._config.get("bat_alpha", 220)
        self._draw_bat(painter, size, alpha, flap)

    def _paint_pulse(self):
        t = time.time() - self._pulse_start
        speed = self._config.get("pulse_speed", 2.0)
        count = self._config.get("pulse_count", 3)
        max_r = self._config.get("pulse_max_radius", 40)
        color = QColor(self._config.get("pulse_color", str(self._color1.name())))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        cx = self.width() / 2
        cy = self.height() / 2

        for i in range(count):
            phase = (t * speed + i / count) % 1.0
            r = max_r * phase
            alpha = int(200 * (1 - phase))
            c = QColor(color)
            c.setAlpha(alpha)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(QPointF(cx, cy), r, r)

        center_alpha = int(180 + 40 * math.sin(t * speed * 2))
        cc = QColor(color)
        cc.setAlpha(center_alpha)
        painter.setBrush(QBrush(cc))
        painter.drawEllipse(QPointF(cx, cy), 6, 6)

    def _paint_dots(self):
        t = time.time() - self._pulse_start
        speed = self._config.get("dots_speed", 3.0)
        count = self._config.get("dots_count", 8)
        radius = self._config.get("dots_radius", 38)
        dot_size = self._config.get("dots_dot_size", 5)
        color = QColor(self._config.get("dots_color", str(self._color1.name())))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        cx = self.width() / 2
        cy = self.height() / 2

        for i in range(count):
            angle = 2 * math.pi * i / count + t * speed
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            phase = (math.sin(t * speed * 2 + i * 0.8) + 1) / 2
            s = dot_size * (0.5 + phase * 0.5)
            alpha = int(100 + 155 * phase)
            c = QColor(color)
            c.setAlpha(alpha)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(QPointF(x, y), s, s)

    def _paint_wave(self):
        t = time.time() - self._pulse_start
        speed = self._config.get("wave_speed", 3.0)
        w = self._config.get("wave_width", 80)
        amp = self._config.get("wave_amplitude", 15)
        lw = self._config.get("wave_line_width", 3)
        color = QColor(self._config.get("wave_color", str(self._color1.name())))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2
        cy = self.height() / 2
        steps = 40

        for wave_idx in range(3):
            wave_offset = wave_idx * 0.7
            wave_alpha = int(200 - wave_idx * 50)
            c = QColor(color)
            c.setAlpha(wave_alpha)
            pen = QPen(QBrush(c), lw)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            path = QPainterPath()
            for j in range(steps + 1):
                frac = j / steps
                x = cx - w / 2 + w * frac
                y = cy + amp * math.sin(frac * 4 * math.pi + t * speed + wave_offset)
                if j == 0:
                    path.moveTo(QPointF(x, y))
                else:
                    path.lineTo(QPointF(x, y))
            painter.drawPath(path)

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

    def _draw_bat(self, painter: QPainter, size: float, alpha: int, flap: float):
        color = QColor(self._bat_color)
        color.setAlpha(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))

        body_h = size * 0.22
        body_w = size * 0.1
        painter.drawEllipse(QPointF(0, 0), body_w, body_h)

        head_r = size * 0.1
        head_y = -body_h * 0.9
        painter.drawEllipse(QPointF(0, head_y), head_r, head_r * 0.85)

        ear_h = size * 0.12
        ear_w = size * 0.045
        for side in (-1, 1):
            path = QPainterPath()
            ex = side * head_r * 0.55
            path.moveTo(ex - side * ear_w * 0.4, head_y - head_r * 0.6)
            path.lineTo(ex, head_y - head_r * 0.5 - ear_h)
            path.lineTo(ex + side * ear_w * 0.4, head_y - head_r * 0.6)
            path.closeSubpath()
            painter.drawPath(path)

        eye_r = size * 0.018
        blink = max(0.1, abs(math.sin((time.time() - self._pulse_start) * 0.4)))
        painter.setBrush(QBrush(QColor(self._config["bat_eye_color"])))
        for side in (-1, 1):
            painter.drawEllipse(
                QPointF(side * head_r * 0.35, head_y),
                eye_r, eye_r * blink
            )

        fang_len = size * 0.07
        fang_w = size * 0.015
        painter.setBrush(QBrush(QColor(self._config["bat_fang_color"])))
        for side in (-1, 1):
            path = QPainterPath()
            fx = side * head_r * 0.18
            fy = head_y + head_r * 0.55
            path.moveTo(fx - fang_w, fy)
            path.lineTo(fx, fy + fang_len)
            path.lineTo(fx + fang_w, fy)
            path.closeSubpath()
            painter.drawPath(path)

        painter.setBrush(QBrush(color))
        wing_span = size * 0.48
        wing_base_y = -body_h * 0.1
        wing_tip_y_up = -size * (0.28 + flap * 0.18)
        wing_tip_y_down = size * 0.08
        scallop_y = size * 0.12

        for side in (-1, 1):
            path = QPainterPath()
            wx = side * body_w * 0.8
            path.moveTo(wx, wing_base_y)
            path.lineTo(wx + side * wing_span * 0.15, wing_tip_y_up * 0.9)
            path.lineTo(wx + side * wing_span * 0.45, wing_tip_y_up)
            path.lineTo(wx + side * wing_span * 0.75, wing_tip_y_up * 0.5)
            path.lineTo(wx + side * wing_span, wing_tip_y_down)
            path.lineTo(wx + side * wing_span * 0.78, scallop_y)
            path.lineTo(wx + side * wing_span * 0.55, wing_tip_y_down * 0.3)
            path.lineTo(wx + side * wing_span * 0.35, scallop_y * 0.8)
            path.lineTo(wx + side * wing_span * 0.15, wing_tip_y_down * 0.5)
            path.lineTo(wx, wing_base_y + body_h * 0.3)
            path.closeSubpath()
            painter.drawPath(path)

        tail_y = body_h * 0.8
        tail_len = size * 0.06
        painter.setBrush(QBrush(color))
        path = QPainterPath()
        path.moveTo(-body_w * 0.4, tail_y)
        path.lineTo(0, tail_y + tail_len)
        path.lineTo(body_w * 0.4, tail_y)
        path.closeSubpath()
        painter.drawPath(path)

    def _resolve_color(self, color):
        if isinstance(color, QColor) and color.isValid():
            return color
        if isinstance(color, str):
            parsed = self._parse_color_string(color)
            if parsed.isValid():
                return parsed

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
        return QColor(load_theme("standart").color_preloader)

    def _parse_color_string(self, value):
        if isinstance(value, QColor):
            return value

        color_str = str(value).strip()
        rgba_match = re.match(
            r"^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$",
            color_str
        )
        if rgba_match:
            red = int(rgba_match.group(1))
            green = int(rgba_match.group(2))
            blue = int(rgba_match.group(3))
            alpha_value = float(rgba_match.group(4))
            alpha = int(alpha_value * 255) if alpha_value <= 1 else int(alpha_value)
            alpha = max(0, min(255, alpha))
            return QColor(red, green, blue, alpha)

        rgb_match = re.match(
            r"^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$",
            color_str
        )
        if rgb_match:
            return QColor(
                int(rgb_match.group(1)),
                int(rgb_match.group(2)),
                int(rgb_match.group(3))
            )

        return QColor(color_str)
