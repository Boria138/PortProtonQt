import os
import urllib.parse


def version_sort_key(entry):
    """
    Create a sort key for version-aware sorting of Proton/Wine entries.
    This sorts alphabetically first, but within entries with the same prefix (like "wine-"),
    it sorts by version number (descending).
    """
    if isinstance(entry, dict):
        # If entry is a dict (from JSON metadata), extract name
        name = entry.get('name', '')

        # Извлекаем имя файла из URL если нет имени
        url = entry.get('url', '')
        if url and not name:
            parsed_url = urllib.parse.urlparse(url)
            name = os.path.basename(parsed_url.path)
    else:
        # If entry is a string (directory name), use it directly
        name = entry

    # Remove extensions to get clean name
    for ext in ['.tar.gz', '.tar.xz', '.zip']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break

    # Determine the prefix (e.g., "wine", "GE-Proton", "proton") for grouping
    prefix = name.lower()
    version_part = name

    # Extract version part and prefix for different naming patterns
    if name.startswith('GE-Proton-'):
        # For "GE-Proton-9-25", prefix is "ge-proton", version is "9-25"
        parts = name.split('-', 2)
        if len(parts) >= 3:
            prefix = f"{parts[0]}-{parts[1]}".lower()  # "ge-proton"
            version_part = parts[2]  # "9-25"
        elif len(parts) >= 2:
            prefix = parts[0].lower()
            version_part = parts[1]
    elif name.lower().startswith('wine-'):
        # For "wine-8.0-rc1", prefix is "wine", version is "8.0-rc1"
        parts = name.split('-', 2)
        if len(parts) >= 2:
            prefix = parts[0].lower()  # "wine"
        if len(parts) >= 3:
            version_part = f"{parts[1]}-{parts[2]}"  # "8.0-rc1"
        elif len(parts) >= 2:
            version_part = parts[1]  # "8.0"
    elif name.lower().startswith('proton-'):
        # For "proton-8.0-rc1", prefix is "proton", version is "8.0-rc1"
        parts = name.split('-', 2)
        if len(parts) >= 2:
            prefix = parts[0].lower()  # "proton"
        if len(parts) >= 3:
            version_part = f"{parts[1]}-{parts[2]}"  # "8.0-rc1"
        elif len(parts) >= 2:
            version_part = parts[1]  # "8.0"
    else:
        # For entries without standard prefixes, use the first part as prefix
        if '-' in name:
            prefix = name.split('-', 1)[0].lower()
        else:
            prefix = name.lower()
        version_part = name

    # Handle different version formats - create a proper version tuple for descending sorting
    if '-' in version_part:
        # Split on '-' and convert numeric parts for proper sorting (inverted for descending)
        parts = version_part.split('-')
        numeric_parts = []
        for part in parts:
            try:
                # Convert to negative integer for descending numeric sorting
                numeric_parts.append(-int(part))
            except ValueError:
                # For non-numeric parts, use a large number to sort them after numeric parts
                # and append the lowercase string for consistent ordering
                numeric_parts.append(float('inf'))
                numeric_parts.append(part.lower())
        # Return tuple: (prefix for alphabetical sort, version for version sort, original name for tie-breaker)
        return (prefix, numeric_parts, name.lower())
    else:
        # If no dash in version part, try to parse as a simple version
        try:
            # Return tuple with prefix for alphabetical sort, version for version sort, and name for tie-breaker
            return (prefix, [-int(version_part)], name.lower())  # Negative for descending order
        except ValueError:
            # For non-numeric versions, use prefix for alphabetical sort and version part for secondary sort
            return (prefix, [float('inf'), version_part.lower()], name.lower())
