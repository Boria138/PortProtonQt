import importlib.util
import os
import glob
from portprotonqt.logger import get_logger
from PySide6.QtGui import QFontDatabase, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from portprotonqt.config_utils import save_theme_to_config, load_theme_metainfo

logger = get_logger(__name__)

# Папка, где располагаются все дополнительные темы
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIRS = [
    os.path.join(xdg_data_home, "PortProtonQT", "themes"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
]

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
        screenshots_folder = os.path.join(theme_folder, "screenshots")
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

def load_theme_logo(theme_name):
    """
    Загружает логотип выбранной темы из файла, имя которого начинается с "theme_logo.".
    Поддерживает векторные форматы (например, SVG) и растровые форматы.
    :param theme_name: Имя темы.
    :return: QPixmap с логотипом или None, если файл не найден или произошла ошибка.
    """
    logo_path = None

    def find_logo_in_folder(folder):
        pattern = os.path.join(folder, "theme_logo.*")
        files = glob.glob(pattern)
        return files[0] if files else None

    if theme_name == "standart":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        theme_folder = os.path.join(base_dir, "themes", "standart")
        logo_path = find_logo_in_folder(theme_folder)
    else:
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            logo_path = find_logo_in_folder(theme_folder)
            if logo_path:
                break

    if not logo_path or not os.path.exists(logo_path):
        logger.error(f"Файл логотипа не найден для темы '{theme_name}'")
        return None

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
        logger.info(f"Логотип темы '{theme_name}' успешно загружен (SVG): {logo_path}")
        return pixmap
    else:
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            logger.error(f"Ошибка загрузки логотипа: {logo_path}")
            return None
        logger.info(f"Логотип темы '{theme_name}' успешно загружен: {logo_path}")
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
        self.current_theme_logo = None

    def get_available_themes(self):
        """Возвращает список доступных тем."""
        return list_themes()

    def get_theme_logo(self, theme_name=None):
        """Возвращает логотип для текущей или указанной темы."""
        if theme_name is None:
            theme_name = self.current_theme_name
        return load_theme_logo(theme_name)

    def apply_theme(self, theme_name):
        """
        Применяет выбранную тему: загружает модуль стилей, шрифты и логотип.
        Если загрузка прошла успешно, сохраняет выбранную тему в конфигурации.
        :param theme_name: Имя темы.
        :return: Загруженный модуль темы (или обёртка).
        """
        theme_module = load_theme(theme_name)
        load_theme_fonts(theme_name)
        self.current_theme_logo = load_theme_logo(theme_name)
        self.current_theme_name = theme_name
        self.current_theme_module = theme_module
        save_theme_to_config(theme_name)
        logger.info(f"Тема '{theme_name}' успешно применена")
        return theme_module

    def get_icon(self, icon_name, theme_name=None):
        """
        Возвращает QIcon из папки icons текущей темы,
        а если файл не найден, то из стандартной темы.
        """
        icon_path = None
        theme_name = theme_name or self.current_theme_name

        # Поиск иконки в папке текущей темы
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            candidate = os.path.join(theme_folder, "icons", icon_name)
            if os.path.exists(candidate):
                icon_path = candidate
                break
        # Если не нашли – используем стандартную тему
        if not icon_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_dir, "themes", "standart", "icons", icon_name)
        return QIcon(icon_path)

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
