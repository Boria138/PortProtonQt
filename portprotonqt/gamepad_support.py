import time
import pygame
from PySide6 import QtCore

class GamepadSupport:
    def __init__(self, parent, axis_deadzone=0.5, axis_move_delay=0.3):
        """
        parent: Родительский объект (например, главное окно), который реализует методы:
            navigateRight, navigateLeft, navigateUp, navigateDown,
            а также опционально: navigateUpRight, navigateUpLeft, navigateDownRight, navigateDownLeft,
            activateFocusedWidget, goBackDetailPage, openSettings.
        axis_deadzone: Порог, ниже которого осевой сигнал игнорируется (чтобы избежать дребезга).
        axis_move_delay: Минимальное время между навигационными перемещениями.
        """
        self.parent = parent
        self.axis_deadzone = axis_deadzone
        self.axis_move_delay = axis_move_delay
        self.last_move_time = 0
        self.latest_horizontal = 0
        self.latest_vertical = 0
        self.joysticks = []
        self.haptics = []
        self.initGamepad()

    def initGamepad(self):
        pygame.init()
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            self.joysticks.append(joystick)
            try:
                haptic = pygame.haptic.Haptic(joystick)
                haptic.init()
                self.haptics.append(haptic)
                print(f"Joystick {i} haptic feedback initialized.")
            except Exception as e:
                print(f"Joystick {i} does not support haptic feedback: {e}")

        self.gamepad_timer = QtCore.QTimer(self.parent)
        self.gamepad_timer.timeout.connect(self.pollGamepad)
        self.gamepad_timer.start(50)
        print("Gamepad support initialized:", len(self.joysticks), "joystick(s) found.")

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
        # Обработка hat-событий: event.value возвращает (x, y)
        x, y = event.value
        if x != 0 and y != 0:
            # Диагональное движение
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
            # Если задействована только одна ось, обрабатываем отдельно.
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
        # Обновляем значения для горизонтальных и вертикальных осей
        if event.axis in (0, 2):  # Горизонтальные оси
            self.latest_horizontal = event.value
        elif event.axis in (1, 3):  # Вертикальные оси
            self.latest_vertical = event.value

        # Если прошло достаточно времени с последнего перемещения
        if current_time - self.last_move_time < self.axis_move_delay:
            return

        h = self.latest_horizontal
        v = self.latest_vertical

        # Если оба значения превышают порог, считаем это диагональным движением
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
            self.last_move_time = current_time
            self.vibrate()
        else:
            # Если только одна ось превышает порог, обрабатываем отдельно.
            if abs(h) > self.axis_deadzone:
                if h > 0:
                    self.parent.navigateRight()
                else:
                    self.parent.navigateLeft()
                self.last_move_time = current_time
                self.vibrate()
            if abs(v) > self.axis_deadzone:
                if v > 0:
                    self.parent.navigateDown()
                else:
                    self.parent.navigateUp()
                self.last_move_time = current_time
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
        """
        Запускает тактильную виброотдачу на всех устройствах, поддерживающих её.
        duration: длительность вибрации в миллисекундах.
        strength: сила вибрации от 0.0 до 1.0.
        """
        for haptic in self.haptics:
            try:
                haptic.rumble_play(strength, duration)
            except Exception as e:
                print("Error during haptic feedback:", e)

if __name__ == "__main__":
    print("Обнаружена поддержка тактильной виброотдачи.")
