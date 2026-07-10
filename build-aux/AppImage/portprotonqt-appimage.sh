#!/bin/sh

set -eu

SHARUN="https://raw.githubusercontent.com/pkgforge-dev/Anylinux-AppImages/refs/heads/main/useful-tools/quick-sharun.sh"
ARCH="$(uname -m)"
VERSION="$(cat ~/version)"
export ARCH VERSION
export OUTPATH=./dist
export DESKTOP=/usr/share/applications/ru.linux_gaming.PortProtonQt.desktop
export ICON=/usr/share/icons/hicolor/scalable/apps/ru.linux_gaming.PortProtonQt.svg
export OUTNAME=PortProtonQt-"$VERSION"-anylinux-"$ARCH".AppImage
export UPINFO="gitea-releases-zsync|git.linux-gaming.ru|Linux-Gaming|PortProtonQt|latest|*$ARCH.AppImage.zsync"
export ADD_HOOKS="self-updater.bg.hook"
export DEPLOY_OPENGL=1
export DEPLOY_SDL=1
export DEPLOY_PYTHON=1
export OPTIMIZE_LAUNCH=1

# Adjust comp settings to bypass oom-killer
export DWARFS_COMP="zstd:level=15 -S22 -B5"

# DEPLOY ALL LIBS
wget --retry-connrefused --tries=30 "$SHARUN" -O ./quick-sharun
chmod +x ./quick-sharun

# Add udev rules
mkdir -p ./AppDir/etc/udev/rules.d
cp /usr/lib/udev/rules.d/60-portprotonqt.rules ./AppDir/etc/udev/rules.d

# Add PortProton scripts
mkdir -p ./AppDir/share
if [ -d /usr/local/share/portproton ]; then
	cp -r /usr/local/share/portproton ./AppDir/share
elif [ -d /usr/share/portproton ]; then
	cp -r /usr/share/portproton ./AppDir/share
fi

# Deploy dependencies
# Qt libs have to be passed manually due to the app being a python script
./quick-sharun \
	/usr/bin/portprotonqt* \
	/usr/lib/libQt6Core.so* \
	/usr/lib/libQt6Gui.so* \
	/usr/lib/libQt6Network.so* \
	/usr/lib/qt6/plugins/imageformats/libqwebp.so

# Turn AppDir into AppImage
./quick-sharun --make-appimage
