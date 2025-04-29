import time
import threading
from typing import Protocol, cast
from evdev import InputDevice, ecodes, list_devices
import pyudev
from PySide6 import QtCore, QtGui, QtWidgets
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

class MainWindowProtocol(Protocol):
    """Protocol describing methods expected from MainWindow."""

    def activateFocusedWidget(self) -> None:
        ...

    def goBackDetailPage(self, page: QtWidgets.QWidget | None) -> None:
        ...

    def switchTab(self, index: int) -> None:
        ...

    currentDetailPage: QtWidgets.QWidget | None

class GamepadSupport(QtCore.QObject):
    def __init__(
        self,
        main_window: MainWindowProtocol,
        axis_deadzone: float = 0.5,
        initial_axis_move_delay: float = 0.3,
        repeat_axis_move_delay: float = 0.15
    ):
        """
        Initialize gamepad support using evdev with hotplug for Qt applications.

        Args:
            main_window: Parent object with navigation methods (navigateRight, navigateLeft, etc.).
            axis_deadzone: Deadzone for D-pad (unused in evdev, kept for compatibility).
            initial_axis_move_delay: Initial delay for D-pad movement.
            repeat_axis_move_delay: Delay for repeated movements.
        """
        super().__init__(cast(QtCore.QObject, main_window))
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

        # Initialize evdev and hotplug
        self.init_gamepad()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Handle keyboard events."""
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = cast(QtGui.QKeyEvent, event)
            key = key_event.key()
            if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                self._parent.activateFocusedWidget()
                return True
            elif key == QtCore.Qt.Key.Key_Escape:
                self._parent.goBackDetailPage(getattr(self._parent, "currentDetailPage", None))
                return True
        return super().eventFilter(obj, event)

    def init_gamepad(self) -> None:
        """Initialize gamepad using evdev with hotplug support via pyudev."""
        # Initial check for connected gamepads
        self.check_gamepad()

        # Start hotplug monitoring via pyudev
        threading.Thread(target=self.run_udev_monitor, daemon=True).start()
        logger.info("Gamepad support initialized with hotplug (evdev + pyudev)")

    def run_udev_monitor(self) -> None:
        """Monitor device connection/disconnection via pyudev."""
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='input')

        observer = pyudev.MonitorObserver(monitor, self.handle_udev_event)
        observer.start()

        # Keep monitoring thread alive
        while self.running:
            time.sleep(1)

    def handle_udev_event(self, device: pyudev.Device) -> None:
        """Handle udev events (device connection/disconnection)."""
        if device.action == 'add':
            # Delay to ensure device readiness
            time.sleep(0.1)
            self.check_gamepad()
        elif device.action == 'remove' and self.gamepad:
            # Check if the current gamepad was disconnected
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

                # Handle buttons
                if event.type == ecodes.EV_KEY and current_state == 1:
                    self.handle_button(button_code)

                # Handle D-pad
                if event.type == ecodes.EV_ABS:
                    self.handle_dpad(button_code, current_state, current_time)

        except Exception as e:
            logger.error(f"Error accessing gamepad: {e}")

    def handle_button(self, button_code: int) -> None:
        """Handle gamepad button presses."""
        if button_code == 304:  # X
            self._parent.activateFocusedWidget()
        elif button_code == 305:  # Circle
            self._parent.goBackDetailPage(getattr(self._parent, "currentDetailPage", None))
        elif button_code == 308:  # Triangle
            self.open_settings()

    def open_settings(self) -> None:
        """Open the 'PortProton Settings' tab (index 4)."""
        try:
            self._parent.switchTab(4)
            logger.info("Switched to PortProton Settings tab (index: 4)")
        except Exception as e:
            logger.error(f"Failed to switch to settings tab: {e}")

    def handle_dpad(self, code: int, value: int, current_time: float) -> None:
        """Handle D-pad movements with delays."""
        # Check D-pad activity
        if value == 0:
            self.axis_moving = False
            self.current_axis_delay = self.initial_axis_move_delay
            return

        # If D-pad was just activated, perform action immediately
        if not self.axis_moving:
            self.trigger_dpad_movement(code, value)
            self.last_move_time = current_time
            self.axis_moving = True
            return

        # If D-pad is held, respect delay
        if current_time - self.last_move_time >= self.current_axis_delay:
            self.trigger_dpad_movement(code, value)
            self.last_move_time = current_time
            self.current_axis_delay = self.repeat_axis_move_delay

    def trigger_dpad_movement(self, code: int, value: int) -> None:
        """Trigger navigation based on D-pad events."""
        if code == ecodes.ABS_HAT0X:  # D-pad horizontal
            if value < 0:
                self._parent.navigateLeft()
            elif value > 0:
                self._parent.navigateRight()
        elif code == ecodes.ABS_HAT0Y:  # D-pad vertical
            if value < 0:
                self._parent.navigateUp()
            elif value > 0:
                self._parent.navigateDown()

    def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        self.running = False
        if self.gamepad:
            self.gamepad.close()
        logger.info("Gamepad support cleaned up")
