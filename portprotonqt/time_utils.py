import os
import locale
from datetime import datetime, timedelta
from babel.dates import format_timedelta, format_date
from portprotonqt.config_utils import read_time_config
from portprotonqt.localization import _

def get_system_locale():
    """Возвращает системную локаль, например, 'ru_RU'. Если не удаётся определить – возвращает 'en'."""
    loc = locale.getdefaultlocale()[0]
    return loc if loc else 'en'

def get_cache_file_path():
    """Возвращает путь к файлу кеша portproton_last_launch."""
    cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    return os.path.join(cache_home, "PortProtonQT", "last_launch")

def save_last_launch(exe_name, launch_time):
    """
    Сохраняет время запуска для exe.
    Формат файла: <exe_name> <isoformatted_time>
    """
    file_path = get_cache_file_path()
    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2:
                        data[parts[0]] = parts[1]
        except Exception as e:
            print("Ошибка чтения файла кеша:", e)
    data[exe_name] = launch_time.isoformat()
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            for key, iso_time in data.items():
                f.write(f"{key} {iso_time}\n")
    except Exception as e:
        print("Ошибка сохранения файла кеша:", e)

def format_last_launch(launch_time):
    """
    Форматирует время запуска с использованием Babel.

    Для detail_level "detailed" возвращает относительный формат с добавлением "назад"
    (например, "2 мин. назад"). Если время меньше минуты – возвращает "только что".
    Для "brief" – дату в формате "день месяц год" (например, "1 апреля 2023")
    на основе системной локали.
    """
    detail_level = read_time_config() or "detailed"
    system_locale = get_system_locale()
    if detail_level == "detailed":
        # Вычисляем delta как launch_time - datetime.now() чтобы получить отрицательное значение для прошедшего времени.
        delta = launch_time - datetime.now()
        if abs(delta.total_seconds()) < 60:
            return "только что"
        return format_timedelta(delta, locale=system_locale, granularity='second', format='short', add_direction=True)
    else:
        return format_date(launch_time, format="d MMMM yyyy", locale=system_locale)

def get_last_launch(exe_name):
    """
    Читает время последнего запуска для заданного exe из файла кеша.
    Возвращает время запуска в нужном формате или "Никогда".
    """
    file_path = get_cache_file_path()
    if not os.path.exists(file_path):
        return "Никогда"
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2 and parts[0] == exe_name:
                    iso_time = parts[1]
                    launch_time = datetime.fromisoformat(iso_time)
                    return format_last_launch(launch_time)
    except Exception as e:
        print("Ошибка чтения файла кеша:", e)
    return "Никогда"

def parse_playtime_file(file_path):
    """
    Парсит файл с данными о времени игры.

    Формат строки в файле:
      <полный путь к exe> <хэш> <playtime_seconds> <platform> <build>

    Возвращает словарь вида:
      {
         '<exe_path>': playtime_seconds (int),
         ...
      }
    """
    playtime_data = {}
    if not os.path.exists(file_path):
        print(f"Файл не найден: {file_path}")
        return playtime_data

    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                exe_path = parts[0]
                try:
                    seconds = int(parts[2])
                except ValueError:
                    seconds = 0
                playtime_data[exe_path] = seconds
    except Exception as e:
        print(f"Ошибка при парсинге файла {file_path}: {e}")
    return playtime_data


def format_playtime(seconds):
    """
    Конвертирует время в секундах в форматированную строку с использованием Babel.

    При "detailed" выводится полный разбор времени, без округления
    (например, "1 ч 1 мин 15 сек").

    При "brief":
      - если время менее часа, выводится точное время с секундами (например, "9 мин 28 сек"),
      - если больше часа – только часы (например, "3 ч").
    """
    detail_level = read_time_config() or "detailed"
    system_locale = get_system_locale()
    seconds = int(seconds)

    if detail_level == "detailed":
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days > 0:
            parts.append(f"{days} " + _("d"))
        if hours > 0:
            parts.append(f"{hours} " + _("h"))
        if minutes > 0:
            parts.append(f"{minutes} " + _("min"))
        if secs > 0 or not parts:
            parts.append(f"{secs} " + _("sec"))
        return " ".join(parts)
    else:
        # Режим brief
        if seconds < 3600:
            minutes, secs = divmod(seconds, 60)
            parts = []
            if minutes > 0:
                parts.append(f"{minutes} " + _("min"))
            if secs > 0 or not parts:
                parts.append(f"{secs} " + _("sec"))
            return " ".join(parts)
        else:
            hours = seconds // 3600
            return format_timedelta(timedelta(hours=hours), locale=system_locale, granularity='hour', format='short')

def get_last_launch_timestamp(exe_name):
    """
    Возвращает метку времени последнего запуска (timestamp) для заданного exe.
    Если записи нет или произошла ошибка, возвращает 0.
    """
    file_path = get_cache_file_path()
    if not os.path.exists(file_path):
        return 0
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2 and parts[0] == exe_name:
                    iso_time = parts[1]
                    dt = datetime.fromisoformat(iso_time)
                    return dt.timestamp()
    except Exception as e:
        print("Ошибка чтения кеша:", e)
    return 0
