#!/bin/sh

set -eu

# Initialize variables
LOCAL_MODE=false
BRANCH="main"
REPO_URL="https://git.linux-gaming.ru/Boria138/PortProtonQt.git"

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --local|-l)
            LOCAL_MODE=true
            ;;
        --branch)
            if [ -n "${2:-}" ] && [ "${2#-}" = "$2" ]; then
                BRANCH="$2"
                shift
            else
                echo "Error: --branch requires an argument"
                exit 1
            fi
            ;;
        --repo)
            if [ -n "${2:-}" ] && [ "${2#-}" = "$2" ]; then
                REPO_URL="$2"
                shift
            else
                echo "Error: --repo requires an argument"
                exit 1
            fi
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

ARCH="$(uname -m)"
PACKAGE_BUILDER="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/make-aur-package.sh"
EXTRA_PACKAGES="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/get-debloated-pkgs.sh"

if [ "$LOCAL_MODE" = true ]; then
    echo "Using local PKGBUILD-git from repository..."
    PPQT_PKGBUILD=""
else
    echo "Using stable version of PortProtonQt from main branch..."
    PPQT_PKGBUILD="https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/build-aux/PKGBUILD"
fi

echo "Disable locale noextract..."
echo "---------------------------------------------------------------"
sed -i -E 's@[[:space:]]*usr/share/locale/\*@@g; s@[[:space:]]+@ @g; s@[[:space:]]+$@@' /etc/pacman.conf

echo "Installing dependencies..."
echo "---------------------------------------------------------------"
pacman-key --init
pacman -Syy --needed --noconfirm archlinux-keyring

echo "Installing AUR packages..."
echo "---------------------------------------------------------------"
wget --retry-connrefused --tries=30 "$PACKAGE_BUILDER" -O ./make-aur-package.sh
chmod +x ./make-aur-package.sh

./make-aur-package.sh --chaotic-aur icoextract
./make-aur-package.sh --chaotic-aur python-vdf

echo "Building PortProtonQt from PKGBUILD..."
echo "---------------------------------------------------------------"
if [ "$LOCAL_MODE" = true ]; then
    cp ../PKGBUILD-git ./PKGBUILD
else
    wget --retry-connrefused --tries=30 "$PPQT_PKGBUILD" -O ./PKGBUILD
fi
sed -i "s|source=(\"git+https://git.linux-gaming.ru/Boria138/PortProtonQt.git\")|source=(\"git+${REPO_URL}#branch=$BRANCH\")|" PKGBUILD
makepkg -si --noconfirm

echo "Installing debloated packages..."
echo "---------------------------------------------------------------"
wget --retry-connrefused --tries=30 "$EXTRA_PACKAGES" -O ./get-debloated-pkgs.sh
chmod +x ./get-debloated-pkgs.sh
./get-debloated-pkgs.sh --add-common --prefer-nano

if [ "$LOCAL_MODE" = true ]; then
    # For git version, we use portprotonqt-git
    pacman -Q portprotonqt-git | awk '{print $2}' | cut -d- -f1 > ~/version
else
    # For stable version, we use portprotonqt
    pacman -Q portprotonqt | awk '{print $2}' | cut -d- -f1 > ~/version
fi
