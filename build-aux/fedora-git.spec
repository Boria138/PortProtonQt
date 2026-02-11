%global pypi_name portprotonqt
%global pypi_version 0.1.10
%global oname PortProtonQt
%global build_timestamp %(date +"%Y%m%d")
%global _python_no_extras_requires 1

%global rel_build 1.git.%{build_timestamp}%{?dist}

Name:           %{pypi_name}-git
Version:        %{pypi_version}
Release:        %{rel_build}
Summary:        Modern GUI for managing and launching games from PortProton, Steam, and Epic Games Store (development build)

License:        GPL-3.0
URL:            https://git.linux-gaming.ru/Boria138/PortProtonQt
ExclusiveArch:  x86_64 aarch64

BuildRequires:  meson >= 0.61.2
BuildRequires:  ninja-build
BuildRequires:  python3-devel
BuildRequires:  git
BuildRequires:  systemd-rpm-macros

Obsoletes:      python3-%{pypi_name}-git < %{version}-%{release}
Provides:       python3-%{pypi_name}-git = %{version}-%{release}

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
Requires:       pciutils
Requires:       vulkan-loader

%ifarch aarch64
Requires:       muvm
%endif

%description
This application provides a sleek, intuitive graphical interface for managing and launching games from PortProton, Steam, and Epic Games Store. It consolidates your game libraries into a single, user-friendly hub for seamless navigation and organization. Its lightweight structure and cross-platform support deliver a cohesive gaming experience, eliminating the need for multiple launchers. Unique PortProton integration enhances Linux gaming, enabling effortless play of Windows-based titles with minimal setup.

%{?python_disable_dependency_generator}

BuildRequires:  vulkan-loader-devel
BuildRequires:  gcc

%prep
git clone https://git.linux-gaming.ru/Boria138/PortProtonQt.git

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
%{_bindir}/vk_gpu_info

%changelog
