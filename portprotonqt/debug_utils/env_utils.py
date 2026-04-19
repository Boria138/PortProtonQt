"""Environment variables and configuration utilities."""

import os
import subprocess

from portprotonqt.logger import get_logger
from portprotonqt.config_utils import get_portproton_location, get_portproton_scripts_path

logger = get_logger(__name__)


def get_file_content(file_path: str, default: str = "") -> str:
    """Safely read file content, removing comments and empty lines."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line.startswith('#') and stripped_line:
                filtered_lines.append(line)
        content = '\n'.join(filtered_lines)

        return content.strip()
    except OSError as e:
        logger.debug("Failed to read %s: %s", file_path, e)
        return default


def get_portproton_env(exe_path: str | None) -> dict[str, str]:
    """Get environment variables as exported by PortProton.

    Priority order:
    1. /tmp/PortProton_$USER/var.log (runtime variables from active session)
    2. var file + user.conf + .ppdb (static configuration)
    """
    env_vars: dict[str, str] = {}

    # Priority 1: Read from /tmp/PortProton_$USER/var.log (most authoritative)
    user = os.getenv('USER', 'unknown')
    var_log_path = f'/tmp/PortProton_{user}/var.log'

    if os.path.exists(var_log_path):
        logger.debug("Reading variables from %s", var_log_path)
        try:
            with open(var_log_path, encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for line in content.split('\n'):
                line = line.strip()
                if '=' in line:
                    key, val = line.split('=', 1)
                    env_vars[key.strip()] = val.strip()

            logger.debug("Found %d variables from var.log", len(env_vars))
            return env_vars
        except Exception as e:
            logger.debug("Error reading var.log: %s", e)

    # Priority 2: Read from static configuration files
    portproton_path = get_portproton_location()
    if not portproton_path:
        return {}

    scripts_path = get_portproton_scripts_path()
    if not scripts_path:
        return {}

    var_file = os.path.join(scripts_path, "var")
    user_conf = os.path.join(portproton_path, "data", "user.conf")

    if not os.path.exists(var_file):
        logger.debug("var file not found: %s", var_file)
        return {}

    bash_script = f'source "{var_file}" 2>/dev/null; '

    if os.path.exists(user_conf):
        bash_script += f'source "{user_conf}" 2>/dev/null; '

    if exe_path:
        ppdb_file = f"{exe_path}.ppdb"
        if os.path.exists(ppdb_file):
            logger.debug("Found .ppdb file: %s", ppdb_file)
            bash_script += f'source "{ppdb_file}" 2>/dev/null; '
        else:
            logger.debug(".ppdb file not found: %s", ppdb_file)

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

        logger.debug("Environment variables found: %s", env_vars)
        return env_vars

    except Exception as e:
        logger.debug("Error getting portproton env: %s", e)
        return {}


def get_runtime_status(
    portproton_path: str,
    exe_path: str | None = None,
    start_cmd: list[str] | None = None
) -> str:
    """Check if RUNTIME is enabled and detect Flatpak usage."""
    env_vars = get_portproton_env(exe_path)
    runtime_val = env_vars.get("PW_USE_RUNTIME", "1")

    is_flatpak = False
    if start_cmd:
        start_cmd_str = " ".join(start_cmd)
        is_flatpak = "flatpak run" in start_cmd_str

    if is_flatpak:
        return "FLATPAK in used"
    elif runtime_val == "0":
        return "RUNTIME is disabled"
    else:
        return "RUNTIME is enabled"


def get_vulkan_use_info(portproton_path: str, exe_path: str | None = None) -> str:
    """Get PW_VULKAN_USE info with DXVK and VKD3D versions."""
    env_vars = get_portproton_env(exe_path)
    pw_vulkan_use = env_vars.get("PW_VULKAN_USE")

    if pw_vulkan_use is None:
        return "PW_VULKAN_USE: Variable not found (stub)"
    elif pw_vulkan_use == "6":
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
    return env_vars.get("PW_WINE_USE", "Unknown")


def get_d3d_extras_status(portproton_path: str, exe_path: str | None = None) -> str:
    """Check if D3D_EXTRAS is enabled."""
    env_vars = get_portproton_env(exe_path)
    d3d_extras_val = env_vars.get("PW_USE_D3D_EXTRAS", "1")

    if d3d_extras_val == "1":
        return "D3D_EXTRAS - enabled"
    return "D3D_EXTRAS - disabled"
