import os
import importlib.util
from PySide6.QtGui import QFontDatabase

# Папка, где располагаются все дополнительные темы
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIR = os.path.join(xdg_data_home, "PortProtonQT", "themes")


def list_themes():
    """
    Возвращает список доступных тем (названий папок) из каталога THEMES_DIR.
    Добавляет стандартную тему под именем "стандартная".
    """
    themes = ["стандартная"]
    if os.path.exists(THEMES_DIR):
        # Добавляем все папки, которые содержат файл styles.py
        for entry in os.listdir(THEMES_DIR):
            theme_path = os.path.join(THEMES_DIR, entry)
            if os.path.isdir(theme_path) and os.path.exists(os.path.join(theme_path, "styles.py")):
                themes.append(entry)
    return themes

def load_theme(theme_name):
    """
    Динамически загружает модуль стилей выбранной темы.
    Если выбрана стандартная тема, импортируется оригинальный styles.py из portprotonqt.
    Для кастомных тем возвращается обёртка, которая подставляет недостающие атрибуты из стандартной темы.

    :param theme_name: Имя темы.
    :return: Объект с атрибутами стилей.
    """
    if theme_name == "стандартная":
        import portprotonqt.styles as default_styles
        return default_styles

    theme_folder = os.path.join(THEMES_DIR, theme_name)
    styles_file = os.path.join(theme_folder, "styles.py")
    if not os.path.exists(styles_file):
        raise FileNotFoundError(f"Файл стилей не найден для темы '{theme_name}': {styles_file}")
    spec = importlib.util.spec_from_file_location("theme_styles", styles_file)
    custom_theme = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(custom_theme)
    return ThemeWrapper(custom_theme)

def load_theme_fonts(theme_name):
    """
    Загружает все шрифты выбранной темы.

    Для стандартной темы шрифты ищутся в папке fonts,
    расположенной рядом с программой (в той же директории, что и этот модуль).

    :param theme_name: Имя темы.
    """
    if theme_name == "стандартная":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fonts_folder = os.path.join(base_dir, "fonts")
    else:
        theme_folder = os.path.join(THEMES_DIR, theme_name)
        fonts_folder = os.path.join(theme_folder, "fonts")

    if not os.path.exists(fonts_folder):
        print(f"Папка fonts не найдена для темы '{theme_name}' по пути: {fonts_folder}")
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
        import portprotonqt.styles as default_styles
        return getattr(default_styles, name)

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

    def apply_theme(self, theme_name):
        """
        Применяет выбранную тему: загружает модуль стилей и шрифты.
        Если загрузка прошла успешно, сохраняет выбранную тему.

        :param theme_name: Имя темы.
        :return: Модуль темы (или обёртка), либо None в случае ошибки.
        """
        try:
            theme_module = load_theme(theme_name)
            load_theme_fonts(theme_name)
            self.current_theme_name = theme_name
            self.current_theme_module = theme_module
            print(f"Тема '{theme_name}' успешно применена")
            return theme_module
        except Exception as e:
            print(f"Ошибка при применении темы '{theme_name}': {e}")
            return None
