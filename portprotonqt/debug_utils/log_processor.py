"""PortProton log processing utilities."""

import os
import re

from portprotonqt.debug_utils.env_utils import _normalize_dist_name


def _strip_pw_wine_use_path(line: str) -> str:
    match = re.match(r'^(\s*(?:export\s+)?PW_WINE_USE=)(["\']?)(/[^"\']+)(\2.*)$', line)
    if not match:
        return line

    prefix, quote, wine_path, suffix = match.groups()
    wine_name = os.path.basename(wine_path.rstrip(os.sep)) or wine_path
    return f"{prefix}{quote}{_normalize_dist_name(wine_name)}{suffix}"


def process_portproton_log(log_content: str) -> str:
    """Process PortProton log: remove duplicates, anonymize, filter noise."""
    if not log_content:
        return log_content

    lines = log_content.split('\n')
    seen_lines: set[str] = set()
    unique_lines: list[str] = []

    section_start_patterns = [
        "export PW_BASE_PFX=",
        "WINEDLLOVERRIDES=",
        "Log WINE:",
    ]

    separator_pattern = r'^-{10,}$'

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        is_section_start = any(
            line.startswith(pattern) for pattern in section_start_patterns
        )
        is_separator = bool(re.match(separator_pattern, line))

        if is_section_start:
            if line in seen_lines:
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if any(
                        next_line.startswith(pattern)
                        for pattern in section_start_patterns
                    ):
                        break
                    j += 1
                i = j
                continue
            else:
                seen_lines.add(line)
                unique_lines.append(lines[i])
                i += 1
        elif is_separator:
            unique_lines.append(lines[i])
            i += 1
        else:
            if line not in seen_lines:
                seen_lines.add(line)
                unique_lines.append(lines[i])
            i += 1

    deduplicated_content = '\n'.join(unique_lines)

    username = os.environ.get("USER", "")
    if username:
        deduplicated_content = deduplicated_content.replace(
            f"/home/{username}", "/home/xuser"
        )
        deduplicated_content = deduplicated_content.replace(
            f"PortProton_{username}", "PortProton_xuser"
        )
        deduplicated_content = deduplicated_content.replace(
            f"#Author: {username}", "#Author: xuser"
        )
        deduplicated_content = deduplicated_content.replace(
            f"/run/media/{username}", "/run/media/xuser"
        )
        deduplicated_content = deduplicated_content.replace(
            f"/media/{username}", "/media/xuser"
        )

    is_flatpak_used = "FLATPAK in used" in deduplicated_content

    filtered_lines = []
    for line in deduplicated_content.split("\n"):
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

        if not skip_line and line.rstrip().lower().endswith('.fx'):
            skip_line = True

        if not skip_line and is_flatpak_used:
            stripped_line = line.strip()
            if (
                stripped_line.startswith("PW_USE_RUNTIME=") or
                stripped_line.startswith("export PW_USE_RUNTIME=")
            ):
                skip_line = True

        if not skip_line:
            filtered_lines.append(_strip_pw_wine_use_path(line))

    return '\n'.join(filtered_lines)
