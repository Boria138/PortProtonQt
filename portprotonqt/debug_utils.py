import os
import platform
import re
import subprocess
import signal
from datetime import datetime
import psutil

from portprotonqt.config_utils import get_portproton_location
from portprotonqt.localization import _
from portprotonqt.logger import get_logger
from portprotonqt import app
import orjson

logger = get_logger(__name__)

# Cache for exported variables to avoid repeated subprocess calls
_exported_vars_cache: dict[str, dict[str, str]] = {}


def get_portproton_env(exe_path: str | None) -> dict[str, str]:
    """
    Get environment variables as they would be exported by PortProton.

    Sources var, user.conf, and .ppdb files in bash and returns the exported variables.
    This matches the actual behavior of start.sh when launching a game.

    Args:
        exe_path: Path to the executable, or None

    Returns:
        Dictionary of environment variable names to values
    """
    cache_key = exe_path or "__no_exe__"

    # Check cache first
    if cache_key in _exported_vars_cache:
        return _exported_vars_cache[cache_key]

    portproton_path = get_portproton_location()
    if not portproton_path:
        return {}

    scripts_path = os.path.join(portproton_path, "data", "scripts")
    var_file = os.path.join(scripts_path, "var")
    user_conf = os.path.join(portproton_path, "data", "user.conf")

    if not os.path.exists(var_file):
        logger.debug(f"var file not found: {var_file}")
        return {}

    # Build bash command to source files and output variables
    # We need to source in order: var -> user.conf -> .ppdb
    bash_script = f'source "{var_file}" 2>/dev/null; '

    if os.path.exists(user_conf):
        bash_script += f'source "{user_conf}" 2>/dev/null; '

    if exe_path:
        ppdb_file = f"{exe_path}.ppdb"
        if os.path.exists(ppdb_file):
            bash_script += f'source "{ppdb_file}" 2>/dev/null; '

    # Output all relevant variables (PW_, DXVK_, VKD3D_)
    bash_script += 'env | grep -E "^(PW_|DXVK_|VKD3D_)"'

    try:
        result = subprocess.run(
            ["bash", "-c", bash_script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )

        env_vars: dict[str, str] = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, val = line.split("=", 1)
                env_vars[key] = val

        # Cache the result
        _exported_vars_cache[cache_key] = env_vars
        return env_vars

    except Exception as e:
        logger.debug(f"Error getting portproton env: {e}")
        return {}


def clear_portproton_env_cache(exe_path: str | None = None):
    """Clear the exported variables cache."""
    if exe_path:
        _exported_vars_cache.pop(exe_path, None)
        _exported_vars_cache.pop("__no_exe__", None)
    else:
        _exported_vars_cache.clear()


def get_file_content(file_path: str, default: str = "") -> str:
    """Safely read file content."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except OSError as e:
        logger.debug(f"Failed to read {file_path}: {e}")
        return default


def get_os_info() -> str:
    """Get operating system info using platform module."""
    try:
        info = platform.freedesktop_os_release()
        return info.get("PRETTY_NAME", platform.platform())
    except Exception:
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
    """Get RAM information using psutil."""
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        mem_total = f"{mem.total // 1024} kB"
        mem_available = f"{mem.available // 1024} kB"
        swap_total = f"{swap.total // 1024} kB"

        return f"MemTotal: {mem_total}\nMemAvailable: {mem_available}\nSwapTotal: {swap_total}"
    except Exception:
        return _("Unable to retrieve RAM info")


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
    """Get locale information from environment, filling missing LC_* values from LANG if empty."""

    try:
        lang = os.environ.get("LANG", "")

        locale_vars = [
            "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "LC_COLLATE",
            "LC_TIME", "LC_NUMERIC", "LC_MONETARY", "LC_PAPER",
            "LC_NAME", "LC_ADDRESS", "LC_TELEPHONE", "LC_MEASUREMENT",
            "LC_IDENTIFICATION"
        ]

        lines = []
        for var in locale_vars:
            value = os.environ.get(var, "")
            if not value and var != "LC_ALL" and lang:
                value = lang
            lines.append(f"{var}={value}")

        return "\n".join(lines) if lines else "No locale info available"

    except Exception as e:
        return f"Error getting locale info: {e}"


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


def get_libc_version() -> str:
    """Get C library version using shell commands to properly detect musl/glibc."""
    try:
        # Run ldd --version to get libc information
        result = subprocess.run(['ldd', '--version'], capture_output=True, text=True, check=False)
        libc_version_output = result.stdout or result.stderr

        # Check if this is musl by looking for musl in the output
        if 'musl' in libc_version_output.lower():
            # Extract musl version from output like:
            # musl libc (x86_64)
            # Version 1.2.5
            lines = libc_version_output.split('\n')
            for line in lines:
                if 'version' in line.lower() and re.search(r'\d+\.\d+', line):
                    # Extract version number like "1.2.5" from "Version 1.2.5" or similar
                    version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', line)
                    if version_match:
                        return f"musl {version_match.group(1)}"
            return "musl (version unknown)"
        else:
            # This is glibc, extract version
            # Format might be like: "ldd (GNU libc) 2.40" or similar
            for line in libc_version_output.split('\n'):
                if 'ldd' in line.lower():
                    # Look for version number after the name
                    version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', line)
                    if version_match:
                        return f"glibc {version_match.group(1)}"

            # Alternative parsing for glibc if the above didn't work
            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', libc_version_output)
            if version_match:
                return f"glibc {version_match.group(1)}"

            return "glibc (version unknown)"
    except Exception:
        return "Unknown"


def get_runtime_status(portproton_path: str, exe_path: str | None = None) -> str:
    """Check if RUNTIME is enabled by checking PW_USE_RUNTIME variable."""
    env_vars = get_portproton_env(exe_path)
    runtime_val = env_vars.get("PW_USE_RUNTIME", "1")  # Default is 1 in var file

    if runtime_val == "1":
        return _("RUNTIME is enabled")
    return _("RUNTIME is disabled")


def get_vulkan_use_info(portproton_path: str, exe_path: str | None = None) -> str:
    """Get PW_VULKAN_USE info with DXVK and VKD3D versions."""
    env_vars = get_portproton_env(exe_path)
    pw_vulkan_use = env_vars.get("PW_VULKAN_USE", "6")

    # Get versions from var file based on PW_VULKAN_USE value
    if pw_vulkan_use == "6":
        dxvk = f"DXVK v.{env_vars.get('DXVK_NEW_VER', '')}"
        vkd3d = f"VKD3D-PROTON v.{env_vars.get('VKD3D_NEW_VER', '')}"
    elif pw_vulkan_use == "2":
        dxvk = f"DXVK v.{env_vars.get('DXVK_OLD_VER', '')}"
        vkd3d = f"VKD3D-PROTON v.{env_vars.get('VKD3D_OLD_VER', '')}"
    elif pw_vulkan_use == "1":
        dxvk = f"DXVK {env_vars.get('DXVK_SAREK_VER', 'Sarek')}"
        vkd3d = f"VKD3D {env_vars.get('VKD3D_SAREK_VER', 'Sarek')}"
    elif pw_vulkan_use == "0":
        dxvk = "WINED3D"
        vkd3d = "OpenGL"
    else:
        dxvk = "DXVK"
        vkd3d = "VKD3D-PROTON"

    return f"PW_VULKAN_USE={pw_vulkan_use} - {dxvk}, {vkd3d}"


def get_wine_version(portproton_path: str, exe_path: str | None = None) -> str:
    """Get Wine/Proton version in use."""
    env_vars = get_portproton_env(exe_path)
    return env_vars.get("PW_WINE_USE", _("Unknown"))


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

    def get_fs_type(path: str) -> str:
        """Get filesystem type using psutil, with lsblk fallback for fuseblk."""
        try:
            path = os.path.realpath(path)
            partitions = {p.mountpoint: (p.device, p.fstype) for p in psutil.disk_partitions(all=True)}

            # Find longest matching mount point
            device, fstype = None, None
            check_path = path
            while check_path != "/":
                if check_path in partitions:
                    device, fstype = partitions[check_path]
                    break
                check_path = os.path.dirname(check_path)

            if fstype is None:
                device, fstype = partitions.get("/", (None, _("Unknown")))

            # For fuseblk, get real fstype via lsblk
            if fstype == "fuseblk" and device:
                try:
                    result = subprocess.run(
                        ["lsblk", "-no", "FSTYPE", device],
                        capture_output=True, text=True, timeout=2, check=False
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        fstype = result.stdout.strip()
                except Exception:
                    pass

            return fstype
        except Exception:
            return _("Unknown")

    lines = []

    if exe_path:
        game_dir = os.path.dirname(exe_path)
        lines.append(f"Filesystem {game_dir} - {get_fs_type(game_dir)}")

    lines.append(f"Filesystem {portproton_path} - {get_fs_type(portproton_path)}")

    tmp_dir = f"/tmp/PortProton_{os.environ.get('USER', 'user')}"
    if os.path.exists(tmp_dir):
        lines.append(f"Filesystem {tmp_dir} - {get_fs_type(tmp_dir)}")

    return "\n".join(lines) if lines else _("Unable to retrieve filesystem info")


def get_graphics_info_detailed() -> str:
    """Get detailed graphics card info using lspci, glxinfo, and inxi."""
    lines = []

    # Parse lspci output to extract graphics devices info in the required format
    try:
        result = subprocess.run(
            ["lspci", "-k"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0:
            # Extract graphics devices and format them
            device_count = 1
            all_lines = result.stdout.split("\n")

            devices_info = []
            i = 0
            while i < len(all_lines):
                line = all_lines[i]
                if any(x in line for x in ["VGA", "3D", "Display"]):
                    # Parse the line to extract device info
                    parts = line.split(maxsplit=1)
                    device_desc = parts[1] if len(parts) > 1 else ""

                    # Extract driver info from the next few lines after the graphics line
                    driver_info = ""
                    # Look for driver info in the next 3 lines (usually appears right after the device line)
                    for j in range(i + 1, min(i + 4, len(all_lines))):
                        next_line = all_lines[j]
                        if "Kernel driver in use:" in next_line:
                            driver_part = next_line.split("Kernel driver in use:")[1].strip()
                            driver_info = driver_part
                            break

                    # Extract the GPU name in the format we want
                    # From: "VGA compatible controller: NVIDIA Corporation GP104 [GeForce GTX 1060 3GB] (rev a1)"
                    # To: "NVIDIA GP104 [GeForce GTX 1060 3GB]"
                    # Match pattern like "NVIDIA Corporation GP104 [GeForce GTX 1060 3GB]"
                    gpu_match = re.search(r'(NVIDIA Corporation )?([A-Z0-9]+\s*\[[^\]]+\])', device_desc)
                    if gpu_match:
                        # Get the GPU chip and model part
                        gpu_part = gpu_match.group(2)
                        formatted_device_desc = f"NVIDIA {gpu_part}"
                    else:
                        # Fallback to original if pattern doesn't match
                        formatted_device_desc = device_desc

                    device_line = f"Device-{device_count}: {formatted_device_desc}"
                    # Always add driver info if available
                    if driver_info:
                        device_line += f" driver: {driver_info}"

                    # Try to get the driver version from the system
                    try:
                        with open('/sys/module/nvidia/version') as f:
                            driver_version = f.read().strip()
                            device_line += f" v: {driver_version}"
                    except OSError:
                        # If we can't get it from /sys/module/nvidia/version, try glxinfo
                        try:
                            glxinfo_result = subprocess.run(
                                ["glxinfo"],
                                capture_output=True,
                                text=True,
                                timeout=10,
                                check=False
                            )
                            if glxinfo_result.returncode == 0:
                                for glx_line in glxinfo_result.stdout.split("\n"):
                                    if "OpenGL core profile version string:" in glx_line or \
                                       "OpenGL version string:" in glx_line:
                                        # Extract version number after NVIDIA
                                        version_match = re.search(r'NVIDIA\s+(\d+\.\d+(?:\.\d+)?)', glx_line)
                                        if version_match:
                                            version_num = version_match.group(1)
                                            device_line += f" v: {version_num}"
                                            break
                        except Exception:
                            pass

                    devices_info.append(device_line)
                    device_count += 1
                i += 1

            # Create the Graphics section with devices and display info
            graphics_lines = []
            for device_info in devices_info:
                graphics_lines.append(f"Graphics:  {device_info}")

            # Add display info to the Graphics section
            session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
            display_info = f"Display: {session_type}"
            if session_type == "wayland":
                display_info += f" server: {os.environ.get('WAYLAND_DISPLAY', 'N/A')}"
            else:
                display_info += f" server: {os.environ.get('DISPLAY', 'N/A')}"

            # X.Org version
            try:
                result = subprocess.run(
                    ["xdpyinfo"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "X.Org version" in line:
                            display_info += f" X.Org version: {line.split('X.Org version')[1].strip()}"
                            break
            except FileNotFoundError:
                pass

            # Add driver info to display line if available
            # We'll add a generic "driver: loaded: nvidia" type info if we can determine it
            if devices_info:
                # Extract driver from the first device if available
                first_device = devices_info[0]
                if "driver: " in first_device:
                    driver_part = first_device.split("driver: ")[1]
                    if " " in driver_part:
                        driver_name = driver_part.split(" ")[0]
                    else:
                        driver_name = driver_part
                    display_info += f" driver: loaded: {driver_name}"

            # Add indented display info after the device info
            if graphics_lines:
                # Add the display info as an indented line after the first device
                graphics_lines.append(f"           {display_info}")

            lines.extend(graphics_lines)

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

    # EGL info
    try:
        result = subprocess.run(
            ["eglinfo"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "EGL API version" in line or "EGL vendor" in line:
                    lines.append(line.strip())
                    break
    except FileNotFoundError:
        pass

    lines.append("-----")

    # Vulkan info
    try:
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0:
            lines.append("Vulkan:")
            for line in result.stdout.split("\n"):
                stripped = line.strip()
                if stripped.startswith("GPU") or "deviceName" in line or "driverName" in line:
                    lines.append(line.rstrip())
    except FileNotFoundError:
        lines.append("vulkaninfo not found")

    # Vulkan cube test
    try:
        portproton_path = get_portproton_location()
        if portproton_path:
            vkcube_path = os.path.join(portproton_path, "data", "plugins", "portable", "bin", "vkcube")
        else:
            vkcube_path = "vkcube"

        if not os.path.exists(vkcube_path):
            vkcube_path = "vkcube"  # Fallback to system-wide

        vkcube_result = subprocess.run(
            [vkcube_path, "--c", "10"],  # Run for 10 frames to get quick result
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        if vkcube_result.returncode == 0:
            lines.append("Vulkan Cube Test: PASSED")
        else:
            lines.append(f"Vulkan Cube Test: FAILED (code: {vkcube_result.returncode})")
    except FileNotFoundError:
        lines.append("Vulkan Cube Test: vkcube not found, test skipped")
    except subprocess.TimeoutExpired:
        lines.append("Vulkan Cube Test: timed out")
    except Exception as e:
        lines.append(f"Vulkan Cube Test: error: {e}")

    # Screen resolution info is obtained separately from PortProton variables

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
    lines.append('# User overrides db and var settings...')

    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "bash" not in line.lower():
            # Properly format the line
            if line.startswith("export "):
                lines.append(line)
            else:
                lines.append(f"export {line}")

    return "\n".join(lines)


def get_screen_info(portproton_path: str, exe_path: str | None = None) -> tuple[str, str]:
    """Get screen resolution and primary info using xrandr or hyprctl."""
    resolution = ""
    primary = ""

    try:
        # Try to get resolution from xrandr
        result = subprocess.run(['xrandr', '--current'], capture_output=True, text=True)

        if result.returncode == 0:
            xrandr_output = result.stdout

            # Extract resolution and primary screen from xrandr output
            for line in xrandr_output.splitlines():
                if 'primary' in line:
                    # Extract resolution pattern like "1920x1080"
                    res_match = re.search(r'^.*primary.* ([0-9]+x[0-9]+).*$', line)
                    if res_match:
                        resolution = res_match.group(1)

                    # Extract primary screen name
                    parts = line.split()
                    if len(parts) > 0:
                        primary = parts[0]
                    break  # Only get the first primary display
    except (subprocess.SubprocessError, FileNotFoundError):
        pass  # If xrandr fails, continue to try hyprctl

    # If resolution wasn't found from xrandr, try hyprctl
    if not resolution or 'x' not in resolution:
        try:
            # Check if hyprctl is available
            if subprocess.run(['which', 'hyprctl'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                result = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True)

                if result.returncode == 0:
                    try:
                        # Parse with orjson
                        monitors_data = orjson.loads(result.stdout)

                        # Find the focused monitor
                        for monitor in monitors_data:
                            if monitor.get('focused', False):
                                width = monitor.get('width')
                                height = monitor.get('height')
                                name = monitor.get('name')

                                if width and height:
                                    resolution = f"{width}x{height}"

                                if name:
                                    primary = name

                                break
                    except (orjson.JSONDecodeError, ValueError):
                        pass
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Default to 1920x1080 if no resolution found
    if not resolution or 'x' not in resolution:
        resolution = "1920x1080"

    return f"PW_SCREEN_RESOLUTION={resolution}", f"PW_SCREEN_PRIMARY={primary}"


def get_d3d_extras_status(portproton_path: str, exe_path: str | None = None) -> str:
    """Check if D3D_EXTRAS is enabled by checking PW_USE_D3D_EXTRAS variable."""
    env_vars = get_portproton_env(exe_path)
    d3d_extras_val = env_vars.get("PW_USE_D3D_EXTRAS", "1")  # Default is 1 in var file

    if d3d_extras_val == "1":
        return "D3D_EXTRAS - enabled"
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
    if not content:
        return ""

    # Apply filtering similar to bash script: remove d3dcomp* and d3dx* lines
    lines = content.split('\n')
    filtered_lines = []
    for line in lines:
        # Skip lines that start with d3dcomp or d3dx
        if not (line.startswith('d3dcomp') or line.startswith('d3dx')):
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)


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

    # C library version (glibc or musl)
    lines.append("libc version:")
    lines.append(get_libc_version())
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

    # Screen resolution and primary info from system
    screen_resolution, screen_primary = get_screen_info(portproton_path, exe_path)
    if screen_resolution:
        lines.append(screen_resolution)

    if screen_primary:
        lines.append(screen_primary)
    lines.append("-" * 61)

    # Locale
    lines.append("locale:")
    lines.append(get_locale_info())
    lines.append("-" * 61)
    locale_avail = get_locale_available()
    if locale_avail:
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
        deduplicated_content = deduplicated_content.replace(f"/home/{username}", "/home/xuser")
        deduplicated_content = deduplicated_content.replace(f"PortProton_{username}", "PortProton_xuser")

    # Filter noise
    filtered_lines = []
    for line in deduplicated_content.split("\n"):
        # Skip lines that match known noise patterns
        skip_line = False
        if any(x in line.lower() for x in [
            "kerberos",
            "ntlm",
            "hack_does_openvr_work",
            "uploading is disabled",
            "wine: rlimit_nice is <= 20",
            "are assuming",
            "to be private",
            "udev monitor"
        ]):
            skip_line = True

        # Skip lines ending with .fx
        if not skip_line and line.rstrip().lower().endswith('.fx'):
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
