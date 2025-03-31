import os
import urllib.request
from PySide6 import QtCore, QtGui, QtWidgets
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.config_utils import read_proxy_config, read_theme_from_config
from portprotonqt.theme_manager import ThemeManager
import functools

def load_pixmap(cover, width, height):
    """
    Загружает изображение из локального файла или по URL (только для Steam CDN), масштабирует и обрезает его.
    Если загрузка не удалась, берёт placeholder из темы.
    Итоговое обрезанное изображение кешируется в памяти через lru_cache.
    """
    return get_cropped_pixmap_cached(cover, width, height)

@functools.lru_cache(maxsize=256)
def get_cropped_pixmap_cached(cover, width, height):
    """
    Загружает исходное изображение, масштабирует и обрезает его до указанных размеров.
    Результат кешируется с помощью lru_cache.
    """
    theme_manager = ThemeManager()
    current_theme_name = read_theme_from_config()

    pixmap = QtGui.QPixmap()

    # Обработка ссылок с CDN Steam
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
                    try:
                        proxy = read_proxy_config()
                        if proxy:
                            proxy_handler = urllib.request.ProxyHandler(proxy)
                            opener = urllib.request.build_opener(proxy_handler)
                            response = opener.open(cover, timeout=5)
                        else:
                            response = urllib.request.urlopen(cover, timeout=5)
                        if response.status == 200:
                            content = response.read()
                            with open(local_path, "wb") as f:
                                f.write(content)
                            pixmap.load(local_path)
                    except Exception as e:
                        print("Ошибка загрузки обложки из Steam CDN:", e)
        except Exception as e:
            print("Ошибка обработки URL:", e)

    # Если путь указывает на локальный файл
    elif QtCore.QFile.exists(cover):
        pixmap.load(cover)

    # Если изображение не загрузилось, используем placeholder
    if pixmap.isNull():
        placeholder_path = theme_manager.get_theme_image("placeholder.png", current_theme_name)
        if placeholder_path and QtCore.QFile.exists(placeholder_path):
            pixmap.load(placeholder_path)
        else:
            pixmap = QtGui.QPixmap(width, height)
            pixmap.fill(QtGui.QColor("#333333"))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QPen(QtGui.QColor("white")))
            painter.setFont(QtGui.QFont("Poppins", 12))
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "No Image")
            painter.end()
        return pixmap

    # Масштабирование с сохранением пропорций и обрезка центральной части
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
    Изображение отображается в области фиксированного размера, а подпись располагается чуть выше нижней границы.
    В окне есть кнопки-стрелки для перелистывания изображений.
    Диалог закрывается при клике по изображению или подписи.
    """
    FIXED_WIDTH = 800
    FIXED_HEIGHT = 400

    def __init__(self, images, current_index=0, parent=None, theme=None):
        """
        :param images: Список кортежей (QPixmap, caption)
        :param current_index: Индекс текущего изображения
        :param theme: Объект темы для стилизации (если None, используется default_styles)
        """
        super().__init__(parent)
        # Удаление диалога после закрытия
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.images = images
        self.current_index = current_index
        self.theme = theme if theme else default_styles

        # Убираем стандартные элементы управления окна
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.init_ui()
        self.update_display()

        # Фильтруем события для закрытия диалога по клику
        self.imageLabel.installEventFilter(self)
        self.captionLabel.installEventFilter(self)

    def init_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Контейнер для изображения и стрелок
        self.imageContainer = QtWidgets.QWidget()
        self.imageContainer.setFixedSize(self.FIXED_WIDTH, self.FIXED_HEIGHT)
        self.imageContainerLayout = QtWidgets.QHBoxLayout(self.imageContainer)
        self.imageContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.imageContainerLayout.setSpacing(0)

        # Левая стрелка
        self.prevButton = QtWidgets.QToolButton()
        self.prevButton.setArrowType(QtCore.Qt.LeftArrow)
        self.prevButton.setStyleSheet(self.theme.PREV_BUTTON_STYLE)
        self.prevButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.prevButton.setFixedSize(40, 40)
        self.prevButton.clicked.connect(self.show_prev)
        self.imageContainerLayout.addWidget(self.prevButton)

        # Метка для изображения
        self.imageLabel = QtWidgets.QLabel()
        self.imageLabel.setFixedSize(self.FIXED_WIDTH - 80, self.FIXED_HEIGHT)
        self.imageLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.imageContainerLayout.addWidget(self.imageLabel, stretch=1)

        # Правая стрелка
        self.nextButton = QtWidgets.QToolButton()
        self.nextButton.setArrowType(QtCore.Qt.RightArrow)
        self.nextButton.setStyleSheet(self.theme.NEXT_BUTTON_STYLE)
        self.nextButton.setCursor(QtCore.Qt.PointingHandCursor)
        self.nextButton.setFixedSize(40, 40)
        self.nextButton.clicked.connect(self.show_next)
        self.imageContainerLayout.addWidget(self.nextButton)

        self.layout.addWidget(self.imageContainer)

        # Небольшой отступ между изображением и подписью
        spacer = QtWidgets.QSpacerItem(20, 10, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.layout.addItem(spacer)

        # Подпись
        self.captionLabel = QtWidgets.QLabel()
        self.captionLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.captionLabel.setFixedHeight(40)
        self.captionLabel.setWordWrap(True)
        self.captionLabel.setStyleSheet(self.theme.CAPTION_LABEL_STYLE)
        self.captionLabel.setCursor(QtCore.Qt.PointingHandCursor)
        self.layout.addWidget(self.captionLabel)

    def update_display(self):
        """Обновляет изображение и подпись согласно текущему индексу."""
        if not self.images:
            return

        # Очищаем старое содержимое
        self.imageLabel.clear()
        self.captionLabel.clear()
        QtWidgets.QApplication.processEvents()

        pixmap, caption = self.images[self.current_index]
        # Масштабируем изображение так, чтобы оно поместилось в область фиксированного размера
        scaled_pixmap = pixmap.scaled(
            self.FIXED_WIDTH - 80,  # учитываем ширину стрелок
            self.FIXED_HEIGHT,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.imageLabel.setPixmap(scaled_pixmap)
        self.captionLabel.setText(caption)
        self.setWindowTitle(caption)

        # Принудительная перерисовка виджетов
        self.imageLabel.repaint()
        self.captionLabel.repaint()
        self.repaint()

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

    def changeEvent(self, event):
        """Закрывает диалог при потере фокуса."""
        if event.type() == QtCore.QEvent.ActivationChange:
            if not self.isActiveWindow():
                self.close()
        super().changeEvent(event)

    def mousePressEvent(self, event):
        """Закрывает диалог при клике на пустую область."""
        pos = event.pos()
        # Проверяем, находится ли клик вне imageContainer и captionLabel
        if not (self.imageContainer.geometry().contains(pos) or
                self.captionLabel.geometry().contains(pos)):
            self.close()
        super().mousePressEvent(event)

class ClickablePixmapItem(QtWidgets.QGraphicsPixmapItem):
    """
    Элемент карусели, реагирующий на клик.
    При клике открывается FullscreenDialog с возможностью перелистывания изображений.
    """
    def __init__(self, pixmap, caption="Просмотр изображения", images_list=None, index=0, carousel=None):
        """
        :param pixmap: QPixmap для отображения в карусели
        :param caption: Подпись к изображению
        :param images_list: Список всех изображений (кортежей (QPixmap, caption)),
                            чтобы в диалоге можно было перелистывать.
                            Если не передан, будет использован только текущее изображение.
        :param index: Индекс текущего изображения в images_list.
        :param carousel: Ссылка на родительскую карусель (ImageCarousel) для управления стрелками.
        """
        super().__init__(pixmap)
        self.caption = caption
        self.images_list = images_list if images_list is not None else [(pixmap, caption)]
        self.index = index
        self.carousel = carousel
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(caption)
        self._click_start_position = None
        self.setAcceptedMouseButtons(QtCore.Qt.LeftButton)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._click_start_position = event.scenePos()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._click_start_position is not None:
            distance = (event.scenePos() - self._click_start_position).manhattanLength()
            if distance < 2:
                self.show_fullscreen()
                event.accept()
                return
        event.accept()

    def show_fullscreen(self):
        # Скрываем стрелки карусели перед открытием FullscreenDialog
        if self.carousel:
            self.carousel.prevArrow.hide()
            self.carousel.nextArrow.hide()
        dialog = FullscreenDialog(self.images_list, current_index=self.index)
        dialog.exec()
        # После закрытия диалога обновляем видимость стрелок
        if self.carousel:
            self.carousel.update_arrows_visibility()


class ImageCarousel(QtWidgets.QGraphicsView):
    """
    Карусель изображений с адаптивностью, возможностью увеличения по клику
    и перетаскиванием мыши.
    """
    def __init__(self, images, parent=None, theme=None):
        super().__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.images = images  # Список кортежей: (QPixmap, caption)
        self.image_items = []
        self._animation = None
        self.theme = theme if theme else default_styles
        self.init_ui()
        self.create_arrows()

        # Переменные для поддержки перетаскивания
        self._drag_active = False
        self._drag_start_position = None
        self._scroll_start_value = None

    def init_ui(self):
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        x_offset = 10  # Отступ между изображениями
        max_height = 300  # Фиксированная высота изображений
        x = 0

        for i, (pixmap, caption) in enumerate(self.images):
            item = ClickablePixmapItem(
                pixmap.scaledToHeight(max_height, QtCore.Qt.SmoothTransformation),
                caption,
                images_list=self.images,
                index=i,
                carousel=self  # Передаём ссылку на карусель
            )
            item.setPos(x, 0)
            self.scene.addItem(item)
            self.image_items.append(item)
            x += item.pixmap().width() + x_offset

        self.setSceneRect(0, 0, x, max_height)

    def create_arrows(self):
        """Создаёт кнопки-стрелки и привязывает их к функциям прокрутки."""
        self.prevArrow = QtWidgets.QToolButton(self)
        self.prevArrow.setArrowType(QtCore.Qt.LeftArrow)
        self.prevArrow.setStyleSheet(self.theme.PREV_BUTTON_STYLE)
        self.prevArrow.setFixedSize(40, 40)
        self.prevArrow.setCursor(QtCore.Qt.PointingHandCursor)
        self.prevArrow.setAutoRepeat(True)
        self.prevArrow.setAutoRepeatDelay(300)
        self.prevArrow.setAutoRepeatInterval(100)
        self.prevArrow.clicked.connect(self.scroll_left)
        self.prevArrow.raise_()

        self.nextArrow = QtWidgets.QToolButton(self)
        self.nextArrow.setArrowType(QtCore.Qt.RightArrow)
        self.nextArrow.setStyleSheet(self.theme.NEXT_BUTTON_STYLE)
        self.nextArrow.setFixedSize(40, 40)
        self.nextArrow.setCursor(QtCore.Qt.PointingHandCursor)
        self.nextArrow.setAutoRepeat(True)
        self.nextArrow.setAutoRepeatDelay(300)
        self.nextArrow.setAutoRepeatInterval(100)
        self.nextArrow.clicked.connect(self.scroll_right)
        self.nextArrow.raise_()

        # Проверяем видимость стрелок при создании
        self.update_arrows_visibility()

    def update_arrows_visibility(self):
        """
        Показывает стрелки, если контент шире видимой области.
        Иначе скрывает их.
        """
        # Если стрелки уже созданы, то обновляем их видимость
        if hasattr(self, "prevArrow") and hasattr(self, "nextArrow"):
            if self.horizontalScrollBar().maximum() == 0:
                self.prevArrow.hide()
                self.nextArrow.hide()
            else:
                self.prevArrow.show()
                self.nextArrow.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 10
        self.prevArrow.move(margin, (self.height() - self.prevArrow.height()) // 2)
        self.nextArrow.move(self.width() - self.nextArrow.width() - margin,
                              (self.height() - self.nextArrow.height()) // 2)
        self.update_arrows_visibility()

    def animate_scroll(self, end_value):
        scrollbar = self.horizontalScrollBar()
        start_value = scrollbar.value()
        animation = QtCore.QPropertyAnimation(scrollbar, b"value", self)
        animation.setDuration(300)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self._animation = animation
        animation.start()

    def scroll_left(self):
        scrollbar = self.horizontalScrollBar()
        new_value = scrollbar.value() - 100
        self.animate_scroll(new_value)

    def scroll_right(self):
        scrollbar = self.horizontalScrollBar()
        new_value = scrollbar.value() + 100
        self.animate_scroll(new_value)

    def update_images(self, new_images):
        self.scene.clear()
        self.images = new_images
        self.image_items.clear()
        self.init_ui()
        self.update_arrows_visibility()

    # Обработка событий мыши для перетаскивания
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_active = True
            self._drag_start_position = event.pos()
            self._scroll_start_value = self.horizontalScrollBar().value()
            # Скрываем стрелки при начале перетаскивания
            if hasattr(self, "prevArrow"):
                self.prevArrow.hide()
            if hasattr(self, "nextArrow"):
                self.nextArrow.hide()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active:
            delta = event.pos().x() - self._drag_start_position.x()
            new_value = self._scroll_start_value - delta
            self.horizontalScrollBar().setValue(new_value)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        # Показываем стрелки после завершения перетаскивания (с проверкой видимости)
        self.update_arrows_visibility()
        super().mouseReleaseEvent(event)
