import os
from PySide6.QtGui import QPen, QColor, QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt, QFile, QEvent, QByteArray, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsItem, QToolButton, QFrame, QLabel, QGraphicsScene, QHBoxLayout, QWidget, QGraphicsView, QVBoxLayout, QSizePolicy
from PySide6.QtWidgets import QSpacerItem, QGraphicsPixmapItem, QDialog, QApplication
from portprotonqt.config_utils import read_theme_from_config
from portprotonqt.theme_manager import ThemeManager
from portprotonqt.downloader import Downloader
from portprotonqt.logger import get_logger
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import threading

downloader = Downloader()
logger = get_logger(__name__)

# Глобальная очередь и пул потоков для загрузки изображений
image_load_queue = Queue()
image_executor = ThreadPoolExecutor(max_workers=4)
queue_lock = threading.Lock()

def get_device_pixel_ratio() -> float:
    """
    Retrieves the device pixel ratio from QApplication, with a fallback of 1.0 if not available.
    """
    app = QApplication.instance()
    return app.devicePixelRatio() if isinstance(app, QApplication) else 1.0

def load_pixmap_async(cover: str, width: int, height: int, callback: Callable[[QPixmap], None], app_name: str = ""):
    """
    Асинхронно загружает обложку через очередь задач.
    """
    def process_image():
        theme_manager = ThemeManager()
        current_theme_name = read_theme_from_config()

        def finish_with(pixmap: QPixmap):
            scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x = (scaled.width() - width) // 2
            y = (scaled.height() - height) // 2
            cropped = scaled.copy(x, y, width, height)
            callback(cropped)

        xdg_cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
        image_folder = os.path.join(xdg_cache_home, "PortProtonQt", "images")
        os.makedirs(image_folder, exist_ok=True)

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
                        finish_with(pixmap)
                        return

                    def on_downloaded(result: str | None):
                        pixmap = QPixmap()
                        if result and os.path.exists(result):
                            pixmap.load(result)
                        if pixmap.isNull():
                            placeholder_path = theme_manager.get_theme_image("placeholder", current_theme_name)
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

                    downloader.download_async(cover, local_path, timeout=5, callback=on_downloaded)
                    return
            except Exception as e:
                logger.error(f"Ошибка обработки URL {cover}: {e}")

        # SteamGridDB (SGDB)
        if cover and cover.startswith("https://cdn2.steamgriddb.com"):
            try:
                parts = cover.split("/")
                filename = parts[-1] if parts else "sgdb_cover.png"
                # SGDB ссылки содержат уникальный хеш в названии — используем как имя
                local_path = os.path.join(image_folder, filename)

                if os.path.exists(local_path):
                    pixmap = QPixmap(local_path)
                    finish_with(pixmap)
                    return

                def on_downloaded(result: str | None):
                    pixmap = QPixmap()
                    if result and os.path.exists(result):
                        pixmap.load(result)
                    if pixmap.isNull():
                        placeholder_path = theme_manager.get_theme_image("placeholder", current_theme_name)
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

                logger.info("Downloading SGDB cover for %s -> %s", app_name or "unknown", filename)
                downloader.download_async(cover, local_path, timeout=5, callback=on_downloaded)
                return

            except Exception as e:
                logger.error(f"Ошибка обработки SGDB URL {cover}: {e}")

        if cover and cover.startswith(("http://", "https://")):
            try:
                local_path = os.path.join(image_folder, f"{app_name}.jpg")
                if os.path.exists(local_path):
                    pixmap = QPixmap(local_path)
                    finish_with(pixmap)
                    return

                def on_downloaded(result: str | None):
                    pixmap = QPixmap()
                    if result and os.path.exists(result):
                        pixmap.load(result)
                    if pixmap.isNull():
                        placeholder_path = theme_manager.get_theme_image("placeholder", current_theme_name)
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

                downloader.download_async(cover, local_path, timeout=5, callback=on_downloaded)
                return
            except Exception as e:
                logger.error("Error processing EGS URL %s: %s", cover, str(e))

        if cover and QFile.exists(cover):
            pixmap = QPixmap(cover)
            finish_with(pixmap)
            return

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

    with queue_lock:
        image_load_queue.put(process_image)
        image_executor.submit(lambda: image_load_queue.get()())

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
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        self.images = images
        self.current_index = current_index
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else self.theme_manager.apply_theme(read_theme_from_config())

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.init_ui()
        self.update_display()

        self.imageLabel.installEventFilter(self)
        self.captionLabel.installEventFilter(self)

    def init_ui(self):
        self.mainLayout = QVBoxLayout(self)
        self.setLayout(self.mainLayout)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self.imageContainer = QWidget()
        self.imageContainer.setFixedSize(self.FIXED_WIDTH, self.FIXED_HEIGHT)
        self.imageContainerLayout = QHBoxLayout(self.imageContainer)
        self.imageContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.imageContainerLayout.setSpacing(0)

        self.prevButton = QToolButton()
        self.prevButton.setArrowType(Qt.ArrowType.LeftArrow)
        self.prevButton.setStyleSheet(getattr(self.theme, "PREV_BUTTON_STYLE", ""))
        self.prevButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prevButton.setFixedSize(40, 40)
        self.prevButton.clicked.connect(self.show_prev)
        self.imageContainerLayout.addWidget(self.prevButton)

        self.imageLabel = QLabel()
        self.imageLabel.setFixedSize(self.FIXED_WIDTH - 80, self.FIXED_HEIGHT)
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageContainerLayout.addWidget(self.imageLabel, stretch=1)

        self.nextButton = QToolButton()
        self.nextButton.setArrowType(Qt.ArrowType.RightArrow)
        self.nextButton.setStyleSheet(getattr(self.theme, "NEXT_BUTTON_STYLE", ""))
        self.nextButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nextButton.setFixedSize(40, 40)
        self.nextButton.clicked.connect(self.show_next)
        self.imageContainerLayout.addWidget(self.nextButton)

        self.mainLayout.addWidget(self.imageContainer)

        spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.mainLayout.addItem(spacer)

        self.captionLabel = QLabel()
        self.captionLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.captionLabel.setFixedHeight(40)
        self.captionLabel.setWordWrap(True)
        self.captionLabel.setStyleSheet(getattr(self.theme, "CAPTION_LABEL_STYLE", ""))
        self.captionLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mainLayout.addWidget(self.captionLabel)

    def update_display(self):
        """Обновляет изображение и подпись согласно текущему индексу."""
        if not self.images:
            return

        self.imageLabel.clear()
        self.captionLabel.clear()
        QApplication.processEvents()

        pixmap, caption = self.images[self.current_index]
        # Учитываем devicePixelRatio для масштабирования высокого качества
        device_pixel_ratio = get_device_pixel_ratio()
        target_width = int((self.FIXED_WIDTH - 80) * device_pixel_ratio)
        target_height = int(self.FIXED_HEIGHT * device_pixel_ratio)

        # Масштабируем изображение из оригинального pixmap
        scaled_pixmap = pixmap.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        scaled_pixmap.setDevicePixelRatio(device_pixel_ratio)
        self.imageLabel.setPixmap(scaled_pixmap)
        self.captionLabel.setText(caption)
        self.setWindowTitle(caption)

        self.imageLabel.repaint()
        self.captionLabel.repaint()
        self.repaint()

    def resizeEvent(self, event):
        """Обновляет изображение при изменении размера окна."""
        super().resizeEvent(event)
        self.update_display()  # Перерисовываем изображение с учетом нового размера

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
        :param pixmap: QPixmap для отображения в карусели (оригинальное, высокое разрешение)
        :param caption: Подпись к изображению
        :param images_list: Список всех изображений (кортежей (QPixmap, caption))
        :param index: Индекс текущего изображения в images_list
        :param carousel: Ссылка на родительскую карусель (ImageCarousel)
        """
        super().__init__()
        self.original_pixmap = pixmap  # Store original high-resolution pixmap
        self.caption = caption
        self.images_list = images_list if images_list is not None else [(pixmap, caption)]
        self.index = index
        self.carousel = carousel
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(caption)
        self._click_start_position = None
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_pixmap()  # Set initial pixmap

    def update_pixmap(self, height=300):
        """Update the displayed pixmap by scaling from the original high-resolution pixmap."""
        if self.original_pixmap.isNull():
            return
        # Scale pixmap to desired height, considering device pixel ratio
        device_pixel_ratio = get_device_pixel_ratio()
        scaled_pixmap = self.original_pixmap.scaledToHeight(
            int(height * device_pixel_ratio),
            Qt.TransformationMode.SmoothTransformation
        )
        scaled_pixmap.setDevicePixelRatio(device_pixel_ratio)
        self.setPixmap(scaled_pixmap)

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
        if self.carousel:
            self.carousel.prevArrow.hide()
            self.carousel.nextArrow.hide()
        dialog = FullscreenDialog(self.images_list, current_index=self.index)
        dialog.exec()
        if self.carousel:
            self.carousel.update_arrows_visibility()

class ImageCarousel(QGraphicsView):
    """
    Карусель изображений с адаптивностью, возможностью увеличения по клику
    и перетаскиванием мыши.
    """
    def __init__(self, images: list[tuple], parent: QWidget | None = None, theme: object | None = None):
        super().__init__(parent)
        self.carousel_scene: QGraphicsScene = QGraphicsScene(self)
        self.setScene(self.carousel_scene)
        self.images = images  # Список кортежей: (QPixmap, caption)
        self.image_items = []
        self._animation = None
        self.theme_manager = ThemeManager()
        self.theme = theme if theme is not None else self.theme_manager.apply_theme(read_theme_from_config())
        self.max_height = 300  # Default height for images
        self.init_ui()
        self.create_arrows()

        self._drag_active = False
        self._drag_start_position = None
        self._scroll_start_value = None

    def init_ui(self):
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.update_scene()

    def update_scene(self):
        """Update the scene with scaled images based on current size and scale."""
        self.carousel_scene.clear()
        self.image_items.clear()

        x_offset = 10
        x = 0
        device_pixel_ratio = get_device_pixel_ratio()

        for i, (pixmap, caption) in enumerate(self.images):
            item = ClickablePixmapItem(
                pixmap,  # Pass original pixmap
                caption,
                images_list=self.images,
                index=i,
                carousel=self
            )
            item.update_pixmap(self.max_height)  # Scale to current height
            item.setPos(x, 0)
            self.carousel_scene.addItem(item)
            self.image_items.append(item)
            x += item.pixmap().width() / device_pixel_ratio + x_offset

        self.setSceneRect(0, 0, x, self.max_height)

    def create_arrows(self):
        """Создаёт кнопки-стрелки и привязывает их к функциям прокрутки."""
        self.prevArrow = QToolButton(self)
        self.prevArrow.setArrowType(Qt.ArrowType.LeftArrow)
        self.prevArrow.setStyleSheet(getattr(self.theme, "PREV_BUTTON_STYLE", ""))
        self.prevArrow.setFixedSize(40, 40)
        self.prevArrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prevArrow.setAutoRepeat(True)
        self.prevArrow.setAutoRepeatDelay(300)
        self.prevArrow.setAutoRepeatInterval(100)
        self.prevArrow.clicked.connect(self.scroll_left)
        self.prevArrow.raise_()

        self.nextArrow = QToolButton(self)
        self.nextArrow.setArrowType(Qt.ArrowType.RightArrow)
        self.nextArrow.setStyleSheet(getattr(self.theme, "NEXT_BUTTON_STYLE", ""))
        self.nextArrow.setFixedSize(40, 40)
        self.nextArrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nextArrow.setAutoRepeat(True)
        self.nextArrow.setAutoRepeatDelay(300)
        self.nextArrow.setAutoRepeatInterval(100)
        self.nextArrow.clicked.connect(self.scroll_right)
        self.nextArrow.raise_()

        self.update_arrows_visibility()

    def update_arrows_visibility(self):
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
        self.update_scene()  # Re-scale images on resize
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
        self.images = new_images
        self.update_scene()
        self.update_arrows_visibility()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_start_position = event.pos()
            self._scroll_start_value = self.horizontalScrollBar().value()
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
        self.update_arrows_visibility()
        super().mouseReleaseEvent(event)
