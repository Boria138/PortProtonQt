from PySide6.QtWidgets import QLabel, QPushButton, QWidget, QLayout, QLayoutItem
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter

def compute_layout(nat_sizes, rect_width, spacing, max_scale):
    """
    Compute layout for flow arrangement.
    nat_sizes: list of tuples [(width, height), ...]
    """
    N = len(nat_sizes)
    if N == 0:
        return [], 0

    result = [[0, 0, 0, 0] for _ in range(N)]
    min_margin = 20
    available_width = rect_width - 2 * min_margin

    # Fast search for max items per row
    max_items_per_row = 1
    global_scale = 1.0
    max_row_x_start = min_margin

    i = 0
    while i < N:
        # Binary search for max items count
        left, right = 1, N - i
        best_count = 1

        while left <= right:
            mid = (left + right) // 2
            end_idx = min(i + mid, N)
            sum_w = sum(nat_sizes[j][0] for j in range(i, end_idx))
            needed_width = sum_w + spacing * (mid - 1)

            if needed_width <= available_width:
                best_count = mid
                left = mid + 1
            else:
                right = mid - 1

        count = best_count
        sum_width = sum(nat_sizes[j][0] for j in range(i, i + count))

        if count > max_items_per_row:
            max_items_per_row = count
            desired_scale = available_width / (sum_width + spacing * (count - 1)) if sum_width > 0 else 1.0
            global_scale = min(desired_scale, max_scale)
            scaled_row_width = int(sum_width * global_scale) + spacing * (count - 1)
            max_row_x_start = max(min_margin, (rect_width - scaled_row_width) // 2)

        i += count

    # Second pass: place elements
    y = 0
    i = 0

    while i < N:
        # Binary search for current row
        left, right = 1, N - i
        best_count = 1

        while left <= right:
            mid = (left + right) // 2
            end_idx = min(i + mid, N)
            sum_w = sum(nat_sizes[j][0] for j in range(i, end_idx))
            needed_width = sum_w + spacing * (mid - 1)

            if needed_width <= available_width:
                best_count = mid
                left = mid + 1
            else:
                right = mid - 1

        count = best_count
        j = i + count

        # Calculate sizes for row
        sum_width = 0
        row_max_height = 0
        for k in range(i, j):
            w, h = nat_sizes[k]
            sum_width += w
            if h > row_max_height:
                row_max_height = h

        scaled_row_width = int(sum_width * global_scale) + spacing * (count - 1)

        # Determine starting position
        if count == max_items_per_row:
            x = max(min_margin, (rect_width - scaled_row_width) // 2)
        else:
            x = max_row_x_start

        # Place elements in row
        for k in range(i, j):
            w, h = nat_sizes[k]
            new_w = int(w * global_scale)
            new_h = int(h * global_scale)
            result[k][0] = x
            result[k][1] = y
            result[k][2] = new_w
            result[k][3] = new_h
            x += new_w + spacing

        y += int(row_max_height * global_scale) + spacing
        i = j

    return result, y


class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(20, 20, 20, 20)
        self._spacing = 20
        self._max_scale = 1.0

        # Simple cache
        self._cache_width = None
        self._cache_visible_hash = None
        self._cache_result = None

    def _get_visible_data(self):
        """Return list of visible items and their sizes"""
        visible_items = []
        visible_indices = []
        visible_sizes = []

        for i, item in enumerate(self.itemList):
            widget = item.widget()
            if widget and widget.isVisible():
                visible_items.append(item)
                visible_indices.append(i)
                s = item.sizeHint()
                visible_sizes.append((s.width(), s.height()))

        return visible_items, visible_indices, visible_sizes

    def _make_visible_hash(self, visible_sizes):
        """Create hash for change detection"""
        return hash(tuple(visible_sizes))

    def addItem(self, item: QLayoutItem) -> None:
        self.itemList.append(item)
        self._invalidate_cache()

    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self.itemList):
            self._invalidate_cache()
            return self.itemList.pop(index)
        raise IndexError("Index out of range")

    def _invalidate_cache(self):
        self._cache_width = None
        self._cache_visible_hash = None
        self._cache_result = None

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
        _, _, visible_sizes = self._get_visible_data()

        if not visible_sizes:
            return 0

        # Check cache
        visible_hash = self._make_visible_hash(visible_sizes)
        if (self._cache_width == width and
            self._cache_visible_hash == visible_hash and
            self._cache_result is not None):
            return self._cache_result[1]

        # Calculate
        geom_array, total_height = compute_layout(visible_sizes, width,
                                                   self._spacing, self._max_scale)

        # Save to cache
        self._cache_width = width
        self._cache_visible_hash = visible_hash
        self._cache_result = (geom_array, total_height)

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

        visible_items, visible_indices, visible_sizes = self._get_visible_data()

        if not visible_sizes:
            if not testOnly:
                for item in self.itemList:
                    item.setGeometry(QRect())
            return 0

        # Check cache
        visible_hash = self._make_visible_hash(visible_sizes)
        if (self._cache_width == rect.width() and
            self._cache_visible_hash == visible_hash and
            self._cache_result is not None):
            geom_array, total_height = self._cache_result
        else:
            # Calculate layout
            geom_array, total_height = compute_layout(visible_sizes, rect.width(),
                                                      self._spacing, self._max_scale)

            # Save to cache
            self._cache_width = rect.width()
            self._cache_visible_hash = visible_hash
            self._cache_result = (geom_array, total_height)

        if not testOnly:
            rx, ry = rect.x(), rect.y()

            # Set geometry for visible items
            for idx, item in enumerate(visible_items):
                x, y, w, h = geom_array[idx]
                item.setGeometry(QRect(x + rx, y + ry, w, h))

            # Hide invisible items
            visible_set = set(visible_indices)
            for i in range(N_total):
                if i not in visible_set:
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
