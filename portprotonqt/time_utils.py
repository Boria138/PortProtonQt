import os
from datetime import datetime
from portprotonqt.config_utils import read_time_config

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

def humanize_time_delta(launch_time):
    """
    Принимает время запуска (datetime) и возвращает строку вида:
    "только что", "5 мин. назад", "2 часа назад", "1 день назад", "3 месяца назад", "2 года назад"
    """
    now = datetime.now()
    delta = now - launch_time
    seconds = delta.total_seconds()

    if seconds < 60:
        return "только что"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} мин. назад"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} час{'а' if hours == 1 else 'ов'} назад"
    elif seconds < 2592000:
        days = int(seconds // 86400)
        return f"{days} дн. назад"
    elif seconds < 31104000:
        months = int(seconds // 2592000)
        return f"{months} мес. назад"
    else:
        years = int(seconds // 31104000)
        return f"{years} год{'а' if years == 1 else 'ов'} назад"

def format_last_launch(launch_time):
    """
    Форматирует время запуска в зависимости от настройки detail_level:
      - "detailed"  -> возвращает относительное время (например, "час назад")
      - "brief" -> возвращает дату в формате "1 апреля"
    """
    detail_level = read_time_config() or "detailed"
    if detail_level == "detailed":
        return humanize_time_delta(launch_time)
    else:
        # Для корректного отображения названия месяца на русском можно использовать словарь.
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
            7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        day = launch_time.day
        month = months.get(launch_time.month, "")
        return f"{day} {month}"

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
    Конвертирует время в секундах в форматированную строку.

    Поведение зависит от настройки detail_level из секции [Time]
    конфигурационного файла. Если detail_level не задан, используется "detailed".

    При "detailed" выводится полный разбор:
       3675 -> "1 ч 1 мин 15 сек"
       90061 -> "1 д 1 ч 1 мин 1 сек"

    При "brief":
       3675 -> "1 ч"
       125 -> "2 мин 5 сек"
    """
    detail_level = read_time_config() or "detailed"
    seconds = int(seconds)

    if detail_level == "detailed":
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days > 0:
            parts.append(f"{days} д")
        if hours > 0:
            parts.append(f"{hours} ч")
        if minutes > 0:
            parts.append(f"{minutes} мин")
        if secs > 0 or not parts:
            parts.append(f"{secs} сек")
        return " ".join(parts)
    else:  # brief
        if seconds < 3600:
            minutes, secs = divmod(seconds, 60)
            parts = []
            if minutes > 0:
                parts.append(f"{minutes} мин")
            if secs > 0 or not parts:
                parts.append(f"{secs} сек")
            return " ".join(parts)
        else:
            hours = seconds // 3600
            return f"{hours} ч"

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
