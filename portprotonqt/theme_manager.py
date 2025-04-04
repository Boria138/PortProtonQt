import importlib.util
import os
from portprotonqt.logger import get_logger
from PySide6.QtGui import QFontDatabase, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QIcon, QColor
from PySide6.QtCore import Qt

from portprotonqt.config_utils import save_theme_to_config, load_theme_metainfo

logger = get_logger(__name__)

# Папка, где располагаются все дополнительные темы
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIRS = [
    os.path.join(xdg_data_home, "PortProtonQT", "themes"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
]

def to_qcolor(color):
    """
    Преобразует значение цвета, заданное в виде QColor, строки или кортежа (r, g, b),
    в объект QColor.
    Поддерживаются следующие форматы:
      - QColor
      - кортеж или список (r, g, b)
      - строка вида "rgb(122,28,26)"
      - строка вида "122,28,26"
      - именованные цвета ("red") или шестнадцатеричные ("#7A1C1A")
    """

    if isinstance(color, QColor):
        return color
    elif isinstance(color, tuple | list) and len(color) >= 3:
        return QColor(*color)
    elif isinstance(color, str):
        # Обработка строки с запятыми без "rgb(...)"
        if "," in color:
            parts = color.split(",")
            if len(parts) >= 3:
                try:
                    r = int(parts[0].strip())
                    g = int(parts[1].strip())
                    b = int(parts[2].strip())
                    return QColor(r, g, b)
                except ValueError:
                    pass
        # Если строка начинается с "rgb", пытаемся распарсить формат "rgb(r, g, b)"
        if color.lower().startswith("rgb"):
            content = color[color.find("(")+1:color.find(")")]
            parts = content.split(",")
            if len(parts) >= 3:
                try:
                    r = int(parts[0].strip())
                    g = int(parts[1].strip())
                    b = int(parts[2].strip())
                    return QColor(r, g, b)
                except ValueError:
                    pass
        return QColor(color)
    return QColor()

def list_themes():
    """
    Возвращает список доступных тем (названий папок) из каталогов THEMES_DIRS.
    """
    themes = []
    for themes_dir in THEMES_DIRS:
        if os.path.exists(themes_dir):
            for entry in os.listdir(themes_dir):
                theme_path = os.path.join(themes_dir, entry)
                if os.path.isdir(theme_path) and os.path.exists(os.path.join(theme_path, "styles.py")):
                    themes.append(entry)
    return themes

def load_theme_screenshots(theme_name):
    """
    Загружает все скриншоты из папки "screenshots", расположенной в папке темы.
    Возвращает список кортежей (pixmap, filename).
    Если папка отсутствует или пуста, возвращается пустой список.
    """
    screenshots = []
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        screenshots_folder = os.path.join(theme_folder, "images", "screenshots")
        if os.path.exists(screenshots_folder) and os.path.isdir(screenshots_folder):
            for file in os.listdir(screenshots_folder):
                screenshot_path = os.path.join(screenshots_folder, file)
                if os.path.isfile(screenshot_path):
                    pixmap = QPixmap(screenshot_path)
                    if not pixmap.isNull():
                        screenshots.append((pixmap, file))
    return screenshots

def load_theme_fonts(theme_name):
    """
    Загружает все шрифты выбранной темы.
    :param theme_name: Имя темы.
    """
    QFontDatabase.removeAllApplicationFonts()
    fonts_folder = None
    if theme_name == "standart":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fonts_folder = os.path.join(base_dir, "themes", "standart", "fonts")
    else:
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            possible_fonts_folder = os.path.join(theme_folder, "fonts")
            if os.path.exists(possible_fonts_folder):
                fonts_folder = possible_fonts_folder
                break

    if not fonts_folder or not os.path.exists(fonts_folder):
        logger.error(f"Папка fonts не найдена для темы '{theme_name}'")
        return

    for filename in os.listdir(fonts_folder):
        if filename.lower().endswith((".ttf", ".otf")):
            font_path = os.path.join(fonts_folder, filename)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                logger.info(f"Шрифт {filename} успешно загружен: {families}")
            else:
                logger.error(f"Ошибка загрузки шрифта: {filename}")

def load_logo():
    logo_path = None

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "themes", "standart", "images", "theme_logo.svg")

    file_extension = os.path.splitext(logo_path)[1].lower()

    if file_extension == ".svg":
        renderer = QSvgRenderer(logo_path)
        if not renderer.isValid():
            logger.error(f"Ошибка загрузки SVG логотипа: {logo_path}")
            return None
        pixmap = QPixmap(128, 128)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap

class ThemeWrapper:
    """
    Обёртка для кастомной темы с поддержкой метаинформации.
    При обращении к атрибуту сначала ищется его наличие в кастомной теме,
    если атрибут отсутствует, значение берётся из стандартного модуля стилей.
    """
    def __init__(self, custom_theme, metainfo=None):
        self.custom_theme = custom_theme
        self.metainfo = metainfo or {}
        self.screenshots = load_theme_screenshots(self.metainfo.get("name", ""))

    def __getattr__(self, name):
        if hasattr(self.custom_theme, name):
            return getattr(self.custom_theme, name)
        import portprotonqt.themes.standart.styles as default_styles
        return getattr(default_styles, name)

def load_theme(theme_name):
    """
    Динамически загружает модуль стилей выбранной темы и метаинформацию.
    Если выбрана стандартная тема, импортируется оригинальный styles.py.
    Для кастомных тем возвращается обёртка, которая подставляет недостающие атрибуты.
    """
    if theme_name == "standart":
        import portprotonqt.themes.standart.styles as default_styles
        default_styles.metainfo = load_theme_metainfo(theme_name)
        default_styles.screenshots = load_theme_screenshots(theme_name)
        return default_styles

    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        styles_file = os.path.join(theme_folder, "styles.py")
        if os.path.exists(styles_file):
            spec = importlib.util.spec_from_file_location("theme_styles", styles_file)
            custom_theme = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(custom_theme)
            meta = load_theme_metainfo(theme_name)
            wrapper = ThemeWrapper(custom_theme, metainfo=meta)
            wrapper.screenshots = load_theme_screenshots(theme_name)
            return wrapper
    raise FileNotFoundError(f"Файл стилей не найден для темы '{theme_name}'")

class ThemeManager:
    """
    Класс для управления темами приложения.

    Позволяет получить список доступных тем, загрузить и применить выбранную тему.
    """
    def __init__(self):
        self.current_theme_name = None
        self.current_theme_module = None

    def get_available_themes(self):
        """Возвращает список доступных тем."""
        return list_themes()

    def get_theme_logo(self):
        """Возвращает логотип для текущей или указанной темы."""
        return load_logo()

    def apply_theme(self, theme_name):
        """
        Применяет выбранную тему: загружает модуль стилей, шрифты и логотип.
        Если загрузка прошла успешно, сохраняет выбранную тему в конфигурации.
        :param theme_name: Имя темы.
        :return: Загруженный модуль темы (или обёртка).
        """
        theme_module = load_theme(theme_name)
        load_theme_fonts(theme_name)
        self.current_theme_name = theme_name
        self.current_theme_module = theme_module
        save_theme_to_config(theme_name)
        logger.info(f"Тема '{theme_name}' успешно применена")
        return theme_module

    def get_icon(self, icon_name, theme_name=None, as_path=False, color=None, icon_size=16):
        """
        Возвращает QIcon из папки icons текущей темы,
        а если файл не найден, то из стандартной темы.
        Принимает название иконки без расширения и находит соответствующий файл
        с поддерживаемым расширением (.svg, .png, .jpg и др.).
        Если as_path=True, возвращает путь к иконке вместо QIcon.
        Параметры:
        color – цвет для перекраски иконки.
        icon_size: размер иконки (ширина и высота).
        """
        # Поддерживаемые расширения файлов изображений
        supported_extensions = ['.svg', '.png', '.jpg', '.jpeg']

        # Проверка, содержит ли icon_name уже расширение
        has_extension = any(icon_name.lower().endswith(ext) for ext in supported_extensions)
        base_name = icon_name if has_extension else icon_name

        # Поиск иконки в папке текущей темы
        icon_path = None
        theme_name = theme_name or self.current_theme_name

        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            icons_folder = os.path.join(theme_folder, "images", "icons")

            # Если передано имя с расширением, проверяем только этот файл
            if has_extension:
                candidate = os.path.join(icons_folder, base_name)
                if os.path.exists(candidate):
                    icon_path = candidate
                    break
            else:
                # Проверяем все поддерживаемые расширения
                for ext in supported_extensions:
                    candidate = os.path.join(icons_folder, base_name + ext)
                    if os.path.exists(candidate):
                        icon_path = candidate
                        break
                if icon_path:
                    break

        # Если не нашли – используем стандартную тему
        if not icon_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            standard_icons_folder = os.path.join(base_dir, "themes", "standart", "images", "icons")

            # Аналогично проверяем в стандартной теме
            if has_extension:
                icon_path = os.path.join(standard_icons_folder, base_name)
                if not os.path.exists(icon_path):
                    icon_path = None
            else:
                for ext in supported_extensions:
                    candidate = os.path.join(standard_icons_folder, base_name + ext)
                    if os.path.exists(candidate):
                        icon_path = candidate
                        break

        # Если иконка всё равно не найдена
        if not icon_path or not os.path.exists(icon_path):
            # Можно вернуть пустую иконку или показать предупреждение
            logger.error(f"Предупреждение: иконка '{icon_name}' не найдена")
            return QIcon() if not as_path else None

        if as_path:
            return icon_path

        # Если перекраска не требуется, возвращаем стандартный QIcon
        if not color:
            return QIcon(icon_path)

        # Преобразование цвета в QColor
        color = to_qcolor(color)

        # Если иконка в формате SVG, используем QSvgRenderer
        if icon_path.lower().endswith(".svg"):
            renderer = QSvgRenderer(icon_path)
            pixmap = QPixmap(icon_size, icon_size)
            pixmap.fill(Qt.transparent)
            temp_painter = QPainter(pixmap)
            renderer.render(temp_painter)
            temp_painter.end()
        else:
            # Для растровых изображений загружаем QPixmap напрямую
            pixmap = QPixmap(icon_path)
            if pixmap.width() != icon_size or pixmap.height() != icon_size:
                pixmap = pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Перекрашивание pixmap
        colored_pixmap = QPixmap(pixmap.size())
        colored_pixmap.fill(Qt.transparent)
        painter = QPainter(colored_pixmap)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(colored_pixmap.rect(), color)
        painter.end()

        return QIcon(colored_pixmap)

    def get_theme_image(self, image_name, theme_name=None):
        """
        Возвращает путь к изображению из папки текущей темы.
        Если не найдено, проверяет стандартную тему.
        """
        theme_name = theme_name or self.current_theme_name
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            candidate = os.path.join(theme_folder, "images", image_name)
            if os.path.exists(candidate):
                return candidate

        # Проверяем стандартную тему
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(base_dir, "themes", "standart", "images", image_name)
        return default_path if os.path.exists(default_path) else None
