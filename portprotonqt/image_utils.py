import os
import requests
from PySide6 import QtCore, QtGui, QtWidgets
import portprotonqt.themes.standart_lite.styles as default_styles


def load_pixmap(cover, width, height):
    """
    Загружает изображение из локального файла или по URL и масштабирует его.
    Если загрузка не удалась, создаёт резервное изображение.
    Если ссылка ведёт на Steam CDN, обложка кешируется локально.
    После масштабирования с KeepAspectRatioByExpanding происходит обрезка центральной части до нужных размеров.
    """
    pixmap = QtGui.QPixmap()

    if cover.startswith("https://steamcdn-a.akamaihd.net/steam/apps/"):
        try:
            parts = cover.split("/")
            appid = None
            if "apps" in parts:
                idx = parts.index("apps")
                if idx + 1 < len(parts):
                    appid = parts[idx + 1]
            if appid:
                xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
                image_folder = os.path.join(xdg_cache_home, "PortProtonQT", "images")
                os.makedirs(image_folder, exist_ok=True)
                local_path = os.path.join(image_folder, f"{appid}.jpg")
                if os.path.exists(local_path):
                    pixmap.load(local_path)
                else:
                    response = requests.get(cover)
                    if response.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(response.content)
                        pixmap.load(local_path)
        except Exception as e:
            print("Ошибка загрузки обложки из Steam CDN:", e)

    elif QtCore.QFile.exists(cover):
        pixmap.load(cover)

    if pixmap.isNull():
        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(QtGui.QColor("#333333"))
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QPen(QtGui.QColor("white")))
        painter.setFont(QtGui.QFont("Poppins", 12))
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "No Image")
        painter.end()

    scaled = pixmap.scaled(width, height, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
    x = (scaled.width() - width) // 2
    y = (scaled.height() - height) // 2
    cropped = scaled.copy(x, y, width, height)
    return cropped


def round_corners(pixmap, radius):
    """
    Возвращает QPixmap с закруглёнными углами.
    """
    if pixmap.isNull():
        return pixmap
    size = pixmap.size()
    rounded = QtGui.QPixmap(size)
    rounded.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(rounded)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    path = QtGui.QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


class FullscreenDialog(QtWidgets.QDialog):
    """
    Диалог для просмотра изображений без стандартных элементов управления.
    Подпись выводится снизу под изображением.
    В окне есть кнопки-стрелки для перелистывания изображений.
    Диалог закрывается при клике по изображению или подписи.
    """
    def __init__(self, images, current_index=0, parent=None, theme=None):
        """
        :param images: Список кортежей (QPixmap, caption)
        :param current_index: Индекс текущего изображения
        :param theme: Объект темы для стилизации (если None, используется default_styles)
        """
        super().__init__(parent)
        self.images = images
        self.current_index = current_index
        self.theme = theme if theme else default_styles

        # Убираем стандартные элементы управления окна
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.init_ui()
        self.update_display()

        # Устанавливаем фильтр событий для закрытия диалога по клику
        self.imageLabel.installEventFilter(self)
        self.captionLabel.installEventFilter(self)

    def init_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Контейнер для изображения и стрелок
        self.imageContainer = QtWidgets.QWidget()
        self.imageContainerLayout = QtWidgets.QHBoxLayout(self.imageContainer)
        self.imageContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.imageContainerLayout.setSpacing(0)

        # Кнопка "назад"
        self.prevButton = QtWidgets.QToolButton()
        self.prevButton.setArrowType(QtCore.Qt.LeftArrow)
        self.prevButton.setStyleSheet(self.theme.PREV_BUTTON_STYLE)
        self.prevButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.prevButton.clicked.connect(self.show_prev)
        self.imageContainerLayout.addWidget(self.prevButton)

        # Метка для изображения
        self.imageLabel = QtWidgets.QLabel()
        self.imageLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.imageContainerLayout.addWidget(self.imageLabel, stretch=1)

        # Кнопка "вперёд"
        self.nextButton = QtWidgets.QToolButton()
        self.nextButton.setArrowType(QtCore.Qt.RightArrow)
        self.nextButton.setStyleSheet(self.theme.NEXT_BUTTON_STYLE)
        self.nextButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.nextButton.clicked.connect(self.show_next)
        self.imageContainerLayout.addWidget(self.nextButton)

        self.layout.addWidget(self.imageContainer)

        # Метка для подписи под изображением
        self.captionLabel = QtWidgets.QLabel()
        self.captionLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.captionLabel.setStyleSheet(self.theme.CAPTION_LABEL_STYLE)
        self.captionLabel.setCursor(QtCore.Qt.PointingHandCursor)
        self.layout.addWidget(self.captionLabel)

    def update_display(self):
        """Обновляет изображение и подпись в соответствии с текущим индексом."""
        if not self.images:
            return
        pixmap, caption = self.images[self.current_index]
        self.imageLabel.setPixmap(pixmap.scaledToWidth(800, QtCore.Qt.SmoothTransformation))
        self.captionLabel.setText(caption)

    def show_prev(self):
        """Показывает предыдущее изображение."""
        if self.images:
            self.current_index = (self.current_index - 1) % len(self.images)
            self.update_display()

    def show_next(self):
        """Показывает следующее изображение."""
        if self.images:
            self.current_index = (self.current_index + 1) % len(self.images)
            self.update_display()

    def eventFilter(self, obj, event):
        """Закрывает диалог при клике по изображению или подписи."""
        if event.type() == QtCore.QEvent.MouseButtonPress and obj in [self.imageLabel, self.captionLabel]:
            self.close()
            return True
        return super().eventFilter(obj, event)


class ClickablePixmapItem(QtWidgets.QGraphicsPixmapItem):
    """
    Элемент карусели, реагирующий на клик.
    При клике открывается FullscreenDialog с возможностью перелистывания изображений.
    """
    def __init__(self, pixmap, caption="Просмотр изображения", images_list=None):
        """
        :param pixmap: QPixmap для отображения в карусели
        :param caption: Подпись к изображению
        :param images_list: Список всех изображений (кортежей (QPixmap, caption)),
                            чтобы в диалоге можно было перелистывать.
                            Если не передан, будет использован только текущее изображение.
        """
        super().__init__(pixmap)
        self.caption = caption
        self.images_list = images_list if images_list is not None else [(pixmap, caption)]
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.show_fullscreen()
        super().mousePressEvent(event)

    def show_fullscreen(self):
        # Получаем представление (виджет) карусели из сцены
        views = self.scene().views()
        if views:
            carousel_view = views[0]
            # Скрываем стрелки карусели
            carousel_view.prevArrow.hide()
            carousel_view.nextArrow.hide()
        else:
            carousel_view = None

        # Определяем индекс текущего изображения в списке, если оно там присутствует
        try:
            idx = self.images_list.index((self.pixmap(), self.caption))
        except ValueError:
            idx = 0

        dialog = FullscreenDialog(self.images_list, current_index=idx)
        dialog.exec()

        # После закрытия диалога – возвращаем стрелки карусели, если они были найдены
        if carousel_view:
            carousel_view.prevArrow.show()
            carousel_view.nextArrow.show()


class ImageCarousel(QtWidgets.QGraphicsView):
    """
    Карусель изображений с адаптивностью и возможностью увеличения по клику.
    При создании передается список кортежей: (QPixmap, caption).
    Добавлены кнопки-стрелки для перемещения карусели с плавной анимацией.
    """
    def __init__(self, images, parent=None, theme=None):
        super().__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.images = images  # Список кортежей: (QPixmap, caption)
        self.image_items = []
        self._animation = None  # Переменная для хранения текущей анимации
        self.theme = theme if theme else default_styles
        self.init_ui()
        self.create_arrows()

    def init_ui(self):
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        x_offset = 10  # Отступ между изображениями
        max_height = 300  # Фиксированная высота изображений
        x = 0

        for pixmap, caption in self.images:
            item = ClickablePixmapItem(
                pixmap.scaledToHeight(max_height, QtCore.Qt.SmoothTransformation),
                caption,
                images_list=self.images
            )
            item.setPos(x, 0)
            self.scene.addItem(item)
            self.image_items.append(item)
            x += item.pixmap().width() + x_offset

        self.setSceneRect(0, 0, x, max_height)

    def create_arrows(self):
        """Создаёт кнопки-стрелки и привязывает к функциям прокрутки."""
        # Левая кнопка
        self.prevArrow = QtWidgets.QToolButton(self)
        self.prevArrow.setArrowType(QtCore.Qt.LeftArrow)
        # Используем стиль из темы
        self.prevArrow.setStyleSheet(self.theme.PREV_BUTTON_STYLE)
        self.prevArrow.setFixedSize(40, 40)
        self.prevArrow.setCursor(QtCore.Qt.PointingHandCursor)
        self.prevArrow.setAutoRepeat(True)
        self.prevArrow.setAutoRepeatDelay(300)
        self.prevArrow.setAutoRepeatInterval(100)
        self.prevArrow.clicked.connect(self.scroll_left)
        self.prevArrow.raise_()  # Поверх содержимого

        # Правая кнопка
        self.nextArrow = QtWidgets.QToolButton(self)
        self.nextArrow.setArrowType(QtCore.Qt.RightArrow)
        # Используем стиль из темы
        self.nextArrow.setStyleSheet(self.theme.NEXT_BUTTON_STYLE)
        self.nextArrow.setFixedSize(40, 40)
        self.nextArrow.setCursor(QtCore.Qt.PointingHandCursor)
        self.nextArrow.setAutoRepeat(True)
        self.nextArrow.setAutoRepeatDelay(300)
        self.nextArrow.setAutoRepeatInterval(100)
        self.nextArrow.clicked.connect(self.scroll_right)
        self.nextArrow.raise_()

    def resizeEvent(self, event):
        """Переопределяем, чтобы кнопки-стрелки корректно позиционировались при изменении размеров."""
        super().resizeEvent(event)
        margin = 10
        self.prevArrow.move(margin, (self.height() - self.prevArrow.height()) // 2)
        self.nextArrow.move(self.width() - self.nextArrow.width() - margin,
                            (self.height() - self.nextArrow.height()) // 2)

    def animate_scroll(self, end_value):
        """Выполняет анимацию скроллинга до указанного значения."""
        scrollbar = self.horizontalScrollBar()
        start_value = scrollbar.value()
        animation = QtCore.QPropertyAnimation(scrollbar, b"value", self)
        animation.setDuration(300)  # длительность анимации в мс
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        # Сохраняем анимацию, чтобы она не была удалена сборщиком мусора
        self._animation = animation
        animation.start()

    def scroll_left(self):
        """Прокручивает карусель влево с плавной анимацией."""
        scrollbar = self.horizontalScrollBar()
        new_value = scrollbar.value() - 100
        self.animate_scroll(new_value)

    def scroll_right(self):
        """Прокручивает карусель вправо с плавной анимацией."""
        scrollbar = self.horizontalScrollBar()
        new_value = scrollbar.value() + 100
        self.animate_scroll(new_value)

    def update_images(self, new_images):
        """
        Обновляет карусель новыми изображениями.
        new_images — список кортежей (QPixmap, caption).
        """
        self.scene.clear()
        self.images = new_images
        self.image_items.clear()
        self.init_ui()
