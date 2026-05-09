%global pypi_name portprotonqt
%global pypi_version 0.1.12
%global oname PortProtonQt
%global _python_no_extras_requires 1

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
Summary:        Modern GUI for managing and launching games from PortProton and Steam

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

Obsoletes:      python3-%{pypi_name} < %{version}-%{release}
Provides:       python3-%{pypi_name} = %{version}-%{release}

Requires:       python3-babel
Requires:       python3-evdev
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
Requires:       jq
Requires:       file
Requires:       findutils
Requires:       gawk
Requires:       grep
Requires:       tar
Requires:       xz
Requires:       zstd
Requires:       unrar
Requires:       glx-utils
Requires:       pciutils
Requires:       vulkan-loader
Requires:       procps-ng
Requires:       psmisc
Requires:       squashfs-tools
Requires:       7zip
Requires:       python3-dbus-fast

# System Tab
Recommends:     NetworkManager
Recommends:     bluez
Recommends:     upower
Recommends:     pulseaudio-utils
Recommends:     python3-qrcode

%ifarch aarch64
Requires:       muvm
%endif

%description
A modern and intuitive interface for managing and launching games from PortProton and Steam. Combines libraries in one place and simplifies running Windows games on Linux.

%package -n %{pypi_name}-steam-compat
Summary:        Steam compatibility tool for PortProtonQt
License:        GPL-3.0
Requires:       %{pypi_name} = %{version}-%{release}

%description -n %{pypi_name}-steam-compat
Steam compatibility tool integration for PortProtonQt. This package installs
the necessary files to use PortProtonQt as a Proton compatibility tool in Steam.

%{?python_disable_dependency_generator}

%prep
git clone https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt
cd %{oname}
git checkout v%{pypi_version}

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

%files -n %{pypi_name}-steam-compat
%{_datadir}/steam/compatibilitytools.d/PortProtonQt/

%changelog
