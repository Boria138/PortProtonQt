from PySide6.QtCore import (
    QAbstractAnimation,
    QByteArray,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def _animation_duration(theme: object, fallback_duration: int) -> int:
    animation_config = getattr(theme, "GAME_CARD_ANIMATION", {})
    return animation_config.get("scale_anim_duration", fallback_duration)


def _animation_easing(theme: object, opening: bool) -> QEasingCurve:
    animation_config = getattr(theme, "GAME_CARD_ANIMATION", {})
    key = "scale_easing_curve" if opening else "scale_easing_curve_out"
    easing_name = animation_config.get(key, QEasingCurve.Type.InOutQuad.name)
    easing_type = getattr(QEasingCurve.Type, easing_name, QEasingCurve.Type.InOutQuad)
    return QEasingCurve(easing_type)


class ExpandingSearchAnimation:
    def __init__(self, widget: QWidget, theme: object, fallback_duration: int):
        self.widget = widget
        self.theme = theme
        self.fallback_duration = fallback_duration
        self.group = QParallelAnimationGroup(widget)

    def setup(self, collapsed_width: int, expanded_width: int) -> None:
        self.collapsed_width = collapsed_width
        self.expanded_width = expanded_width
        self.widget.setFixedWidth(collapsed_width)

    def expand(self) -> None:
        self._start(self.expanded_width)

    def collapse(self) -> None:
        if getattr(self.widget, "text", lambda: "")():
            return
        self._start(self.collapsed_width)

    def _start(self, target_width: int) -> None:
        if self.group.state() == QAbstractAnimation.State.Running:
            self.group.stop()
        self.group = QParallelAnimationGroup(self.widget)
        self.group.addAnimation(self._create_width_animation(b"minimumWidth", target_width))
        self.group.addAnimation(self._create_width_animation(b"maximumWidth", target_width))
        self.group.start()

    def _create_width_animation(self, property_name: bytes, target_width: int) -> QPropertyAnimation:
        animation = QPropertyAnimation(self.widget, QByteArray(property_name))
        animation.setDuration(_animation_duration(self.theme, self.fallback_duration))
        animation.setStartValue(self.widget.width())
        animation.setEndValue(target_width)
        animation.setEasingCurve(_animation_easing(self.theme, target_width == self.expanded_width))
        return animation


class LibraryControlsAnimation:
    def __init__(self, widget: QWidget, theme: object, fallback_duration: int):
        self.widget = widget
        self.theme = theme
        self.fallback_duration = fallback_duration
        self.opacity_effect = QGraphicsOpacityEffect(widget)
        self.opacity_effect.setOpacity(0)
        self.widget.setGraphicsEffect(self.opacity_effect)
        self.group = QParallelAnimationGroup(widget)

    def setup_hidden(self) -> None:
        self.widget.setVisible(False)

    def toggle(self, opening: bool) -> None:
        if self.group.state() == QAbstractAnimation.State.Running:
            self.group.stop()
        if opening:
            self.widget.setVisible(True)
            self.widget.raise_()

        self.group = QParallelAnimationGroup(self.widget)
        geometry_animation = self._create_geometry_animation(opening)
        opacity_animation = self._create_opacity_animation(opening, geometry_animation.duration())
        self.group.addAnimation(geometry_animation)
        self.group.addAnimation(opacity_animation)
        if not opening:
            self.group.finished.connect(self.widget.hide)
        self.group.start()

    def _create_geometry_animation(self, opening: bool) -> QPropertyAnimation:
        target_rect = self.widget.geometry()
        hidden_rect = QRect(target_rect.right(), target_rect.y(), 0, target_rect.height())
        start_rect = hidden_rect if opening else target_rect
        end_rect = target_rect if opening else hidden_rect
        return self._create_widget_animation(b"geometry", start_rect, end_rect)

    def _create_widget_animation(
        self,
        property_name: bytes,
        start_value: object,
        end_value: object,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(self.widget, QByteArray(property_name))
        animation.setDuration(_animation_duration(self.theme, self.fallback_duration))
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(_animation_easing(self.theme, end_value != 0))
        return animation

    def _create_opacity_animation(self, opening: bool, duration: int) -> QPropertyAnimation:
        animation = QPropertyAnimation(self.opacity_effect, QByteArray(b"opacity"))
        animation.setDuration(duration)
        animation.setStartValue(self.opacity_effect.opacity())
        animation.setEndValue(1 if opening else 0)
        animation.setEasingCurve(_animation_easing(self.theme, opening))
        return animation
