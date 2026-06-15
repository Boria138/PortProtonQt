import os
import hashlib
import shutil
from datetime import datetime, timedelta
from babel.dates import format_timedelta, format_date
from portprotonqt.config import ui_config
from portprotonqt.localization import _, get_system_locale
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

_migrated = False


def _migrate_last_launch_file(data_home: str) -> str:
    """Migrate last_launch from old cache dir to XDG_DATA_HOME."""
    global _migrated
    if _migrated:
        return ""
    _migrated = True
    new_path = os.path.join(data_home, "PortProtonQt", "last_launch")
    cache_home = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    old_path = os.path.join(cache_home, "PortProtonQt", "last_launch")
    if not os.path.exists(old_path) or os.path.exists(new_path):
        return ""
    try:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)
        logger.info("Migrated last_launch from %s to %s", old_path, new_path)
        return old_path
    except OSError as e:
        logger.warning("Failed to migrate last_launch: %s", e)
        return ""


def get_last_launch_path():
    """Return path to last_launch state file."""
    data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    _migrate_last_launch_file(data_home)
    return os.path.join(data_home, "PortProtonQt", "last_launch")

def _parse_last_launch_line(line: str) -> tuple[str, str] | None:
    parts = line.strip().rsplit(maxsplit=1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]

def save_last_launch(exe_name, launch_time):
    """
    Save launch time for exe.
    File format: <exe_name> <isoformatted_time>
    """
    file_path = get_last_launch_path()
    data = {}
    if os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                parsed_line = _parse_last_launch_line(line)
                if parsed_line:
                    data[parsed_line[0]] = parsed_line[1]
    data[exe_name] = launch_time.isoformat()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        for key, iso_time in data.items():
            f.write(f"{key} {iso_time}\n")

def format_last_launch(launch_time):
    """
    Format launch time using Babel.

    For detail_level "detailed" returns relative format with "ago" added
    (e.g., "2 min. ago"). If time is less than a minute - returns translated string.
    For "brief" – date in "day month year" format (e.g., "April 1, 2023")
    based on system locale.
    """
    detail_level = ui_config.get_time_detail_level() or "detailed"
    system_locale = get_system_locale()
    if detail_level == "detailed":
        # Calculate delta as launch_time - datetime.now() to get negative value for elapsed time.
        delta = launch_time - datetime.now()
        if abs(delta.total_seconds()) < 60:
            return _("just now")
        return format_timedelta(delta, locale=system_locale, granularity='second', format='short', add_direction=True)
    else:
        return format_date(launch_time, format="d MMMM yyyy", locale=system_locale)

def get_last_launch(exe_name):
    """
    Read last launch time for given exe from cache file.
    Return launch time in required format or translated "Never" string.
    """
    file_path = get_last_launch_path()
    if not os.path.exists(file_path):
        return _("Never")
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            parsed_line = _parse_last_launch_line(line)
            if parsed_line and parsed_line[0] == exe_name:
                iso_time = parsed_line[1]
                launch_time = datetime.fromisoformat(iso_time)
                return format_last_launch(launch_time)
    return _("Never")

def parse_playtime_file(file_path):
    """
    Parse playtime data file.

    Line format in file:
      <full exe path> <hash> <playtime_seconds> <platform> <build>

    Return dictionary like:
      {
         '<exe_path>': playtime_seconds (int),
         ...
      }
    """
    playtime_data = {}
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return playtime_data

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            exe_path = parts[0]
            # Find playtime: first numeric value after exe_path
            # Format: <exe_path> <hash> <playtime_seconds> <platform> ...
            # Hash is 64 hex chars, playtime is digits only
            for i in range(1, len(parts)):
                if parts[i].isdigit():
                    playtime_data[exe_path] = int(parts[i])
                    break
    return playtime_data


def get_playtime_for_exe(file_path: str, exe_path: str) -> int | None:
    """Return playtime for the target executable from statistics file."""
    if not exe_path or not os.path.exists(file_path):
        return None

    target_path = os.path.normpath(exe_path)
    target_name = os.path.splitext(os.path.basename(target_path))[0].lower()
    target_sha = None
    try:
        sha = hashlib.sha256()
        with open(target_path, "rb") as exe_file:
            for chunk in iter(lambda: exe_file.read(1024 * 1024), b""):
                sha.update(chunk)
        target_sha = sha.hexdigest()
    except OSError:
        target_sha = None

    sha_seconds = None
    sha_last_launch = -1
    exact_seconds = None
    exact_last_launch = -1
    fallback_seconds = None
    fallback_last_launch = -1

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) < 3:
                continue

            seconds = None
            for token in parts[1:]:
                if token.isdigit():
                    seconds = int(token)
                    break
            if seconds is None:
                continue

            last_launch_index = -1
            for token in parts[1:]:
                if token.startswith("L5-") and token[3:].isdigit():
                    last_launch_index = int(token[3:])
                    break

            stat_path = os.path.normpath(parts[0].replace("#@_@#", " "))
            stat_sha = parts[1] if len(parts) > 1 and len(parts[1]) == 64 else ""

            if target_sha and stat_sha == target_sha:
                if last_launch_index >= sha_last_launch:
                    sha_seconds = seconds
                    sha_last_launch = last_launch_index
                continue

            if stat_path == target_path:
                if last_launch_index >= exact_last_launch:
                    exact_seconds = seconds
                    exact_last_launch = last_launch_index
                continue

            stat_name = os.path.splitext(os.path.basename(stat_path))[0].lower()
            if stat_name == target_name and last_launch_index >= fallback_last_launch:
                fallback_seconds = seconds
                fallback_last_launch = last_launch_index

    if sha_seconds is not None:
        return sha_seconds
    if exact_seconds is not None:
        return exact_seconds
    return fallback_seconds

def format_playtime(seconds):
    """
    Convert time in seconds to formatted string using Babel.

    For "detailed" outputs full time breakdown, without rounding
    (e.g., "1 h 1 min 15 sec").

    For "brief":
      - if time is less than hour, output exact time with seconds (e.g., "9 min 28 sec"),
      - if more than hour – only hours (e.g., "3 h").
    """
    detail_level = ui_config.get_time_detail_level() or "detailed"
    system_locale = get_system_locale()
    seconds = int(seconds)

    if detail_level == "detailed":
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days > 0:
            parts.append(f"{days} " + _("d."))
        if hours > 0:
            parts.append(f"{hours} " + _("h."))
        if minutes > 0:
            parts.append(f"{minutes} " + _("min."))
        if secs > 0 or not parts:
            parts.append(f"{secs} " + _("sec."))
        return " ".join(parts)
    else:
        # Brief mode
        if seconds < 3600:
            minutes, secs = divmod(seconds, 60)
            parts = []
            if minutes > 0:
                parts.append(f"{minutes} " + _("min."))
            if secs > 0 or not parts:
                parts.append(f"{secs} " + _("sec."))
            return " ".join(parts)
        else:
            hours = seconds // 3600
            return format_timedelta(timedelta(hours=hours), locale=system_locale, granularity='hour', format='short')

def get_last_launch_timestamp(exe_name):
    """
    Return last launch timestamp for given exe.
    If no record, return 0.
    """
    file_path = get_last_launch_path()
    if not os.path.exists(file_path):
        return 0
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            parsed_line = _parse_last_launch_line(line)
            if parsed_line and parsed_line[0] == exe_name:
                iso_time = parsed_line[1]
                dt = datetime.fromisoformat(iso_time)
                return dt.timestamp()
    return 0
