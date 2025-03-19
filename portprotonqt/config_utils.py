import os
import configparser

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
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Пропускаем комментарии и пустые строки
                    if not line or line.startswith("#"):
                        continue
                    key, sep, value = line.partition("=")
                    if sep:
                        config_dict[key.strip()] = value.strip()
        except Exception as e:
            print("Ошибка чтения конфигурационного файла:", e)
    return config_dict

def read_theme_from_config():
    """
    Читает из конфигурационного файла, какая тема указана в секции [Appearance].
    Если чтение не удалось или параметр не задан, возвращает "standart_lite".
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
            return cp.get("Appearance", "theme", fallback="standart_lite")
        except Exception as e:
            print("Ошибка чтения конфигурации темы:", e)
    return "standart_lite"

def save_theme_to_config(theme_name):
    """
    Сохраняет имя выбранной темы в конфигурационном файле (CONFIG_FILE)
    под секцией [Appearance].
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cp.read(CONFIG_FILE, encoding="utf-8")
    if "Appearance" not in cp:
        cp["Appearance"] = {}
    cp["Appearance"]["theme"] = theme_name
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            cp.write(configfile)
    except Exception as e:
        print("Ошибка сохранения конфигурации темы:", e)

def read_time_config():
    """
    Читает настройки времени из секции [Time] конфигурационного файла.
    Если секция или параметр отсутствуют, сохраняет и возвращает "detailed" по умолчанию.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
            if not cp.has_section("Time") or not cp.has_option("Time", "detail_level"):
                save_time_config("detailed")
                return "detailed"
            return cp.get("Time", "detail_level", fallback="detailed").lower()
        except Exception as e:
            print("Ошибка чтения конфигурации времени:", e)
    return "detailed"


def save_time_config(detail_level):
    """
    Сохраняет настройку уровня детализации времени в секции [Time] конфигурационного файла.
    :param detail_level: Значение detail_level (например, "detailed" или "brief")
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cp.read(CONFIG_FILE, encoding="utf-8")
    if "Time" not in cp:
        cp["Time"] = {}
    cp["Time"]["detail_level"] = detail_level
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            cp.write(configfile)
    except Exception as e:
        print("Ошибка сохранения конфигурации времени:", e)

def read_file_content(file_path):
    """
    Читает содержимое файла и возвращает его как строку,
    либо None в случае ошибки.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Ошибка чтения файла {file_path}: {e}")
        return None

def get_portproton_location():
    """
    Возвращает путь к директории PortProton.
    Если конфигурационный файл PORTPROTON_CONFIG_FILE существует и содержит путь,
    возвращается его содержимое. Иначе используется fallback-директория.
    """
    if os.path.exists(PORTPROTON_CONFIG_FILE):
        location = read_file_content(PORTPROTON_CONFIG_FILE)
        if location:
            print(f"Current PortProton location from config: {location}")
            return location

    fallback_dir = os.path.join(os.path.expanduser("~"), ".var", "app", "ru.linux_gaming.PortProton")
    if os.path.isdir(fallback_dir):
        print(f"Using fallback PortProton location from data directory: {fallback_dir}")
        return fallback_dir

    print(f"Не найден конфигурационный файл {CONFIG_FILE} и директория PortProton не существует.")
    return None

def parse_desktop_entry(file_path):
    """
    Читает и парсит .desktop файл с помощью configparser.
    Если секция [Desktop Entry] отсутствует или происходит ошибка,
    возвращается None.
    """
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read(file_path, encoding="utf-8")
    except Exception as e:
        print(f"Ошибка чтения файла {file_path}: {e}")
        return None

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
    Читает из конфигурационного файла размер карточек (ширину) из секции [Cards].
    Если параметр не задан, возвращает 250.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            cp.read(CONFIG_FILE, encoding="utf-8")
            if not cp.has_section("Cards") or not cp.has_option("Cards", "card_width"):
                save_card_size("250")
                return 250
            return cp.getint("Cards", "card_width", fallback=250)
        except Exception as e:
            print("Ошибка чтения конфигурации размера карточек:", e)
    return 250

def save_card_size(card_width):
    """
    Сохраняет размер карточек (ширину) в секцию [Cards] конфигурационного файла.
    """
    cp = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cp.read(CONFIG_FILE, encoding="utf-8")
    if "Cards" not in cp:
        cp["Cards"] = {}
    cp["Cards"]["card_width"] = str(card_width)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            cp.write(configfile)
    except Exception as e:
        print("Ошибка сохранения конфигурации размера карточек:", e)
