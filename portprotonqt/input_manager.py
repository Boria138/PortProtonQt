import time
import threading
from typing import Protocol, cast
from evdev import InputDevice, ecodes, list_devices
import pyudev
from PySide6.QtWidgets import QWidget, QStackedWidget, QApplication, QScrollArea
from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QKeyEvent
from portprotonqt.logger import get_logger
from portprotonqt.image_utils import FullscreenDialog
from portprotonqt.custom_widgets import NavLabel
from portprotonqt.game_card import GameCard

logger = get_logger(__name__)

class MainWindowProtocol(Protocol):
    def activateFocusedWidget(self) -> None:
        ...
    def goBackDetailPage(self, page: QWidget | None) -> None:
        ...
    def switchTab(self, index: int) -> None:
        ...
    def openAddGameDialog(self, exe_path: str | None = None) -> None:
        ...
    def toggleGame(self, exec_line: str | None, button: QWidget | None = None) -> None:
        ...
    stackedWidget: QStackedWidget
    tabButtons: dict[int, QWidget]
    gamesListWidget: QWidget
    currentDetailPage: QWidget | None
    current_exec_line: str | None

# Mapping of actions to evdev button codes, includes PlayStation, Xbox, and Switch controllers (https://www.kernel.org/doc/html/v4.12/input/gamepad.html)
BUTTONS = {
    # South button: X (PlayStation), A (Xbox), B (Switch Joy-Con south)
    'confirm':   {ecodes.BTN_SOUTH, ecodes.BTN_A},
    # East button: Circle (PS), B (Xbox), A (Switch Joy-Con east)
    'back':      {ecodes.BTN_EAST,  ecodes.BTN_B},
    # North button: Triangle (PS), Y (Xbox), X (Switch Joy-Con north)
    'add_game':  {ecodes.BTN_NORTH, ecodes.BTN_Y},
    # Shoulder buttons: L1/L2 (PS), LB (Xbox), L (Switch): BTN_TL, BTN_TL2
    'prev_tab':  {ecodes.BTN_TL,    ecodes.BTN_TL2},
    # Shoulder buttons: R1/R2 (PS), RB (Xbox), R (Switch): BTN_TR, BTN_TR2
    'next_tab':  {ecodes.BTN_TR,    ecodes.BTN_TR2},
    # Optional: stick presses on Switch Joy-Con
    'confirm_stick': {ecodes.BTN_THUMBL, ecodes.BTN_THUMBR},
    # Start/select/home for menu/back
    'menu':      {ecodes.BTN_START, ecodes.BTN_SELECT, ecodes.BTN_MODE},
}

class InputManager(QObject):
    """
    Manages input from gamepads and keyboards for navigating the application interface.
    Supports gamepad hotplugging, button and axis events, and keyboard event filtering
    for seamless UI interaction.
    """
    def __init__(
        self,
        main_window: MainWindowProtocol,
        axis_deadzone: float = 0.5,
        initial_axis_move_delay: float = 0.3,
        repeat_axis_move_delay: float = 0.15
    ):
        super().__init__(cast(QObject, main_window))
        self._parent = main_window
        # Ensure attributes exist on main_window
        self._parent.currentDetailPage = getattr(self._parent, 'currentDetailPage', None)
        self._parent.current_exec_line = getattr(self._parent, 'current_exec_line', None)

        self.axis_deadzone = axis_deadzone
        self.initial_axis_move_delay = initial_axis_move_delay
        self.repeat_axis_move_delay = repeat_axis_move_delay
        self.current_axis_delay = initial_axis_move_delay
        self.last_move_time = 0.0
        self.axis_moving = False
        self.gamepad: InputDevice | None = None
        self.gamepad_thread: threading.Thread | None = None
        self.running = True

        # Install keyboard event filter
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        else:
            logger.error("QApplication instance is None, cannot install event filter")

        # Initialize evdev + hotplug
        self.init_gamepad()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        app = QApplication.instance()
        if not app:
            return super().eventFilter(obj, event)

        # 1) Интересуют только нажатия клавиш
        if not (isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress):
            return super().eventFilter(obj, event)

        key = event.key()
        focused = QApplication.focusWidget()
        popup = QApplication.activePopupWidget()

        # 2) Если открыт любой popup — не перехватываем ENTER, ESC и стрелки
        if popup:
            # возвращаем False, чтобы событие пошло дальше в Qt и закрыло popup как нужно
            return False

        # 3) Навигация в полноэкранном просмотре
        active_win = QApplication.activeWindow()
        if isinstance(active_win, FullscreenDialog):
            if key == Qt.Key.Key_Right:
                active_win.show_next()
                return True
            if key == Qt.Key.Key_Left:
                active_win.show_prev()
                return True
            if key in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                active_win.close()
                return True

        # 4) На странице деталей Enter запускает/останавливает игру
        if self._parent.currentDetailPage and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._parent.current_exec_line:
                self._parent.toggleGame(self._parent.current_exec_line, None)
                return True

        # 5) Навигация по карточкам в Library
        if self._parent.stackedWidget.currentIndex() == 0:
            game_cards = self._parent.gamesListWidget.findChildren(GameCard)
            scroll_area = self._parent.gamesListWidget.parentWidget()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parentWidget()
            if not scroll_area:
                logger.warning("No QScrollArea found for gamesListWidget")

            if isinstance(focused, GameCard):
                current_index = game_cards.index(focused) if focused in game_cards else -1
                if key == Qt.Key.Key_Down:
                    if current_index >= 0 and current_index + 1 < len(game_cards):
                        next_card = game_cards[current_index + 1]
                        next_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(next_card, 50, 50)
                        return True
                elif key == Qt.Key.Key_Up:
                    if current_index > 0:
                        prev_card = game_cards[current_index - 1]
                        prev_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(prev_card, 50, 50)
                        return True
                    elif current_index == 0:
                        self._parent.tabButtons[0].setFocus()
                        return True
                elif key == Qt.Key.Key_Left:
                    if current_index > 0:
                        prev_card = game_cards[current_index - 1]
                        prev_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(prev_card, 50, 50)
                        return True
                elif key == Qt.Key.Key_Right:
                    if current_index >= 0 and current_index + 1 < len(game_cards):
                        next_card = game_cards[current_index + 1]
                        next_card.setFocus()
                        if scroll_area:
                            scroll_area.ensureWidgetVisible(next_card, 50, 50)
                        return True

        # 6) Переключение вкладок ←/→
        idx = self._parent.stackedWidget.currentIndex()
        total = len(self._parent.tabButtons)
        if key == Qt.Key.Key_Left and not isinstance(focused, GameCard):
            new = (idx - 1) % total
            self._parent.switchTab(new)
            self._parent.tabButtons[new].setFocus()
            return True
        if key == Qt.Key.Key_Right and not isinstance(focused, GameCard):
            new = (idx + 1) % total
            self._parent.switchTab(new)
            self._parent.tabButtons[new].setFocus()
            return True

        # 7) Спуск в содержимое вкладки ↓
        if key == Qt.Key.Key_Down:
            if isinstance(focused, NavLabel):
                page = self._parent.stackedWidget.currentWidget()
                focusables = page.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                if focusables:
                    focusables[0].setFocus()
                    return True
            else:
                if focused is not None:
                    focused.focusNextChild()
                    return True

        # 8) Подъём по содержимому вкладки ↑
        if key == Qt.Key.Key_Up:
            if isinstance(focused, NavLabel):
                return True  # Не даём уйти выше NavLabel
            if focused is not None:
                focused.focusPreviousChild()
                return True

        # 9) Общие: Activate, Back, Add
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._parent.activateFocusedWidget()
            return True
        elif key == Qt.Key.Key_Escape:
            self._parent.goBackDetailPage(self._parent.currentDetailPage)
            return True
        elif key == Qt.Key.Key_E:
            self._parent.openAddGameDialog()
            return True

        return super().eventFilter(obj, event)

    def init_gamepad(self) -> None:
        self.check_gamepad()
        threading.Thread(target=self.run_udev_monitor, daemon=True).start()
        logger.info("Input support initialized with hotplug (evdev + pyudev)")

    def run_udev_monitor(self) -> None:
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='input')
        observer = pyudev.MonitorObserver(monitor, self.handle_udev_event)
        observer.start()
        while self.running:
            time.sleep(1)

    def handle_udev_event(self, action: str, device: pyudev.Device) -> None:
        if action == 'add':
            time.sleep(0.1)
            self.check_gamepad()
        elif action == 'remove' and self.gamepad:
            if not any(self.gamepad.path == path for path in list_devices()):
                logger.info("Gamepad disconnected")
                self.gamepad = None
                if self.gamepad_thread:
                    self.gamepad_thread.join()

    def check_gamepad(self) -> None:
        new_gamepad = self.find_gamepad()
        if new_gamepad and new_gamepad != self.gamepad:
            logger.info(f"Gamepad connected: {new_gamepad.name}")
            self.gamepad = new_gamepad
            if self.gamepad_thread:
                self.gamepad_thread.join()
            self.gamepad_thread = threading.Thread(target=self.monitor_gamepad, daemon=True)
            self.gamepad_thread.start()

    def find_gamepad(self) -> InputDevice | None:
        devices = [InputDevice(path) for path in list_devices()]
        for device in devices:
            caps = device.capabilities()
            if ecodes.EV_KEY in caps or ecodes.EV_ABS in caps:
                return device
        return None

    def monitor_gamepad(self) -> None:
        try:
            if not self.gamepad:
                return
            for event in self.gamepad.read_loop():
                if not self.running:
                    break
                if event.type not in (ecodes.EV_KEY, ecodes.EV_ABS):
                    continue
                now = time.time()
                if event.type == ecodes.EV_KEY and event.value == 1:
                    self.handle_button(event.code)
                elif event.type == ecodes.EV_ABS:
                    self.handle_dpad(event.code, event.value, now)
        except Exception as e:
            logger.error(f"Error accessing gamepad: {e}")

    def handle_button(self, button_code: int) -> None:
        app = QApplication.instance()
        if app is None:
            logger.error("QApplication instance is None")
            return
        active = QApplication.activeWindow()

        # FullscreenDialog
        if isinstance(active, FullscreenDialog):
            if button_code in BUTTONS['prev_tab']:
                active.show_prev()
            elif button_code in BUTTONS['next_tab']:
                active.show_next()
            elif button_code in BUTTONS['back']:
                active.close()
            return

        # Game launch on detail page
        if (button_code in BUTTONS['confirm'] or button_code in BUTTONS['confirm_stick']) and self._parent.currentDetailPage is not None:
            if self._parent.current_exec_line:
                self._parent.toggleGame(self._parent.current_exec_line, None)
                return

        # Standard navigation
        if button_code in BUTTONS['confirm'] or button_code in BUTTONS['confirm_stick']:
            self._parent.activateFocusedWidget()
        elif button_code in BUTTONS['back'] or button_code in BUTTONS['menu']:
            self._parent.goBackDetailPage(getattr(self._parent, 'currentDetailPage', None))
        elif button_code in BUTTONS['add_game']:
            self._parent.openAddGameDialog()
        elif button_code in BUTTONS['prev_tab']:
            idx = (self._parent.stackedWidget.currentIndex() - 1) % len(self._parent.tabButtons)
            self._parent.switchTab(idx)
            self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)
        elif button_code in BUTTONS['next_tab']:
            idx = (self._parent.stackedWidget.currentIndex() + 1) % len(self._parent.tabButtons)
            self._parent.switchTab(idx)
            self._parent.tabButtons[idx].setFocus(Qt.FocusReason.OtherFocusReason)

    def handle_dpad(self, code: int, value: int, current_time: float) -> None:
        app = QApplication.instance()
        if app is None:
            logger.error("QApplication instance is None")
            return
        active = QApplication.activeWindow()

        # Fullscreen horizontal
        if isinstance(active, FullscreenDialog) and code == ecodes.ABS_HAT0X:
            if value < 0:
                active.show_prev()
            elif value > 0:
                active.show_next()
            return

        # Vertical navigation (DPAD up/down)
        if code == ecodes.ABS_HAT0Y:
            # ignore release
            if value == 0:
                return
            focused = QApplication.focusWidget()
            page = self._parent.stackedWidget.currentWidget()
            if value > 0:
                # down
                if isinstance(focused, NavLabel):
                    focusables = page.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively)
                    focusables = [w for w in focusables if w.focusPolicy() & Qt.FocusPolicy.StrongFocus]
                    if focusables:
                        focusables[0].setFocus()
                        return
                elif focused:
                    focused.focusNextChild()
                    return
            elif value < 0 and focused:
                # up
                focused.focusPreviousChild()
                return

        # Horizontal wrap navigation repeat logic
        if code != ecodes.ABS_HAT0X:
            return
        if value == 0:
            self.axis_moving = False
            self.current_axis_delay = self.initial_axis_move_delay
            return
        if not self.axis_moving:
            self.trigger_dpad_movement(code, value)
            self.last_move_time = current_time
            self.axis_moving = True
        elif current_time - self.last_move_time >= self.current_axis_delay:
            self.trigger_dpad_movement(code, value)
            self.last_move_time = current_time
            self.current_axis_delay = self.repeat_axis_move_delay

    def trigger_dpad_movement(self, code: int, value: int) -> None:
        if code != ecodes.ABS_HAT0X:
            return
        idx = self._parent.stackedWidget.currentIndex()
        if value < 0:
            new = (idx - 1) % len(self._parent.tabButtons)
        else:
            new = (idx + 1) % len(self._parent.tabButtons)
        self._parent.switchTab(new)
        self._parent.tabButtons[new].setFocus(Qt.FocusReason.OtherFocusReason)

    def cleanup(self) -> None:
        self.running = False
        if self.gamepad:
            self.gamepad.close()
        logger.info("Input support cleaned up")
