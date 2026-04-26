%global pypi_name portprotonqt
%global pypi_version 0.1.12
%global oname PortProtonQt
%global build_timestamp %(date +"%Y%m%d")
%global _python_no_extras_requires 1

%global rel_build 1.git.%{build_timestamp}%{?dist}

Name:           %{pypi_name}-git
Version:        %{pypi_version}
Release:        %{rel_build}
Summary:        Modern GUI for managing and launching games from PortProton, Steam, and Epic Games Store (development build)

License:        GPL-3.0
URL:            https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt
ExclusiveArch:  x86_64 aarch64

BuildRequires:  meson >= 0.61.2
BuildRequires:  ninja-build
BuildRequires:  python3-devel
BuildRequires:  git
BuildRequires:  gettext
BuildRequires:  systemd-rpm-macros
BuildRequires:  vulkan-loader-devel
BuildRequires:  gcc

Obsoletes:      python3-%{pypi_name}-git < %{version}-%{release}
Provides:       python3-%{pypi_name}-git = %{version}-%{release}

Requires:       python3-babel
Requires:       python3-evdev
Requires:       python3-icoextract
Requires:       python3-websocket-client
Requires:       python3-orjson
Requires:       python3-psutil
Requires:       python3-pyside6
Requires:       python3-pygame
Requires:       python3-requests
Requires:       python3-tqdm
Requires:       python3-vdf
Requires:       python3-pefile
Requires:       python3-pillow
Requires:       python3-beautifulsoup4
Requires:       python3-rapidfuzz
Requires:       python3-libarchive-c
Requires:       perl-Image-ExifTool
Requires:       qt6-qtsvg
Requires:       cabextract
Requires:       gzip
Requires:       unzip
Requires:       curl
Requires:       unrar
Requires:       glx-utils
Requires:       pciutils
Requires:       vulkan-loader
Requires:       7zip

# System Tab
Recommends:     NetworkManager
Recommends:     bluez
Recommends:     upower
Recommends:     pulseaudio-utils
Recommends:     python3-dbus-fast
Recommends:     python3-qrcode

%ifarch aarch64
Requires:       muvm
%endif

%description
This application provides a sleek, intuitive graphical interface for managing and launching games from PortProton, Steam, and Epic Games Store. It consolidates your game libraries into a single, user-friendly hub for seamless navigation and organization. Its lightweight structure and cross-platform support deliver a cohesive gaming experience, eliminating the need for multiple launchers. Unique PortProton integration enhances Linux gaming, enabling effortless play of Windows-based titles with minimal setup.

%package -n %{pypi_name}-git-steam-compat
Summary:        Steam compatibility tool for PortProtonQt (development build)
License:        GPL-3.0
Requires:       %{pypi_name}-git = %{version}-%{release}

%description -n %{pypi_name}-git-steam-compat
Steam compatibility tool integration for PortProtonQt. This package installs
the necessary files to use PortProtonQt as a Proton compatibility tool in Steam.

%{?python_disable_dependency_generator}

%prep
git clone https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt.git

%build
cd %{oname}
%meson \
    -Dpython_purelibdir=%{python3_sitelib} \
    -Dudev_rulesdir=%{_udevrulesdir}
%meson_build

%install
cd %{oname}
%meson_install
bash ./dev-scripts/generate-completions.sh
install -Dpm 0644 ./completions/portprotonqt -t %{buildroot}%{bash_completions_dir}
install -Dpm 0644 ./completions/portprotonqt.fish -t %{buildroot}%{fish_completions_dir}
install -Dpm 0644 ./completions/_portprotonqt -t %{buildroot}%{zsh_completions_dir}
%find_lang %{pypi_name}

%files -f %{oname}/%{pypi_name}.lang
%{_bindir}/%{pypi_name}
%{_bindir}/vk_gpu_info
%{python3_sitelib}/%{pypi_name}/
%{_datadir}/icons/hicolor/scalable/apps/ru.linux_gaming.PortProtonQt.svg
%{_metainfodir}/ru.linux_gaming.PortProtonQt.metainfo.xml
%{_udevrulesdir}/60-portprotonqt.rules
%{_datadir}/polkit-1/rules.d/ru.linux_gaming.PortProtonQt.rules
%{_datadir}/applications/ru.linux_gaming.PortProtonQt.desktop
%{_datadir}/portproton/scripts/
%{bash_completions_dir}/portprotonqt
%{fish_completions_dir}/portprotonqt.fish
%{zsh_completions_dir}/_portprotonqt

%files -n %{pypi_name}-git-steam-compat
%{_datadir}/steam/compatibilitytools.d/PortProtonQt/

%changelog
