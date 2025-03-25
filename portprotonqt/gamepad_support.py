import time
import pygame
from PySide6 import QtCore
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

class GamepadSupport(QtCore.QObject):
    def __init__(self, parent, axis_deadzone=0.5, initial_axis_move_delay=0.3, repeat_axis_move_delay=0.15):
        """
        parent: Родительский объект (например, главное окно), реализующий методы:
            navigateRight, navigateLeft, navigateUp, navigateDown,
            navigateUpRight, navigateUpLeft, navigateDownRight, navigateDownLeft (опционально),
            activateFocusedWidget, goBackDetailPage, openSettings.
        """
        super().__init__(parent)
        self.parent = parent
        self.axis_deadzone = axis_deadzone
        self.initial_axis_move_delay = initial_axis_move_delay
        self.repeat_axis_move_delay = repeat_axis_move_delay
        self.current_axis_delay = self.initial_axis_move_delay
        self.last_move_time = 0
        self.latest_horizontal = 0
        self.latest_vertical = 0
        self.axis_moving = False  # Флаг, сигнализирующий, что ось уже активна
        self.joysticks = []
        self.haptics = []
        self.initGamepad()
        # Устанавливаем фильтр событий для перехвата клавиатурных событий (стрелочные клавиши)
        self.parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key_Right:
                self.parent.navigateRight()
                return True
            elif key == QtCore.Qt.Key_Left:
                self.parent.navigateLeft()
                return True
            elif key == QtCore.Qt.Key_Up:
                self.parent.navigateUp()
                return True
            elif key == QtCore.Qt.Key_Down:
                self.parent.navigateDown()
                return True
            elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self.parent.activateFocusedWidget()
                return True
            # Например, клавиша B может использоваться для возврата
            elif key == QtCore.Qt.Key_Escape:
                if hasattr(self.parent, "goBackDetailPage"):
                    self.parent.goBackDetailPage(getattr(self.parent, "currentDetailPage", None))
                return True
        return super().eventFilter(obj, event)

    def initGamepad(self):
        pygame.init()
        pygame.joystick.init()

        self.gamepad_timer = QtCore.QTimer(self.parent)
        self.gamepad_timer.timeout.connect(self.pollGamepad)
        self.gamepad_timer.start(50)
        logger.info(f"Gamepad support initialized: found {len(self.joysticks)}")

    def pollGamepad(self):
        current_time = time.time()
        for event in pygame.event.get():
            if event.type == pygame.JOYHATMOTION:
                self.handle_hat_motion(event)
            elif event.type == pygame.JOYAXISMOTION:
                self.handle_axis_motion(event, current_time)
            elif event.type == pygame.JOYBUTTONDOWN:
                self.handle_button_down(event)

    def handle_hat_motion(self, event):
        x, y = event.value
        # Обработка диагональных движений
        if x != 0 and y != 0:
            if x > 0 and y > 0:
                if hasattr(self.parent, "navigateUpRight"):
                    self.parent.navigateUpRight()
                else:
                    self.parent.navigateUp()
                    self.parent.navigateRight()
            elif x < 0 and y > 0:
                if hasattr(self.parent, "navigateUpLeft"):
                    self.parent.navigateUpLeft()
                else:
                    self.parent.navigateUp()
                    self.parent.navigateLeft()
            elif x > 0 and y < 0:
                if hasattr(self.parent, "navigateDownRight"):
                    self.parent.navigateDownRight()
                else:
                    self.parent.navigateDown()
                    self.parent.navigateRight()
            elif x < 0 and y < 0:
                if hasattr(self.parent, "navigateDownLeft"):
                    self.parent.navigateDownLeft()
                else:
                    self.parent.navigateDown()
                    self.parent.navigateLeft()
            self.vibrate()
        else:
            # Обработка одиночных движений по одной оси
            if x == 1:
                self.parent.navigateRight()
                self.vibrate()
            elif x == -1:
                self.parent.navigateLeft()
                self.vibrate()
            if y == 1:
                self.parent.navigateUp()
                self.vibrate()
            elif y == -1:
                self.parent.navigateDown()
                self.vibrate()

    def handle_axis_motion(self, event, current_time):
        # последние значения осей
        if event.axis in (0, 2):  # Горизонтальные оси
            self.latest_horizontal = event.value
        elif event.axis in (1, 3):  # Вертикальные оси
            self.latest_vertical = event.value

        # Если обе оси в пределах мертвой зоны, сбрасывается состояние
        if abs(self.latest_horizontal) < self.axis_deadzone and abs(self.latest_vertical) < self.axis_deadzone:
            self.axis_moving = False
            self.current_axis_delay = self.initial_axis_move_delay
            return

        # Если ось только что активировалась (перешла из нейтрального положения), перемещается сразу
        if not self.axis_moving:
            self.trigger_movement()
            self.last_move_time = current_time
            self.axis_moving = True
            return

        # Если ось удерживается
        if current_time - self.last_move_time >= self.current_axis_delay:
            self.trigger_movement()
            self.last_move_time = current_time
            # После первого перемещения более короткая задержка
            self.current_axis_delay = self.repeat_axis_move_delay

    def trigger_movement(self):
        h = self.latest_horizontal
        v = self.latest_vertical
        # Если оба значения превышают порог – движение диагональное
        if abs(h) > self.axis_deadzone and abs(v) > self.axis_deadzone:
            if h > 0 and v > 0:
                if hasattr(self.parent, "navigateDownRight"):
                    self.parent.navigateDownRight()
                else:
                    self.parent.navigateDown()
                    self.parent.navigateRight()
            elif h < 0 and v > 0:
                if hasattr(self.parent, "navigateDownLeft"):
                    self.parent.navigateDownLeft()
                else:
                    self.parent.navigateDown()
                    self.parent.navigateLeft()
            elif h > 0 and v < 0:
                if hasattr(self.parent, "navigateUpRight"):
                    self.parent.navigateUpRight()
                else:
                    self.parent.navigateUp()
                    self.parent.navigateRight()
            elif h < 0 and v < 0:
                if hasattr(self.parent, "navigateUpLeft"):
                    self.parent.navigateUpLeft()
                else:
                    self.parent.navigateUp()
                    self.parent.navigateLeft()
        else:
            # Обработка одиночных движений по каждой оси отдельно
            if abs(h) > self.axis_deadzone:
                if h > 0:
                    self.parent.navigateRight()
                else:
                    self.parent.navigateLeft()
            if abs(v) > self.axis_deadzone:
                if v > 0:
                    self.parent.navigateDown()
                else:
                    self.parent.navigateUp()
        self.vibrate()

    def handle_button_down(self, event):
        if event.button == 0:
            self.parent.activateFocusedWidget()
            self.vibrate(duration=50, strength=0.8)
        elif event.button == 1:
            if hasattr(self.parent, "stackedWidget") and self.parent.stackedWidget.currentIndex() != 0 and hasattr(self.parent, "currentDetailPage"):
                self.parent.goBackDetailPage(self.parent.currentDetailPage)
                del self.parent.currentDetailPage
                self.vibrate(duration=50, strength=0.8)
        elif event.button == 2:
            if hasattr(self.parent, "openSettings"):
                self.parent.openSettings()
                self.vibrate(duration=50, strength=0.8)

    def vibrate(self, duration=100, strength=0.5):
        for haptic in self.haptics:
            haptic.rumble_play(strength, duration)
