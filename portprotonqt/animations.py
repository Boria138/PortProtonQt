from typing import Any, cast
from PySide6.QtCore import QPropertyAnimation, QByteArray, QEasingCurve, QAbstractAnimation, QParallelAnimationGroup, QRect, Qt, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QConicalGradient, QBrush
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from collections.abc import Callable
from portprotonqt.logger import get_logger
from portprotonqt.config_utils import read_theme_from_config
from portprotonqt.theme_manager import ThemeManager

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
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else self.theme_manager.apply_theme(read_theme_from_config())
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
                        pass  # Signal was already disconnected
                self.thickness_anim.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
            self.thickness_anim = None

        if self.gradient_anim:
            try:
                self.gradient_anim.stop()
                self.gradient_anim.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
            self.gradient_anim = None

        if self.scale_anim:
            try:
                self.scale_anim.stop()
                self.scale_anim.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
            self.scale_anim = None

        if self.pulse_anim:
            try:
                self.pulse_anim.stop()
                self.pulse_anim.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
            self.pulse_anim = None

        self._isPulseAnimationConnected = False

    def setup_animations(self):
        """Initialize animation properties based on theme."""
        self.thickness_anim = QPropertyAnimation(self.game_card, QByteArray(b"borderWidth"))
        self.thickness_anim.setDuration(self.theme.GAME_CARD_ANIMATION["thickness_anim_duration"])

        animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")
        if animation_type == "gradient":
            self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
            self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
        elif animation_type == "scale":
            self.scale_anim = QPropertyAnimation(self.game_card, QByteArray(b"scale"))
            self.scale_anim.setDuration(self.theme.GAME_CARD_ANIMATION["scale_anim_duration"])

    def start_pulse_animation(self):
        """Start pulse animation for border width when hovered or focused."""
        if not (self.game_card._hovered or self.game_card._focused):
            return

        # Clean up existing pulse animation to prevent memory leaks
        if self.pulse_anim:
            try:
                self.pulse_anim.stop()
                self.pulse_anim.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
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
                    pass  # Signal was already disconnected
                self._isPulseAnimationConnected = False
            self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
            self.thickness_anim.setStartValue(self.game_card._borderWidth)
            self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["hover_border_width"])
            self.thickness_anim.finished.connect(self.start_pulse_animation)
            self._isPulseAnimationConnected = True
            self.thickness_anim.start()

        if animation_type == "gradient":
            # Clean up existing gradient animation to prevent memory leaks
            if self.gradient_anim:
                try:
                    self.gradient_anim.stop()
                    self.gradient_anim.deleteLater()
                except RuntimeError:
                    pass  # Object already deleted
                self.gradient_anim = None

            self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
            self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
            self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
            self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
            self.gradient_anim.setLoopCount(-1)
            self.gradient_anim.start()
        elif animation_type == "scale":
            # Clean up existing scale animation to prevent memory leaks
            if self.scale_anim:
                try:
                    self.scale_anim.stop()
                    self.scale_anim.deleteLater()
                except RuntimeError:
                    pass  # Object already deleted
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
            if animation_type == "gradient":
                if self.gradient_anim:
                    try:
                        self.gradient_anim.stop()
                        self.gradient_anim.deleteLater()
                    except RuntimeError:
                        pass  # Object already deleted
                    self.gradient_anim = None
            elif animation_type == "scale":
                if self.scale_anim:
                    try:
                        self.scale_anim.stop()
                        self.scale_anim.deleteLater()
                    except RuntimeError:
                        pass  # Object already deleted
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
                    pass  # Object already deleted
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    try:
                        self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    except RuntimeError:
                        pass  # Signal was already disconnected
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
                        pass  # Signal was already disconnected
                    self._isPulseAnimationConnected = False
                self.thickness_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION["thickness_easing_curve"]]))
                self.thickness_anim.setStartValue(self.game_card._borderWidth)
                self.thickness_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["focus_border_width"])
                self.thickness_anim.finished.connect(self.start_pulse_animation)
                self._isPulseAnimationConnected = True
                self.thickness_anim.start()

            if animation_type == "gradient":
                # Clean up existing gradient animation to prevent memory leaks
                if self.gradient_anim:
                    try:
                        self.gradient_anim.stop()
                        self.gradient_anim.deleteLater()
                    except RuntimeError:
                        pass  # Object already deleted
                    self.gradient_anim = None

                self.gradient_anim = QPropertyAnimation(self.game_card, QByteArray(b"gradientAngle"))
                self.gradient_anim.setDuration(self.theme.GAME_CARD_ANIMATION["gradient_anim_duration"])
                self.gradient_anim.setStartValue(self.theme.GAME_CARD_ANIMATION["gradient_start_angle"])
                self.gradient_anim.setEndValue(self.theme.GAME_CARD_ANIMATION["gradient_end_angle"])
                self.gradient_anim.setLoopCount(-1)
                self.gradient_anim.start()
            elif animation_type == "scale":
                # Clean up existing scale animation to prevent memory leaks
                if self.scale_anim:
                    try:
                        self.scale_anim.stop()
                        self.scale_anim.deleteLater()
                    except RuntimeError:
                        pass  # Object already deleted
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
            if animation_type == "gradient":
                if self.gradient_anim:
                    try:
                        self.gradient_anim.stop()
                        self.gradient_anim.deleteLater()
                    except RuntimeError:
                        pass  # Object already deleted
                    self.gradient_anim = None
            elif animation_type == "scale":
                if self.scale_anim:
                    try:
                        self.scale_anim.stop()
                        self.scale_anim.deleteLater()
                    except RuntimeError:
                        pass  # Object already deleted
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
                    pass  # Object already deleted
                self.pulse_anim = None
            if self.thickness_anim:
                self.thickness_anim.stop()
                if self._isPulseAnimationConnected:
                    try:
                        self.thickness_anim.finished.disconnect(self.start_pulse_animation)
                    except RuntimeError:
                        pass  # Signal was already disconnected
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
        animation_type = self.theme.GAME_CARD_ANIMATION.get("card_animation_type", "gradient")
        if (self.game_card._hovered or self.game_card._focused) and animation_type == "gradient":
            center = self.game_card.rect().center()
            gradient = QConicalGradient(center, self.game_card._gradientAngle)
            for stop in self.theme.GAME_CARD_ANIMATION["gradient_colors"]:
                gradient.setColorAt(stop["position"], QColor(stop["color"]))
            pen.setBrush(QBrush(gradient))
        else:
            pen.setColor(QColor(0, 0, 0, 0))
        painter.setPen(pen)
        radius = 18 * self.game_card._scale
        bw = round(self.game_card._borderWidth / 2)
        rect = self.game_card.rect().adjusted(bw, bw, -bw, -bw)
        if rect.isEmpty():
            return
        painter.drawRoundedRect(rect, radius, radius)

class DetailPageAnimations:
    def __init__(self, main_window, theme=None):
        self.main_window = main_window
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else self.theme_manager.apply_theme(read_theme_from_config())
        # Ensure the main window has an animations dict
        if not hasattr(main_window, '_animations'):
            main_window._animations = {}
        self.animations = main_window._animations

    def cleanup(self):
        """Clean up all animations to prevent memory leaks."""
        # Stop and clean up all animations in the dict
        for _detail_page, animation in list(self.animations.items()):
            try:
                if isinstance(animation, QAbstractAnimation):
                    animation.stop()
                    animation.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
        self.animations.clear()

    def animate_detail_page(self, detail_page: QWidget, load_image_and_restore_effect: Callable, cleanup_animation: Callable):
        """Animate the detail page based on theme settings."""
        # Check if the detail page is still valid before proceeding
        if not detail_page or detail_page.isHidden() or detail_page.parent() is None:
            logger.warning("Detail page is not valid, skipping enter animation")
            load_image_and_restore_effect()
            cleanup_animation()
            return

        animation_type = self.theme.GAME_CARD_ANIMATION.get("detail_page_animation_type", "fade")
        duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_fade_duration", 350)

        # Safely stop and remove any existing animation for this detail page
        if detail_page in self.animations:
            try:
                existing_animation = self.animations[detail_page]
                if isinstance(existing_animation, QAbstractAnimation) and existing_animation.state() == QAbstractAnimation.State.Running:
                    existing_animation.stop()
                    existing_animation.deleteLater()
            except RuntimeError:
                logger.debug("Existing animation already deleted")
            except Exception as e:
                logger.error(f"Error stopping existing animation: {e}", exc_info=True)
            finally:
                self.animations.pop(detail_page, None)

        if animation_type == "fade":
            # Check again if page is still valid before starting animation
            if not detail_page or detail_page.isHidden():
                logger.warning("Detail page became invalid during fade setup, skipping animation")
                load_image_and_restore_effect()
                cleanup_animation()
                return

            original_effect = detail_page.graphicsEffect()
            opacity_effect = SafeOpacityEffect(detail_page, disable_at_full=True)
            opacity_effect.setOpacity(0.0)
            detail_page.setGraphicsEffect(opacity_effect)
            animation = QPropertyAnimation(opacity_effect, QByteArray(b"opacity"))
            animation.setDuration(duration)
            animation.setStartValue(0.0)
            animation.setEndValue(0.999)

            def restore_effect():
                try:
                    # Check if page is still valid before restoring effect
                    if detail_page and not detail_page.isHidden():
                        detail_page.setGraphicsEffect(cast(Any, original_effect))
                except RuntimeError:
                    logger.warning("Original effect already deleted")

            # Only start animation if page is still valid
            if detail_page and not detail_page.isHidden():
                animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = animation
                animation.finished.connect(restore_effect)
                animation.finished.connect(load_image_and_restore_effect)
                animation.finished.connect(opacity_effect.deleteLater)
            else:
                logger.warning("Detail page invalid when starting fade, cleaning up")
                restore_effect()
                load_image_and_restore_effect()
                opacity_effect.deleteLater()
                cleanup_animation()
        elif animation_type in ["slide_left", "slide_right", "slide_up", "slide_down"]:
            # Check again if page is still valid before starting animation
            if not detail_page or detail_page.isHidden():
                logger.warning("Detail page became invalid during slide setup, skipping animation")
                load_image_and_restore_effect()
                cleanup_animation()
                return

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

            # Only start animation if page is still valid
            if detail_page and not detail_page.isHidden():
                animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = animation
                animation.finished.connect(cleanup_animation)
                animation.finished.connect(load_image_and_restore_effect)
            else:
                logger.warning("Detail page invalid when starting slide, cleaning up")
                load_image_and_restore_effect()
                cleanup_animation()
        elif animation_type == "bounce":
            # Check again if page is still valid before starting animation
            if not detail_page or detail_page.isHidden():
                logger.warning("Detail page became invalid during bounce setup, skipping animation")
                load_image_and_restore_effect()
                cleanup_animation()
                return

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

            # Only start animation if page is still valid
            if detail_page and not detail_page.isHidden():
                group_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = group_anim
                group_anim.finished.connect(load_image_and_restore_effect)
                group_anim.finished.connect(cleanup_animation)
            else:
                logger.warning("Detail page invalid when starting bounce, cleaning up")
                load_image_and_restore_effect()
                cleanup_animation()

    def animate_detail_page_exit(self, detail_page: QWidget, cleanup_callback: Callable):
        """Animate the detail page exit based on theme settings."""
        try:
            # Check if the detail page is still valid before proceeding
            if not detail_page or detail_page.isHidden() or detail_page.parent() is None:
                logger.warning("Detail page is not valid, skipping exit animation")
                cleanup_callback()
                return

            animation_type = self.theme.GAME_CARD_ANIMATION.get("detail_page_animation_type", "fade")

            # Safely stop and remove any existing animation
            if detail_page in self.animations:
                try:
                    animation = self.animations[detail_page]
                    if isinstance(animation, QAbstractAnimation) and animation.state() == QAbstractAnimation.State.Running:
                        animation.stop()
                        animation.deleteLater()
                except RuntimeError:
                    logger.warning("Animation already deleted for page")
                except Exception as e:
                    logger.error(f"Error stopping existing animation: {e}", exc_info=True)
                finally:
                    self.animations.pop(detail_page, None)

            # Define animation based on type
            if animation_type == "fade":
                duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_fade_duration_exit", 350)

                # Check if page is still valid before accessing properties
                if not detail_page or detail_page.isHidden():
                    logger.warning("Detail page became invalid during fade exit setup, skipping animation")
                    cleanup_callback()
                    return

                original_effect = detail_page.graphicsEffect()
                opacity_effect = SafeOpacityEffect(detail_page, disable_at_full=False)
                opacity_effect.setOpacity(0.999)
                detail_page.setGraphicsEffect(opacity_effect)
                animation = QPropertyAnimation(opacity_effect, QByteArray(b"opacity"))
                animation.setDuration(duration)
                animation.setStartValue(0.999)
                animation.setEndValue(0.0)

                def restore_and_cleanup():
                    try:
                        # Check if page is still valid before restoring effect
                        if detail_page and not detail_page.isHidden():
                            detail_page.setGraphicsEffect(cast(Any, original_effect))
                    except RuntimeError:
                        logger.debug("Original effect already deleted")
                    cleanup_callback()

                # Check if animation is still valid before starting
                if animation and not detail_page.isHidden():
                    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                    self.animations[detail_page] = animation
                    animation.finished.connect(restore_and_cleanup)
                    animation.finished.connect(opacity_effect.deleteLater)
                else:
                    logger.warning("Animation or detail page invalid when starting fade exit, cleaning up")
                    restore_and_cleanup()
                    opacity_effect.deleteLater()

            elif animation_type in ["slide_left", "slide_right", "slide_up", "slide_down"]:
                duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_slide_duration_exit", 500)

                # Check if page is still valid before accessing properties
                if not detail_page or detail_page.isHidden():
                    logger.warning("Detail page became invalid during slide exit setup, skipping animation")
                    cleanup_callback()
                    return

                easing_curve = QEasingCurve(QEasingCurve.Type[self.theme.GAME_CARD_ANIMATION.get("detail_page_easing_curve_exit", "InCubic")])
                end_pos = {
                    "slide_left": QPoint(-self.main_window.width(), 0),
                    "slide_right": QPoint(self.main_window.width(), 0),
                    "slide_up": QPoint(0, self.main_window.height()),
                    "slide_down": QPoint(0, -self.main_window.height())
                }[animation_type]

                animation = QPropertyAnimation(detail_page, QByteArray(b"pos"))
                animation.setDuration(duration)
                animation.setStartValue(detail_page.pos())
                animation.setEndValue(end_pos)
                animation.setEasingCurve(easing_curve)

                def slide_cleanup():
                    # Check if page is still valid before cleanup
                    if not detail_page or detail_page.isHidden():
                        logger.debug("Detail page already cleaned up")
                    cleanup_callback()

                # Check if animation is still valid before starting
                if animation and not detail_page.isHidden():
                    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                    self.animations[detail_page] = animation
                    animation.finished.connect(slide_cleanup)
                else:
                    logger.warning("Animation or detail page invalid when starting slide exit, cleaning up")
                    slide_cleanup()

            elif animation_type == "bounce":
                duration = self.theme.GAME_CARD_ANIMATION.get("detail_page_bounce_duration_exit", 400)

                # Check if page is still valid before accessing properties
                if not detail_page or detail_page.isHidden():
                    logger.warning("Detail page became invalid during bounce exit setup, skipping animation")
                    cleanup_callback()
                    return

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

                # Check if animations are still valid before creating group
                if not detail_page or detail_page.isHidden():
                    logger.warning("Detail page became invalid during bounce exit setup, cleaning up")
                    cleanup_callback()
                    return

                group_anim = QParallelAnimationGroup()
                group_anim.addAnimation(opacity_anim)
                group_anim.addAnimation(geometry_anim)

                # Check if group animation is still valid before connecting
                if not detail_page or detail_page.isHidden():
                    logger.warning("Detail page became invalid during group animation setup, cleaning up")
                    cleanup_callback()
                    return

                def bounce_cleanup():
                    # Check if page is still valid before cleanup
                    if not detail_page or detail_page.isHidden():
                        logger.debug("Detail page already cleaned up")
                    cleanup_callback()

                group_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                self.animations[detail_page] = group_anim
                group_anim.finished.connect(bounce_cleanup)
        except RuntimeError:
            # Widget was already deleted, which is expected after deleteLater()
            logger.debug("Detail page already deleted during animation setup")
            cleanup_callback()
        except Exception as e:
            logger.error(f"Error in animate_detail_page_exit: {e}", exc_info=True)
            if detail_page in self.animations:
                self.animations.pop(detail_page, None)
            cleanup_callback()
