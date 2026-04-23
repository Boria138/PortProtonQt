#!/bin/sh

set -eu

# Initialize variables
LOCAL_MODE=false
BRANCH="main"
REPO_URL="https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt.git"

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
EXTRA_PACKAGES="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/get-debloated-pkgs.sh"

if [ "$LOCAL_MODE" = true ]; then
    echo "Using local PKGBUILD-git from repository..."
    PPQT_PKGBUILD=""
else
    echo "Using stable version of PortProtonQt from main branch..."
    PPQT_PKGBUILD="https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt/raw/branch/main/build-aux/PKGBUILD"
fi

echo "Tweak makepkg..."
echo "---------------------------------------------------------------"
# Disable creating debug packages
sed -i 's/OPTIONS=(.*)/OPTIONS=(strip docs !libtool !staticlibs emptydirs zipman purge lto)/g' /etc/makepkg.conf
# Setup packager name
sed -i 's/#PACKAGER=".*"/PACKAGER="Linux Gaming Team"/g' /etc/makepkg.conf
# Use all threads for building
sed -i 's/#MAKEFLAGS="-j2"/MAKEFLAGS="-j$(nproc) -l$(nproc)"/g' /etc/makepkg.conf
# makepkg cannot not as root by default
sed -i -e 's|EUID == 0|EUID == 69|g' /usr/bin/makepkg
# always disable this nonsense that was recently added to makepkg
sed -i -e 's/(( ${#arch\[@\]} != $(printf "%s\\n" ${arch\[@\]} | sort -u | wc -l) ))/false/' /usr/share/makepkg/lint_pkgbuild/arch.sh 2>/dev/null || :

echo "Tweak pacman..."
echo "---------------------------------------------------------------"
pacman-key --init
pacman -S --noconfirm archlinux-keyring

# Chaotic-AUR keys
pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com
pacman-key --lsign-key 3056513887B78AEB

pacman -U --noconfirm 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst'
pacman -U --noconfirm 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst'

# Enable the multilib repository
cat << EOM >> /etc/pacman.conf
[multilib]
Include = /etc/pacman.d/mirrorlist

[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
SigLevel = Never
EOM

# Disable locale noextract
sed -i -E 's@[[:space:]]*usr/share/locale/\*@@g; s@[[:space:]]+@ @g; s@[[:space:]]+$@@' /etc/pacman.conf

pacman -Syy

echo "Building PortProtonQt from PKGBUILD..."
echo "---------------------------------------------------------------"
if [ "$LOCAL_MODE" = true ]; then
    cp ../PKGBUILD-git ./PKGBUILD
else
    wget --retry-connrefused --tries=30 "$PPQT_PKGBUILD" -O ./PKGBUILD
fi
sed -i "s|source=(\"git+https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt.git\")|source=(\"git+${REPO_URL}#branch=$BRANCH\")|" PKGBUILD
makepkg -si --noconfirm

echo "Installing optional runtime dependencies from PKGBUILD..."
echo "---------------------------------------------------------------"
OPTDEPENDS_PACKAGES="$(sed -n '/optdepends=(/,/)/p' PKGBUILD \
    | grep -o "'[^']*'" \
    | sed "s/'//g" \
    | awk -F: '{print $1}' \
    | tr '\n' ' ' \
    | xargs)"

if [ -n "${OPTDEPENDS_PACKAGES// /}" ]; then
    # Install all optional dependencies used by system integrations.
    pacman -S --needed --noconfirm $OPTDEPENDS_PACKAGES
fi

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
