import argparse
import os
import re
from pathlib import Path

from portprotonqt.steam_api import get_steam_home


def parse_args():
    """
    Parses command-line arguments.
    """
    parser = argparse.ArgumentParser(description="PortProtonQt CLI")
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Launch the application in fullscreen mode and save this setting"
    )
    parser.add_argument(
        "--resolution",
        type=str,
        metavar="WIDTHxHEIGHT",
        help="Launch the application with a specific resolution (e.g., 1920x1080)"
    )
    parser.add_argument(
        "--debug-level",
        choices=['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='NOTSET',
        help="Set logging level (ALL for all messages, default: NOTSET)"
    )
    parser.add_argument(
        "--force-muvm",
        action="store_true",
        help="Force running the application under muvm even if not on Apple Silicon"
    )
    parser.add_argument(
        "--add-steam-compat-tool",
        action="store_true",
        help="Add PortProtonQt as a Steam compatibility tool if not already installed"
    )
    # Add positional argument to accept exe files or portproton:// URLs
    parser.add_argument(
        'file_or_url',
        nargs='?',
        help="Executable file path or portproton:// URL"
    )
    return parser.parse_args()


def add_steam_compat_tool() -> bool:
    """
    Add PortProtonQt as a Steam compatibility tool.

    Creates the following files in Steam's compatibilitytools.d directory:
    - compatibilitytool.vdf
    - toolmanifest.vdf
    - portproton (launch script)

    Returns:
        True if successful, False otherwise
    """
    steam_home = get_steam_home()
    if not steam_home:
        print("Steam directory not found")
        return False

    compat_tools_dir = steam_home / "compatibilitytools.d" / "PortProtonQt"
    system_compat_dir = Path("/usr/share/steam/compatibilitytools.d/PortProtonQt")

    # Check if already installed in user or system directory
    if compat_tools_dir.exists():
        print("PortProtonQt is already installed as a Steam compatibility tool")
        return True

    if system_compat_dir.exists():
        print("PortProtonQt is already installed as a Steam compatibility tool (system-wide)")
        return True

    # Create directory structure
    compat_tools_dir.mkdir(parents=True, exist_ok=True)

    # Create compatibilitytool.vdf
    compatibilitytool_vdf = compat_tools_dir / "compatibilitytool.vdf"
    compatibilitytool_vdf.write_text('''"compatibilitytools"
{
	"compat_tools"
	{
		"PortProtonQt"
		{
			"install_path" "."
			"display_name" "PortProtonQt"
			"from_oslist" "windows"
			"to_oslist" "linux"
			"Priority" "75"
		}
	}
}
''')

    # Create toolmanifest.vdf
    toolmanifest_vdf = compat_tools_dir / "toolmanifest.vdf"
    toolmanifest_vdf.write_text('''"manifest"
{
	"commandline" "/portproton"
}
''')

    # Create portproton launch script
    portproton_script = compat_tools_dir / "portproton"
    portproton_script.write_text('''#!/usr/bin/env bash

# Remove Steam Runtime libraries
unset LD_LIBRARY_PATH
unset LD_PRELOAD

# Set Steam compatibility mode flag (unless GUI mode is requested)
if [[ ! -n "$PPQT_GUI" ]]; then
    export STEAM_COMPAT=1
fi

exe_name="$(basename "$1")"
exe_dir="$(dirname "$1")"

# Ignore specific executables
if [[ "$exe_name" == "iscriptevaluator.exe" ]] || \\
   [[ "$exe_name" == "d3ddriverquery64.exe" ]]; then
    exit 0
fi

# Copy PPDB file from steam_scripts to exe directory if it exists
# Steam passes the appid via SteamAppId environment variable
if [[ -n "$SteamAppId" ]]; then
    # Get PortProton directory from config file or Flatpak default
    portproton_dir=""
    config_file="$HOME/.config/PortProton.conf"

    if [[ -f "$config_file" ]]; then
        portproton_dir="$(cat "$config_file" | tr -d '\\n')"
    fi

    if [[ -z "$portproton_dir" ]] || [[ ! -d "$portproton_dir" ]]; then
        # Fallback to Flatpak default
        portproton_dir="$HOME/.var/app/ru.linux_gaming.PortProton"
    fi

    ppdb_source="$portproton_dir/steam_scripts/${SteamAppId}.exe.ppdb"
    ppdb_dest="$exe_dir/${exe_name}.ppdb"

    if [[ -f "$ppdb_source" ]]; then
        cp "$ppdb_source" "$ppdb_dest"
        echo "Copied PPDB from $ppdb_source to $ppdb_dest"
    fi
fi

# Activate virtual environment if available
if [[ -n "$PPQT_VENV_PATH" ]]; then
    cd "$PPQT_VENV_PATH" || exit 1
    source .venv/bin/activate || exit 1
fi

# Use AppImage if specified, otherwise use portprotonqt from PATH
if [[ -n "$PPQT_BIN_PATH" ]]; then
    "$PPQT_BIN_PATH" --debug-level INFO "$@"
else
    portprotonqt --debug-level INFO "$@"
fi
''')

    # Make script executable
    os.chmod(portproton_script, 0o755)

    print("PortProtonQt has been added as a Steam compatibility tool")
    print(f"Installed to: {compat_tools_dir}")
    print("Restart Steam to use the new compatibility tool")

    return True


def is_portproton_url(url: str) -> bool:
    """Check if the given URL is a portproton:// URL.

    Args:
        url: The URL to check

    Returns:
        True if it's a portproton:// URL, False otherwise
    """
    return url.lower().startswith('portproton://')


def is_exe_file(path: str) -> bool:
    """Check if the given path is an exe file.

    Args:
        path: The path to check

    Returns:
        True if it's an exe file, False otherwise
    """
    return path.lower().endswith('.exe') and os.path.isfile(path)


def parse_portproton_url(url: str) -> str | None:
    """Parse a portproton:// URL to extract the full download URL.

    Expected format: portproton://https//ppdb.linux-gaming.ru/api/games/130127/ppdb/download

    Args:
        url: The portproton:// URL to parse

    Returns:
        The full download URL if parsing is successful, None otherwise
    """
    # Remove the portproton:// prefix
    if not url.lower().startswith('portproton://'):
        return None

    # Extract the actual URL part after portproton://
    actual_url = url[13:]  # Length of 'portproton://'

    # Check if the URL starts with 'https//' (without colon) and fix it
    if actual_url.startswith('https//'):
        # Replace 'https//' with 'https://'
        corrected_url = 'https://' + actual_url[7:]  # Remove 'https//' (7 chars) and add '://'
    elif actual_url.startswith('http//'):
        # Replace 'http//' with 'http://'
        corrected_url = 'http://' + actual_url[6:]  # Remove 'http//' (6 chars) and add '://'
    elif not actual_url.startswith(('http://', 'https://')):
        # Add the protocol if it's missing
        corrected_url = 'https://' + actual_url
    else:
        corrected_url = actual_url

    return corrected_url


def parse_resolution(resolution: str) -> tuple[int, int] | None:
    """Parse a resolution string in the format WIDTHxHEIGHT.

    Args:
        resolution: Resolution string (e.g., "1920x1080")

    Returns:
        Tuple of (width, height) if valid, None otherwise
    """
    try:
        # Match pattern like "1920x1080"
        match = re.match(r'^(\d+)x(\d+)$', resolution, re.IGNORECASE)
        if not match:
            return None

        width = int(match.group(1))
        height = int(match.group(2))

        # Validate reasonable resolution bounds
        if width < 320 or height < 200:
            return None
        if width > 7680 or height > 4320:
            return None

        return (width, height)
    except (ValueError, AttributeError):
        return None
