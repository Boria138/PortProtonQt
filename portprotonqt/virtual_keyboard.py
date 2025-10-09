from typing import cast
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QPushButton, QGridLayout,
                               QSizePolicy, QWidget, QLineEdit)
from PySide6.QtCore import Qt, Signal, QProcess
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
        self.focus_delay = 150  # Задержка между перемещениями в мс
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
        self.button_height = 40
        self.spacing = 4
        self.margins = 10
        self.num_cols = 14

        self.initUI()
        self.hide()

        self.setStyleSheet(self.theme.VIRTUAL_KEYBOARD_STYLE)

    def highlight_cursor_position(self):
        """Подсвечиваем текущую позицию курсора"""
        if not self.current_input_widget or not isinstance(self.current_input_widget, QLineEdit):
            return

        # Просто устанавливаем курсор на нужную позицию без выделения
        self.current_input_widget.setCursorPosition(self.current_input_widget.cursorPosition())

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
        """Получаем раскладки, которые используются в системе, возвращаем список вида ['us', 'ru'] и т.п."""
        cmd = r'''localectl status | awk -F: '/X11 Layout/ {gsub(/^[ \t]+/, "", $2); print $2}' '''
        output = self.run_shell_command(cmd)
        if output:
            layouts = [lang.strip() for lang in output.split(',') if lang.strip()]
            return layouts if layouts else ['en']
        else:
            return ['en']

    def create_keyboard(self):
        # TODO: сделать нормальное описание (сейчас лень)
        # Основные раскладки с учетом Shift
        # Фильтруем доступные раскладки

        LAYOUT_MAP = {'us': 'en'}

        # Assume keyboard_layouts is dict[str, dict[str, list[list[str]]]]
        self.layouts: dict[str, dict[str, list[list[str]]]] = {
            lang: keyboard_layouts.get(LAYOUT_MAP.get(lang, lang), keyboard_layouts['en'])
            for lang in self.available_layouts
        }

        self.current_layout = (self.current_layout if self.current_layout in self.layouts else next(iter(self.layouts.keys()), None) or 'en')

        self.buttons: dict[str, QPushButton] = {}
        self.update_keyboard()

    def update_keyboard(self):
        coords = self._save_focused_coords()

        # Очищаем предыдущие кнопки
        while self.keyboard_layout.count():
            item = self.keyboard_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        fixed_w = self.button_width
        fixed_h = self.button_height

        # Выбираем текущую раскладку (обычная или с shift)
        layout_mode = 'shift' if self.shift_pressed else 'normal'
        layout_data = self.layouts.get(self.current_layout, {})
        buttons: list[list[str]] = layout_data.get(layout_mode, [])

        # Добавляем основные кнопки
        for row_idx, row in enumerate(buttons):
            for col_idx, key in enumerate(row):
                button = QPushButton(key)
                button.setFixedSize(fixed_w, fixed_h)

                # Обработчики для CAPS и левого Shift
                if key == 'CAPS':
                    button.setCheckable(True)
                    button.setChecked(self.caps_lock)
                    button.clicked.connect(self.on_caps_click)
                elif key == '⬆':  # Левый Shift
                    button.setCheckable(True)
                    button.setChecked(self.shift_pressed)
                    button.clicked.connect(lambda checked: self.on_shift_click(checked))
                else:
                    button.clicked.connect(lambda checked=False, k=key: self.on_button_click(k))

                self.keyboard_layout.addWidget(button, row_idx, col_idx)
                self.buttons[key] = button

        # Нижний ряд (специальные кнопки)
        shift = QPushButton('⬆')
        shift.setFixedSize(fixed_w * 3 + 2 * self.spacing, fixed_h)
        shift.setCheckable(True)
        shift.setChecked(self.shift_pressed)
        shift.clicked.connect(lambda checked: self.on_shift_click(checked))
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
        self.keyboard_layout.addWidget(backspace, 0, 13, 1, 1)

        enter = QPushButton('Enter')
        enter.setFixedSize(fixed_w * 2 + self.spacing, fixed_h)
        enter.clicked.connect(self.on_enter_click)
        self.keyboard_layout.addWidget(enter, 2, 12, 1, 2)

        lang = QPushButton('🌐')
        lang.setFixedSize(fixed_w, fixed_h)
        lang.clicked.connect(self.on_lang_click)
        self.keyboard_layout.addWidget(lang, 4, 0, 1, 1)

        clear = QPushButton('Clear')
        clear.setFixedSize(fixed_w * 2 + self.spacing, fixed_h)
        clear.clicked.connect(self.on_clear_click)
        self.keyboard_layout.addWidget(clear, 4, 10, 1, 2)

        up = QPushButton('▲')
        up.setFixedSize(fixed_w, fixed_h)
        up.clicked.connect(self.up_key)  # Обработка клика мышью - управление курсором
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
        self.keyboard_layout.addWidget(hide_button, 4, 12, 1, 2)

        if coords:
            row, col = coords
            item = self.keyboard_layout.itemAtPosition(row, col)
            if item and item.widget():
                item.widget().setFocus()

    def up_key(self):
        """Перемещает курсор в QLineEdit вверх/в начало, если клавиатура видима"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            self.current_input_widget.setCursorPosition(0)
            self.current_input_widget.setFocus()

    def down_key(self):
        """Перемещает курсор в QLineEdit вниз/в конец, если клавиатура видима"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            self.current_input_widget.setCursorPosition(len(self.current_input_widget.text()))
            self.current_input_widget.setFocus()

    def left_key(self):
        """Перемещает курсор в QLineEdit влево, если клавиатура видима"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            pos = self.current_input_widget.cursorPosition()
            if pos > 0:
                self.current_input_widget.setCursorPosition(pos - 1)
            self.current_input_widget.setFocus()

    def right_key(self):
        """Перемещает курсор в QLineEdit вправо, если клавиатура видима"""
        if self.current_input_widget and isinstance(self.current_input_widget, QLineEdit):
            pos = self.current_input_widget.cursorPosition()
            text_len = len(self.current_input_widget.text())
            if pos < text_len:
                self.current_input_widget.setCursorPosition(pos + 1)
            self.current_input_widget.setFocus()

    def move_focus_up(self):
        """Перемещает фокус по кнопкам клавиатуры вверх с фиксированной скоростью"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("up")
            self.last_focus_time = current_time

    def move_focus_down(self):
        """Перемещает фокус по кнопкам клавиатуры вниз с фиксированной скоростью"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("down")
            self.last_focus_time = current_time

    def move_focus_left(self):
        """Перемещает фокус по кнопкам клавиатуры влево с фиксированной скоростью"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("left")
            self.last_focus_time = current_time

    def move_focus_right(self):
        """Перемещает фокус по кнопкам клавиатуры вправо с фиксированной скоростью"""
        current_time = self.get_current_time()
        if current_time - self.last_focus_time >= self.focus_delay:
            self.focusNextKey("right")
            self.last_focus_time = current_time

    def get_current_time(self):
        """Возвращает текущее время в миллисекундах"""
        from time import time
        return int(time() * 1000)

    def _save_focused_coords(self) -> tuple[int, int] | None:
        """Возвращает (row, col) кнопки с фокусом или None"""
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
            # Сохраняем текущую кнопку с фокусом
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

            # Если был нажат SHIFT, но не CapsLock, отключаем его после ввода символа
            if self.shift_pressed and not self.caps_lock:
                self.shift_pressed = False
                self.update_keyboard()
                if key_to_restore and key_to_restore in self.buttons:
                    self.buttons[key_to_restore].setFocus()

    def on_tab_click(self):
        if self.current_input_widget is not None:
            self.current_input_widget.insert('\t')
            self.keyPressed.emit('Tab')
            self.current_input_widget.setFocus()
            self.highlight_cursor_position()

    def on_caps_click(self):
        """Включаем/выключаем CapsLock"""
        self.caps_lock = not self.caps_lock
        self.shift_pressed = self.caps_lock
        self.update_keyboard()

    # ---------- таймерное событие ----------
    def timerEvent(self, event):
        if event.timerId() == self.backspace_timer:
            self.on_backspace_click()  # стираем ещё один символ
            # первое срабатывание прошло – ускоряем
            if self.backspace_timer:
                self.killTimer(self.backspace_timer)
                self.backspace_timer = self.startTimer(self.backspace_repeat_delay)
    def on_backspace_click(self):
        """Обработка одного нажатия Backspace"""
        if self.current_input_widget is not None:
            cursor_pos = self.current_input_widget.cursorPosition()
            text = self.current_input_widget.text()

            if cursor_pos > 0:
                new_text = text[:cursor_pos - 1] + text[cursor_pos:]
                self.current_input_widget.setText(new_text)
                self.current_input_widget.setCursorPosition(cursor_pos - 1)
                self.keyPressed.emit('Backspace')
                self.highlight_cursor_position()

    def on_backspace_pressed(self):
        """Обработка зажатого Backspace"""
        self.backspace_pressed = True
        self.start_backspace_repeat()

    def start_backspace_repeat(self):
        """Запуск автоповтора нажатия Backspace"""
        self.on_backspace_click()  # Первое нажатие
        self.backspace_timer = self.startTimer(self.backspace_initial_delay)

    def stop_backspace_repeat(self):
        """Остановка автоповтора нажатия Backspace"""
        if self.backspace_timer:
            self.killTimer(self.backspace_timer)
            self.backspace_timer = None
        self.backspace_pressed = False

    def on_enter_click(self):
        """Обработка действия кнопки Enter"""
        # TODO: тут подумать, как обрабатывать нажатие.
        #  Пока болванка перехода на новую строку, в QlineEdit работает как нажатие пробела
        if self.current_input_widget is not None:
            self.current_input_widget.insert('\n')
            self.keyPressed.emit('Enter')

    def on_clear_click(self):
        """Чистим строку от введённого текста"""
        if self.current_input_widget is not None:
            self.current_input_widget.clear()
            self.keyPressed.emit('Clear')
            self.highlight_cursor_position()

    def on_lang_click(self):
        """Переключение раскладки"""
        if not self.available_layouts:
            return

        try:
            current_index = self.available_layouts.index(self.current_layout)
            next_index = (current_index + 1) % len(self.available_layouts)
            self.current_layout = self.available_layouts[next_index]
        except ValueError:
            # Если текущей раскладки нет в available_layouts
            self.current_layout = self.available_layouts[0] if self.available_layouts else 'en'

        self.update_keyboard()

    def on_shift_click(self, checked):
        self.shift_pressed = checked
        self.update_keyboard()

    def show_for_widget(self, widget):
        self.current_input_widget = widget
        if widget:
            widget.setFocus()
            self.highlight_cursor_position()

        # Позиционирование клавиатуры внизу родительского виджета
        if self._parent and isinstance(self._parent, QWidget):
            keyboard_height = 220
            self.setFixedWidth(self._parent.width())
            self.setFixedHeight(keyboard_height)
            self.move(0, self._parent.height() - keyboard_height)

        self.show()
        self.raise_()

        # Установить фокус на первую кнопку, если нет фокуса на виджете ввода
        if not widget:
            first_button: QPushButton | None = next((cast(QPushButton, btn) for btn in self.buttons.values()), None)
            if first_button:
                first_button.setFocus()

    def activateFocusedKey(self):
        """Активирует текущую выделенную кнопку на клавиатуре"""
        focused = self.focusWidget()
        if isinstance(focused, QPushButton):
            focused.animateClick()

    def focusNextKey(self, direction: str):
        """Перемещает фокус на следующую кнопку в указанном направлении с обертыванием"""
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
            # Сначала ищем в той же строке вправо
            search_row = current_row
            search_col = current_col + col_span
            while search_col < num_cols:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                if item and item.widget() and item.widget().isEnabled():
                    next_button = cast(QPushButton, item.widget())
                    next_button.setFocus()
                    found = True
                    break
                search_col += 1

            if not found:
                # Переходим к следующей строке, начиная с col 0
                search_row = (current_row + 1) % num_rows
                search_col = 0
                # Ищем первую кнопку в этой строке
                while search_col < num_cols:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    if item and item.widget() and item.widget().isEnabled():
                        next_button = cast(QPushButton, item.widget())
                        next_button.setFocus()
                        found = True
                        break
                    search_col += 1

        elif direction == "left":
            # Сначала ищем в той же строке влево
            search_row = current_row
            search_col = current_col - 1
            while search_col >= 0:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                if item and item.widget() and item.widget().isEnabled():
                    next_button = cast(QPushButton, item.widget())
                    next_button.setFocus()
                    found = True
                    break
                search_col -= 1

            if not found:
                # Переходим к предыдущей строке, начиная с последнего столбца
                search_row = (current_row - 1) % num_rows
                search_col = num_cols - 1
                # Ищем последнюю кнопку в этой строке
                while search_col >= 0:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    if item and item.widget() and item.widget().isEnabled():
                        next_button = cast(QPushButton, item.widget())
                        next_button.setFocus()
                        found = True
                        break
                    search_col -= 1

        elif direction == "down":
            # Сначала ищем в том же столбце вниз
            search_col = current_col
            search_row = current_row + row_span
            while search_row < num_rows:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                if item and item.widget() and item.widget().isEnabled():
                    next_button = cast(QPushButton, item.widget())
                    next_button.setFocus()
                    found = True
                    break
                search_row += 1

            if not found:
                # Переходим к следующему столбцу, начиная с row 0
                search_col = (current_col + col_span) % num_cols
                search_row = 0
                # Ищем первую кнопку в этом столбце
                while search_row < num_rows:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    if item and item.widget() and item.widget().isEnabled():
                        next_button = cast(QPushButton, item.widget())
                        next_button.setFocus()
                        found = True
                        break
                    search_row += 1

        elif direction == "up":
            # Сначала ищем в том же столбце вверх
            search_col = current_col
            search_row = current_row - 1
            while search_row >= 0:
                item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                if item and item.widget() and item.widget().isEnabled():
                    next_button = cast(QPushButton, item.widget())
                    next_button.setFocus()
                    found = True
                    break
                search_row -= 1

            if not found:
                # Переходим к предыдущему столбцу, начиная с последней строки
                search_col = (current_col - 1) % num_cols
                search_row = num_rows - 1
                # Ищем последнюю кнопку в этом столбце
                while search_row >= 0:
                    item = self.keyboard_layout.itemAtPosition(search_row, search_col)
                    if item and item.widget() and item.widget().isEnabled():
                        next_button = cast(QPushButton, item.widget())
                        next_button.setFocus()
                        found = True
                        break
                    search_row -= 1

    def findFirstFocusableButton(self) -> QPushButton | None:
        """Находит первую фокусируемую кнопку на клавиатуре"""
        for row in range(self.keyboard_layout.rowCount()):
            for col in range(self.keyboard_layout.columnCount()):
                item = self.keyboard_layout.itemAtPosition(row, col)
                if item and item.widget() and item.widget().isEnabled():
                    return cast(QPushButton, item.widget())
        return None
