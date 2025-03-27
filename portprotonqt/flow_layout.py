from PySide6 import QtCore, QtWidgets
import numpy as np
from numba import njit

@njit
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
