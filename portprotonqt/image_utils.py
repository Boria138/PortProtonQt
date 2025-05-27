import os
from PySide6.QtGui import QPen, QColor, QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt, QFile, QEvent, QByteArray, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsItem, QToolButton, QFrame, QLabel, QGraphicsScene, QHBoxLayout, QWidget, QGraphicsView, QVBoxLayout, QSizePolicy
from PySide6.QtWidgets import QSpacerItem, QGraphicsPixmapItem, QDialog, QApplication
import portprotonqt.themes.standart.styles as default_styles
from portprotonqt.config_utils import read_theme_from_config
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger
from collections.abc import Callable

downloader = Downloader()
logger = get_logger(__name__)

def load_pixmap_async(cover: str, width: int, height: int, callback: Callable[[QPixmap], None], app_name: str = ""):
    """
    Асинхронно загружает обложку и вызывает callback с готовым QPixmap.
    """
    theme_manager = ThemeManager()
    current_theme_name = read_theme_from_config()

    def finish_with(pixmap: QPixmap):
        # Обрезаем и масштабируем
        scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - width) // 2
        y = (scaled.height() - height) // 2
        cropped = scaled.copy(x, y, width, height)
        callback(cropped)

    # Cache directory
    xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    image_folder = os.path.join(xdg_cache_home, "PortProtonQT", "images")
    os.makedirs(image_folder, exist_ok=True)

    # Проверяем CDN Steam
    if cover and cover.startswith("https://steamcdn-a.akamaihd.net/steam/apps/"):
        try:
            parts = cover.split("/")
            appid = None
            if "apps" in parts:
                idx = parts.index("apps")
                if idx + 1 < len(parts):
                    appid = parts[idx + 1]
            if appid:
                local_path = os.path.join(image_folder, f"{appid}.jpg")

                if os.path.exists(local_path):
                    pixmap = QPixmap(local_path)
                    return finish_with(pixmap)

                def on_downloaded(result: str | None):
                    pixmap = QPixmap()
                    if result and os.path.exists(result):
                        pixmap.load(result)
                    if pixmap.isNull():
                        placeholder_path = theme_manager.get_theme_image("placeholder", current_theme_name)
                        if placeholder_path and QFile.exists(placeholder_path):
                            pixmap.load(placeholder_path)
                        else:
                            logger.warning("Placeholder image not found for theme %s", current_theme_name)
                            pixmap = QPixmap(width, height)
                            pixmap.fill(QColor("#333333"))
                            painter = QPainter(pixmap)
                            painter.setPen(QPen(QColor("white")))
                            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "No Image")
                            painter.end()
                    finish_with(pixmap)

                downloader.download_async(cover, local_path, timeout=5, callback=on_downloaded)
                return
        except Exception as e:
            logger.error(f"Ошибка обработки URL {cover}: {e}")

    # Generic HTTP/HTTPS URL (e.g., EGS covers)
    if cover and cover.startswith(("http://", "https://")):
        try:
            # Generate a cache filename based on URL hash
            local_path = os.path.join(image_folder, f"{app_name}.jpg")  # Assume JPG for EGS
            if os.path.exists(local_path):
                logger.debug("Loading cached EGS cover: %s", local_path)
                pixmap = QPixmap(local_path)
                return finish_with(pixmap)

            def on_downloaded(result: str | None):
                pixmap = QPixmap()
                if result and os.path.exists(result):
                    pixmap.load(result)
                    logger.info("Downloaded EGS cover: %s", result)
                if pixmap.isNull():
                    logger.warning("Failed to download EGS cover from %s", cover)
                    placeholder_path = theme_manager.get_theme_image("placeholder", current_theme_name)
                    if placeholder_path and QFile.exists(placeholder_path):
                        pixmap.load(placeholder_path)
                    else:
                        logger.warning("Placeholder image not found for theme %s", current_theme_name)
                        pixmap = QPixmap(width, height)
                        pixmap.fill(QColor("#333333"))
                        painter = QPainter(pixmap)
                        painter.setPen(QPen(QColor("white")))
                        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "No Image")
                        painter.end()
                finish_with(pixmap)

            logger.debug("Downloading EGS cover: %s", cover)
            downloader.download_async(cover, local_path, timeout=5, callback=on_downloaded)
            return
        except Exception as e:
            logger.error("Error processing EGS URL %s: %s", cover, str(e))

    # Локальный файл
    if cover and QFile.exists(cover):
        pixmap = QPixmap(cover)
        return finish_with(pixmap)

    # Placeholder
    placeholder_path = theme_manager.get_theme_image("placeholder", current_theme_name)
    pixmap = QPixmap()
    if placeholder_path and QFile.exists(placeholder_path):
        pixmap.load(placeholder_path)
    else:
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#333333"))
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor("white")))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "No Image")
        painter.end()
    finish_with(pixmap)

def round_corners(pixmap, radius):
    """
    Возвращает QPixmap с закруглёнными углами.
    """
    if pixmap.isNull():
        return pixmap
    size = pixmap.size()
    rounded = QPixmap(size)
    rounded.fill(QColor(0, 0, 0, 0))
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded

class FullscreenDialog(QDialog):
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
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        self.images = images
        self.current_index = current_index
        self.theme = theme if theme else default_styles

        # Убираем стандартные элементы управления окна
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.init_ui()
        self.update_display()

        # Фильтруем события для закрытия диалога по клику
        self.imageLabel.installEventFilter(self)
        self.captionLabel.installEventFilter(self)

    def init_ui(self):
        self.mainLayout = QVBoxLayout(self)
        self.setLayout(self.mainLayout)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # Контейнер для изображения и стрелок
        self.imageContainer = QWidget()
        self.imageContainer.setFixedSize(self.FIXED_WIDTH, self.FIXED_HEIGHT)
        self.imageContainerLayout = QHBoxLayout(self.imageContainer)
        self.imageContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.imageContainerLayout.setSpacing(0)

        # Левая стрелка
        self.prevButton = QToolButton()
        self.prevButton.setArrowType(Qt.ArrowType.LeftArrow)
        self.prevButton.setStyleSheet(self.theme.PREV_BUTTON_STYLE)
        self.prevButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prevButton.setFixedSize(40, 40)
        self.prevButton.clicked.connect(self.show_prev)
        self.imageContainerLayout.addWidget(self.prevButton)

        # Метка для изображения
        self.imageLabel = QLabel()
        self.imageLabel.setFixedSize(self.FIXED_WIDTH - 80, self.FIXED_HEIGHT)
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageContainerLayout.addWidget(self.imageLabel, stretch=1)

        # Правая стрелка
        self.nextButton = QToolButton()
        self.nextButton.setArrowType(Qt.ArrowType.RightArrow)
        self.nextButton.setStyleSheet(self.theme.NEXT_BUTTON_STYLE)
        self.nextButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nextButton.setFixedSize(40, 40)
        self.nextButton.clicked.connect(self.show_next)
        self.imageContainerLayout.addWidget(self.nextButton)

        self.mainLayout.addWidget(self.imageContainer)

        # Небольшой отступ между изображением и подписью
        spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.mainLayout.addItem(spacer)

        # Подпись
        self.captionLabel = QLabel()
        self.captionLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.captionLabel.setFixedHeight(40)
        self.captionLabel.setWordWrap(True)
        self.captionLabel.setStyleSheet(self.theme.CAPTION_LABEL_STYLE)
        self.captionLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mainLayout.addWidget(self.captionLabel)

    def update_display(self):
        """Обновляет изображение и подпись согласно текущему индексу."""
        if not self.images:
            return

        # Очищаем старое содержимое
        self.imageLabel.clear()
        self.captionLabel.clear()
        QApplication.processEvents()

        pixmap, caption = self.images[self.current_index]
        # Масштабируем изображение так, чтобы оно поместилось в область фиксированного размера
        scaled_pixmap = pixmap.scaled(
            self.FIXED_WIDTH - 80,  # учитываем ширину стрелок
            self.FIXED_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
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
        if event.type() == QEvent.Type.MouseButtonPress and obj in [self.imageLabel, self.captionLabel]:
            self.close()
            return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        """Закрывает диалог при потере фокуса."""
        if event.type() == QEvent.Type.ActivationChange:
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

class ClickablePixmapItem(QGraphicsPixmapItem):
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(caption)
        self._click_start_position = None
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_start_position = event.scenePos()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._click_start_position is not None:
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


class ImageCarousel(QGraphicsView):
    """
    Карусель изображений с адаптивностью, возможностью увеличения по клику
    и перетаскиванием мыши.
    """
    def __init__(self, images: list[tuple], parent: QWidget | None = None, theme: object | None = None):
        super().__init__(parent)

        # Аннотируем тип scene как QGraphicsScene
        self.carousel_scene: QGraphicsScene = QGraphicsScene(self)
        self.setScene(self.carousel_scene)

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
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        x_offset = 10  # Отступ между изображениями
        max_height = 300  # Фиксированная высота изображений
        x = 0

        for i, (pixmap, caption) in enumerate(self.images):
            item = ClickablePixmapItem(
                pixmap.scaledToHeight(max_height, Qt.TransformationMode.SmoothTransformation),
                caption,
                images_list=self.images,
                index=i,
                carousel=self  # Передаем ссылку на карусель
            )
            item.setPos(x, 0)
            self.carousel_scene.addItem(item)
            self.image_items.append(item)
            x += item.pixmap().width() + x_offset

        self.setSceneRect(0, 0, x, max_height)

    def create_arrows(self):
        """Создаёт кнопки-стрелки и привязывает их к функциям прокрутки."""
        self.prevArrow = QToolButton(self)
        self.prevArrow.setArrowType(Qt.ArrowType.LeftArrow)
        self.prevArrow.setStyleSheet(self.theme.PREV_BUTTON_STYLE) # type: ignore
        self.prevArrow.setFixedSize(40, 40)
        self.prevArrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prevArrow.setAutoRepeat(True)
        self.prevArrow.setAutoRepeatDelay(300)
        self.prevArrow.setAutoRepeatInterval(100)
        self.prevArrow.clicked.connect(self.scroll_left)
        self.prevArrow.raise_()

        self.nextArrow = QToolButton(self)
        self.nextArrow.setArrowType(Qt.ArrowType.RightArrow)
        self.nextArrow.setStyleSheet(self.theme.NEXT_BUTTON_STYLE) # type: ignore
        self.nextArrow.setFixedSize(40, 40)
        self.nextArrow.setCursor(Qt.CursorShape.PointingHandCursor)
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
        animation = QPropertyAnimation(scrollbar, QByteArray(b"value"), self)
        animation.setDuration(300)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
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
        self.carousel_scene.clear()
        self.images = new_images
        self.image_items.clear()
        self.init_ui()
        self.update_arrows_visibility()

    # Обработка событий мыши для перетаскивания
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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
        if self._drag_active and self._drag_start_position is not None:
            delta = event.pos().x() - self._drag_start_position.x()
            new_value = self._scroll_start_value - delta
            self.horizontalScrollBar().setValue(new_value)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        # Показываем стрелки после завершения перетаскивания (с проверкой видимости)
        self.update_arrows_visibility()
        super().mouseReleaseEvent(event)
