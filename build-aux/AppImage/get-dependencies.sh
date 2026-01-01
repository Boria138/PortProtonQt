#!/bin/sh

set -eu

# Determine if git mode is enabled based on the first argument
if [ "${1:-}" = "--git" ] || [ "${1:-}" = "-g" ]; then
    GIT_MODE=true
else
    GIT_MODE=false
fi

ARCH="$(uname -m)"
PACKAGE_BUILDER="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/make-aur-package.sh"
EXTRA_PACKAGES="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/get-debloated-pkgs.sh"

if [ "$GIT_MODE" = true ]; then
    echo "Using git version of PortProtonQt..."
    PPQT_PKGBUILD="https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/build-aux/PKGBUILD-git"
else
    echo "Using stable version of PortProtonQt..."
    PPQT_PKGBUILD="https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/build-aux/PKGBUILD"
fi


echo "Installing dependencies..."
echo "---------------------------------------------------------------"
pacman-key --init
pacman -Syy --needed --noconfirm archlinux-keyring qt6-wayland

echo "Installing debloated packages..."
echo "---------------------------------------------------------------"
wget --retry-connrefused --tries=30 "$EXTRA_PACKAGES" -O ./get-debloated-pkgs.sh
chmod +x ./get-debloated-pkgs.sh
./get-debloated-pkgs.sh --add-common --prefer-nano

echo "Installing AUR packages..."
echo "---------------------------------------------------------------"
wget --retry-connrefused --tries=30 "$PACKAGE_BUILDER" -O ./make-aur-package.sh
chmod +x ./make-aur-package.sh

./make-aur-package.sh --chaotic-aur icoextract
./make-aur-package.sh --chaotic-aur python-vdf

echo "Building PortProtonQt from PKGBUILD..."
echo "---------------------------------------------------------------"
wget --retry-connrefused --tries=30 "$PPQT_PKGBUILD" -O ./PKGBUILD
makepkg -si --noconfirm

if [ "$GIT_MODE" = true ]; then
    # For git version, we use portprotonqt-git
    pacman -Q portprotonqt-git | awk '{print $2}' | cut -d- -f1 > ~/version
else
    # For stable version, we use portprotonqt
    pacman -Q portprotonqt | awk '{print $2}' | cut -d- -f1 > ~/version
fi
