import numpy as np
from PySide6.QtWidgets import QLabel, QPushButton, QWidget, QLayout, QStyleOption, QLayoutItem
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter

def compute_layout(nat_sizes, rect_width, spacing, max_scale):
    """
    Вычисляет расположение элементов с учетом отступов и возможного увеличения карточек.
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
        # Подбираем количество элементов для текущего ряда
        while j < N:
            w = nat_sizes[j, 0]
            # Если уже есть хотя бы один элемент и следующий не помещается с учетом spacing, выходим
            if count > 0 and (sum_width + spacing + w) > rect_width:
                break
            sum_width += w
            count += 1
            h = nat_sizes[j, 1]
            if h > row_max_height:
                row_max_height = h
            j += 1
        # Доступная ширина ряда с учетом обязательных отступов между элементами
        available_width = rect_width - spacing * (count - 1)
        desired_scale = available_width / sum_width if sum_width > 0 else 1.0
        # Разрешаем увеличение карточек, но не более max_scale
        scale = desired_scale if desired_scale < max_scale else max_scale
        # Выравниваем по левому краю (offset = 0)
        x = 0
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
        # Устанавливаем отступы контейнера в 0 и задаем spacing между карточками
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = 5  # отступ между карточками
        self._max_scale = 1.2  # максимальное увеличение карточек (например, на 20%)

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
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                             margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        N = len(self.itemList)
        if N == 0:
            return 0

        # Собираем натуральные размеры всех элементов в массив NumPy
        nat_sizes = np.empty((N, 2), dtype=np.int32)
        for i, item in enumerate(self.itemList):
            s = item.sizeHint()
            nat_sizes[i, 0] = s.width()
            nat_sizes[i, 1] = s.height()

        # Вычисляем геометрию с учетом spacing и max_scale через numba-функцию
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

    def __init__(self, *args, icon=None, icon_size=16, icon_space=5, **kwargs):
        """
        Поддерживаются вызовы:
          - ClickableLabel("текст", parent=...) – первый аргумент строка,
          - ClickableLabel(parent, text="...") – если первым аргументом передается родитель.

        Аргументы:
          icon: QIcon или None – иконка, которая будет отрисована вместе с текстом.
          icon_size: int – размер иконки (ширина и высота).
          icon_space: int – отступ между иконкой и текстом.
        """
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setIcon(self, icon):
        """Устанавливает иконку и перерисовывает виджет."""
        self._icon = icon
        self.update()

    def icon(self):
        """Возвращает текущую иконку."""
        return self._icon

    def paintEvent(self, event):
        """Переопределяем отрисовку: рисуем иконку и текст в одном лейбле."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.contentsRect()
        alignment = self.alignment()

        icon_size = self._icon_size
        spacing = self._icon_space

        icon_rect = QRect()
        text_rect = QRect()
        text = self.text()

        if self._icon:
            # Получаем QPixmap нужного размера
            pixmap = self._icon.pixmap(icon_size, icon_size)
            icon_rect = QRect(0, 0, icon_size, icon_size)
            icon_rect.moveTop(rect.top() + (rect.height() - icon_size) // 2)
        else:
            pixmap = None

        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(text)
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
            icon_rect.moveLeft(x)
            text_rect = QRect(x + icon_size + spacing, y, text_width, text_height)
        else:
            text_rect = QRect(x, y, text_width, text_height)

        option = QStyleOption()
        option.initFrom(self)
        if pixmap:
            painter.drawPixmap(icon_rect, pixmap)
        self.style().drawItemText(
            painter,
            text_rect,
            alignment,
            self.palette(),
            self.isEnabled(),
            text,
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
                 min_font_size=8, max_font_size=14, padding=20, update_size=True, **kwargs):
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
            if self._checkable:
                self.setChecked(not self._isChecked)
            self.clicked.emit()
        super().mousePressEvent(event)
