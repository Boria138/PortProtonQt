"""Procedural detail page backgrounds adapted from omikuji."""

import math
from weakref import WeakKeyDictionary

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class DetailBackgroundAnimations:
    """Manage animated and static omikuji detail backgrounds."""

    effects = frozenset({"aurora", "diagnostics", "metaballs", "sakura", "veins"})

    def __init__(self) -> None:
        self._states: WeakKeyDictionary[QWidget, dict] = WeakKeyDictionary()

    def setup(self, page: QWidget, palette: list, theme) -> bool:
        """Setup an omikuji background and report whether its mode matched."""
        mode = getattr(theme, "DETAIL_PAGE_BG_MODE", "gradient")
        effect = mode.removeprefix("static_")
        if effect not in self.effects:
            self.remove(page)
            return False
        config = theme.DETAIL_PAGE_BACKGROUNDS
        self.remove(page)
        state = {
            "effect": effect,
            "palette": palette,
            "phase": 0.0,
            "config": config,
            "original_paint": page.paintEvent,
            "timer": None,
        }
        self._states[page] = state

        def paint_event(event) -> None:
            state["original_paint"](event)
            self._paint(page, state)

        page.paintEvent = paint_event
        if not mode.startswith("static_"):
            self._start_timer(page, state)
        return True

    def remove(self, page: QWidget) -> None:
        """Remove the omikuji background from a detail page."""
        state = self._states.pop(page, None)
        if state is None:
            return
        timer = state["timer"]
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        page.paintEvent = state["original_paint"]

    def _start_timer(self, page: QWidget, state: dict) -> None:
        config = state["config"]
        timer = QTimer(page)
        timer.setInterval(config["animation_interval_ms"])

        def tick() -> None:
            if page.isHidden() or page.parent() is None:
                timer.stop()
                return
            state["phase"] += config["animation_speed"]
            page.update()

        timer.timeout.connect(tick)
        timer.start()
        state["timer"] = timer

    def _paint(self, page: QWidget, state: dict) -> None:
        if not state["palette"]:
            return
        painter = QPainter(page)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(page.rect())
        painters = {
            "aurora": self._paint_aurora,
            "diagnostics": self._paint_diagnostics,
            "metaballs": self._paint_metaballs,
            "sakura": self._paint_sakura,
            "veins": self._paint_veins,
        }
        painters[state["effect"]](painter, rect, state)
        painter.end()

    def _paint_diagnostics(
        self, painter: QPainter, rect: QRectF, state: dict,
    ) -> None:
        config = state["config"]["diagnostics"]
        color = QColor(config["color"])
        grid_color = QColor(color)
        grid_color.setAlphaF(config["grid_opacity"])
        painter.setPen(QPen(grid_color, config["grid_line_width"]))
        spacing = config["grid_spacing"]
        for x in range(0, int(rect.width()), spacing):
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.height()))
        for y in range(0, int(rect.height()), spacing):
            painter.drawLine(QPointF(0, y), QPointF(rect.width(), y))

        trace_color = QColor(color)
        trace_color.setAlphaF(config["trace_opacity"])
        painter.setPen(QPen(trace_color, config["trace_line_width"]))
        trace = QPainterPath()
        steps = max(int(rect.width() / config["trace_step_width"]), 1)
        for step in range(steps + 1):
            progress = step / steps
            signal = math.sin(
                progress * config["trace_frequency"]
                + state["phase"] * config["trace_speed"]
            )
            point = QPointF(
                rect.width() * progress,
                rect.height() * (config["trace_baseline"] + signal * config["trace_amplitude"]),
            )
            trace.moveTo(point) if step == 0 else trace.lineTo(point)
        painter.drawPath(trace)
        self._paint_diagnostic_status(painter, rect, state)

    def _paint_diagnostic_status(
        self, painter: QPainter, rect: QRectF, state: dict,
    ) -> None:
        config = state["config"]["diagnostics"]
        color = QColor(config["color"])
        color.setAlphaF(config["text_opacity"])
        painter.setPen(color)
        font = QFont(config["font_family"])
        font.setPixelSize(config["font_size"])
        painter.setFont(font)
        x = rect.width() * config["text_x_ratio"]
        first_y = rect.height() * config["first_line_y_ratio"]
        second_y = rect.height() * config["second_line_y_ratio"]
        painter.drawText(QPointF(x, first_y), config["status_text"])
        painter.drawText(QPointF(x, second_y), config["containment_text"])
        sweep = (
            config["sweep_offset"] + state["phase"] * config["sweep_speed"]
        ) % 1
        sweep_color = QColor(color)
        sweep_color.setAlphaF(config["sweep_opacity"])
        painter.setPen(QPen(sweep_color, config["sweep_width"]))
        sweep_x = rect.width() * sweep
        painter.drawLine(QPointF(sweep_x, 0), QPointF(sweep_x, rect.height()))

    def _paint_aurora(self, painter: QPainter, rect: QRectF, state: dict) -> None:
        config = state["config"]["aurora"]
        color = QColor(state["palette"][-1])
        color.setAlphaF(config["opacity"])
        painter.setPen(QPen(color, rect.width() * config["line_width_ratio"]))
        for index in range(config["line_count"]):
            path = QPainterPath()
            for step in range(config["steps"] + 1):
                progress = step / config["steps"]
                drift = math.sin(
                    progress * config["frequency"]
                    + state["phase"] * config["speed"]
                    + index * config["phase_step"]
                )
                x = rect.width() * (
                    (index + config["edge_offset"]) / config["line_count"]
                    + drift * config["drift_ratio"]
                )
                point = QPointF(x, rect.height() * progress)
                path.moveTo(point) if step == 0 else path.lineTo(point)
            painter.drawPath(path)

    def _paint_metaballs(self, painter: QPainter, rect: QRectF, state: dict) -> None:
        config = state["config"]["metaballs"]
        accent = QColor(state["palette"][-1])
        for index in range(config["count"]):
            seed = index + config["seed_offset"]
            radius = rect.height() * (
                config["min_radius_ratio"] + self._hash(seed) * config["radius_range"]
            )
            x = rect.width() * self._hash(seed * config["x_seed"])
            travel = state["phase"] * (
                config["min_speed"] + self._hash(seed * config["speed_seed"])
            )
            y = rect.height() * ((self._hash(seed * config["y_seed"]) + travel) % 1)
            gradient = QRadialGradient(QPointF(x, y), radius)
            center = QColor(accent)
            center.setAlphaF(config["opacity"])
            edge = QColor(accent)
            edge.setAlpha(0)
            gradient.setColorAt(0, center)
            gradient.setColorAt(1, edge)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def _paint_sakura(self, painter: QPainter, rect: QRectF, state: dict) -> None:
        config = state["config"]["sakura"]
        color = QColor(state["palette"][-1])
        color.setAlphaF(config["opacity"])
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(config["count"]):
            seed = index + config["seed_offset"]
            size = rect.height() * (
                config["min_size_ratio"] + self._hash(seed) * config["size_range"]
            )
            fall = state["phase"] * (
                config["min_speed"] + self._hash(seed * config["speed_seed"])
            )
            y = rect.height() * ((self._hash(seed * config["y_seed"]) + fall) % 1)
            sway = math.sin(state["phase"] + seed) * config["sway_ratio"]
            x = rect.width() * ((self._hash(seed * config["x_seed"]) + sway) % 1)
            painter.save()
            painter.translate(x, y)
            painter.rotate(state["phase"] * config["rotation_speed"] + seed)
            painter.drawEllipse(QRectF(-size, -size / 2, size * 2, size))
            painter.restore()

    def _paint_veins(self, painter: QPainter, rect: QRectF, state: dict) -> None:
        config = state["config"]["veins"]
        color = QColor(state["palette"][-1])
        color.setAlphaF(config["opacity"])
        painter.setPen(QPen(color, config["line_width"]))
        columns = config["columns"]
        rows = config["rows"]
        points = []
        for row in range(rows):
            row_points = []
            for column in range(columns):
                seed = row * columns + column + config["seed_offset"]
                motion = math.sin(state["phase"] + seed) * config["motion_ratio"]
                x = rect.width() * ((column + config["cell_offset"] + motion) / columns)
                y = rect.height() * (
                    (row + config["cell_offset"] + self._hash(seed)) / rows
                )
                row_points.append(QPointF(x, y))
            points.append(row_points)
        for row in range(rows):
            for column in range(columns):
                if column + 1 < columns:
                    painter.drawLine(points[row][column], points[row][column + 1])
                if row + 1 < rows:
                    painter.drawLine(points[row][column], points[row + 1][column])

    @staticmethod
    def _hash(value: float) -> float:
        return math.sin(value * 12.9898) * 43758.5453 % 1
