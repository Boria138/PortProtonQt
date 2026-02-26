import argparse
import os


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
    # Add positional argument to accept exe files or portproton:// URLs
    parser.add_argument(
        'file_or_url',
        nargs='?',
        help="Executable file path or portproton:// URL"
    )
    return parser.parse_args()


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
