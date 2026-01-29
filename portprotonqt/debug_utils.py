import os
import platform
import re
import subprocess
import signal
from datetime import datetime

from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt import app

logger = get_logger(__name__)

# DXVK and VKD3D version mappings for PW_VULKAN_USE
VULKAN_VERSIONS = {
    "6": ("DXVK v.2.6.2", "VKD3D-PROTON v.2.14.1"),
    "2": ("DXVK v.2.4", "VKD3D-PROTON v.2.12"),
    "1": ("DXVK-Sarek", "VKD3D-Sarek"),
    "0": ("WINED3D", "OpenGL"),
}


def get_file_content(file_path: str, default: str = "") -> str:
    """Safely read file content."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except OSError as e:
        logger.debug(f"Failed to read {file_path}: {e}")
        return default


def get_os_info() -> str:
    """Get operating system info from /etc/os-release."""
    content = get_file_content("/etc/os-release")
    for line in content.split("\n"):
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return platform.platform()


def get_cpu_info() -> dict:
    """Get CPU information from /proc/cpuinfo."""
    info = {
        "model": _("Unknown"),
        "physical_cores": "0",
        "logical_cores": "0"
    }

    content = get_file_content("/proc/cpuinfo")
    if not content:
        return info

    model_names = set()
    cpu_cores = set()
    processors = 0

    for line in content.split("\n"):
        if line.startswith("model name"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                model_names.add(parts[1].strip())
        elif line.startswith("cpu cores"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                cpu_cores.add(parts[1].strip())
        elif line.startswith("processor"):
            processors += 1

    if model_names:
        info["model"] = list(model_names)[0]
    if cpu_cores:
        info["physical_cores"] = list(cpu_cores)[0]
    info["logical_cores"] = str(processors)

    return info


def get_ram_info() -> str:
    """Get RAM information from /proc/meminfo."""
    content = get_file_content("/proc/meminfo")
    if not content:
        return _("Unable to retrieve RAM info")

    mem_total = ""
    mem_available = ""
    swap_total = ""

    for line in content.split("\n"):
        if line.startswith("MemTotal:"):
            mem_total = line.split(":")[1].strip()
        elif line.startswith("MemAvailable:"):
            mem_available = line.split(":")[1].strip()
        elif line.startswith("SwapTotal:"):
            swap_total = line.split(":")[1].strip()

    return f"MemTotal: {mem_total}\nMemAvailable: {mem_available}\nSwapTotal: {swap_total}"


def get_desktop_environment() -> dict:
    """Get desktop environment information."""
    return {
        "session": os.environ.get("DESKTOP_SESSION", _("Unknown")),
        "current_desktop": os.environ.get("XDG_CURRENT_DESKTOP", _("Unknown")),
        "session_type": os.environ.get("XDG_SESSION_TYPE", _("Unknown"))
    }


def test_vulkan(portproton_path: str) -> str:
    """Test Vulkan using vkcube."""
    vkcube_path = os.path.join(portproton_path, "data", "plugins", "portable", "bin", "vkcube")

    if not os.path.exists(vkcube_path):
        vkcube_path = "vkcube"

    try:
        result = subprocess.run(
            [vkcube_path, "--c", "50"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        if result.returncode == 0:
            return _("Vulkan test PASSED")
        return _("Vulkan test FAILED") + f" (code: {result.returncode})"
    except FileNotFoundError:
        return _("vkcube not found, test skipped")
    except subprocess.TimeoutExpired:
        return _("Vulkan test timed out")
    except Exception as e:
        return _("Vulkan test error:") + f" {e}"


def get_locale_info() -> str:
    """Get locale information from environment."""
    import locale

    # Get locale settings using Python's locale module
    try:
        # Get the current locale settings
        current_locale = locale.getlocale()

        # Get all locale environment variables
        locale_vars = ["LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "LC_COLLATE",
                      "LC_TIME", "LC_NUMERIC", "LC_MONETARY", "LC_PAPER",
                      "LC_NAME", "LC_ADDRESS", "LC_TELEPHONE", "LC_MEASUREMENT",
                      "LC_IDENTIFICATION"]

        lines = []
        for var in locale_vars:
            value = os.environ.get(var, "")
            if value:
                lines.append(f"{var}={value}")

        # If no environment variables are set, fall back to locale.getlocale()
        if not lines and current_locale != (None, None):
            lines.append(f"Current locale: {current_locale}")

        return "\n".join(lines) if lines else _("No locale info available")
    except Exception:
        # Fallback to environment variables if Python locale module fails
        locale_vars = ["LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES"]
        lines = []
        for var in locale_vars:
            value = os.environ.get(var, "")
            if value:
                lines.append(f"{var}={value}")
        return "\n".join(lines) if lines else _("No locale info available")


def get_locale_available() -> str:
    """Get available locales matching current LANG."""
    try:
        lang = os.environ.get("LANG", "")
        if not lang:
            return ""

        # Extract base locale name (e.g., ru_RU from ru_RU.UTF-8)
        base_locale = lang.replace("-8", "").replace(".UTF", "").replace(".utf", "")

        # Use subprocess to get available locales
        # Note: Python doesn't have a direct way to list all available system locales
        # so we still need to use the locale command
        import subprocess
        result = subprocess.run(
            ["locale", "-a"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            locales = result.stdout.strip().split("\n")
            # Filter for matching locales (case insensitive)
            matching = [loc for loc in locales if base_locale.lower().replace(".utf-8", "") in loc.lower()]
            if matching:
                return "\n".join(matching)
    except Exception:
        pass
    return ""


def get_glibc_version() -> str:
    """Get GLIBC version."""
    try:
        result = subprocess.run(
            ["ldd", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            first_line = result.stdout.strip().split("\n")[0]
            # Extract version number (e.g., "ldd (GNU libc) 2.40" -> "2.40")
            match = re.search(r'(\d+\.\d+)', first_line)
            if match:
                return match.group(1)
    except Exception:
        pass
    return _("Unknown")

def get_runtime_status(portproton_path: str, exe_path: str | None = None) -> str:
    """Check if RUNTIME is enabled by checking PW_USE_RUNTIME environment variable."""
    # Get value from environment variable
    runtime_env = os.environ.get("PW_USE_RUNTIME")
    if runtime_env is not None:
        if str(runtime_env) == "1":
            return _("RUNTIME is enabled")
        return _("RUNTIME is disabled")

    # Default is disabled
    return _("RUNTIME is disabled")


def get_vulkan_use_info(portproton_path: str, exe_path: str | None = None) -> str:
    """Get PW_VULKAN_USE info with DXVK and VKD3D versions."""
    # Get value from environment variable
    pw_vulkan_use = os.environ.get("PW_VULKAN_USE")
    if pw_vulkan_use is not None:
        dxvk, vkd3d = VULKAN_VERSIONS.get(pw_vulkan_use, ("DXVK", "VKD3D-PROTON"))
        return f"PW_VULKAN_USE={pw_vulkan_use} - {dxvk}, {vkd3d}"

    # Default to 6
    pw_vulkan_use = "6"
    dxvk, vkd3d = VULKAN_VERSIONS.get(pw_vulkan_use, ("DXVK", "VKD3D-PROTON"))
    return f"PW_VULKAN_USE={pw_vulkan_use} - {dxvk}, {vkd3d}"


def get_wine_version(portproton_path: str, exe_path: str | None = None) -> str:
    """Get Wine/Proton version in use."""
    # Get value from environment variable
    wine_version = os.environ.get("PW_WINE_USE")
    if wine_version:
        return wine_version

    # Try to find from dist directory
    dist_path = os.path.join(portproton_path, "data", "dist")
    if os.path.exists(dist_path):
        try:
            versions = [d for d in os.listdir(dist_path)
                       if os.path.isdir(os.path.join(dist_path, d))]
            if versions:
                wine_version = versions[0]  # Return first found
        except OSError:
            pass

    return wine_version or _("Unknown")


def get_program_bit_depth(exe_path: str | None) -> str:
    """Get program bit depth (32 or 64 bit) from PE header."""
    if not exe_path or not os.path.exists(exe_path):
        return _("Unknown")

    try:
        with open(exe_path, 'rb') as f:
            # Read DOS header
            dos_header = f.read(64)
            if len(dos_header) < 64 or dos_header[:2] != b'MZ':
                return _("Not a valid PE file")

            # Get PE header offset
            pe_offset = int.from_bytes(dos_header[60:64], 'little')
            f.seek(pe_offset)

            # Read PE signature
            pe_sig = f.read(4)
            if pe_sig != b'PE\x00\x00':
                return _("Not a valid PE file")

            # Read machine type
            machine = f.read(2)
            machine_type = int.from_bytes(machine, 'little')

            if machine_type == 0x014c:  # IMAGE_FILE_MACHINE_I386
                return "32 bit"
            elif machine_type == 0x8664:  # IMAGE_FILE_MACHINE_AMD64
                return "64 bit"
            elif machine_type == 0x01c4:  # IMAGE_FILE_MACHINE_ARMNT
                return "32 bit (ARM)"
            elif machine_type == 0xAA64:  # IMAGE_FILE_MACHINE_ARM64
                return "64 bit (ARM64)"
            else:
                return _("Unknown") + f" (0x{machine_type:04x})"
    except Exception as e:
        logger.debug(f"Failed to detect bit depth: {e}")
        return _("Unknown")


def get_filesystem_info(exe_path: str | None, portproton_path: str) -> str:
    """Get filesystem info for game and PortProton directories."""
    lines = []

    def get_fs_type(path: str) -> str:
        """Get filesystem type for a given path."""
        try:
            result = subprocess.run(
                ["df", "-T", path],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                output_lines = result.stdout.strip().split("\n")
                if len(output_lines) >= 2:
                    # Second line contains: Filesystem Type ...
                    parts = output_lines[1].split()
                    if len(parts) >= 2:
                        return parts[1]
        except Exception:
            pass
        return _("Unknown")

    if exe_path:
        game_dir = os.path.dirname(exe_path)
        fs_type = get_fs_type(game_dir)
        lines.append(f"Filesystem {game_dir} - {fs_type}")

    fs_type = get_fs_type(portproton_path)
    lines.append(f"Filesystem {portproton_path} - {fs_type}")

    # Check tmp directory
    tmp_dir = f"/tmp/PortProton_{os.environ.get('USER', 'user')}"
    if os.path.exists(tmp_dir):
        fs_type = get_fs_type(tmp_dir)
        lines.append(f"Filesystem {tmp_dir} - {fs_type}")

    return "\n".join(lines) if lines else _("Unable to retrieve filesystem info")


def get_graphics_info_detailed() -> str:
    """Get detailed graphics card info using lspci, glxinfo, and inxi."""
    lines = []

    # lspci output
    try:
        result = subprocess.run(
            ["lspci", "-k"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0:
            lines.append("lspci -k | grep -EA3 VGA|3D|Display :")
            in_block = False
            block_lines = 0
            for line in result.stdout.split("\n"):
                if any(x in line for x in ["VGA", "3D", "Display"]):
                    in_block = True
                    block_lines = 0
                if in_block:
                    lines.append(line)
                    block_lines += 1
                    if block_lines >= 4:
                        in_block = False
    except Exception as e:
        lines.append(f"lspci error: {e}")

    lines.append("----")

    # glxinfo output
    try:
        result = subprocess.run(
            ["glxinfo"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0:
            keep_patterns = [
                "name of display",
                "display:",
                "direct rendering",
                "Memory info",
                "Dedicated video memory",
                "Total available memory",
                "Currently available",
                "OpenGL vendor",
                "OpenGL renderer",
                "OpenGL core profile version",
                "OpenGL core profile shading",
                "OpenGL core profile context",
                "OpenGL core profile profile",
                "OpenGL version string",
                "OpenGL shading language",
                "OpenGL context flags",
                "OpenGL profile mask",
                "OpenGL ES profile",
            ]
            for line in result.stdout.split("\n"):
                if any(p in line for p in keep_patterns):
                    lines.append(line)
    except FileNotFoundError:
        lines.append("glxinfo not found")
    except Exception as e:
        lines.append(f"glxinfo error: {e}")

    lines.append("-----")

    # inxi -G output
    try:
        result = subprocess.run(
            ["inxi", "-G"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0:
            lines.append("inxi -G:")
            lines.append(result.stdout.strip())
    except FileNotFoundError:
        lines.append("inxi not found")
    except Exception as e:
        lines.append(f"inxi error: {e}")

    # Screen resolution
    try:
        result = subprocess.run(
            ["xrandr", "--current"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if " connected" in line and "x" in line:
                    # Extract resolution
                    match = re.search(r'(\d+x\d+)', line)
                    if match:
                        lines.append(f"PW_SCREEN_RESOLUTION={match.group(1)}")
                    # Extract output name
                    output_name = line.split()[0]
                    if " primary " in line:
                        lines.append(f"PW_SCREEN_PRIMARY={output_name}")
                    break
    except Exception:
        pass

    return "\n".join(lines) if lines else _("Unable to retrieve graphics info")


def get_ram_info_detailed() -> str:
    """Get RAM info in free command format."""
    try:
        result = subprocess.run(
            ["free", "-m"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Fallback to /proc/meminfo
    return get_ram_info()


def get_ppdb_content(exe_path: str | None) -> str:
    """Get content of PPDB file for the executable."""
    if not exe_path:
        return ""

    ppdb_path = f"{exe_path}.ppdb"
    if not os.path.exists(ppdb_path):
        return ""

    content = get_file_content(ppdb_path)
    return content if content else ""


def get_user_overrides(portproton_path: str) -> str:
    """Get user override settings from user.conf."""
    user_conf = os.path.join(portproton_path, "data", "user.conf")
    if not os.path.exists(user_conf):
        return ""

    content = get_file_content(user_conf)
    if not content:
        return ""

    lines = []
    lines.append('# User overides db and var settings..."')

    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "bash" not in line.lower():
            # Convert to comment format for disabled settings
            if line.startswith("export "):
                lines.append(f'# {line}"')
            else:
                lines.append(f"export {line}")

    return "\n".join(lines)




def get_d3d_extras_status(portproton_path: str, exe_path: str | None = None) -> str:
    """Check if D3D_EXTRAS is enabled by checking PW_USE_D3D_EXTRAS environment variable."""
    # Get value from environment variable
    d3d_extras_env = os.environ.get("PW_USE_D3D_EXTRAS")
    if d3d_extras_env is not None:
        if d3d_extras_env == "1":
            return "D3D_EXTRAS - enabled"
        return "D3D_EXTRAS - disabled"

    # Default is disabled
    return "D3D_EXTRAS - disabled"


def get_winetricks_log(portproton_path: str, prefix_name: str = "DEFAULT") -> str:
    """Get winetricks log content for a prefix."""
    winetricks_log = os.path.join(
        portproton_path, "data", "prefixes", prefix_name, "winetricks.log"
    )
    if not os.path.exists(winetricks_log):
        # Try default location
        winetricks_log = os.path.join(
            portproton_path, "data", "prefixes", "DEFAULT", "winetricks.log"
        )

    content = get_file_content(winetricks_log)
    return content if content else ""


def get_prefix_name(exe_path: str | None) -> str:
    """Get prefix name from PPDB file."""
    if not exe_path:
        return "DEFAULT"

    ppdb_path = f"{exe_path}.ppdb"
    if os.path.exists(ppdb_path):
        content = get_file_content(ppdb_path)
        for line in content.split("\n"):
            if line.startswith("export PW_PREFIX_NAME="):
                return line.split("=", 1)[1].strip().strip('"')

    return "DEFAULT"




def generate_system_info(exe_path: str | None = None) -> str:
    """Generate system information part of debug log matching PortProton format."""
    portproton_path = get_portproton_location()
    if not portproton_path:
        return _("Error: PortProton location not found")

    lines = []

    # Header message
    lines.append(_("Debug log mode was launched and the log was successfully saved in the PortProton root directory"))
    lines.append(_("To diagnose the problem, copy the ENTIRE log to the site:") + " https://linux-gaming.ru/t/opisanie-kategorii-portproton-pomoshh/1642")
    lines.append("-" * 61)

    # PPQT version
    lines.append("PPQT version:")
    ppqt_version = app.get_version()
    lines.append(ppqt_version)
    lines.append("-" * 61)

    # Scripts version
    lines.append("Scripts version:")
    scripts_ver_file = os.path.join(portproton_path, "data", "tmp", "scripts_ver")
    scripts_version = get_file_content(scripts_ver_file, _("Unknown"))
    lines.append(scripts_version)
    lines.append("-" * 61)

    # RUNTIME status
    lines.append(get_runtime_status(portproton_path, exe_path))
    lines.append("-" * 61)

    # Debug for program
    if exe_path:
        lines.append("Debug for programm:")
        lines.append(exe_path)
        lines.append("-" * 61)

    # GLIBC version
    lines.append("GLIBC version:")
    lines.append(get_glibc_version())
    lines.append("-" * 61)

    # PW_VULKAN_USE with DXVK/VKD3D versions
    lines.append(get_vulkan_use_info(portproton_path, exe_path))
    lines.append("-" * 61)

    # Version WINE in use
    lines.append("Version WINE in use:")
    lines.append(get_wine_version(portproton_path, exe_path))
    lines.append("-" * 61)

    # Program bit depth
    lines.append("Program bit depth:")
    lines.append(get_program_bit_depth(exe_path))
    lines.append("-" * 61)

    # Date and time
    lines.append("Date and time of start debug for PortProton:")
    lines.append(datetime.now().strftime("%c %z"))
    lines.append("-" * 61)

    # Installation path
    lines.append("The installation path of the PortProton:")
    lines.append(portproton_path)
    lines.append("-" * 61)

    # Operating system
    lines.append("Operating system:")
    lines.append(get_os_info())
    lines.append("-" * 61)

    # Desktop environment
    lines.append("Desktop environment:")
    desktop = get_desktop_environment()
    lines.append(f"Desktop session: {desktop['session']}")
    lines.append(f"Current desktop: {desktop['current_desktop']}")
    lines.append(f"Session type: {desktop['session_type']}")
    lines.append("-" * 61)

    # Kernel
    lines.append("Kernel:")
    lines.append(platform.release())
    lines.append("-" * 61)

    # CPU
    lines.append("CPU:")
    cpu = get_cpu_info()
    lines.append(f"CPU physical cores: {cpu['physical_cores']}")
    lines.append(f"CPU logical cores: {cpu['logical_cores']}")
    lines.append(f"CPU model name: {cpu['model']}")
    lines.append("-" * 61)

    # RAM (using free format)
    lines.append("RAM:")
    lines.append(get_ram_info_detailed())
    lines.append("-" * 61)

    # Filesystem info
    lines.append(get_filesystem_info(exe_path, portproton_path))
    lines.append("-" * 61)

    # Graphic cards and drivers (detailed)
    lines.append("Graphic cards and drivers:")
    lines.append(get_graphics_info_detailed())
    lines.append("-" * 61)

    # Locale
    lines.append("locale:")
    lines.append(get_locale_info())
    lines.append("-" * 61)
    locale_avail = get_locale_available()
    if locale_avail:
        lines.append('locale -a | grep -i "$(locale | grep -e ^LANG= | sed s/LANG=// | sed  s/-8//)" :')
        lines.append(locale_avail)
        lines.append("-" * 61)

    # D3D_EXTRAS status
    lines.append(get_d3d_extras_status(portproton_path, exe_path))
    lines.append("-" * 61)

    # Winetricks log
    prefix_name = get_prefix_name(exe_path)
    winetricks_content = get_winetricks_log(portproton_path, prefix_name)
    if winetricks_content:
        lines.append("winetricks.log:")
        lines.append(winetricks_content)
        lines.append("-" * 61)

    # PPDB file content
    if exe_path:
        ppdb_content = get_ppdb_content(exe_path)
        if ppdb_content:
            lines.append(f"Use {exe_path}.ppdb db file:")
            lines.append(ppdb_content)
            lines.append("-" * 61)

    # User overrides
    user_overrides = get_user_overrides(portproton_path)
    if user_overrides:
        lines.append(user_overrides)
        lines.append("-" * 61)

    lines.append("-" * 61)

    # Safeguard: ensure all elements in lines are strings
    safe_lines = []
    for i, line in enumerate(lines):
        if line is None:
            logger.warning(f"None value found at index {i} in generate_system_info, replacing with empty string")
            safe_lines.append("")
        else:
            safe_lines.append(str(line))  # Convert to string to be extra safe

    return "\n".join(safe_lines)


def process_portproton_log(log_content: str) -> str:
    """
    Process PortProton log content by removing duplicates, anonymizing, and filtering noise.

    Args:
        log_content (str): The raw log content

    Returns:
        str: Fully processed log content
    """
    import re

    if not log_content:
        return log_content

    lines = log_content.split('\n')
    seen_lines = set()
    unique_lines = []

    # Track sections to identify repeating blocks
    section_start_patterns = [
        "export PW_BASE_PFX=",
        "WINEDLLOVERRIDES=",
        "Log WINE:",
    ]

    # Special handling for separator lines
    separator_pattern = r'^-{10,}$'  # Matches lines with 10 or more dashes

    # Process lines to remove duplicates
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Check if this line starts a new section
        is_section_start = any(line.startswith(pattern) for pattern in section_start_patterns)

        # Check if this is a separator line
        is_separator = bool(re.match(separator_pattern, line))

        if is_section_start:
            # If we see a repeated section start pattern, skip until next section
            if line in seen_lines:
                # Skip this entire section until we find another section start or end
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if any(next_line.startswith(pattern) for pattern in section_start_patterns):
                        break
                    j += 1
                i = j
                continue
            else:
                seen_lines.add(line)
                unique_lines.append(lines[i])
                i += 1
        elif is_separator:
            # For separator lines, we want to preserve them even if similar ones exist
            # This ensures that section dividers remain intact
            unique_lines.append(lines[i])
            i += 1
        else:
            # For regular lines, check if we've seen this exact line
            if line not in seen_lines:
                seen_lines.add(line)
                unique_lines.append(lines[i])
            i += 1

    # Join the unique lines
    deduplicated_content = '\n'.join(unique_lines)

    # Anonymize the content
    username = os.environ.get("USER", "")
    if username:
        deduplicated_content = deduplicated_content.replace(username, "xuser")
        deduplicated_content = deduplicated_content.replace(f"/home/{username}", "/home/xuser")

    # Filter noise
    filtered_lines = []
    for line in deduplicated_content.split("\n"):
        # Skip lines that match known noise patterns
        skip_line = False
        if any(x in line for x in [
            "kerberos",
            "ntlm",
            "HACK_does_openvr_work",
            "Uploading is disabled",
            "wine: RLIMIT_NICE is <= 20",
            "to be private",
            "UDEV monitor"
        ]):
            skip_line = True

        # Skip lines ending with .fx
        if not skip_line and line.rstrip().endswith('.fx'):
            skip_line = True

        if not skip_line:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)


class DebugLogManager:
    """Manages debug log creation with game launch and Wine output capture."""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.exe_path: str | None = None
        self.wine_output: list[str] = []
        self.is_running = False

    def start(self, exe_path: str, start_command: list[str]) -> bool:
        """Start game with PW_LOG=1 and capture output."""
        if self.is_running:
            return False

        self.exe_path = exe_path
        self.wine_output = []

        env_vars = os.environ.copy()
        env_vars["PW_LOG"] = "1"

        cmd = start_command + [exe_path]

        try:
            self.process = subprocess.Popen(
                cmd,
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid
            )
            self.is_running = True
            logger.info(f"Started debug session for {exe_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to start debug session: {e}")
            return False

    def stop(self) -> str | None:
        """Stop game and save debug log with captured Wine output."""
        if not self.is_running or self.process is None:
            return None

        # Read any remaining output
        try:
            if self.process.stdout:
                remaining = self.process.stdout.read()
                if remaining:
                    self.wine_output.append(remaining)
        except Exception as e:
            logger.debug(f"Error reading remaining output: {e}")

        # Terminate process with shorter timeout to prevent UI freezing
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            # Use a very short timeout to avoid blocking the UI
            try:
                self.process.wait(timeout=0.1)  # Very short timeout
            except subprocess.TimeoutExpired:
                # If process doesn't terminate quickly, force kill
                logger.debug("Process didn't terminate quickly, attempting SIGKILL")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                try:
                    self.process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    logger.warning("Process still hasn't terminated after SIGKILL")
        except Exception as e:
            logger.debug(f"Error terminating process: {e}")
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception:
                pass

        # Generate and save log
        log_file = self._save_log()

        self.process = None
        self.is_running = False

        return log_file


    def check_running(self) -> bool:
        """Check if process is still running."""
        if self.process is None:
            self.is_running = False
            return False

        poll = self.process.poll()
        if poll is not None:
            # Process finished
            self.is_running = False
            return False

        return True

    def _save_log(self) -> str | None:
        """Save complete debug log to file."""
        portproton_path = get_portproton_location()
        if not portproton_path:
            return None

        # Generate system info (without the Wine log part since bash script handles it)
        system_info = generate_system_info(self.exe_path)

        # Build complete log with system info
        lines = [system_info]

        # Read the content of the PortProton log file that was created by the bash script when PW_LOG=1
        # The log is always at portproton_location/PortProton.log
        portproton_log_content = ""

        if portproton_path:
            portproton_log_path = os.path.join(portproton_path, "PortProton.log")

            if os.path.exists(portproton_log_path):
                try:
                    with open(portproton_log_path, encoding="utf-8", errors="ignore") as f:
                        portproton_log_content = f.read()
                except OSError as e:
                    logger.debug(f"Could not read PortProton log file {portproton_log_path}: {e}")

        if portproton_log_content.strip():
            lines.append(portproton_log_content)

        log_content = "\n".join(lines)

        # Process the log content (remove duplicates, anonymize, filter noise)
        log_content = process_portproton_log(log_content)

        log_file = os.path.join(portproton_path, "PPQT.log")

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(log_content)
            logger.info(f"Debug log saved to {log_file}")
            return log_file
        except OSError as e:
            logger.error(f"Failed to save debug log: {e}")
            return None
