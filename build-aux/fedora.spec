%global pypi_name portprotonqt
%global pypi_version 0.1.10
%global oname PortProtonQt
%global _python_no_extras_requires 1

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
Summary:        Modern GUI for managing and launching games from PortProton, Steam, and Epic Games Store

License:        GPL-3.0
URL:            https://git.linux-gaming.ru/Boria138/PortProtonQt
BuildArch:      noarch

BuildRequires:  meson >= 0.61.2
BuildRequires:  ninja-build
BuildRequires:  python3-devel
BuildRequires:  git
BuildRequires:  systemd-rpm-macros

Obsoletes:      python3-%{pypi_name} < %{version}-%{release}
Provides:       python3-%{pypi_name} = %{version}-%{release}

Requires:       python3-babel
Requires:       python3-evdev
Requires:       python3-icoextract
Requires:       python3-websocket-client
Requires:       python3-orjson
Requires:       python3-psutil
Requires:       python3-pyside6
Requires:       python3-pyudev
Requires:       python3-requests
Requires:       python3-tqdm
Requires:       python3-vdf
Requires:       python3-pefile
Requires:       python3-pillow
Requires:       python3-beautifulsoup4
Requires:       python3-rapidfuzz
Requires:       python3-libarchive-c
Requires:       perl-Image-ExifTool
Requires:       xdg-utils
Requires:       qt6-qtsvg
Requires:       cabextract
Requires:       gzip
Requires:       unzip
Requires:       curl
Requires:       unrar
Requires:       glx-utils
Requires:       xdpyinfo
Requires:       xrandr
Requires:       pciutils
Requires:       vulkan-tools

%ifarch aarch64
Requires:       muvm
%endif

%description
This application provides a sleek, intuitive graphical interface for managing and launching games from PortProton, Steam, and Epic Games Store. It consolidates your game libraries into a single, user-friendly hub for seamless navigation and organization. Its lightweight structure and cross-platform support deliver a cohesive gaming experience, eliminating the need for multiple launchers. Unique PortProton integration enhances Linux gaming, enabling effortless play of Windows-based titles with minimal setup.

%{?python_disable_dependency_generator}

%prep
git clone https://git.linux-gaming.ru/Boria138/PortProtonQt
cd %{oname}
git checkout v%{pypi_version}

%build
cd %{oname}
%meson
%meson_build

%install
cd %{oname}
%meson_install
%find_lang %{pypi_name}

%files -f %{oname}/%{pypi_name}.lang
%{_bindir}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}/
%{_datadir}/icons/hicolor/scalable/apps/ru.linux_gaming.PortProtonQt.svg
%{_metainfodir}/ru.linux_gaming.PortProtonQt.metainfo.xml
%{_udevrulesdir}/60-portprotonqt.rules
%{_datadir}/applications/ru.linux_gaming.PortProtonQt.desktop
%{bash_completions_dir}/portprotonqt

%changelog
