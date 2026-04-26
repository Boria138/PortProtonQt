"""PortProton configuration and launch helpers."""
import configparser
import os
import shlex
import subprocess
from pathlib import Path
from portprotonqt.config.base import (
    BaseConfig,
    CONFIG_FILE,
    PORTPROTON_CONFIG_FILE,
    _config_cache,
    _config_mtime,
)
from portprotonqt.config.validators import validate_path
from portprotonqt.localization import _
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
_portproton_start_command: list[str] | None = None


class PortProtonConfig(BaseConfig):
    """PortProton location configuration."""

    _section = "PortProton"
    _portproton_location: str | None = None

    def __init__(self):
        super().__init__()
        self._config_file = PORTPROTON_CONFIG_FILE

    def get_location(self) -> str | None:
        """Get PortProton directory location."""
        if self._portproton_location is not None:
            return self._portproton_location

        if self._config_file.exists():
            try:
                location = self._config_file.read_text(encoding="utf-8").strip()
                if location and os.path.isdir(location):
                    self._portproton_location = location
                    logger.info("PortProton path from configuration: %s", location)
                    return self._portproton_location
                logger.warning("Invalid PortProton path in configuration: %s", location)
            except (OSError, PermissionError) as error:
                logger.warning("Failed to read PortProton configuration file: %s", error)
            except Exception as error:
                logger.warning("Unexpected error reading PortProton configuration file: %s", error)

        default_flatpak_dir = Path.home() / ".var" / "app" / "ru.linux_gaming.PortProton"
        if default_flatpak_dir.is_dir():
            self._portproton_location = str(default_flatpak_dir)
            logger.info("Using Flatpak PortProton directory: %s", default_flatpak_dir)
            return self._portproton_location

        logger.warning("PortProton configuration and Flatpak directory not found")
        return None

    def set_location(self, location: str):
        """Set PortProton directory location."""
        validate_path(location, "portproton_location", must_exist=True)
        self._config_file.write_text(location, encoding="utf-8")
        self._portproton_location = location
        logger.info("PortProton location set to: %s", location)


def _read_config_safely(config_file: Path = CONFIG_FILE) -> configparser.ConfigParser | None:
    """Read a config file with local cache awareness."""
    config_path = str(config_file)
    if not config_file.exists():
        return None
    try:
        current_mtime = config_file.stat().st_mtime
    except OSError:
        return None

    if config_path in _config_cache and config_path in _config_mtime:
        if _config_mtime[config_path] == current_mtime:
            return _config_cache[config_path]

    cp = configparser.ConfigParser()
    try:
        cp.read(config_path, encoding="utf-8")
        _config_cache[config_path] = cp
        _config_mtime[config_path] = current_mtime
        return cp
    except (configparser.DuplicateSectionError, configparser.DuplicateOptionError):
        return None


def read_portdata_path_from_config() -> str | None:
    """Read PortProton data path from main config."""
    cp = _read_config_safely(CONFIG_FILE)
    if cp is None or not cp.has_section("PortProton"):
        return None

    portdata_path = cp.get("PortProton", "portdata_path", fallback="").strip()
    if not portdata_path or not os.path.isdir(portdata_path):
        return None
    return portdata_path


def get_portproton_location() -> str | None:
    """Return PortProton directory path."""
    saved_portdata_path = read_portdata_path_from_config()
    if saved_portdata_path:
        return saved_portdata_path

    portproton_location = PortProtonConfig().get_location()
    if portproton_location:
        save_portdata_path_to_config(portproton_location)
    return portproton_location


def save_portdata_path_to_config(portdata_path: str) -> bool:
    """Save PortProton data path to main config."""
    if not portdata_path or not os.path.isdir(portdata_path):
        logger.warning("Invalid PORT_DATA_PATH for config save: %s", portdata_path)
        return False

    cp = _read_config_safely(CONFIG_FILE) or configparser.ConfigParser()
    if "PortProton" not in cp:
        cp["PortProton"] = {}
    cp["PortProton"]["portdata_path"] = portdata_path
    try:
        os.makedirs(CONFIG_FILE.parent, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
            cp.write(config_file)
        _config_cache.pop(str(CONFIG_FILE), None)
        _config_mtime.pop(str(CONFIG_FILE), None)
        return True
    except OSError as error:
        logger.warning("Failed to save PORT_DATA_PATH to config: %s", error)
        return False


def get_portproton_scripts_path() -> str | None:
    """Return PortProton scripts directory path."""
    sharun_prefix = os.getenv("SHARUN_DIR")
    prefixes = [Path("/usr"), Path("/app")]
    if sharun_prefix:
        prefixes.append(Path(sharun_prefix))

    scripts_dirs = (
        Path(__file__).resolve().parent.parent.parent / "build-aux" / "share" / "portproton" / "scripts",
        *[prefix / "share" / "portproton" / "scripts" for prefix in prefixes],
    )
    for scripts_dir in scripts_dirs:
        if scripts_dir.exists():
            return str(scripts_dir)
    return None


def _detect_flatpak_start_command() -> list[str] | None:
    """Return Flatpak launch command when PortProton is installed via Flatpak."""
    try:
        subprocess.run(["flatpak", "--version"], capture_output=True, text=True, check=False, timeout=5)
    except FileNotFoundError:
        return None
    except Exception as error:
        logger.debug("Flatpak version check failed: %s", error)
        return None

    try:
        result = subprocess.run(
            ["flatpak", "list"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if "ru.linux_gaming.PortProton" in result.stdout:
            logger.info("Detected Flatpak installation")
            return ["flatpak", "run", "ru.linux_gaming.PortProton"]
    except subprocess.TimeoutExpired:
        logger.warning("Flatpak list command timed out")
    except Exception as error:
        logger.warning("Error checking flatpak list: %s", error)
    return None


def get_portproton_start_command() -> list[str] | None:
    """Return command list for PortProton launch."""
    global _portproton_start_command
    if _portproton_start_command is not None:
        return _portproton_start_command

    flatpak_command = _detect_flatpak_start_command()
    if flatpak_command is not None:
        _portproton_start_command = flatpak_command
        return _portproton_start_command

    scripts_path = get_portproton_scripts_path()
    if scripts_path:
        _portproton_start_command = [os.path.join(scripts_path, "start.sh")]
        return _portproton_start_command

    logger.warning("Neither flatpak nor start.sh found for PortProton")
    return None


def parse_desktop_entry(file_path: str) -> configparser.SectionProxy | None:
    """Read and parse a .desktop file using configparser."""
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(file_path, encoding="utf-8")
    if "Desktop Entry" not in cp:
        return None
    return cp["Desktop Entry"]


def find_game_by_exe(exe_path: str) -> configparser.SectionProxy | None:
    """Find a game desktop entry by executable path."""
    portproton_path = get_portproton_location()
    if not portproton_path:
        return None

    target_exe = os.path.abspath(exe_path)
    for entry in os.scandir(portproton_path):
        if not entry.name.endswith(".desktop"):
            continue
        if entry.name.lower() in ("portproton.desktop", "readme.desktop"):
            continue

        desktop_entry = parse_desktop_entry(entry.path)
        if not desktop_entry:
            continue
        exec_line = desktop_entry.get("Exec", "")
        if not exec_line:
            continue

        try:
            parts = shlex.split(exec_line)
        except ValueError:
            continue

        game_exe = ""
        if len(parts) >= 4:
            game_exe = os.path.expanduser(parts[3])
        else:
            for part in parts:
                if part.endswith(".exe"):
                    game_exe = part
                    break
        if game_exe and os.path.abspath(game_exe) == target_exe:
            return desktop_entry
    return None


def create_desktop_file(
    exe_path: str,
    game_name: str | None = None,
) -> tuple[str, str] | None:
    """Create desktop entry content and destination path for a game."""
    portproton_path = get_portproton_location()
    scripts_path = get_portproton_scripts_path()
    if not os.path.isfile(exe_path):
        logger.error("Executable not found: %s", exe_path)
        return None
    if not portproton_path:
        logger.error("PortProton location not found")
        return None
    if not scripts_path:
        logger.error("PortProton scripts path not found")
        return None

    if not game_name:
        game_name = os.path.splitext(os.path.basename(exe_path))[0]
    is_flatpak = ".var" in portproton_path
    base_path = os.path.join(portproton_path, "data")
    icon_path = os.path.join(base_path, "img", f"{game_name}.png")
    desktop_path = os.path.join(portproton_path, f"{game_name}.desktop")
    os.makedirs(os.path.dirname(icon_path), exist_ok=True)

    if is_flatpak:
        exec_str = f'flatpak run ru.linux_gaming.PortProton "{exe_path}"'
    else:
        start_sh = os.path.join(scripts_path, "start.sh")
        if not os.path.exists(start_sh):
            logger.error("start.sh not found in supported paths")
            return None
        exec_str = f'env "{start_sh}" "{exe_path}"'

    comment = _('Launch game "{name}" with PortProton').format(name=game_name)
    desktop_entry = (
        "[Desktop Entry]\n"
        f"Name={game_name}\n"
        f"Comment={comment}\n"
        f"Exec={exec_str}\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Game;\n"
        "StartupNotify=true\n"
        f"Path={scripts_path}\n"
        f"Icon={icon_path}\n"
    )
    return desktop_entry, desktop_path
