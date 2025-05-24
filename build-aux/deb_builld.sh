#!/bin/bash

DEST_DIR=/tmp/portprotonqt.build
VERSION=0.1.1
GEM_HOME="$HOME/.local/share/gem/ruby/3.0.0"

set -e

cd "$(dirname "$0")"

# Check if on Debian-based system
cat /etc/debian_version || {
  echo "Not on Debian-based system"
  exit 1
}

# Install required tools
type git || {
  apt install -y git
}

type python3 || {
  apt install -y python3 python3-pip
}

type ar || {
  apt install -y binutils
}

pip3 install --upgrade --user setuptools pip wheel build installer packaging

type fpm || {
  gem install --user-install fpm
}

# Clean up previous build
rm -rf PortProtonQt "$DEST_DIR"

git clone https://github.com/Boria138/PortProtonQt.git
cd PortProtonQt
git checkout $VERSION

# Build the wheel
python3 -m build --wheel --no-isolation

# Install to temporary directory
python3 -m installer --destdir="$DEST_DIR" dist/*.whl

# Copy additional files as specified in PKGBUILD
cp -r build-aux/share "$DEST_DIR/usr/"

# Create Debian package with fpm
$GEM_HOME/bin/fpm -s dir -t deb \
  -n portprotonqt \
  -v "$VERSION" \
  --license "MIT" \
  --maintainer "Boris Yumankulov <boria138@altlinux.org>" \
  --description "A modern GUI for PortProton project." \
  --url "https://github.com/Boria138/PortProtonQt" \
  --depends "python3-numpy, python3-requests, python3-babel, python3-evdev, python3-pyudev, python3-orjson, python3-psutil, python3-tqdm, python3-vdf, python3-pyside6, python3-icoextract, python3-pil, libimage-exiftool-perl, xdg-utils" \
  --prefix / \
  -C "$DEST_DIR" \
  usr
