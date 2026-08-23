#!/bin/sh

set -eu

REPOSITORY="Linux-Gaming/PortProtonQt"
SERVER="https://git.linux-gaming.ru"
GITHUB_REPOSITORY="linux-gaming-ru/PortProtonQt"

command -v curl >/dev/null 2>&1 || {
    echo "PortProtonQt installer requires curl." >&2
    exit 1
}
command -v mktemp >/dev/null 2>&1 || {
    echo "PortProtonQt installer requires mktemp." >&2
    exit 1
}

ARCH=$(uname -m)
case "$ARCH" in
    amd64) ARCH="x86_64" ;;
    arm64) ARCH="aarch64" ;;
esac

GITEA_API="${SERVER}/api/v1/repos/${REPOSITORY}/releases/latest"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPOSITORY}/releases/latest"
APPIMAGE_PATH=$(mktemp "${TMPDIR:-/tmp}/portprotonqt.XXXXXX.AppImage")
DOWNLOADED=false

trap 'rm -f "$APPIMAGE_PATH"' EXIT HUP INT TERM

for RELEASE_API in "$GITEA_API" "$GITHUB_API"; do
    APPIMAGE_URL=$(curl -fsSL "$RELEASE_API" |
        tr ',' '\n' |
        sed -n 's/.*"browser_download_url"[[:space:]]*:[[:space:]]*"\([^"]*\.AppImage\)".*/\1/p' |
        grep -- "-${ARCH}\.AppImage$" |
        head -n 1 || true)
    if [ -z "$APPIMAGE_URL" ]; then
        continue
    fi
    echo "Downloading PortProtonQt AppImage from ${APPIMAGE_URL}..."
    if curl -fL --progress-bar "$APPIMAGE_URL" -o "$APPIMAGE_PATH"; then
        DOWNLOADED=true
        break
    fi
done

if [ "$DOWNLOADED" != true ]; then
    echo "Failed to download PortProtonQt AppImage for ${ARCH}." >&2
    exit 1
fi

chmod 755 "$APPIMAGE_PATH"

if ! PORTPROTONQT_INTEGRATE_APPIMAGE=1 "$APPIMAGE_PATH"; then
    echo "Failed to integrate PortProtonQt AppImage." >&2
    exit 1
fi

echo "PortProtonQt was installed and integrated."
