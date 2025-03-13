import importlib.util
import os

from PySide6.QtGui import QFontDatabase, QPixmap

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

def load_theme(theme_name):
    """
    Динамически загружает модуль стилей выбранной темы.
    Если выбрана стандартная тема, импортируется оригинальный styles.py из portprotonqt.
    Для кастомных тем возвращается обёртка, которая подставляет недостающие атрибуты из стандартной темы.
    """
    if theme_name == "standart_lite":
        import portprotonqt.themes.standart_lite.styles as default_styles
        return default_styles

    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        styles_file = os.path.join(theme_folder, "styles.py")
        if os.path.exists(styles_file):
            spec = importlib.util.spec_from_file_location("theme_styles", styles_file)
            custom_theme = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(custom_theme)
            return ThemeWrapper(custom_theme)

    raise FileNotFoundError(f"Файл стилей не найден для темы '{theme_name}'")

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
    Загружает логотип выбранной темы из файла theme_logo.png.
    Ищет файл логотипа в корне папки темы.

    :param theme_name: Имя темы.
    :return: QPixmap с логотипом или None, если файл не найден или произошла ошибка.
    """
    logo_path = None
    if theme_name == "standart_lite":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "themes", "standart_lite", "theme_logo.png")
    else:
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, theme_name)
            possible_logo_path = os.path.join(theme_folder, "theme_logo.png")
            if os.path.exists(possible_logo_path):
                logo_path = possible_logo_path
                break

    if logo_path and os.path.exists(logo_path):
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            print(f"Ошибка загрузки логотипа: {logo_path}")
            return None
        else:
            print(f"Логотип темы '{theme_name}' успешно загружен: {logo_path}")
            return pixmap
    else:
        print(f"Файл логотипа не найден для темы '{theme_name}'")
        return None

class ThemeWrapper:
    """
    Обёртка для кастомной темы.
    При обращении к атрибуту сначала ищется его наличие в кастомной теме,
    если атрибут отсутствует, значение берётся из стандартного модуля стилей.
    """
    def __init__(self, custom_theme):
        self.custom_theme = custom_theme

    def __getattr__(self, name):
        if hasattr(self.custom_theme, name):
            return getattr(self.custom_theme, name)
        import portprotonqt.themes.standart_lite.styles as default_styles
        return getattr(default_styles, name)

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
