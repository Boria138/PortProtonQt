import importlib.util
import configparser
import os
from PySide6.QtGui import QFontDatabase, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt

# Папка, где располагаются все дополнительные темы
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIRS = [
    os.path.join(xdg_data_home, "PortProtonQT", "themes"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
]

# Файл конфигурации для хранения выбранной темы
CONFIG_FILE = os.path.join(
    os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "PortProtonQT.conf"
)

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


def load_theme_metainfo(theme_name):
    """
    Загружает метаинформацию темы из файла metainfo.ini в корне папки темы.
    Ожидаемые поля: author, author_link, description, name.
    """
    meta = {}
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        metainfo_file = os.path.join(theme_folder, "metainfo.ini")
        if os.path.exists(metainfo_file):
            config = configparser.ConfigParser()
            config.read(metainfo_file, encoding="utf-8")
            if "Metainfo" in config:
                meta["author"] = config.get("Metainfo", "author", fallback="Unknown")
                meta["author_link"] = config.get("Metainfo", "author_link", fallback="")
                meta["description"] = config.get("Metainfo", "description", fallback="")
                meta["name"] = config.get("Metainfo", "name", fallback=theme_name)
            break
    return meta

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
                        # Вместо просто pixmap, добавляем кортеж (pixmap, file)
                        screenshots.append((pixmap, file))
    return screenshots

def load_theme_fonts(theme_name):
    """
    Загружает все шрифты выбранной темы.

    Для стандартной темы шрифты ищутся в папке fonts,
    расположенной рядом с программой (в той же директории, что и этот модуль).

    :param theme_name: Имя темы.
    """
    fonts_folder = None
    if theme_name == "standart_lite":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fonts_folder = os.path.join(base_dir, "themes", "standart_lite", "fonts")
    else:
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            possible_fonts_folder = os.path.join(theme_folder, "fonts")
            if os.path.exists(possible_fonts_folder):
                fonts_folder = possible_fonts_folder
                break

    if not fonts_folder or not os.path.exists(fonts_folder):
        print(f"Папка fonts не найдена для темы '{theme_name}'")
        return

    for filename in os.listdir(fonts_folder):
        if filename.lower().endswith(".ttf"):
            font_path = os.path.join(fonts_folder, filename)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                print(f"Шрифт {filename} успешно загружен: {families}")
            else:
                print(f"Ошибка загрузки шрифта: {filename}")


def load_theme_logo(theme_name):
    """
    Загружает логотип выбранной темы из файла theme_logo.svg или theme_logo.png.
    Сначала ищется SVG, затем PNG, в корне папки темы.

    :param theme_name: Имя темы.
    :return: QPixmap с логотипом или None, если файл не найден или произошла ошибка.
    """
    logo_path = None
    file_extension = None

    if theme_name == "standart_lite":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        svg_path = os.path.join(base_dir, "themes", "standart_lite", "theme_logo.svg")
        png_path = os.path.join(base_dir, "themes", "standart_lite", "theme_logo.png")
        if os.path.exists(svg_path):
            logo_path = svg_path
            file_extension = "svg"
        elif os.path.exists(png_path):
            logo_path = png_path
            file_extension = "png"
    else:
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            svg_path = os.path.join(theme_folder, "theme_logo.svg")
            png_path = os.path.join(theme_folder, "theme_logo.png")
            if os.path.exists(svg_path):
                logo_path = svg_path
                file_extension = "svg"
                break
            elif os.path.exists(png_path):
                logo_path = png_path
                file_extension = "png"
                break

    if not logo_path or not os.path.exists(logo_path):
        print(f"Файл логотипа не найден для темы '{theme_name}'")
        return None

    if file_extension == "svg":
        renderer = QSvgRenderer(logo_path)
        if not renderer.isValid():
            print(f"Ошибка загрузки SVG логотипа: {logo_path}")
            return None
        pixmap = QPixmap(128, 128)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        print(f"Логотип темы '{theme_name}' успешно загружен (SVG): {logo_path}")
        return pixmap
    else:
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            print(f"Ошибка загрузки PNG логотипа: {logo_path}")
            return None
        print(f"Логотип темы '{theme_name}' успешно загружен (PNG): {logo_path}")
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
        self.screenshots = load_theme_screenshots(self.metainfo.get("name", ""), )

    def __getattr__(self, name):
        if hasattr(self.custom_theme, name):
            return getattr(self.custom_theme, name)
        import portprotonqt.themes.standart_lite.styles as default_styles
        return getattr(default_styles, name)


def load_theme(theme_name):
    """
    Динамически загружает модуль стилей выбранной темы и метаинформацию.
    Если выбрана стандартная тема, импортируется оригинальный styles.py.
    Для кастомных тем возвращается обёртка, которая подставляет недостающие атрибуты.
    """
    if theme_name == "standart_lite":
        import portprotonqt.themes.standart_lite.styles as default_styles
        default_styles.metainfo = load_theme_metainfo(theme_name)
        # Можно также загрузить скриншоты для стандартной темы
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
            # Обёртка также может сохранить список скриншотов
            wrapper = ThemeWrapper(custom_theme, metainfo=meta)
            wrapper.screenshots = load_theme_screenshots(theme_name)
            return wrapper
    raise FileNotFoundError(f"Файл стилей не найден для темы '{theme_name}'")


def read_theme_from_config():
    """
    Читает из конфигурационного файла, какая тема указана в разделе [Appearance].
    """
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding="utf-8")
            return config.get("Appearance", "theme", fallback="standart_lite")
        except Exception as e:
            print("Ошибка чтения конфигурации темы:", e)
    return "standart_lite"


def save_theme_to_config(theme_name):
    """
    Сохраняет имя выбранной темы в CONFIG_FILE под секцией [Appearance].
    """
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding="utf-8")
    if "Appearance" not in config:
        config["Appearance"] = {}
    config["Appearance"]["theme"] = theme_name
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            config.write(configfile)
    except Exception as e:
        print("Ошибка сохранения конфигурации темы:", e)


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

    def apply_theme(self, theme_name):
        """
        Применяет выбранную тему: загружает модуль стилей, шрифты и логотип.
        Если загрузка прошла успешно, сохраняет выбранную тему.

        :param theme_name: Имя темы.
        :return: Модуль темы (или обёртка), либо None в случае ошибки.
        """
        try:
            theme_module = load_theme(theme_name)
            load_theme_fonts(theme_name)
            self.current_theme_logo = load_theme_logo(theme_name)
            self.current_theme_name = theme_name
            self.current_theme_module = theme_module
            print(f"Тема '{theme_name}' успешно применена")
            return theme_module
        except Exception as e:
            print(f"Ошибка при применении темы '{theme_name}': {e}")
            return None
