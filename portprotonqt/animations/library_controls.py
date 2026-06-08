from PySide6.QtCore import (
    QAbstractAnimation,
    QByteArray,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class ExpandingSearchAnimation:
    def __init__(self, widget: QWidget, theme: object, fallback_duration: int):
        self.widget = widget
        self.theme = theme
        self.fallback_duration = fallback_duration
        self.animation = QPropertyAnimation(widget, QByteArray(b"maximumWidth"))

    def setup(self, collapsed_width: int, expanded_width: int) -> None:
        self.collapsed_width = collapsed_width
        self.expanded_width = expanded_width
        self.widget.setMaximumWidth(collapsed_width)

    def expand(self) -> None:
        self._start(self.expanded_width)

    def collapse(self) -> None:
        if getattr(self.widget, "text", lambda: "")():
            return
        self._start(self.collapsed_width)

    def _start(self, target_width: int) -> None:
        if self.animation.state() == QAbstractAnimation.State.Running:
            self.animation.stop()
        self.animation = QPropertyAnimation(self.widget, QByteArray(b"maximumWidth"))
        self.animation.setDuration(self._duration())
        self.animation.setStartValue(self.widget.maximumWidth())
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(self._easing(target_width == self.expanded_width))
        self.animation.start()

    def _duration(self) -> int:
        animation_config = getattr(self.theme, "GAME_CARD_ANIMATION", {})
        return animation_config.get("scale_anim_duration", self.fallback_duration)

    def _easing(self, opening: bool) -> QEasingCurve:
        animation_config = getattr(self.theme, "GAME_CARD_ANIMATION", {})
        key = "scale_easing_curve" if opening else "scale_easing_curve_out"
        easing_name = animation_config.get(key, QEasingCurve.Type.InOutQuad.name)
        easing_type = getattr(QEasingCurve.Type, easing_name, QEasingCurve.Type.InOutQuad)
        return QEasingCurve(easing_type)


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
        self.widget.setMaximumHeight(0)

    def toggle(self, opening: bool) -> None:
        if self.group.state() == QAbstractAnimation.State.Running:
            self.group.stop()
        if opening:
            self.widget.setVisible(True)

        target_height = self.widget.sizeHint().height() if opening else 0
        self.group = QParallelAnimationGroup(self.widget)
        height_animation = self._create_widget_animation(
            b"maximumHeight",
            self.widget.maximumHeight(),
            target_height,
        )
        opacity_animation = self._create_opacity_animation(opening, height_animation.duration())
        self.group.addAnimation(height_animation)
        self.group.addAnimation(opacity_animation)
        if not opening:
            self.group.finished.connect(self.widget.hide)
        self.group.start()

    def _create_widget_animation(
        self,
        property_name: bytes,
        start_value: object,
        end_value: object,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(self.widget, QByteArray(property_name))
        animation.setDuration(self._duration())
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(self._easing(end_value != 0))
        return animation

    def _create_opacity_animation(self, opening: bool, duration: int) -> QPropertyAnimation:
        animation = QPropertyAnimation(self.opacity_effect, QByteArray(b"opacity"))
        animation.setDuration(duration)
        animation.setStartValue(self.opacity_effect.opacity())
        animation.setEndValue(1 if opening else 0)
        animation.setEasingCurve(self._easing(opening))
        return animation

    def _duration(self) -> int:
        animation_config = getattr(self.theme, "GAME_CARD_ANIMATION", {})
        return animation_config.get("scale_anim_duration", self.fallback_duration)

    def _easing(self, opening: bool) -> QEasingCurve:
        animation_config = getattr(self.theme, "GAME_CARD_ANIMATION", {})
        key = "scale_easing_curve" if opening else "scale_easing_curve_out"
        easing_name = animation_config.get(key, QEasingCurve.Type.InOutQuad.name)
        easing_type = getattr(QEasingCurve.Type, easing_name, QEasingCurve.Type.InOutQuad)
        return QEasingCurve(easing_type)
