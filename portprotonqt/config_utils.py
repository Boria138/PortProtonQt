import os
import configparser
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

# Пути к конфигурационным файлам
CONFIG_FILE = os.path.join(
    os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "PortProtonQT.conf"
)

PORTPROTON_CONFIG_FILE = os.path.join(
    os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "PortProton.conf"
)

# Пути к папкам с темами
xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
THEMES_DIRS = [
    os.path.join(xdg_data_home, "PortProtonQT", "themes"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
]

def read_config():
    """
    Читает конфигурационный файл и возвращает словарь параметров.
    Пример строки в конфиге (без секций):
      detail_level = detailed
    """
    config_dict = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, sep, value = line.partition("=")
                if sep:
                    config_dict[key.strip()] = value.strip()
    return config_dict

def read_theme_from_config():
    """
    Читает из конфигурационного файла тему из секции [Appearance].
    Если параметр не задан, возвращает "standart_lite".
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
            return "standart_lite"
    return cp.get("Appearance", "theme", fallback="standart_lite")

def save_theme_to_config(theme_name):
    """
    Сохраняет имя выбранной темы в секции [Appearance] конфигурационного файла.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
    if "Appearance" not in cp:
        cp["Appearance"] = {}
    cp["Appearance"]["theme"] = theme_name
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)

def read_time_config():
    """
    Читает настройки времени из секции [Time] конфигурационного файла.
    Если секция или параметр отсутствуют, сохраняет и возвращает "detailed" по умолчанию.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
            save_time_config("detailed")
            return "detailed"
        if not cp.has_section("Time") or not cp.has_option("Time", "detail_level"):
            save_time_config("detailed")
            return "detailed"
        return cp.get("Time", "detail_level", fallback="detailed").lower()
    return "detailed"

def save_time_config(detail_level):
    """
    Сохраняет настройку уровня детализации времени в секции [Time].
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
    if "Time" not in cp:
        cp["Time"] = {}
    cp["Time"]["detail_level"] = detail_level
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)

def read_file_content(file_path):
    """
    Читает содержимое файла и возвращает его как строку.
    """
    with open(file_path, encoding="utf-8") as f:
        return f.read().strip()

def get_portproton_location():
    """
    Возвращает путь к директории PortProton.
    Если файл PORTPROTON_CONFIG_FILE существует и содержит путь,
    возвращается его содержимое. Иначе используется fallback-директория.
    """
    if os.path.exists(PORTPROTON_CONFIG_FILE):
        try:
            location = read_file_content(PORTPROTON_CONFIG_FILE)
            if location:
                logger.info("Текущий путь PortProton из конфига: %s", location)
                return location
        except Exception as e:
            logger.error("Ошибка чтения конфига PortProton: %s", e)
    fallback_dir = os.path.join(os.path.expanduser("~"), ".var", "app", "ru.linux_gaming.PortProton")
    if os.path.isdir(fallback_dir):
        logger.info("Используется fallback-директория PortProton: %s", fallback_dir)
        return fallback_dir
    logger.warning("Конфиг PortProton и fallback-директория не найдены.")
    return None

def parse_desktop_entry(file_path):
    """
    Читает и парсит .desktop файл с помощью configparser.
    Если секция [Desktop Entry] отсутствует, возвращается None.
    """
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(file_path, encoding="utf-8")
    if "Desktop Entry" not in cp:
        return None
    return cp["Desktop Entry"]

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
            cp = configparser.ConfigParser()
            cp.read(metainfo_file, encoding="utf-8")
            if "Metainfo" in cp:
                meta["author"] = cp.get("Metainfo", "author", fallback="Unknown")
                meta["author_link"] = cp.get("Metainfo", "author_link", fallback="")
                meta["description"] = cp.get("Metainfo", "description", fallback="")
                meta["name"] = cp.get("Metainfo", "name", fallback=theme_name)
            break
    return meta

def read_card_size():
    """
    Читает размер карточек (ширину) из секции [Cards],
    Если параметр не задан, возвращает 250.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
            save_card_size(250)
            return 250
        if not cp.has_section("Cards") or not cp.has_option("Cards", "card_width"):
            save_card_size(250)
            return 250
        return cp.getint("Cards", "card_width", fallback=250)
    return 250

def save_card_size(card_width):
    """
    Сохраняет размер карточек (ширину) в секцию [Cards].
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
    if "Cards" not in cp:
        cp["Cards"] = {}
    cp["Cards"]["card_width"] = str(card_width)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)

def read_sort_method():
    """
    Читает метод сортировки из секции [Games].
    Если параметр не задан, возвращает last_launch.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
            save_sort_method("last_launch")
            return "last_launch"
        if not cp.has_section("Games") or not cp.has_option("Games", "sort_method"):
            save_sort_method("last_launch")
            return "last_launch"
        return cp.get("Games", "sort_method", fallback="last_launch").lower()
    return "last_launch"

def save_sort_method(sort_method):
    """
    Сохраняет метод сортировки в секцию [Games].
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
    if "Games" not in cp:
        cp["Games"] = {}
    cp["Games"]["sort_method"] = sort_method
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
