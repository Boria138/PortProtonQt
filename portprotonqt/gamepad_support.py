import pygame
import time
from PySide6 import QtCore

class GamepadSupport:
    def __init__(self, parent):
        self.parent = parent
        self.initGamepad()

    def initGamepad(self):
        pygame.init()
        pygame.joystick.init()
        self.joysticks = []
        for i in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            self.joysticks.append(joystick)

        self.last_axis_move_x = 0
        self.last_axis_move_y = 0
        self.axis_move_delay = 0.3  # задержка в секундах

        self.gamepad_timer = QtCore.QTimer(self.parent)
        self.gamepad_timer.timeout.connect(self.pollGamepad)
        self.gamepad_timer.start(50)
        print("Gamepad support initialized:", len(self.joysticks), "joystick(s) found.")

    def pollGamepad(self):
        current_time = time.time()
        for event in pygame.event.get():
            if event.type == pygame.JOYHATMOTION:
                hat_value = event.value  # (x, y)
                if hat_value[0] == 1:
                    self.parent.navigateRight()
                elif hat_value[0] == -1:
                    self.parent.navigateLeft()
                if hat_value[1] == 1:
                    self.parent.navigateUp()
                elif hat_value[1] == -1:
                    self.parent.navigateDown()
            elif event.type == pygame.JOYAXISMOTION:
                if event.axis in (0, 2):
                    if event.value > 0.5 and current_time - self.last_axis_move_x > self.axis_move_delay:
                        self.parent.navigateRight()
                        self.last_axis_move_x = current_time
                    elif event.value < -0.5 and current_time - self.last_axis_move_x > self.axis_move_delay:
                        self.parent.navigateLeft()
                        self.last_axis_move_x = current_time
                elif event.axis in (1, 3):
                    if event.value > 0.5 and current_time - self.last_axis_move_y > self.axis_move_delay:
                        self.parent.navigateDown()
                        self.last_axis_move_y = current_time
                    elif event.value < -0.5 and current_time - self.last_axis_move_y > self.axis_move_delay:
                        self.parent.navigateUp()
                        self.last_axis_move_y = current_time
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    self.parent.activateFocusedWidget()
                elif event.button == 1:
                    if self.parent.stackedWidget.currentIndex() != 0 and hasattr(self.parent, "currentDetailPage"):
                        self.parent.goBackDetailPage(self.parent.currentDetailPage)
                        del self.parent.currentDetailPage
