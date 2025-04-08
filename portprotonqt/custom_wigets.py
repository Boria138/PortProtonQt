from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QPainter
import numpy as np

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

class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemList = []
        # Устанавливаем отступы контейнера в 0 и задаем spacing между карточками
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = 5  # отступ между карточками
        self._max_scale = 1.2  # максимальное увеличение карточек (например, на 20%)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(),
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
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), QtCore.QSize(w, h)))

        return total_height

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

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
        elif args and isinstance(args[0], QtWidgets.QWidget):
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
        self.setCursor(QtCore.Qt.PointingHandCursor)

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
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.contentsRect()
        alignment = self.alignment()

        icon_size = self._icon_size
        spacing = self._icon_space

        icon_rect = QtCore.QRect()
        text_rect = QtCore.QRect()
        text = self.text()

        if self._icon:
            # Получаем QPixmap нужного размера
            pixmap = self._icon.pixmap(icon_size, icon_size)
            icon_rect = QtCore.QRect(0, 0, icon_size, icon_size)
            icon_rect.moveTop(rect.top() + (rect.height() - icon_size) // 2)
        else:
            pixmap = None

        fm = QtGui.QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(text)
        text_height = fm.height()
        total_width = text_width + (icon_size + spacing if pixmap else 0)

        if alignment & QtCore.Qt.AlignHCenter:
            x = rect.left() + (rect.width() - total_width) // 2
        elif alignment & QtCore.Qt.AlignRight:
            x = rect.right() - total_width
        else:
            x = rect.left()

        y = rect.top() + (rect.height() - text_height) // 2

        if pixmap:
            icon_rect.moveLeft(x)
            text_rect = QtCore.QRect(x + icon_size + spacing, y, text_width, text_height)
        else:
            text_rect = QtCore.QRect(x, y, text_width, text_height)

        option = QtWidgets.QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget, option, painter, self)

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
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

class AutoSizeButton(QtWidgets.QPushButton):
    def __init__(self, *args, icon=None, icon_size=16,
                 min_font_size=8, max_font_size=14,
                 horizontal_padding=35, vertical_padding=10,
                 update_size=True, **kwargs):
        if args and isinstance(args[0], str):
            text = args[0]
            parent = kwargs.get("parent", None)
            super().__init__(text, parent)
        elif args and isinstance(args[0], QtWidgets.QWidget):
            parent = args[0]
            text = kwargs.get("text", "")
            super().__init__(text, parent)
        else:
            text = ""
            parent = kwargs.get("parent", None)
            super().__init__(text, parent)

        self._icon = icon
        self._icon_size = icon_size
        self._alignment = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        self._min_font_size = min_font_size
        self._max_font_size = max_font_size
        self._horizontal_padding = horizontal_padding
        self._vertical_padding = vertical_padding
        self._update_size = update_size
        self._original_font = self.font()
        self._original_text = self.text()

        if self._icon:
            self.setIcon(self._icon)
            self.setIconSize(QtCore.QSize(self._icon_size, self._icon_size))

        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFlat(True)
        super().setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

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
            self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._update_size:
            self.adjustFontSize()

    def adjustFontSize(self):
        if not self._original_text or not self._update_size:
            return

        # Определяем доступную ширину внутри кнопки
        available_width = self.width()
        if self._icon:
            available_width -= self._icon_size

        margins = self.contentsMargins()
        available_width -= (margins.left() + margins.right() + self._horizontal_padding * 2)

        font = QtGui.QFont(self._original_font)
        text = self._original_text

        # Подбираем максимально возможный размер шрифта, при котором текст укладывается
        chosen_size = self._max_font_size
        for font_size in range(self._max_font_size, self._min_font_size - 1, -1):
            font.setPointSize(font_size)
            fm = QtGui.QFontMetrics(font)
            text_width = fm.horizontalAdvance(text)
            if text_width <= available_width:
                chosen_size = font_size
                break

        font.setPointSize(chosen_size)
        self.setFont(font)

        # Вычисляем требуемую ширину для полного отображения текста
        fm = QtGui.QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        required_width = text_width + margins.left() + margins.right() + self._horizontal_padding * 2
        if self._icon:
            required_width += self._icon_size

        # Устанавливаем шрину
        self.setFixedWidth(required_width)

        super().setText(text)

    def sizeHint(self):
        if not self._update_size:
            return super().sizeHint()
        else:
            # Вычисляем оптимальный размер кнопки на основе текста и отступов
            font = self.font()
            fm = QtGui.QFontMetrics(font)
            text_width = fm.horizontalAdvance(self._original_text)
            margins = self.contentsMargins()
            width = text_width + margins.left() + margins.right() + self._horizontal_padding * 2
            if self._icon:
                width += self._icon_size
            height = fm.height() + margins.top() + margins.bottom() + self._vertical_padding * 2
            return QtCore.QSize(width, height)
