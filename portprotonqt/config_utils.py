import os
import configparser
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

_portproton_location = None

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
    Если параметр не задан, возвращает "standart".
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
            return "standart"
    return cp.get("Appearance", "theme", fallback="standart")

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
    Сначала проверяется кэшированный путь. Если он отсутствует, проверяется
    наличие пути в файле PORTPROTON_CONFIG_FILE. Если путь недоступен,
    используется директория по умолчанию.
    """
    global _portproton_location
    if _portproton_location is not None:
        return _portproton_location

    # Попытка чтения пути из конфигурационного файла
    if os.path.isfile(PORTPROTON_CONFIG_FILE):
        try:
            location = read_file_content(PORTPROTON_CONFIG_FILE).strip()
            if location and os.path.isdir(location):
                _portproton_location = location
                logger.info(f"Путь PortProton из конфигурации: {location}")
                return _portproton_location
            logger.warning(f"Недействительный путь в конфиге PortProton: {location}")
        except (OSError, PermissionError) as e:
            logger.error(f"Ошибка чтения файла конфигурации PortProton: {e}")

    default_dir = os.path.join(os.path.expanduser("~"), ".var", "app", "ru.linux_gaming.PortProton")
    if os.path.isdir(default_dir):
        _portproton_location = default_dir
        logger.info(f"Используется директория flatpak PortProton: {default_dir}")
        return _portproton_location

    logger.warning("Конфигурация и директория flatpak PortProton не найдены")
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

def read_display_filter():
    """
    Читает параметр display_filter из секции [Games].
    Если параметр отсутствует, сохраняет и возвращает значение "all".
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения конфига: %s", e)
            save_display_filter("all")
            return "all"
        if not cp.has_section("Games") or not cp.has_option("Games", "display_filter"):
            save_display_filter("all")
            return "all"
        return cp.get("Games", "display_filter", fallback="all").lower()
    return "all"

def save_display_filter(filter_value):
    """
    Сохраняет параметр display_filter в секцию [Games] конфигурационного файла.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения конфига: %s", e)
    if "Games" not in cp:
        cp["Games"] = {}
    cp["Games"]["display_filter"] = filter_value
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)

def read_favorites():
    """
    Читает список избранных игр из секции [Favorites] конфигурационного файла.
    Список хранится как строка, заключённая в кавычки, с именами, разделёнными запятыми.
    Если секция или параметр отсутствуют, возвращает пустой список.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения конфига: %s", e)
            return []
        if cp.has_section("Favorites") and cp.has_option("Favorites", "games"):
            favs = cp.get("Favorites", "games", fallback="").strip()
            # Если строка начинается и заканчивается кавычками, удаляем их
            if favs.startswith('"') and favs.endswith('"'):
                favs = favs[1:-1]
            return [s.strip() for s in favs.split(",") if s.strip()]
    return []

def save_favorites(favorites):
    """
    Сохраняет список избранных игр в секцию [Favorites] конфигурационного файла.
    Список сохраняется как строка, заключённая в двойные кавычки, где имена игр разделены запятыми.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения конфига: %s", e)
    if "Favorites" not in cp:
        cp["Favorites"] = {}
    fav_str = ", ".join(favorites)
    cp["Favorites"]["games"] = f'"{fav_str}"'
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)

def ensure_default_proxy_config():
    """
    Проверяет наличие секции [Proxy] в конфигурационном файле.
    Если секция отсутствует, создаёт её с пустыми значениями.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения конфигурационного файла: %s", e)
            return
        if not cp.has_section("Proxy"):
            cp.add_section("Proxy")
            cp["Proxy"]["proxy_url"] = ""
            cp["Proxy"]["proxy_user"] = ""
            cp["Proxy"]["proxy_password"] = ""
            with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
                cp.write(configfile)


def read_proxy_config():
    """
    Читает настройки прокси из секции [Proxy] конфигурационного файла.
    Если параметр proxy_url не задан или пустой, возвращает пустой словарь.
    """
    ensure_default_proxy_config()
    cp = configparser.ConfigParser()
    try:
        cp.read(CONFIG_FILE, encoding="utf-8")
    except Exception as e:
        logger.error("Ошибка чтения конфигурационного файла: %s", e)
        return {}

    proxy_url = cp.get("Proxy", "proxy_url", fallback="").strip()
    if proxy_url:
        # Если указаны логин и пароль, добавляем их к URL
        proxy_user = cp.get("Proxy", "proxy_user", fallback="").strip()
        proxy_password = cp.get("Proxy", "proxy_password", fallback="").strip()
        if "://" in proxy_url and "@" not in proxy_url and proxy_user and proxy_password:
            protocol, rest = proxy_url.split("://", 1)
            proxy_url = f"{protocol}://{proxy_user}:{proxy_password}@{rest}"
        return {"http": proxy_url, "https": proxy_url}
    return {}

def save_proxy_config(proxy_url="", proxy_user="", proxy_password=""):
    """
    Сохраняет настройки proxy в секцию [Proxy] конфигурационного файла.
    Если секция отсутствует, создаёт её.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка чтения конфигурационного файла: %s", e)
    if "Proxy" not in cp:
        cp["Proxy"] = {}
    cp["Proxy"]["proxy_url"] = proxy_url
    cp["Proxy"]["proxy_user"] = proxy_user
    cp["Proxy"]["proxy_password"] = proxy_password
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)

def read_fullscreen_config():
    """
    Читает настройку полноэкранного режима приложения из секции [Display].
    Если параметр отсутствует, сохраняет и возвращает False по умолчанию.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения конфигурационного файла: %s", e)
            save_fullscreen_config(False)
            return False
        if not cp.has_section("Display") or not cp.has_option("Display", "fullscreen"):
            save_fullscreen_config(False)
            return False
        return cp.getboolean("Display", "fullscreen", fallback=False)
    return False

def save_fullscreen_config(fullscreen):
    """
    Сохраняет настройку полноэкранного режима приложения в секцию [Display].
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка чтения конфигурационного файла: %s", e)
    if "Display" not in cp:
        cp["Display"] = {}
    cp["Display"]["fullscreen"] = str(fullscreen)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)



def read_window_geometry() -> tuple[int, int]:
    """
    Читает ширину и высоту окна из секции [MainWindow] конфигурационного файла.
    Возвращает кортеж (width, height). Если данные отсутствуют, возвращает (0, 0).
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
            return (0, 0)
        if cp.has_section("MainWindow"):
            width = cp.getint("MainWindow", "width", fallback=0)
            height = cp.getint("MainWindow", "height", fallback=0)
            return (width, height)
    return (0, 0)

def save_window_geometry(width: int, height: int):
    """
    Сохраняет ширину и высоту окна в секцию [MainWindow] конфигурационного файла.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
        except (configparser.DuplicateSectionError, configparser.DuplicateOptionError) as e:
            logger.error("Ошибка в конфигурационном файле: %s", e)
    if "MainWindow" not in cp:
        cp["MainWindow"] = {}
    cp["MainWindow"]["width"] = str(width)
    cp["MainWindow"]["height"] = str(height)
    with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
        cp.write(configfile)
