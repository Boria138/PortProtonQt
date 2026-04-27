from math import radians, sin

from PySide6.QtCore import QPropertyAnimation, QByteArray, QEasingCurve, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QConicalGradient, QBrush

from portprotonqt.logger import get_logger
from portprotonqt.config import ui_config
from portprotonqt.theme_manager import ThemeManager

logger = get_logger(__name__)


class GameCardAnimations:
    def __init__(self, game_card, theme=None):
        self.game_card = game_card
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else self.theme_manager.apply_theme(ui_config.get_theme())
        self.thickness_anim: QPropertyAnimation | None = None
        self.gradient_anim: QPropertyAnimation | None = None
        self.scale_anim: QPropertyAnimation | None = None
        self.pulse_anim: QPropertyAnimation | None = None
        self._isPulseAnimationConnected = False

    def cleanup(self):
        """Clean up all animation objects to prevent memory leaks."""
        if self.thickness_anim:
            try:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    try:
                        self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    except RuntimeError:
                        pass
                self.thickness_anim.deleteLater()
            except RuntimeError:
                pass
            self.thickness_anim = None

        if self.gradient_anim:
            try:
                self.gradient_anim.stop()
                self.gradient_anim.deleteLater()
            except RuntimeError:
                pass
            self.gradient_anim = None

        if self.scale_anim:
            try:
                self.scale_anim.stop()
                self.scale_anim.deleteLater()
            except RuntimeError:
                pass
            self.scale_anim = None

        if self.pulse_anim:
            try:
                self.pulse_anim.stop()
                self.pulse_anim.deleteLater()
            except RuntimeError:
                pass
            self.pulse_anim = None

        self._isPulseAnimationConnected = False

    def setup_animations(self):
        """Initialize animation properties based on theme."""
        self.thickness_anim = QPropertyAnimation(self.game_card, QByteArray(b"borderWidth"))
        self.thickness_anim.setDuration(self.theme.GAME_CARD_ANIMATION["thickness_anim_duration"])

        animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")
        if animation_type in {"gradient", "glow"}:
            self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
            self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
        elif animation_type in {"scale", "scale_fill"}:
            self.scale_anim = QPropertyAnimation(self.game_card, QByteArray(b"scale"))
            self.scale_anim.setDuration(self.theme.GAME_CARD_ANIMATION["scale_anim_duration"])

    def start_pulse_animation(self):
        """Start pulse animation for border width when hovered or focused."""
        if not (self.game_card._hovered or self.game_card._focused):
            return

        if self.pulse_anim:
            try:
                self.pulse_anim.stop()
                self.pulse_anim.deleteLater()
            except RuntimeError:
                pass
            self.pulse_anim = None

        self.pulse_anim = QPropertyAnimation(self.game_card, QByteArray(b"borderWidth"))
        self.pulse_anim.setDuration(self.theme.GAME_CARD_ANIMATION["pulse_anim_duration"])
        self.pulse_anim.setLoopCount(0)
        self.pulse_anim.setKeyValueAt(0, self.theme.GAME_CARD_ANIMATION["pulse_min_border_width"])
        self.pulse_anim.setKeyValueAt(0.5, self.theme.GAME_CARD_ANIMATION["pulse_max_border_width"])
        self.pulse_anim.setKeyValueAt(1, self.theme.GAME_CARD_ANIMATION["pulse_min_border_width"])
        self.pulse_anim.start()

    def handle_enter_event(self):
        """Handle mouse enter event animations."""
        self.game_card._hovered = True
        self.game_card.hoverChanged.emit(self.game_card.name, True)
        self.game_card.setFocus(Qt.FocusReason.MouseFocusReason)

        if not self.thickness_anim:
            self.setup_animations()

        animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")

        if self.thickness_anim:
            self.thickness_anim.stop()
            if self._isPulseAnimationConnected:
                try:
                    self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                except RuntimeError:
                    pass
                self._isPulseAnimationConnected = False
            self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
            self.thickness_anim.setStartValue(self.game_card._borderWidth)
            self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["hover_border_width"])
            self.thickness_anim.finished.connect(self.start_pulse_animation)
            self._isPulseAnimationConnected = True
            self.thickness_anim.start()

        if animation_type in {"gradient", "glow"}:
            if self.gradient_anim:
                try:
                    self.gradient_anim.stop()
                    self.gradient_anim.deleteLater()
                except RuntimeError:
                    pass
                self.gradient_anim = None

            self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
            self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
            self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
            self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
            self.gradient_anim.setLoopCount(-1)
            self.gradient_anim.start()
        elif animation_type in {"scale", "scale_fill"}:
            if self.scale_anim:
                try:
                    self.scale_anim.stop()
                    self.scale_anim.deleteLater()
                except RuntimeError:
                    pass
                self.scale_anim = None

            self.scale_anim = QPropertyAnimation(self.game_card, QByteArray(b"scale"))
            self.scale_anim.setDuration(self.theme.GAME_CARD_ANIMATION["scale_anim_duration"])
            self.scale_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["scale_easing_curve"]]))
            self.scale_anim.setStartValue(self.game_card._scale)
            self.scale_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["hover_scale"])
            self.scale_anim.start()

    def handle_leave_event(self):
        """Handle mouse leave event animations."""
        self.game_card._hovered = False
        self.game_card.hoverChanged.emit(self.game_card.name, False)
        if not self.game_card._focused:
            animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")
            if animation_type in {"gradient", "glow"}:
                if self.gradient_anim:
                    try:
                        self.gradient_anim.stop()
                        self.gradient_anim.deleteLater()
                    except RuntimeError:
                        pass
                    self.gradient_anim = None
            elif animation_type in {"scale", "scale_fill"}:
                if self.scale_anim:
                    try:
                        self.scale_anim.stop()
                        self.scale_anim.deleteLater()
                    except RuntimeError:
                        pass
                    self.scale_anim = None

                self.scale_anim = QPropertyAnimation(self.game_card, QByteArray(b"scale"))
                self.scale_anim.setDuration(self.theme.GAME_CARD_ANIMATION["scale_anim_duration"])
                self.scale_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["scale_easing_curve_out"]]))
                self.scale_anim.setStartValue(self.game_card._scale)
                self.scale_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_scale"])
                self.scale_anim.start()
            if self.pulse_anim:
                try:
                    self.pulse_anim.stop()
                    self.pulse_anim.deleteLater()
                except RuntimeError:
                    pass
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    try:
                        self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    except RuntimeError:
                        pass
                    self._isPulseAnimationConnected = False
                self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve_out"]]))
                self.thickness_anim.setStartValue(self.game_card._borderWidth)
                self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_border_width"])
                self.thickness_anim.start()

    def handle_focus_in_event(self):
        """Handle focus in event animations."""
        if not self.game_card._hovered:
            self.game_card._focused = True
            self.game_card.focusChanged.emit(self.game_card.name, True)

            if not self.thickness_anim:
                self.setup_animations()

            animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")

            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    try:
                        self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    except RuntimeError:
                        pass
                    self._isPulseAnimationConnected = False
                self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
                self.thickness_anim.setStartValue(self.game_card._borderWidth)
                self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["focus_border_width"])
                self.thickness_anim.finished.connect(self.start_pulse_animation)
                self._isPulseAnimationConnected = True
                self.thickness_anim.start()

            if animation_type in {"gradient", "glow"}:
                if self.gradient_anim:
                    try:
                        self.gradient_anim.stop()
                        self.gradient_anim.deleteLater()
                    except RuntimeError:
                        pass
                    self.gradient_anim = None

                self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
                self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
                self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
                self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
                self.gradient_anim.setLoopCount(-1)
                self.gradient_anim.start()
            elif animation_type in {"scale", "scale_fill"}:
                if self.scale_anim:
                    try:
                        self.scale_anim.stop()
                        self.scale_anim.deleteLater()
                    except RuntimeError:
                        pass
                    self.scale_anim = None

                self.scale_anim = QPropertyAnimation(self.game_card, QByteArray(b"scale"))
                self.scale_anim.setDuration(self.theme.GAME_CARD_ANIMATION["scale_anim_duration"])
                self.scale_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["scale_easing_curve"]]))
                self.scale_anim.setStartValue(self.game_card._scale)
                self.scale_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["focus_scale"])
                self.scale_anim.start()

    def handle_focus_out_event(self):
        """Handle focus out event animations."""
        self.game_card._focused = False
        self.game_card.focusChanged.emit(self.game_card.name, False)
        if not self.game_card._hovered:
            animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")
            if animation_type in {"gradient", "glow"}:
                if self.gradient_anim:
                    try:
                        self.gradient_anim.stop()
                        self.gradient_anim.deleteLater()
                    except RuntimeError:
                        pass
                    self.gradient_anim = None
            elif animation_type in {"scale", "scale_fill"}:
                if self.scale_anim:
                    try:
                        self.scale_anim.stop()
                        self.scale_anim.deleteLater()
                    except RuntimeError:
                        pass
                    self.scale_anim = None

                self.scale_anim = QPropertyAnimation(self.game_card, QByteArray(b"scale"))
                self.scale_anim.setDuration(self.theme.GAME_CARD_ANIMATION["scale_anim_duration"])
                self.scale_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["scale_easing_curve_out"]]))
                self.scale_anim.setStartValue(self.game_card._scale)
                self.scale_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_scale"])
                self.scale_anim.start()
            if self.pulse_anim:
                try:
                    self.pulse_anim.stop()
                    self.pulse_anim.deleteLater()
                except RuntimeError:
                    pass
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    try:
                        self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    except RuntimeError:
                        pass
                    self._isPulseAnimationConnected = False
                self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve_out"]]))
                self.thickness_anim.setStartValue(self.game_card._borderWidth)
                self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_border_width"])
                self.thickness_anim.start()

    def paint_border(self, painter: QPainter):
        if not painter.isActive():
            logger.debug("Painter is not active; skipping border paint")
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(self.game_card._borderWidth)
        fill_brush = QBrush(Qt.BrushStyle.NoBrush)
        animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")
        if (self.game_card._hovered or self.game_card._focused) and animation_type == "gradient":
            center = self.game_card.rect().center()
            gradient = QConicalGradient(center, self.game_card._gradientAngle)
            for stop in self.theme.GAME_CARD_ANIMATION["gradient_colors"]:
                gradient.setColorAt(stop["position"], QColor(stop["color"]))
            pen.setBrush(QBrush(gradient))
        elif (self.game_card._hovered or self.game_card._focused) and animation_type == "fill":
            fill_color_value = self.theme.GAME_CARD_ANIMATION.get(
                "fill_color",
                getattr(self.theme, "color_a", self.theme.color_f),
            )
            fill_alpha = int(self.theme.GAME_CARD_ANIMATION.get("fill_alpha", 90))
            fill_color = QColor(fill_color_value)
            fill_color.setAlpha(max(0, min(255, fill_alpha)))
            fill_brush = QBrush(fill_color)
            pen.setColor(QColor(0, 0, 0, 0))
        elif (self.game_card._hovered or self.game_card._focused) and animation_type == "scale_fill":
            fill_color_value = self.theme.GAME_CARD_ANIMATION.get(
                "fill_color",
                getattr(self.theme, "color_a", self.theme.color_f),
            )
            fill_alpha = int(self.theme.GAME_CARD_ANIMATION.get("fill_alpha", 90))
            fill_color = QColor(fill_color_value)
            fill_color.setAlpha(max(0, min(255, fill_alpha)))
            fill_brush = QBrush(fill_color)
            pen.setColor(QColor(0, 0, 0, 0))
        elif (self.game_card._hovered or self.game_card._focused) and animation_type == "stripe":
            stripe_color_value = self.theme.GAME_CARD_ANIMATION.get(
                "stripe_color",
                getattr(self.theme, "color_a", self.theme.color_f),
            )
            stripe_alpha = int(self.theme.GAME_CARD_ANIMATION.get("stripe_alpha", 255))
            stripe_color = QColor(stripe_color_value)
            stripe_color.setAlpha(max(0, min(255, stripe_alpha)))
            pen.setColor(stripe_color)
        elif (self.game_card._hovered or self.game_card._focused) and animation_type == "glow":
            glow_color_value = self.theme.GAME_CARD_ANIMATION.get(
                "stripe_color",
                getattr(self.theme, "color_a", self.theme.color_f),
            )
            glow_base_alpha = int(self.theme.GAME_CARD_ANIMATION.get("glow_base_alpha", 120))
            glow_pulse_alpha = int(self.theme.GAME_CARD_ANIMATION.get("glow_pulse_alpha", 80))
            glow_wave = 0.5 + 0.5 * sin(radians(self.game_card._gradientAngle))
            glow_alpha = max(0, min(255, glow_base_alpha + int(glow_pulse_alpha * glow_wave)))
            glow_color = QColor(glow_color_value)
            glow_color.setAlpha(glow_alpha)
            pen.setColor(glow_color)
        else:
            pen.setColor(QColor(0, 0, 0, 0))
        painter.setPen(pen)
        painter.setBrush(fill_brush)
        radius = 18 * self.game_card._scale
        bw = round(self.game_card._borderWidth / 2)
        rect = self.game_card.rect().adjusted(bw, bw, -bw, -bw)
        if rect.isEmpty():
            return
        painter.drawRoundedRect(rect, radius, radius)
