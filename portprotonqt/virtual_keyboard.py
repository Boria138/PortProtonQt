from typing import cast, Any
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QPushButton, QGridLayout,
                               QSizePolicy, QWidget, QLineEdit, QScrollArea)
from PySide6.QtCore import Qt, Signal, QProcess, QSize, QEvent
from PySide6.QtGui import QPixmap, QIcon
from portprotonqt.keyboard_layouts import keyboard_layouts
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config_utils import read_theme_from_config

theme_manager = ThemeManager()

class VirtualKeyboard(QFrame):
    keyPressed = Signal(str)

    def __init__(self, parent: QWidget | None = None, theme=None, button_width: int = 80):
        super().__init__(parent)
        self._parent: QWidget | None = parent
        self.available_layouts: list[str] = self.get_layouts_setxkbmap()
        self.theme = theme if theme else theme_manager.apply_theme(read_theme_from_config())
        if not self.available_layouts:
            self.available_layouts.append('en')
        self.current_layout: str = self.available_layouts[0]

        self.focus_timer = None
        self.focus_delay = 150  # Delay between moves in ms
        self.last_focus_time = 0

        self.backspace_pressed = False
        self.backspace_timer = None
        self.backspace_initial_delay = 500
        self.backspace_repeat_delay = 50
        self.gamepad_x_pressed = False
        self.caps_lock = False
        self.shift_pressed = False
        self.current_input_widget = None
        self.cursor_visible = True
        self.last_focused_button = None

        self.base_button_width = 40
        self.base_min_width = 574
        self.button_width = button_width
        self.max_button_width = button_width
        self.button_height = 40
        self.spacing = 4
        self.margins = 10
        self.num_cols = 14

        # Find input_manager and main_window
        self.input_manager: Any = None
        self.main_window: Any = None
        parent_widget: QWidget | None = self._parent
        while parent_widget:
            if hasattr(parent_widget, 'input_manager'):
                self.input_manager = cast(Any, parent_widget).input_manager
                self.main_window = cast(Any, parent_widget)
            parent_widget = cast(QWidget | None, parent_widget.parent())


        self.current_theme_name = read_theme_from_config()
        self.initUI()
        if self._parent and isinstance(self._parent, QWidget):
            self._parent.installEventFilter(self)
        self.hide()

        self.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_STYLE)

    def _apply_responsive_metrics(self) -> None:
        if not self._parent or not isinstance(self._parent, QWidget):
            return

        available_width = max(0, self._parent.width() - self.margins * 2)
        width_without_spacing = available_width - self.spacing * (self.num_cols - 1)
        new_button_width = max(18, width_without_spacing // self.num_cols)
        self.button_width = min(self.max_button_width, new_button_width)

    def _sync_keyboard_geometry(self) -> None:
        if not self._parent or not isinstance(self._parent, QWidget):
            return

        self._apply_responsive_metrics()
        keyboard_height = 220
        self.setFixedWidth(self._parent.width())
        self.setFixedHeight(keyboard_height)
        self.move(0, self._parent.height() - keyboard_height)

    def highlight_cursor_position(self):
        """Highlight current cursor position"""
        if not self.current_input_widget or not isinstance(self.current_input_widget, QLineEdit):
            return

        try:
            # Just set cursor to position without selection
            self.current_input_widget.setCursorPosition(self.current_input_widget.cursorPosition())
        except RuntimeError:
            self.current_input_widget = None

    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.keyboard_layout = QGridLayout()
        self.keyboard_layout.setSpacing(self.spacing)
        self.keyboard_layout.setContentsMargins(self.margins // 2, self.margins // 2, self.margins // 2, self.margins // 2)
        self.create_keyboard()

        self.keyboard_container = QWidget()
        self.keyboard_container.setLayout(self.keyboard_layout)
        ratio = self.button_width / self.base_button_width
        self.keyboard_container.setMinimumWidth(int(self.base_min_width * ratio))
        self.keyboard_container.setMinimumHeight(220)
        self.keyboard_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout.addWidget(self.keyboard_container, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def run_shell_command(self, cmd: str) -> str | None:
        process = QProcess(self)
        process.start("sh", ["-c", cmd])
        process.waitForFinished(-1)
        if process.exitCode() == 0:
            output_bytes = process.readAllStandardOutput().data()
            if isinstance(output_bytes, memoryview):
                output_str = output_bytes.tobytes().decode('utf-8').strip()
            else:
                output_str = output_bytes.decode('utf-8').strip()
            return output_str
        else:
            return None

    def get_layouts_setxkbmap(self) -> list[str]:
        """Get layouts used in system, return list like ['us', 'ru'] etc."""
        cmd = r'''localectl status | awk -F: '/X11 Layout/ {gsub(/^[ \t]+/, "", $2); print $2}' '''
        output = self.run_shell_command(cmd)
        if output:
            layouts = [lang.strip() for lang in output.split(',') if lang.strip()]
            return layouts if layouts else ['en']
        else:
            return ['en']

    def create_keyboard(self):
        # Main layouts with Shift
        # Filter available layouts

        LAYOUT_MAP = {'us': 'en'}

        # Assume keyboard_layouts is dict[str, dict[str, list[list[str]]]]
        self.layouts: dict[str, dict[str, list[list[str]]]] = {
            lang: keyboard_layouts.get(LAYOUT_MAP.get(lang, lang), keyboard_layouts['en'])
            for lang in self.available_layouts
        }

        self.current_layout = (self.current_layout if self.current_layout in self.layouts else next(iter(self.layouts.keys()), None) or 'en')

        self.buttons: dict[str, QPushButton] = {}
        self.update_keyboard()

    def set_gamepad_icon(self, button, icon_type, gtype=''):
        """Set gamepad icon on button based on type"""
        if icon_type in ['back', 'add_game']:
            icon_name = self.main_window.get_button_icon(icon_type, gtype)
        else:  # nav left/right
            if icon_type in ['left', 'right']:
                direction = icon_type
                icon_name = self.main_window.get_nav_icon(direction, gtype)
            else:
                direction = 'left' if icon_type == 'left' else 'right'
                icon_name = self.main_window.get_nav_icon(direction, gtype)

        icon_path = theme_manager.get_theme_image(icon_name, self.current_theme_name)
        pixmap = QPixmap()
        if icon_path:
            pixmap.load(str(icon_path))
        if not pixmap.isNull():
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(20, 20))
            return
        else:
            # Fallback to placeholder
            placeholder = theme_manager.get_theme_image("placeholder", self.current_theme_name)
            if placeholder:
                button.setIcon(QIcon(placeholder))
                button.setIconSize(QSize(20, 20))
                return

    def update_keyboard(self):
        self._apply_responsive_metrics()
        coords = self._save_focused_coords()

        # Clear previous buttons
        while self.keyboard_layout.count():
            item = self.keyboard_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        fixed_w = self.button_width
        fixed_h = self.button_height

        # Select current layout (normal or with shift)
        layout_mode = 'shift' if self.shift_pressed else 'normal'
        layout_data = self.layouts.get(self.current_layout, {})
        buttons: list[list[str]] = layout_data.get(layout_mode, [])

        # Add main buttons
        for row_idx, row in enumerate(buttons):
            for col_idx, key in enumerate(row):
                button = QPushButton(key)
                button.setFixedSize(fixed_w, fixed_h)

                # Handlers for CAPS and left Shift
                if key == 'CAPS':
                    button.setCheckable(True)
                    button.setChecked(self.caps_lock)
                    button.clicked.connect(self.on_caps_click)
                elif key == '⬆':  # Left Shift
                    button.setCheckable(True)
                    button.setChecked(self.shift_pressed)
                    button.clicked.connect(lambda checked: self.on_shift_click(checked))
                    # Add gamepad icon for Shift (RB/R)
                    gtype = self.input_manager.gamepad_type
                    self.set_gamepad_icon(button, 'right', gtype)
                else:
                    button.clicked.connect(lambda checked=False, k=key: self.on_button_click(k))

                self.keyboard_layout.addWidget(button, row_idx, col_idx)
                self.buttons[key] = button

        # Bottom row (special buttons)
        shift = QPushButton('⬆')
        shift.setFixedSize(fixed_w * 3 + 2 * self.spacing, fixed_h)
        shift.setCheckable(True)
        shift.setChecked(self.shift_pressed)
        shift.clicked.connect(lambda checked: self.on_shift_click(checked))
        # Add gamepad icon for Shift (RB/R)
        gtype = self.input_manager.gamepad_type
        self.set_gamepad_icon(shift, 'right', gtype)
        self.keyboard_layout.addWidget(shift, 3, 11, 1, 3)

        button = QPushButton('CAPS')
        button.setCheckable(True)
        button.setChecked(self.caps_lock)
        button.clicked.connect(self.on_caps_click)

        space = QPushButton('Space')
        space.setFixedSize(fixed_w * 5 + 4 * self.spacing, fixed_h)
        space.clicked.connect(lambda: self.on_button_click(' '))
        self.keyboard_layout.addWidget(space, 4, 1, 1, 5)

        backspace = QPushButton('⌫')
        backspace.setFixedSize(fixed_w, fixed_h)
        backspace.pressed.connect(self.on_backspace_pressed)
        backspace.released.connect(self.stop_backspace_repeat)
        # Add gamepad icon for Backspace (X/Triangle)
        gtype = self.input_manager.gamepad_type
        self.set_gamepad_icon(backspace, 'add_game', gtype)
        self.keyboard_layout.addWidget(backspace, 0, 13, 1, 1)

        enter = QPushButton('Enter')
        enter.setFixedSize(fixed_w * 2 + self.spacing, fixed_h)
        enter.clicked.connect(self.on_enter_click)
        self.keyboard_layout.addWidget(enter, 2, 12, 1, 2)

        lang = QPushButton('🌐')
        lang.setFixedSize(fixed_w, fixed_h)
        lang.clicked.connect(self.on_lang_click)
        # Add gamepad icon for Lang (LB/L)
        gtype = self.input_manager.gamepad_type
        self.set_gamepad_icon(lang, 'left', gtype)
        self.keyboard_layout.addWidget(lang, 4, 0, 1, 1)

        clear = QPushButton('Clear')
        clear.setFixedSize(fixed_w * 2 + self.spacing, fixed_h)
        clear.clicked.connect(self.on_clear_click)
        self.keyboard_layout.addWidget(clear, 4, 10, 1, 2)

        up = QPushButton('▲')
        up.setFixedSize(fixed_w, fixed_h)
        up.clicked.connect(self.up_key)  # Handle mouse click - cursor control
        self.keyboard_layout.addWidget(up, 4, 6, 1, 1)

        down = QPushButton('▼')
        down.setFixedSize(fixed_w, fixed_h)
        down.clicked.connect(self.down_key)
        self.keyboard_layout.addWidget(down, 4, 7, 1, 1)

        left = QPushButton('◄')
        left.setFixedSize(fixed_w, fixed_h)
        left.clicked.connect(self.left_key)
        self.keyboard_layout.addWidget(left, 4, 8, 1, 1)

        right = QPushButton('►')
        right.setFixedSize(fixed_w, fixed_h)
        right.clicked.connect(self.right_key)
        self.keyboard_layout.addWidget(right, 4, 9, 1, 1)

        hide_button = QPushButton('Hide')
        hide_button.setFixedSize(fixed_w * 2 + self.spacing, fixed_h)
        hide_button.clicked.connect(self.hide)
        # Add gamepad icon for Hide (B/Circle)
        gtype = self.input_manager.gamepad_type
        self.set_gamepad_icon(hide_button, 'back', gtype)
        self.keyboard_layout.addWidget(hide_button, 4, 12, 1, 2)

        if coords:
            row, col = coords
            item = self.keyboard_layout.itemAtPosition(row, col)
            if item:
                widget = item.widget()
                if widget:
                    widget.setFocus()

    def up_key(self):
        """Move cursor in QLineEdit up/to start if keyboard visible"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            try:
                self.current_input_widget.setCursorPosition(0)
                self.current_input_widget.setFocus()
            except RuntimeError:
                self.current_input_widget = None

    def down_key(self):
        """Move cursor in QLineEdit down/to end if keyboard visible"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            try:
                self.current_input_widget.setCursorPosition(len(self.current_input_widget.text()))
                self.current_input_widget.setFocus()
            except RuntimeError:
                self.current_input_widget = None

    def left_key(self):
        """Move cursor in QLineEdit left if keyboard visible"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            try:
                pos = self.current_input_widget.cursorPosition()
                if pos > 0:
                    self.current_input_widget.setCursorPosition(pos - 1)
                self.current_input_widget.setFocus()
            except RuntimeError:
                self.current_input_widget = None

    def right_key(self):
        """Move cursor in QLineEdit right if keyboard visible"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            try:
                pos = self.current_input_widget.cursorPosition()
                text_len = len(self.current_input_widget.text())
                if pos < text_len:
                    self.current_input_widget.setCursorPosition(pos + 1)
                self.current_input_widget.setFocus()
            except RuntimeError:
                self.current_input_widget = None

    def move_focus_up(self):
        """Move focus up across keyboard buttons with fixed speed"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("up")
            self.last_focus_time = current_time

    def move_focus_down(self):
        """Move focus down across keyboard buttons with fixed speed"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("down")
            self.last_focus_time = current_time

    def move_focus_left(self):
        """Move focus left across keyboard buttons with fixed speed"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("left")
            self.last_focus_time = current_time

    def move_focus_right(self):
        """Move focus right across keyboard buttons with fixed speed"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("right")
            self.last_focus_time = current_time

    def get_current_time(self):
        """Return current time in milliseconds"""
        from time import time
        return int(time() * 1000)

    def _save_focused_coords(self) -> tuple[int, int] | None:
        """Return (row, col) of focused button or None"""
        current = self.focusWidget()
        if not current:
            return None
        idx = self.keyboard_layout.indexOf(current)
        if idx == -1:
            return None
        position = cast(tuple[int, int, int, int], self.keyboard_layout.getItemPosition(idx))
        return position[:2]  # row, col

    def on_button_click(self, key):
        if key in ['TAB', 'CAPS', '⬆']:
            if key == 'TAB':
                self.on_tab_click()
            elif key == 'CAPS':
                self.on_caps_click()
            elif key == '⬆':
                self.on_shift_click(not self.shift_pressed)
            self.highlight_cursor_position()
        elif self.current_input_widget is not None:
            try:
                # Save current focused button
                focused_button = self.focusWidget()
                key_to_restore = None
                if isinstance(focused_button, QPushButton) and focused_button in self.buttons.values():
                    key_to_restore = next((k for k, btn in self.buttons.items() if btn == focused_button), None)

                key = "&" if key == "&&" else key
                cursor_pos = self.current_input_widget.cursorPosition()
                text = self.current_input_widget.text()
                new_text = text[:cursor_pos] + key + text[cursor_pos:]
                self.current_input_widget.setText(new_text)
                self.current_input_widget.setCursorPosition(cursor_pos + len(key))
                self.keyPressed.emit(key)
                self.highlight_cursor_position()

                # If SHIFT was pressed but not CapsLock, disable it after character input
                if self.shift_pressed and not self.caps_lock:
                    self.shift_pressed = False
                    self.update_keyboard()
                    if key_to_restore and key_to_restore in self.buttons:
                        self.buttons[key_to_restore].setFocus()
            except RuntimeError:
                self.current_input_widget = None

    def on_tab_click(self):
        if self.current_input_widget is not None:
            try:
                self.current_input_widget.insert('\t')
                self.keyPressed.emit('Tab')
                if self.current_input_widget:
                    self.current_input_widget.setFocus()
                self.highlight_cursor_position()
            except RuntimeError:
                self.current_input_widget = None

    def on_caps_click(self):
        """Toggle CapsLock"""
        self.caps_lock = not self.caps_lock
        self.shift_pressed = self.caps_lock
        self.update_keyboard()

    # ---------- timer event ----------
    def timerEvent(self, event):
        if event.timerId() == self.backspace_timer:
            self.on_backspace_click()  # erase one more character
            # first trigger passed - speed up
            if self.backspace_timer:
                self.killTimer(self.backspace_timer)
                self.backspace_timer = self.startTimer(self.backspace_repeat_delay)
    def on_backspace_click(self):
        """Handle single Backspace press"""
        if self.current_input_widget is not None:
            try:
                cursor_pos = self.current_input_widget.cursorPosition()
                text = self.current_input_widget.text()

                if cursor_pos > 0:
                    new_text = text[:cursor_pos - 1] + text[cursor_pos:]
                    self.current_input_widget.setText(new_text)
                    self.current_input_widget.setCursorPosition(cursor_pos - 1)
                    self.keyPressed.emit('Backspace')
                    self.highlight_cursor_position()
            except RuntimeError:
                self.current_input_widget = None

    def on_backspace_pressed(self):
        """Handle held Backspace"""
        self.backspace_pressed = True
        self.start_backspace_repeat()

    def start_backspace_repeat(self):
        """Start Backspace auto-repeat"""
        self.on_backspace_click()  # First press
        self.backspace_timer = self.startTimer(self.backspace_initial_delay)

    def stop_backspace_repeat(self):
        """Stop Backspace auto-repeat"""
        if self.backspace_timer:
            self.killTimer(self.backspace_timer)
            self.backspace_timer = None
        self.backspace_pressed = False

    def on_enter_click(self):
        """Handle Enter button action"""
        #  For now placeholder for new line, in QLineEdit works as space press
        if self.current_input_widget is not None:
            try:
                self.current_input_widget.insert('\n')
                self.keyPressed.emit('Enter')
            except RuntimeError:
                self.current_input_widget = None

    def on_clear_click(self):
        """Clear line from entered text"""
        if self.current_input_widget is not None:
            try:
                self.current_input_widget.clear()
                self.keyPressed.emit('Clear')
                self.highlight_cursor_position()
            except RuntimeError:
                self.current_input_widget = None

    def on_lang_click(self):
        """Switch layout"""
        if not self.available_layouts:
            return

        try:
            current_index = self.available_layouts.index(self.current_layout)
            next_index = (current_index + 1) % len(self.available_layouts)
            self.current_layout = self.available_layouts[next_index]
        except ValueError:
            # If current layout not in available_layouts
            self.current_layout = self.available_layouts[0] if self.available_layouts else 'en'

        self.update_keyboard()

    def on_shift_click(self, checked):
        self.shift_pressed = checked
        if not checked and self.caps_lock:
            self.caps_lock = False
        self.update_keyboard()

    def show_for_widget(self, widget):
        self.current_input_widget = widget
        if widget:
            try:
                widget.setFocus()
                self.highlight_cursor_position()
            except RuntimeError:
                self.current_input_widget = None

        # Position keyboard at bottom of parent widget
        if self._parent and isinstance(self._parent, QWidget):
            self._sync_keyboard_geometry()
            self.update_keyboard()

        self.show()
        self.raise_()
        self.ensure_input_visible()

        # Set focus to first button if no focus on input widget
        if not widget:
            first_button: QPushButton | None = next((cast(QPushButton, btn) for btn in self.buttons.values()), None)
            if first_button:
                first_button.setFocus()

    def eventFilter(self, obj, event):
        if (
            self._parent
            and obj is self._parent
            and event.type() == QEvent.Type.Resize
            and self.isVisible()
        ):
            self._sync_keyboard_geometry()
            self.update_keyboard()
        return super().eventFilter(obj, event)

    def ensure_input_visible(self):
        if (
            not self._parent
            or not isinstance(self._parent, QWidget)
            or not self.current_input_widget
            or not isinstance(self.current_input_widget, QWidget)
            or not self.current_input_widget.isVisible()
        ):
            return

        widget = self.current_input_widget
        keyboard_top = self.y()
        widget_bottom = widget.mapTo(self._parent, widget.rect().bottomLeft()).y()
        if widget_bottom <= keyboard_top:
            return

        parent_widget = widget.parentWidget()
        while parent_widget:
            if isinstance(parent_widget, QScrollArea):
                parent_widget.ensureWidgetVisible(widget, 0, self.button_height)
                widget_bottom = widget.mapTo(self._parent, widget.rect().bottomLeft()).y()
                if widget_bottom <= keyboard_top:
                    return
                break
            parent_widget = parent_widget.parentWidget()

        # Fallback for dialogs without scrollable container.
        self.move(0, 0)

    def activateFocusedKey(self):
        """Activate current highlighted button on keyboard"""
        focused = self.focusWidget()
        if isinstance(focused, QPushButton):
            focused.animateClick()

    def focusNextKey(self, direction: str):
        """Move focus to next button in specified direction with wrapping"""
        current = self.focusWidget()
        if not current:
            first_button = self.findFirstFocusableButton()
            if first_button:
                first_button.setFocus()
            return

        current_idx = self.keyboard_layout.indexOf(current)
        if current_idx == -1:
            return

        position = cast(tuple[int, int, int, int], self.keyboard_layout.getItemPosition(current_idx))
        current_row, current_col, row_span, col_span = position

        num_rows = self.keyboard_layout.rowCount()
        num_cols = self.keyboard_layout.columnCount()

        found = False

        if direction == "right":
            # First search right in same row
            search_row = current_row
            search_col = current_col + col_span
            while search_col < num_cols:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                widget = item.widget() if item else None
                if widget and widget.isEnabled():
                    next_button = cast(QPushButton, widget)
                    next_button.setFocus()
                    found = True
                    break
                search_col += 1

            if not found:
                # Move to next row, starting at col 0
                search_row = (current_row + 1) % num_rows
                search_col = 0
                # Find first button in this row
                while search_col < num_cols:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    widget = item.widget() if item else None
                    if widget and widget.isEnabled():
                        next_button = cast(QPushButton, widget)
                        next_button.setFocus()
                        found = True
                        break
                    search_col += 1

        elif direction == "left":
            # First search left in same row
            search_row = current_row
            search_col = current_col - 1
            while search_col >= 0:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                widget = item.widget() if item else None
                if widget and widget.isEnabled():
                    next_button = cast(QPushButton, widget)
                    next_button.setFocus()
                    found = True
                    break
                search_col -= 1

            if not found:
                # Move to previous row, starting at last column
                search_row = (current_row - 1) % num_rows
                search_col = num_cols - 1
                # Find last button in this row
                while search_col >= 0:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    widget = item.widget() if item else None
                    if widget and widget.isEnabled():
                        next_button = cast(QPushButton, widget)
                        next_button.setFocus()
                        found = True
                        break
                    search_col -= 1

        elif direction == "down":
            # First search down in same column
            search_col = current_col
            search_row = current_row + row_span
            while search_row < num_rows:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                widget = item.widget() if item else None
                if widget and widget.isEnabled():
                    next_button = cast(QPushButton, widget)
                    next_button.setFocus()
                    found = True
                    break
                search_row += 1

            if not found:
                # Move to next column, starting at row 0
                search_col = (current_col + col_span) % num_cols
                search_row = 0
                # Find first button in this column
                while search_row < num_rows:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    widget = item.widget() if item else None
                    if widget and widget.isEnabled():
                        next_button = cast(QPushButton, widget)
                        next_button.setFocus()
                        found = True
                        break
                    search_row += 1

        elif direction == "up":
            # First search up in same column
            search_col = current_col
            search_row = current_row - 1
            while search_row >= 0:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                widget = item.widget() if item else None
                if widget and widget.isEnabled():
                    next_button = cast(QPushButton, widget)
                    next_button.setFocus()
                    found = True
                    break
                search_row -= 1

            if not found:
                # Move to previous column, starting at last row
                search_col = (current_col - 1) % num_cols
                search_row = num_rows - 1
                # Find last button in this column
                while search_row >= 0:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    widget = item.widget() if item else None
                    if widget and widget.isEnabled():
                        next_button = cast(QPushButton, widget)
                        next_button.setFocus()
                        found = True
                        break
                    search_row -= 1

    def findFirstFocusableButton(self) -> QPushButton | None:
        """Find first focusable button on keyboard"""
        for row in range(self.keyboard_layout.rowCount()):
            for col in range(self.keyboard_layout.columnCount()):
                item = self.keyboard_layout.itemAtPosition(row, col)
                widget = item.widget() if item else None
                if widget and widget.isEnabled():
                    return cast(QPushButton, widget)
        return None
