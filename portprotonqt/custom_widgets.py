import numpy as np
from PySide6.QtWidgets import QLabel, QPushButton, QWidget, QLayout, QLayoutItem
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter

def compute_layout(nat_sizes, rect_width, spacing, max_scale):
    """
    Вычисляет расположение элементов с учетом отступов и максимального масштабирования карточек.
    nat_sizes: массив (N, 2) с натуральными размерами элементов (ширина, высота).
    rect_width: доступная ширина контейнера.
    spacing: отступ между элементами.
    max_scale: максимальный коэффициент масштабирования (например, 1.2).

    Возвращает:
      result: массив (N, 4), где каждая строка содержит [x, y, new_width, new_height].
      total_height: итоговая высота всех рядов.
    """
    N = nat_sizes.shape[0]
    result = np.zeros((N, 4), dtype=np.int32)
    y = 0
    i = 0

    while i < N:
        sum_width = 0
        row_max_height = 0
        count = 0
        j = i

        # Подбираем количество элементов для текущего ряда с учетом max_scale
        scaled_sizes = nat_sizes * max_scale
        while j < N:
            w = scaled_sizes[j, 0]
            if count > 0 and (sum_width + spacing + w) > rect_width:
                break
            sum_width += w
            count += 1
            h = scaled_sizes[j, 1]
            if h > row_max_height:
                row_max_height = h
            j += 1

        # Вычисляем общую ширину ряда включая отступы
        total_row_width = sum_width + spacing * (count - 1)

        # Вычисляем смещение для центрирования ряда
        x_offset = (rect_width - total_row_width) // 2

        # Размещаем элементы в ряду с центрированием
        x = x_offset
        for k in range(i, j):
            new_w = int(nat_sizes[k, 0] * max_scale)
            new_h = int(nat_sizes[k, 1] * max_scale)
            result[k, 0] = x
            result[k, 1] = y
            result[k, 2] = new_w
            result[k, 3] = new_h
            x += new_w + spacing

        y += int(row_max_height) + spacing
        i = j

    return result, y

class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = 3
        self._max_scale = 1.2

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
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            # Учитываем максимальный масштаб при расчете минимального размера
            item_size = item.sizeHint()
            scaled_size = QSize(int(item_size.width() * self._max_scale), int(item_size.height() * self._max_scale))
            size = size.expandedTo(scaled_size)
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        N = len(self.itemList)
        if N == 0:
            return 0

        nat_sizes = np.empty((N, 2), dtype=np.int32)
        for i, item in enumerate(self.itemList):
            s = item.sizeHint()
            nat_sizes[i, 0] = s.width()
            nat_sizes[i, 1] = s.height()

        geom_array, total_height = compute_layout(nat_sizes, rect.width(), self._spacing, self._max_scale)

        if not testOnly:
            for i, item in enumerate(self.itemList):
                x = geom_array[i, 0] + rect.x()
                y = geom_array[i, 1] + rect.y()
                w = geom_array[i, 2]
                h = geom_array[i, 3]
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))

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
        self._card_width = 250  # Значение по умолчанию
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
        """Обновляет ширину карточки и пересчитывает размер шрифта."""
        self._card_width = card_width
        self.updateFontSize()

    def updateFontSize(self):
        """Обновляет размер шрифта на основе card_width и font_scale_factor."""
        font = self.font()
        font_size = int(self._card_width * self._font_scale_factor)
        font.setPointSize(max(8, font_size))  # Минимальный размер шрифта 8
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

        # Считаем, сколько места остаётся под текст
        available_width = rect.width()
        if pixmap:
            available_width -= (icon_size + spacing)
        # Отступы по 2px с каждой стороны
        available_width = max(0, available_width - 4)

        # Получаем «обрезанный» текст с многоточием
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

        # Изначально выставляем минимальную ширину
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

        # Определяем доступную ширину внутри кнопки
        available_width = self.width()
        if self._icon:
            available_width -= self._icon_size

        margins = self.contentsMargins()
        available_width -= (margins.left() + margins.right() + self._padding * 2)

        font = QFont(self._original_font)
        text = self._original_text

        # Подбираем максимально возможный размер шрифта, при котором текст укладывается
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

        # После выбора шрифта вычисляем требуемую ширину для полного отображения текста
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        required_width = text_width + margins.left() + margins.right() + self._padding * 2
        if self._icon:
            required_width += self._icon_size

        # Если текущая ширина меньше требуемой, обновляем минимальную ширину
        if self.width() < required_width:
            self.setMinimumWidth(required_width)

        super().setText(text)

    def sizeHint(self):
        if not self._update_size:
            return super().sizeHint()
        else:
            # Вычисляем оптимальный размер кнопки на основе текста и отступов
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
        # Explicitly enable focus
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
            # Ensure widget can take focus on click
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            if self._checkable:
                self.setChecked(not self._isChecked)
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)
