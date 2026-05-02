import os
import re
import urllib.parse

def version_sort_key(entry):
    """
    Create a sort key for version-aware sorting of Proton/Wine entries.
    Sorts by prefix alphabetically, then by version number (descending - newer first).
    """
    if isinstance(entry, dict):
        name = entry.get('name', '')
        url = entry.get('url', '')
        if url and not name:
            parsed_url = urllib.parse.urlparse(url)
            name = os.path.basename(parsed_url.path)
    else:
        name = entry

    # Remove extensions
    for ext in ['.tar.gz', '.tar.xz', '.zip']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break

    # Normalize the name
    name_lower = name.lower().strip()

    # Replace underscores and spaces with hyphens for consistency
    normalized = name_lower.replace('_', '-').replace(' ', '-')
    if normalized == 'proton-lg':
        proton_lg_priority = 0
    elif normalized.startswith('proton-lg-'):
        proton_lg_priority = 1
    elif normalized == 'wine-lg':
        proton_lg_priority = 2
    elif normalized.startswith('wine-lg-'):
        proton_lg_priority = 3
    else:
        proton_lg_priority = 4

    # Extract all numeric sequences and text parts
    tokens = re.findall(r'\d+|\D+', normalized)

    # Find where the version numbers start
    # Usually after the first text token(s)
    prefix_parts = []
    version_parts = []
    first_number_index = -1

    # Find the first number token
    for i, token in enumerate(tokens):
        if token.isdigit():
            first_number_index = i
            break

    # If we found a number, everything before it is prefix
    if first_number_index > 0:
        for i in range(first_number_index):
            prefix_parts.append(tokens[i].strip('-'))

        # Everything from first number onwards is version
        for i in range(first_number_index, len(tokens)):
            token = tokens[i]
            if token.isdigit():
                # Negative for descending order (higher versions first)
                version_parts.append((0, -int(token)))
            else:
                # Part of version string (like "rc", "staging", etc.)
                cleaned = token.strip('-')
                if cleaned:
                    version_parts.append((1, cleaned))
    else:
        # No numbers found, treat entire thing as prefix
        prefix_parts = [t.strip('-') for t in tokens if t.strip('-')]

    # Clean up prefix
    prefix = '-'.join(p for p in prefix_parts if p).strip('-')

    # If no prefix found, use first token
    if not prefix:
        prefix = tokens[0] if tokens else normalized

    # If no version parts found, add a default
    if not version_parts:
        version_parts = [(0, 0)]

    # Return sort key: (prefix for grouping, version parts for version sorting, normalized name)
    # Use normalized name for tie-breaking to avoid issues with spaces vs underscores
    return (proton_lg_priority, prefix, version_parts, normalized)
