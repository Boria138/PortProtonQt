import numpy as np
from PySide6.QtWidgets import QLabel, QPushButton, QWidget, QLayout, QLayoutItem
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter

def compute_layout(nat_sizes, rect_width, spacing, max_scale):
    """
    Computes the layout of elements considering spacing and potential scaling of cards.
    nat_sizes: Array (N, 2) with natural sizes of elements (width, height).
    rect_width: Available container width.
    spacing: Spacing between elements (horizontal and vertical).
    max_scale: Maximum scaling factor (e.g., 1.0).

    Returns:
      result: Array (N, 4), where each row contains [x, y, new_width, new_height].
      total_height: Total height of all rows.
    """
    N = nat_sizes.shape[0]
    result = np.zeros((N, 4), dtype=np.int32)
    y = 0
    i = 0
    min_margin = 20  # Minimum margin on edges

    # Determine the maximum number of items per row and overall scale
    max_items_per_row = 0
    global_scale = 1.0
    max_row_x_start = min_margin  # Starting x position of the widest row
    temp_i = 0

    # First pass: Find the maximum number of items in a row
    while temp_i < N:
        sum_width = 0
        count = 0
        temp_j = temp_i
        while temp_j < N:
            w = nat_sizes[temp_j, 0]
            if count > 0 and (sum_width + spacing + w) > rect_width - 2 * min_margin:
                break
            sum_width += w
            count += 1
            temp_j += 1

        if count > max_items_per_row:
            max_items_per_row = count
            # Calculate scale for the most populated row
            available_width = rect_width - spacing * (count - 1) - 2 * min_margin
            desired_scale = available_width / sum_width if sum_width > 0 else 1.0
            global_scale = desired_scale if desired_scale < max_scale else max_scale
            # Store starting x position for the widest row
            scaled_row_width = int(sum_width * global_scale) + spacing * (count - 1)
            max_row_x_start = max(min_margin, (rect_width - scaled_row_width) // 2)
        temp_i = temp_j

    # Second pass: Place elements
    while i < N:
        sum_width = 0
        row_max_height = 0
        count = 0
        j = i

        # Determine the number of items for the current row
        while j < N:
            w = nat_sizes[j, 0]
            if count > 0 and (sum_width + spacing + w) > rect_width - 2 * min_margin:
                break
            sum_width += w
            count += 1
            h = nat_sizes[j, 1]
            if h > row_max_height:
                row_max_height = h
            j += 1

        # Use global scale for all rows
        scale = global_scale
        scaled_row_width = int(sum_width * scale) + spacing * (count - 1)

        # Determine starting x coordinate
        if count == max_items_per_row:
            # Center the full row
            x = max(min_margin, (rect_width - scaled_row_width) // 2)
        else:
            # Align incomplete row to the left, matching the widest row's start
            x = max_row_x_start

        for k in range(i, j):
            new_w = int(nat_sizes[k, 0] * scale)
            new_h = int(nat_sizes[k, 1] * scale)
            result[k, 0] = x
            result[k, 1] = y
            result[k, 2] = new_w
            result[k, 3] = new_h
            x += new_w + spacing

        y += int(row_max_height * scale) + spacing
        i = j
    return result, y

class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(20, 20, 20, 20)  # Margins around the layout
        self._spacing = 20  # Spacing for animation and overlap prevention
        self._max_scale = 1.0  # Scaling disabled in layout

    def addItem(self, item: QLayoutItem) -> None:
        self.itemList.append(item)

    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        raise IndexError("Index out of range")

    def count(self) -> int:
        return len(self.itemList)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        # Аналогично фильтруем видимые для тестового расчёта высоты
        visible_items = []
        nat_sizes = np.empty((0, 2), dtype=np.int32)
        for item in self.itemList:
            if item.widget() and item.widget().isVisible():
                visible_items.append(item)
                s = item.sizeHint()
                new_row = np.array([[s.width(), s.height()]], dtype=np.int32)
                nat_sizes = np.vstack([nat_sizes, new_row]) if len(nat_sizes) > 0 else new_row

        if len(visible_items) == 0:
            return 0

        _, total_height = compute_layout(nat_sizes, width, self._spacing, self._max_scale)
        return total_height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                      margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        N_total = len(self.itemList)
        if N_total == 0:
            return 0

        # Фильтруем только видимые элементы
        visible_items = []
        visible_indices = []  # Индексы в оригинальном itemList для установки геометрии
        nat_sizes = np.empty((0, 2), dtype=np.int32)
        for i, item in enumerate(self.itemList):
            if item.widget() and item.widget().isVisible():
                visible_items.append(item)
                visible_indices.append(i)
                s = item.sizeHint()
                new_row = np.array([[s.width(), s.height()]], dtype=np.int32)
                nat_sizes = np.vstack([nat_sizes, new_row]) if len(nat_sizes) > 0 else new_row

        N = len(visible_items)
        if N == 0:
            # Если все скрыты, устанавливаем нулевые геометрии для всех
            if not testOnly:
                for item in self.itemList:
                    item.setGeometry(QRect())
            return 0

        geom_array, total_height = compute_layout(nat_sizes, rect.width(), self._spacing, self._max_scale)

        if not testOnly:
            # Устанавливаем геометрии только для видимых
            for idx, (_vis_idx, item) in enumerate(zip(visible_indices, visible_items, strict=True)):
                x = geom_array[idx, 0] + rect.x()
                y = geom_array[idx, 1] + rect.y()
                w = geom_array[idx, 2]
                h = geom_array[idx, 3]
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))

            # Для невидимых — нулевая геометрия
            for i in range(N_total):
                if i not in visible_indices:
                    self.itemList[i].setGeometry(QRect())

        return total_height

class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, *args, icon=None, icon_size=16, icon_space=5, change_cursor=True, font_scale_factor=0.06, **kwargs):
        if args and isinstance(args[0], str):
            text = args[0]
            parent = kwargs.get("parent", None)
            super().__init__(text, parent)
        elif args and isinstance(args[0], QWidget):
            parent = args[0]
            text = kwargs.get("text", "")
            super().__init__(parent)
            self.setText(text)
        else:
            text = ""
            parent = kwargs.get("parent", None)
            super().__init__(text, parent)

        self._icon = icon
        self._icon_size = icon_size
        self._icon_space = icon_space
        self._font_scale_factor = font_scale_factor
        self._card_width = 250
        if change_cursor:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.updateFontSize()

    def setIcon(self, icon):
        self._icon = icon
        self.update()

    def icon(self):
        return self._icon

    def setIconSize(self, icon_size: int, icon_space: int):
        self._icon_size = icon_size
        self._icon_space = icon_space
        self.update()

    def setCardWidth(self, card_width: int):
        self._card_width = card_width
        self.updateFontSize()

    def updateFontSize(self):
        font = self.font()
        font_size = int(self._card_width * self._font_scale_factor)
        font.setPointSize(max(8, font_size))
        self.setFont(font)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.contentsRect()
        alignment = self.alignment()
        icon_size = self._icon_size
        spacing = self._icon_space
        text = self.text()

        if self._icon:
            pixmap = self._icon.pixmap(icon_size, icon_size)
        else:
            pixmap = None

        fm = QFontMetrics(self.font())
        available_width = rect.width()
        if pixmap:
            available_width -= (icon_size + spacing)
        available_width = max(0, available_width - 4)
        display_text = fm.elidedText(text, Qt.TextElideMode.ElideRight, available_width)
        text_width = fm.horizontalAdvance(display_text)
        text_height = fm.height()
        total_width = text_width + (icon_size + spacing if pixmap else 0)

        if alignment & Qt.AlignmentFlag.AlignHCenter:
            x = rect.left() + (rect.width() - total_width) // 2
        elif alignment & Qt.AlignmentFlag.AlignRight:
            x = rect.right() - total_width
        else:
            x = rect.left()
        y = rect.top() + (rect.height() - text_height) // 2

        if pixmap:
            icon_rect = QRect(x, y + (text_height - icon_size) // 2, icon_size, icon_size)
            painter.drawPixmap(icon_rect, pixmap)
            text_x = x + icon_size + spacing
        else:
            text_x = x

        text_rect = QRect(text_x, y, text_width, text_height)
        self.style().drawItemText(
            painter,
            text_rect,
            alignment,
            self.palette(),
            self.isEnabled(),
            display_text,
            self.foregroundRole(),
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

class AutoSizeButton(QPushButton):
    def __init__(self, *args, icon=None, icon_size=16,
                 min_font_size=6, max_font_size=14, padding=20, update_size=True, **kwargs):
        if args and isinstance(args[0], str):
            text = args[0]
            parent = kwargs.get("parent", None)
            super().__init__(text, parent)
        elif args and isinstance(args[0], QWidget):
            parent = args[0]
            text = kwargs.get("text", "")
            super().__init__(text, parent)
        else:
            text = ""
            parent = kwargs.get("parent", None)
            super().__init__(text, parent)

        self._icon = icon
        self._icon_size = icon_size
        self._alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self._min_font_size = min_font_size
        self._max_font_size = max_font_size
        self._padding = padding
        self._update_size = update_size
        self._original_font = self.font()
        self._original_text = self.text()

        if self._icon:
            self.setIcon(self._icon)
            self.setIconSize(QSize(self._icon_size, self._icon_size))

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setMinimumWidth(50)
        self.adjustFontSize()

    def setAlignment(self, alignment):
        self._alignment = alignment
        self.update()

    def alignment(self):
        return self._alignment

    def setText(self, text):
        self._original_text = text
        if not self._update_size:
            super().setText(text)
        else:
            super().setText(text)
            self.adjustFontSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._update_size:
            self.adjustFontSize()

    def adjustFontSize(self):
        if not self._original_text:
            return

        if not self._update_size:
            return

        available_width = self.width()
        if self._icon:
            available_width -= self._icon_size

        margins = self.contentsMargins()
        available_width -= (margins.left() + margins.right() + self._padding * 2)

        font = QFont(self._original_font)
        text = self._original_text

        chosen_size = self._max_font_size
        for font_size in range(self._max_font_size, self._min_font_size - 1, -1):
            font.setPointSize(font_size)
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(text)
            if text_width <= available_width:
                chosen_size = font_size
                break

        font.setPointSize(chosen_size)
        self.setFont(font)

        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        required_width = text_width + margins.left() + margins.right() + self._padding * 2
        if self._icon:
            required_width += self._icon_size

        if self.width() < required_width:
            self.setMinimumWidth(required_width)

        super().setText(text)

    def sizeHint(self):
        if not self._update_size:
            return super().sizeHint()
        else:
            font = self.font()
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(self._original_text)
            margins = self.contentsMargins()
            width = text_width + margins.left() + margins.right() + self._padding * 2
            if self._icon:
                width += self._icon_size
            height = fm.height() + margins.top() + margins.bottom() + self._padding
            return QSize(width, height)

class NavLabel(QLabel):
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._checkable = False
        self._isChecked = False
        self.setProperty("checked", self._isChecked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def setCheckable(self, checkable):
        self._checkable = checkable

    def setChecked(self, checked):
        if self._checkable:
            self._isChecked = checked
            self.setProperty("checked", checked)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def isChecked(self):
        return self._isChecked

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            if self._checkable:
                self.setChecked(not self._isChecked)
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)
