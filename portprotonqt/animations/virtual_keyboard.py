from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import (
    QAbstractAnimation,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget
from shiboken6 import isValid


class VirtualKeyboardAnimations:
    def __init__(self, keyboard: QWidget, theme) -> None:
        self.keyboard = keyboard
        self.theme = theme
        self.animation: QAbstractAnimation | None = None
        self.opacity_effect: QGraphicsOpacityEffect | None = None

    def stop(self) -> None:
        if self.animation:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None

    def animate_show(self, start_pos: QPoint, end_pos: QPoint, enabled: bool) -> None:
        self.stop()
        if not enabled:
            self._clear_opacity_effect()
            self.keyboard.move(end_pos)
            return

        animation_type = self._get_animation_type()
        duration = self._duration(animation_type, "slide")
        if animation_type == "fade":
            self.keyboard.move(end_pos)
            self.animation = self._opacity_animation(0.0, 1.0, duration, "OutCubic")
        elif animation_type == "slide_fade":
            self.keyboard.move(start_pos)
            pos_anim = self._position_animation(start_pos, end_pos, duration, "OutCubic")
            opacity_anim = self._opacity_animation(0.0, 1.0, duration, "OutCubic")
            group = QParallelAnimationGroup()
            group.addAnimation(pos_anim)
            group.addAnimation(opacity_anim)
            self.animation = group
        elif animation_type == "slide_bounce":
            self._clear_opacity_effect()
            self.keyboard.move(start_pos)
            self.animation = self._position_animation(start_pos, end_pos, duration, "OutBack")
        else:
            self._clear_opacity_effect()
            self.keyboard.move(start_pos)
            self.animation = self._position_animation(start_pos, end_pos, duration, "OutCubic")

        if self.animation:
            self.animation.start()

    def animate_hide(self, start_pos: QPoint, end_pos: QPoint, enabled: bool, on_finished: Callable[[], None]) -> None:
        self.stop()
        if not enabled:
            self._clear_opacity_effect()
            on_finished()
            return

        animation_type = self._get_animation_type()
        duration = self._duration(animation_type, "slide")
        if animation_type == "fade":
            self.keyboard.move(start_pos)
            self.animation = self._opacity_animation(1.0, 0.0, duration, "InCubic")
        elif animation_type == "slide_fade":
            self.keyboard.move(start_pos)
            pos_anim = self._position_animation(start_pos, end_pos, duration, "InCubic")
            opacity_anim = self._opacity_animation(1.0, 0.0, duration, "InCubic")
            group = QParallelAnimationGroup()
            group.addAnimation(pos_anim)
            group.addAnimation(opacity_anim)
            self.animation = group
        elif animation_type == "slide_bounce":
            self._clear_opacity_effect()
            self.keyboard.move(start_pos)
            self.animation = self._position_animation(start_pos, end_pos, duration, "InBack")
        else:
            self._clear_opacity_effect()
            self.keyboard.move(start_pos)
            self.animation = self._position_animation(start_pos, end_pos, duration, "InCubic")

        if self.animation:
            self.animation.finished.connect(on_finished)
            self.animation.start()

    def _get_animation_type(self) -> str:
        animation_type = str(getattr(self.theme, "virtual_keyboard_animation_type", "slide"))
        if animation_type not in {"slide", "fade", "slide_fade", "slide_bounce"}:
            return "slide"
        return animation_type

    def _duration(self, animation_type: str, default_kind: str) -> int:
        specific_attr = f"virtual_keyboard_{animation_type}_animation_duration"
        specific_duration = getattr(self.theme, specific_attr, None)
        if specific_duration is not None:
            return max(0, int(specific_duration))
        fallback_attr = f"virtual_keyboard_{default_kind}_animation_duration"
        fallback_duration = getattr(self.theme, fallback_attr, 160)
        return max(0, int(fallback_duration))

    def _position_animation(self, start_pos: QPoint, end_pos: QPoint, duration: int, curve_name: str) -> QPropertyAnimation:
        animation = QPropertyAnimation(self.keyboard, b"pos", self.keyboard)
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(self._easing_curve(curve_name))
        return animation

    def _opacity_animation(self, start_opacity: float, end_opacity: float, duration: int, curve_name: str) -> QPropertyAnimation:
        effect = self._ensure_opacity_effect()
        effect.setOpacity(start_opacity)
        animation = QPropertyAnimation(effect, b"opacity", self.keyboard)
        animation.setDuration(duration)
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setEasingCurve(self._easing_curve(curve_name))
        if end_opacity >= 1.0:
            animation.finished.connect(self._clear_opacity_effect)
        return animation

    def _ensure_opacity_effect(self) -> QGraphicsOpacityEffect:
        if self.opacity_effect is None or not isValid(self.opacity_effect):
            self.opacity_effect = QGraphicsOpacityEffect(self.keyboard)
        try:
            self.keyboard.setGraphicsEffect(self.opacity_effect)
        except RuntimeError:
            self.opacity_effect = QGraphicsOpacityEffect(self.keyboard)
            self.keyboard.setGraphicsEffect(self.opacity_effect)
        return self.opacity_effect

    def _clear_opacity_effect(self) -> None:
        if self.opacity_effect and isValid(self.opacity_effect):
            try:
                if self.keyboard.graphicsEffect() is self.opacity_effect:
                    self.keyboard.setGraphicsEffect(cast(Any, None))
            except RuntimeError:
                pass
            try:
                self.opacity_effect.deleteLater()
            except RuntimeError:
                pass
        self.opacity_effect = None

    def _easing_curve(self, curve_name: str) -> QEasingCurve:
        try:
            return QEasingCurve(QEasingCurve.Type[curve_name])
        except KeyError:
            return QEasingCurve(QEasingCurve.Type.OutCubic)
