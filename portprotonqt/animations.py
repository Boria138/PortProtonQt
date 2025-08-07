from PySide6.QtCore import QPropertyAnimation, QByteArray, QEasingCurve, QAbstractAnimation, QParallelAnimationGroup, QRect, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QConicalGradient, QBrush
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from collections.abc import Callable
import portprotonqt.themes.standart.styles as default_styles

class GameCardAnimations:
    def __init__(self, game_card, theme=None):
        self.game_card = game_card
        self.theme = theme if theme is not None else default_styles
        self.thickness_anim: QPropertyAnimation | None = None
        self.gradient_anim: QPropertyAnimation | None = None
        self.pulse_anim: QPropertyAnimation | None = None
        self._isPulseAnimationConnected = False

    def setup_animations(self):
        """Initialize animation properties."""
        self.thickness_anim = QPropertyAnimation(self.game_card, QByteArray(b"borderWidth"))
        self.thickness_anim.setDuration(self.theme.GAME_CARD_ANIMATION["thickness_anim_duration"])

    def start_pulse_animation(self):
        """Start pulse animation for border width when hovered or focused."""
        if not (self.game_card._hovered or self.game_card._focused):
            return
        if self.pulse_anim:
            self.pulse_anim.stop()
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

        # Ensure thickness_anim is initialized
        if not self.thickness_anim:
            self.setup_animations()

        if self.thickness_anim:
            self.thickness_anim.stop()
            if self._isPulseAnimationConnected:
                self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                self._isPulseAnimationConnected = False
            self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
            self.thickness_anim.setStartValue(self.game_card._borderWidth)
            self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["hover_border_width"])
            self.thickness_anim.finished.connect(self.start_pulse_animation)
            self._isPulseAnimationConnected = True
            self.thickness_anim.start()

        if self.gradient_anim:
            self.gradient_anim.stop()
        self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
        self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
        self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
        self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
        self.gradient_anim.setLoopCount(-1)
        self.gradient_anim.start()

    def handle_leave_event(self):
        """Handle mouse leave event animations."""
        self.game_card._hovered = False
        self.game_card.hoverChanged.emit(self.game_card.name, False)
        if not self.game_card._focused:
            if self.gradient_anim:
                self.gradient_anim.stop()
                self.gradient_anim = None
            if self.pulse_anim:
                self.pulse_anim.stop()
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    self.thickness_anim.finished.disconnect(self.start_pulse_animation)
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

            # Ensure thickness_anim is initialized
            if not self.thickness_anim:
                self.setup_animations()

            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    self._isPulseAnimationConnected = False
                self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
                self.thickness_anim.setStartValue(self.game_card._borderWidth)
                self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["focus_border_width"])
                self.thickness_anim.finished.connect(self.start_pulse_animation)
                self._isPulseAnimationConnected = True
                self.thickness_anim.start()

            if self.gradient_anim:
                self.gradient_anim.stop()
            self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
            self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
            self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
            self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
            self.gradient_anim.setLoopCount(-1)
            self.gradient_anim.start()

    def handle_focus_out_event(self):
        """Handle focus out event animations."""
        self.game_card._focused = False
        self.game_card.focusChanged.emit(self.game_card.name, False)
        if not self.game_card._hovered:
            if self.gradient_anim:
                self.gradient_anim.stop()
                self.gradient_anim = None
            if self.pulse_anim:
                self.pulse_anim.stop()
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    self._isPulseAnimationConnected = False
                self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve_out"]]))
                self.thickness_anim.setStartValue(self.game_card._borderWidth)
                self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["default_border_width"])
                self.thickness_anim.start()

    def paint_border(self, painter: QPainter):
        """Paint the animated border for the GameCard."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(self.game_card._borderWidth)
        if self.game_card._hovered or self.game_card._focused:
            center = self.game_card.rect().center()
            gradient = QConicalGradient(center, self.game_card._gradientAngle)
            for stop in self.theme.GAME_CARD_ANIMATION["gradient_colors"]:
                gradient.setColorAt(stop["position"], QColor(stop["color"]))
            pen.setBrush(QBrush(gradient))
        else:
            pen.setColor(QColor(0, 0, 0, 0))
        painter.setPen(pen)
        radius = 18
        bw = round(self.game_card._borderWidth / 2)
        rect = self.game_card.rect().adjusted(bw, bw, -bw, -bw)
        painter.drawRoundedRect(rect, radius, radius)

class DetailPageAnimations:
    def __init__(self, main_window, theme=None):
        self.main_window = main_window
        self.theme = theme if theme is not None else default_styles
        self.animations = main_window._animations if hasattr(main_window, '_animations') else {}

    def animate_detail_page(self, detail_page: QWidget, load_image_and_restore_effect: Callable, cleanup_animation: Callable):
        """Animate the detail page based on theme settings."""
        shadow = detail_page.graphicsEffect()
        animation_type = self.theme.GAME_CARD_ANIMATION.get("detail_page_animation_type", "fade")
        duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_fade_duration", 350)

        if animation_type == "fade":
            opacity_effect = QGraphicsOpacityEffect(detail_page)
            detail_page.setGraphicsEffect(opacity_effect)
            animation = QPropertyAnimation(opacity_effect, QByteArray(b"opacity"))
            animation.setDuration(duration)
            animation.setStartValue(0)
            animation.setEndValue(1)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            animation.finished.connect(lambda: detail_page.setGraphicsEffect(shadow) if shadow is not None else detail_page.setGraphicsEffect(None)) # type: ignore
            animation.finished.connect(load_image_and_restore_effect)
        elif animation_type == "slide_left":
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration", 500)
            detail_page.move(self.main_window.width(), 0)
            animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
            animation.setDuration(duration)
            animation.setStartValue(detail_page.pos())
            animation.setEndValue(self.main_window.stackedWidget.rect().topLeft())
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            animation.finished.connect(cleanup_animation)
            animation.finished.connect(load_image_and_restore_effect)
        elif animation_type == "slide_right":
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration", 500)
            detail_page.move(-self.main_window.width(), 0)
            animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
            animation.setDuration(duration)
            animation.setStartValue(detail_page.pos())
            animation.setEndValue(self.main_window.stackedWidget.rect().topLeft())
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            animation.finished.connect(cleanup_animation)
            animation.finished.connect(load_image_and_restore_effect)
        elif animation_type == "slide_up":
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration", 500)
            detail_page.move(0, self.main_window.height())
            animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
            animation.setDuration(duration)
            animation.setStartValue(detail_page.pos())
            animation.setEndValue(self.main_window.stackedWidget.rect().topLeft())
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            animation.finished.connect(cleanup_animation)
            animation.finished.connect(load_image_and_restore_effect)
        elif animation_type == "slide_down":
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration", 500)
            detail_page.move(0, -self.main_window.height())
            animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
            animation.setDuration(duration)
            animation.setStartValue(detail_page.pos())
            animation.setEndValue(self.main_window.stackedWidget.rect().topLeft())
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            animation.finished.connect(cleanup_animation)
            animation.finished.connect(load_image_and_restore_effect)
        elif animation_type == "bounce":
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_zoom_duration", 400)
            detail_page.setWindowOpacity(0.0)
            opacity_anim = QPropertyAnimation(detail_page, QByteArray(b"windowOpacity"))
            opacity_anim.setDuration(duration)
            opacity_anim.setStartValue(0.0)
            opacity_anim.setEndValue(1.0)
            initial_rect = QRect(detail_page.x() + detail_page.width() // 4, detail_page.y() + detail_page.height() // 4,
                                detail_page.width() // 2, detail_page.height() // 2)
            final_rect = detail_page.geometry()
            geometry_anim = QPropertyAnimation(detail_page, QByteArray(b"geometry"))
            geometry_anim.setDuration(duration)
            geometry_anim.setStartValue(initial_rect)
            geometry_anim.setEndValue(final_rect)
            geometry_anim.setEasingCurve(QEasingCurve.Type.OutBack)
            group_anim = QParallelAnimationGroup()
            group_anim.addAnimation(opacity_anim)
            group_anim.addAnimation(geometry_anim)
            group_anim.finished.connect(load_image_and_restore_effect)
            group_anim.finished.connect(cleanup_animation)
            group_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = group_anim
