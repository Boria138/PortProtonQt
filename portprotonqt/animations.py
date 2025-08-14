from PySide6.QtCore import QPropertyAnimation, QByteArray, QEasingCurve, QAbstractAnimation, QParallelAnimationGroup, QRect, Qt, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QConicalGradient, QBrush
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from collections.abc import Callable
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

class SafeOpacityEffect(QGraphicsOpacityEffect):
    def __init__(self, parent=None, disable_at_full=True):
        super().__init__(parent)
        self.disable_at_full = disable_at_full

    def setOpacity(self, opacity: float):
        opacity = max(0.0, min(1.0, opacity))
        super().setOpacity(opacity)
        if opacity < 1.0:
            self.setEnabled(True)
        elif self.disable_at_full:
            self.setEnabled(False)

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
        if not painter.isActive():
            logger.warning("Painter is not active; skipping border paint")
            return
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
        if rect.isEmpty():
            return  # Avoid drawing invalid rect
        painter.drawRoundedRect(rect, radius, radius)

class DetailPageAnimations:
    def __init__(self, main_window, theme=None):
        self.main_window = main_window
        self.theme = theme if theme is not None else default_styles
        self.animations = main_window._animations if hasattr(main_window, '_animations') else {}

    def animate_detail_page(self, detail_page: QWidget, load_image_and_restore_effect: Callable, cleanup_animation: Callable):
        """Animate the detail page based on theme settings."""
        animation_type = self.theme.GAME_CARD_ANIMATION.get("detail_page_animation_type", "fade")
        duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_fade_duration", 350)

        if animation_type == "fade":
            original_effect = detail_page.graphicsEffect()
            opacity_effect = SafeOpacityEffect(detail_page, disable_at_full=True)
            opacity_effect.setOpacity(0.0)
            detail_page.setGraphicsEffect(opacity_effect)
            animation = QPropertyAnimation(opacity_effect, QByteArray(b"opacity"))
            animation.setDuration(duration)
            animation.setStartValue(0.0)
            animation.setEndValue(0.999)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            def restore_effect():
                try:
                    detail_page.setGraphicsEffect(original_effect) # type: ignore
                except RuntimeError:
                    logger.debug("Original effect already deleted")
            animation.finished.connect(restore_effect)
            animation.finished.connect(load_image_and_restore_effect)
            animation.finished.connect(opacity_effect.deleteLater)
        elif animation_type in ["slide_left", "slide_right", "slide_up", "slide_down"]:
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration", 500)
            easing_curve = QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION.get("detail_page_easing_curve", "OutCubic")])
            start_pos = {
                "slide_left": QPoint(self.main_window.width(), 0),
                "slide_right": QPoint(-self.main_window.width(), 0),
                "slide_up": QPoint(0, self.main_window.height()),
                "slide_down": QPoint(0, -self.main_window.height())
            }[animation_type]
            detail_page.move(start_pos)
            animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
            animation.setDuration(duration)
            animation.setStartValue(start_pos)
            animation.setEndValue(self.main_window.stackedWidget.rect().topLeft())
            animation.setEasingCurve(easing_curve)
            animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = animation
            animation.finished.connect(cleanup_animation)
            animation.finished.connect(load_image_and_restore_effect)
        elif animation_type == "bounce":
            duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_bounce_duration", 400)
            easing_curve = QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION.get("detail_page_easing_curve", "OutCubic")])
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
            geometry_anim.setEasingCurve(easing_curve)
            group_anim = QParallelAnimationGroup()
            group_anim.addAnimation(opacity_anim)
            group_anim.addAnimation(geometry_anim)
            group_anim.finished.connect(load_image_and_restore_effect)
            group_anim.finished.connect(cleanup_animation)
            group_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self.animations[detail_page] = group_anim

    def animate_detail_page_exit(self, detail_page: QWidget, cleanup_callback: Callable):
        """Animate the detail page exit based on theme settings."""
        try:
            animation_type = self.theme.GAME_CARD_ANIMATION.get("detail_page_animation_type", "fade")

            # Safely stop and remove any existing animation
            if detail_page in self.animations:
                try:
                    animation = self.animations[detail_page]
                    if isinstance(animation, QAbstractAnimation) and animation.state() == QAbstractAnimation.State.Running:
                        animation.stop()
                except RuntimeError:
                    logger.debug("Animation already deleted for page")
                except Exception as e:
                    logger.error(f"Error stopping existing animation: {e}", exc_info=True)
                finally:
                    self.animations.pop(detail_page, None)

            # Define animation based on type
            if animation_type == "fade":
                duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_fade_duration_exit", 350)
                original_effect = detail_page.graphicsEffect()
                opacity_effect = SafeOpacityEffect(detail_page, disable_at_full=False)
                opacity_effect.setOpacity(0.999)
                detail_page.setGraphicsEffect(opacity_effect)
                animation = QPropertyAnimation(opacity_effect, QByteArray(b"opacity"))
                animation.setDuration(duration)
                animation.setStartValue(0.999)
                animation.setEndValue(0.0)
                animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = animation
                def restore_and_cleanup():
                    try:
                        detail_page.setGraphicsEffect(original_effect) # type: ignore
                    except RuntimeError:
                        logger.debug("Original effect already deleted")
                    cleanup_callback()
                animation.finished.connect(restore_and_cleanup)
                animation.finished.connect(opacity_effect.deleteLater)  # Clean up effect
            elif animation_type in ["slide_left", "slide_right", "slide_up", "slide_down"]:
                duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration_exit", 500)
                easing_curve = QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION.get("detail_page_easing_curve_exit", "InCubic")])
                end_pos = {
                    "slide_left": QPoint(-self.main_window.width(), 0),  # Exit to left (opposite of entry)
                    "slide_right": QPoint(self.main_window.width(), 0),  # Exit to right
                    "slide_up": QPoint(0, self.main_window.height()),    # Exit downward
                    "slide_down": QPoint(0, -self.main_window.height())  # Exit upward
                }[animation_type]
                animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
                animation.setDuration(duration)
                animation.setStartValue(detail_page.pos())
                animation.setEndValue(end_pos)
                animation.setEasingCurve(easing_curve)
                animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = animation
                animation.finished.connect(cleanup_callback)
            elif animation_type == "bounce":
                duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_bounce_duration_exit", 400)
                easing_curve = QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION.get("detail_page_easing_curve_exit", "InCubic")])
                opacity_anim = QPropertyAnimation(detail_page, QByteArray(b"windowOpacity"))
                opacity_anim.setDuration(duration)
                opacity_anim.setStartValue(1.0)
                opacity_anim.setEndValue(0.0)
                final_rect = QRect(detail_page.x() + detail_page.width() // 4, detail_page.y() + detail_page.height() // 4,
                                  detail_page.width() // 2, detail_page.height() // 2)
                geometry_anim = QPropertyAnimation(detail_page, QByteArray(b"geometry"))
                geometry_anim.setDuration(duration)
                geometry_anim.setStartValue(detail_page.geometry())
                geometry_anim.setEndValue(final_rect)
                geometry_anim.setEasingCurve(easing_curve)
                group_anim = QParallelAnimationGroup()
                group_anim.addAnimation(opacity_anim)
                group_anim.addAnimation(geometry_anim)
                group_anim.finished.connect(cleanup_callback)
                group_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = group_anim
        except Exception as e:
            logger.error(f"Error in animate_detail_page_exit: {e}", exc_info=True)
            self.animations.pop(detail_page, None)
            cleanup_callback()  # Fallback to cleanup if animation setup fails
