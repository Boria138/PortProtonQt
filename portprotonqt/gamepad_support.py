import time
import threading
from typing import Protocol, cast
from evdev import InputDevice, ecodes, list_devices
import pyudev
from PySide6.QtWidgets import QWidget, QStackedWidget
from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QKeyEvent
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

class MainWindowProtocol(Protocol):
    def activateFocusedWidget(self) -> None:
        ...
    def goBackDetailPage(self, page: QWidget) -> None:
        ...
    def switchTab(self, index: int) -> None:
        ...
    def openAddGameDialog(self, exe_path: str | None = None) -> None:
        ...
    currentDetailPage: QWidget
    stackedWidget: QStackedWidget
    tabButtons: dict[int, QWidget]
    gamesListWidget: QWidget

class GamepadSupport(QObject):
    def __init__(
        self,
        main_window: MainWindowProtocol,
        axis_deadzone: float = 0.5,
        initial_axis_move_delay: float = 0.3,
        repeat_axis_move_delay: float = 0.15
    ):
        """
        Initialize input support for both gamepad and keyboard with hotplug for Qt applications.

        Args:
            main_window: Parent object with navigation methods.
            axis_deadzone: Deadzone for D-pad (unused in evdev, kept for compatibility).
            initial_axis_move_delay: Initial delay for D-pad movement.
            repeat_axis_move_delay: Delay for repeated movements.
        """
        super().__init__(cast(QObject, main_window))
        self._parent = main_window
        self.axis_deadzone = axis_deadzone
        self.initial_axis_move_delay = initial_axis_move_delay
        self.repeat_axis_move_delay = repeat_axis_move_delay
        self.current_axis_delay = initial_axis_move_delay
        self.last_move_time = 0.0
        self.axis_moving = False
        self.gamepad: InputDevice | None = None
        self.gamepad_thread: threading.Thread | None = None
        self.running = True

        # Install event filter for keyboard events
        main_window.installEventFilter(self)

        # Initialize evdev and hotplug for gamepad
        self.init_gamepad()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Handle keyboard events."""
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            key = key_event.key()
            current_index = self._parent.stackedWidget.currentIndex()
            total_tabs = len(self._parent.tabButtons)

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._parent.activateFocusedWidget()
                return True
            elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace):
                self._parent.goBackDetailPage(getattr(self._parent, "currentDetailPage", None))
                return True
            elif key == Qt.Key.Key_Left:
                new_index = (current_index - 1) % total_tabs
                self._parent.switchTab(new_index)
                self._parent.tabButtons[new_index].setFocus(Qt.FocusReason.OtherFocusReason)
                return True
            elif key == Qt.Key.Key_Right:
                new_index = (current_index + 1) % total_tabs
                self._parent.switchTab(new_index)
                self._parent.tabButtons[new_index].setFocus(Qt.FocusReason.OtherFocusReason)
                return True
            elif key == Qt.Key.Key_E:
                self._parent.openAddGameDialog()
                return True
        return super().eventFilter(obj, event)

    def init_gamepad(self) -> None:
        """Initialize gamepad using evdev with hotplug support via pyudev."""
        self.check_gamepad()
        threading.Thread(target=self.run_udev_monitor, daemon=True).start()
        logger.info("Input support initialized with hotplug (evdev + pyudev)")

    def run_udev_monitor(self) -> None:
        """Monitor device connection/disconnection via pyudev."""
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='input')
        observer = pyudev.MonitorObserver(monitor, self.handle_udev_event)
        observer.start()
        while self.running:
            time.sleep(1)

    def handle_udev_event(self, device: pyudev.Device) -> None:
        """Handle udev events (device connection/disconnection)."""
        if device.action == 'add':
            time.sleep(0.1)
            self.check_gamepad()
        elif device.action == 'remove' and self.gamepad:
            if not any(self.gamepad.path == path for path in list_devices()):
                logger.info("Gamepad disconnected")
                self.gamepad = None
                if self.gamepad_thread:
                    self.gamepad_thread.join()

    def check_gamepad(self) -> None:
        """Check for gamepad connection via evdev."""
        new_gamepad = self.find_gamepad()
        if new_gamepad and new_gamepad != self.gamepad:
            logger.info(f"Gamepad connected: {new_gamepad.name}")
            self.gamepad = new_gamepad
            if self.gamepad_thread:
                self.gamepad_thread.join()
            self.gamepad_thread = threading.Thread(target=self.monitor_gamepad, daemon=True)
            self.gamepad_thread.start()

    def find_gamepad(self) -> InputDevice | None:
        """Find an available gamepad via evdev."""
        devices = [InputDevice(path) for path in list_devices()]
        for device in devices:
            capabilities = device.capabilities()
            if ecodes.EV_KEY in capabilities or ecodes.EV_ABS in capabilities:
                return device
        return None

    def monitor_gamepad(self) -> None:
        """Process gamepad events via evdev."""
        try:
            if not self.gamepad:
                return
            for event in self.gamepad.read_loop():
                if not self.running:
                    break
                if event.type not in (ecodes.EV_KEY, ecodes.EV_ABS):
                    continue
                current_time = time.time()
                button_code = event.code
                current_state = event.value
                if event.type == ecodes.EV_KEY and current_state == 1:
                    self.handle_button(button_code)
                if event.type == ecodes.EV_ABS:
                    self.handle_dpad(button_code, current_state, current_time)
        except Exception as e:
            logger.error(f"Error accessing gamepad: {e}")

    def handle_button(self, button_code: int) -> None:
        """Handle gamepad button presses."""
        current_index = self._parent.stackedWidget.currentIndex()
        total_tabs = len(self._parent.tabButtons)
        if button_code == 304:  # X
            self._parent.activateFocusedWidget()
        elif button_code == 305:  # Circle
            self._parent.goBackDetailPage(getattr(self._parent, "currentDetailPage", None))
        elif button_code == 308:  # Triangle
            self._parent.openAddGameDialog()
        elif button_code == 310:  # L1 (BTN_TL)
            new_index = (current_index - 1) % total_tabs
            self._parent.switchTab(new_index)
            self._parent.tabButtons[new_index].setFocus(Qt.FocusReason.OtherFocusReason)
        elif button_code == 311:  # R1 (BTN_TR)
            new_index = (current_index + 1) % total_tabs
            self._parent.switchTab(new_index)
            self._parent.tabButtons[new_index].setFocus(Qt.FocusReason.OtherFocusReason)

    def handle_dpad(self, code: int, value: int, current_time: float) -> None:
        """Handle D-pad movements with delays."""
        if value == 0:
            self.axis_moving = False
            self.current_axis_delay = self.initial_axis_move_delay
            return
        if not self.axis_moving:
            self.trigger_dpad_movement(code, value)
            self.last_move_time = current_time
            self.axis_moving = True
            return
        if current_time - self.last_move_time >= self.current_axis_delay:
            self.trigger_dpad_movement(code, value)
            self.last_move_time = current_time
            self.current_axis_delay = self.repeat_axis_move_delay

    def trigger_dpad_movement(self, code: int, value: int) -> None:
        """Trigger navigation based on D-pad events."""
        current_index = self._parent.stackedWidget.currentIndex()
        total_tabs = len(self._parent.tabButtons)
        if code == ecodes.ABS_HAT0X:  # D-pad horizontal
            if value < 0:  # Left
                new_index = (current_index - 1) % total_tabs
                self._parent.switchTab(new_index)
                self._parent.tabButtons[new_index].setFocus(Qt.FocusReason.OtherFocusReason)
            elif value > 0:  # Right
                new_index = (current_index + 1) % total_tabs
                self._parent.switchTab(new_index)
                self._parent.tabButtons[new_index].setFocus(Qt.FocusReason.OtherFocusReason)

    def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        self.running = False
        if self.gamepad:
            self.gamepad.close()
        logger.info("Input support cleaned up")
