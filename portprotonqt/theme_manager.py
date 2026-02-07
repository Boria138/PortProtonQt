import importlib.util
import os
from portprotonqt.logger import get_logger
from portprotonqt.theme_security import check_theme_safety, is_safe_image_file
from PySide6.QtGui import QIcon, QFontDatabase, QPixmap
from portprotonqt.config_utils import save_theme_to_config, load_theme_metainfo
from portprotonqt.localization import get_screenshot_caption

# Icon caching for performance optimization
_icon_cache = {}
# Directory structure cache for performance optimization
_icon_dirs_cache = {}

logger = get_logger(__name__)

# Папка, где располагаются все дополнительные темы
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIRS = [
    os.path.join(xdg_data_home, "PortProtonQt", "themes"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
]
_loaded_theme = None


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
    Возвращает список кортежей (pixmap, caption), где caption - это перевод названия скриншота.
    Если папка отсутствует или пуста, возвращается пустой список.
    """
    screenshots = []

    # Find the metainfo file for the theme
    metainfo_file = None
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        temp_metainfo_file = os.path.join(theme_folder, "metainfo.ini")
        if os.path.exists(temp_metainfo_file):
            metainfo_file = temp_metainfo_file
            break

    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        screenshots_folder = os.path.join(theme_folder, "images", "screenshots")
        if os.path.exists(screenshots_folder) and os.path.isdir(screenshots_folder):
            for file in os.listdir(screenshots_folder):
                screenshot_path = os.path.join(screenshots_folder, file)
                if os.path.isfile(screenshot_path) and is_safe_image_file(screenshot_path):
                    pixmap = QPixmap(screenshot_path)
                    if not pixmap.isNull():
                        # Get the base filename without extension
                        base_filename = os.path.splitext(file)[0]

                        # Get translated caption using localization function
                        caption = get_screenshot_caption(base_filename, metainfo_file)

                        screenshots.append((pixmap, caption))
    return screenshots

def build_icon_cache(theme_name):
    """
    Builds a cache of all image files in the theme for fast lookup.
    """
    global _icon_dirs_cache

    # Check if cache already exists for this theme
    if theme_name in _icon_dirs_cache:
        return _icon_dirs_cache[theme_name]

    image_map = {}

    # Find the theme directory and scan all image files
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        images_folder = os.path.join(theme_folder, "images")

        if os.path.exists(images_folder):
            # Walk through all subdirectories to build image map
            for root, _dirs, files in os.walk(images_folder):
                for file in files:
                    if file.lower().endswith(('.svg', '.png', '.jpg', '.jpeg')):
                        image_name = os.path.splitext(file)[0]
                        image_path = os.path.join(root, file)
                        image_map[image_name] = image_path
            break

    # Also check standard theme if not found in custom theme
    if theme_name != "standart":
        for themes_dir in THEMES_DIRS:
            theme_folder = os.path.join(themes_dir, "standart")
            images_folder = os.path.join(theme_folder, "images")

            if os.path.exists(images_folder):
                # Walk through all subdirectories to build image map
                for root, _dirs, files in os.walk(images_folder):
                    for file in files:
                        if file.lower().endswith(('.svg', '.png', '.jpg', '.jpeg')):
                            image_name = os.path.splitext(file)[0]
                            # Only add to map if not already present (custom theme takes precedence)
                            if image_name not in image_map:
                                image_path = os.path.join(root, file)
                                image_map[image_name] = image_path
                break

    _icon_dirs_cache[theme_name] = image_map
    return image_map

def load_theme_fonts(theme_name):
    """
    Загружает все шрифты выбранной темы, если они ещё не были загружены.
    """
    global _loaded_theme
    if _loaded_theme == theme_name:
        logger.debug(f"Fonts for theme '{theme_name}' already loaded, skipping")
        return

    def load_fonts_delayed():
        global _loaded_theme
        try:
            # Only remove fonts if this is a theme change (not initial load)
            current_loaded_theme = _loaded_theme  # Capture the current value
            if current_loaded_theme is not None and current_loaded_theme != theme_name:
                # Run font removal in the GUI thread with delay
                QFontDatabase.removeAllApplicationFonts()

            import time
            import os
            start_time = time.time()
            timeout = 3  # Reduced timeout to 3 seconds for faster loading

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
                logger.error(f"Fonts folder not found for theme '{theme_name}'")
                return

            font_files = []
            for filename in os.listdir(fonts_folder):
                if filename.lower().endswith((".ttf", ".otf")):
                    font_files.append(filename)

            # Limit number of fonts loaded to prevent too much blocking
            font_files = font_files[:10]  # Only load first 10 fonts to prevent too much blocking

            for filename in font_files:
                if time.time() - start_time > timeout:
                    logger.warning(f"Font loading timed out for theme '{theme_name}' after loading {len(font_files)} fonts")
                    break

                font_path = os.path.join(fonts_folder, filename)
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    logger.info(f"Font {filename} successfully loaded: {families}")
                else:
                    logger.error(f"Error loading font: {filename}")

            # Update the global variable in the main thread
            _loaded_theme = theme_name
        except Exception as e:
            logger.error(f"Error loading fonts for theme '{theme_name}': {e}")

    # Use QTimer to delay font loading until after the UI is rendered
    from PySide6.QtCore import QTimer
    QTimer.singleShot(100, load_fonts_delayed)  # Delay font loading by 100ms

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
        self._default_theme = None  # Lazy-loaded default theme

    def __getattr__(self, name):
        if hasattr(self.custom_theme, name):
            return getattr(self.custom_theme, name)
        if self._default_theme is None:
            self._default_theme = load_theme("standart")  # Dynamically load standard theme
        return getattr(self._default_theme, name)

def load_theme(theme_name):
    """
    Динамически загружает модуль стилей выбранной темы и метаинформацию.
    Все темы, включая стандартную, проходят проверку безопасности.
    Для кастомных тем возвращается обёртка, которая подставляет недостающие атрибуты.
    """
    for themes_dir in THEMES_DIRS:
        theme_folder = os.path.join(themes_dir, theme_name)
        styles_file = os.path.join(theme_folder, "styles.py")
        if os.path.exists(styles_file):
            # Проверяем безопасность темы перед загрузкой
            if not check_theme_safety(styles_file):
                logger.error(f"Theme '{theme_name}' is unsafe, falling back to 'standart'")
                raise FileNotFoundError(f"Theme '{theme_name}' contains forbidden modules or functions")

            spec = importlib.util.spec_from_file_location("theme_styles", styles_file)
            if spec is None or spec.loader is None:
                continue
            custom_theme = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(custom_theme)
            if theme_name == "standart":
                return custom_theme
            meta = load_theme_metainfo(theme_name)
            wrapper = ThemeWrapper(custom_theme, metainfo=meta)
            wrapper.screenshots = load_theme_screenshots(theme_name)
            return wrapper
    raise FileNotFoundError(f"Styles file not found for theme '{theme_name}'")

class ThemeManager:
    """
    Класс для управления темами приложения.
    Реализует паттерн Singleton для единого экземпляра.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_theme_name = None
            cls._instance.current_theme_module = None
        return cls._instance

    def get_available_themes(self) -> list:
        """Возвращает список доступных тем."""
        return list_themes()

    def apply_theme(self, theme_name: str):
        """
        Применяет указанную тему, если она ещё не применена.
        Возвращает модуль темы или обёртку.
        """
        if self.current_theme_name == theme_name and self.current_theme_module is not None:
            logger.debug(f"Theme '{theme_name}' is already applied, skipping")
            return self.current_theme_module

        try:
            theme_module = load_theme(theme_name)
        except FileNotFoundError:
            logger.warning(f"Theme '{theme_name}' not found or unsafe, applying standard theme 'standart'")
            theme_module = load_theme("standart")
            theme_name = "standart"
            save_theme_to_config("standart")

        load_theme_fonts(theme_name)

        # Clear icon cache when theme changes to rebuild it for the new theme
        if self.current_theme_name != theme_name:
            global _icon_dirs_cache
            if theme_name in _icon_dirs_cache:
                del _icon_dirs_cache[theme_name]

        self.current_theme_name = theme_name
        self.current_theme_module = theme_module
        save_theme_to_config(theme_name)
        logger.info(f"Theme '{theme_name}' successfully applied")
        return theme_module

    def get_icon(self, icon_name, theme_name=None, as_path=False):
        """
        Возвращает QIcon из папки icons текущей темы (включая поддиректории),
        а если файл не найден, то из стандартной темы.
        Если as_path=True, возвращает путь к иконке вместо QIcon.
        """
        # Create cache key
        cache_key = f"{icon_name}_{theme_name or self.current_theme_name}_{as_path}"

        # Check if we already have this icon cached
        if cache_key in _icon_cache:
            logger.debug(f"Using cached icon for {icon_name}")
            return _icon_cache[cache_key]

        icon_path = None
        theme_name = theme_name or self.current_theme_name

        # Extract base name without extension if present
        supported_extensions = ['.svg', '.png', '.jpg', '.jpeg']
        has_extension = any(icon_name.lower().endswith(ext) for ext in supported_extensions)
        base_name = os.path.splitext(icon_name)[0] if has_extension else icon_name

        # Build icon cache for this theme if not already done
        icon_map = build_icon_cache(theme_name)

        # Look up the icon in the cache
        if base_name in icon_map:
            icon_path = icon_map[base_name]
            if not is_safe_image_file(icon_path):
                icon_path = None

        # Если иконка всё равно не найдена
        if not icon_path or not os.path.exists(icon_path):
            logger.error(f"Warning: icon '{icon_name}' not found")
            result = QIcon() if not as_path else None
            # Cache the result even if it's None
            _icon_cache[cache_key] = result
            return result

        if as_path:
            # Cache the path
            _icon_cache[cache_key] = icon_path
            return icon_path

        # Create QIcon and cache it
        icon = QIcon(icon_path)
        _icon_cache[cache_key] = icon
        return icon

    def get_theme_image(self, image_name, theme_name=None):
        """
        Возвращает путь к изображению из папки текущей темы.
        Если не найдено, проверяет стандартную тему.
        Принимает название иконки без расширения и находит соответствующий файл
        с поддерживаемым расширением (.svg, .png, .jpg и др.).
        """
        image_path = None
        theme_name = theme_name or self.current_theme_name

        # Extract base name without extension if present
        supported_extensions = ['.svg', '.png', '.jpg', '.jpeg']
        has_extension = any(image_name.lower().endswith(ext) for ext in supported_extensions)
        base_name = os.path.splitext(image_name)[0] if has_extension else image_name

        # Build icon cache for this theme if not already done
        # Note: We reuse the same cache mechanism for all images in the theme
        icon_map = build_icon_cache(theme_name)

        # Look up the image in the cache
        if base_name in icon_map:
            image_path = icon_map[base_name]
            if not is_safe_image_file(image_path):
                image_path = None

        return image_path
