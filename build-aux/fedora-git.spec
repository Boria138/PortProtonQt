%global pypi_name portprotonqt
%global pypi_version 0.1.1
%global oname PortProtonQt
%global build_timestamp %(date +"%Y%m%d")

%global rel_build 1.git.%{build_timestamp}%{?dist}

Name:           python-%{pypi_name}-git
Version:        %{pypi_version}
Release:        %{rel_build}
Summary:        Modern GUI for managing and launching games from PortProton, Steam, and Epic Games Store (development build)

License:        GPL-3.0
URL:            https://git.linux-gaming.ru/Boria138/PortProtonQt
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-wheel
BuildRequires:  python3-pip
BuildRequires:  python3-build
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3dist(setuptools)
BuildRequires:  git

%description
%{summary}

%package -n     python3-%{pypi_name}-git
Summary:        %{summary}
%{?python_provide:%python_provide python3-%{pypi_name}}
Requires:       python3dist(babel)
Requires:       python3dist(evdev)
Requires:       python3dist(icoextract)
Requires:       python3dist(numpy)
Requires:       python3dist(orjson)
Requires:       python3dist(psutil)
Requires:       python3dist(pyside6)
Requires:       python3dist(pyudev)
Requires:       python3dist(requests)
Requires:       python3dist(tqdm)
Requires:       python3dist(vdf)
Requires:       python3dist(pefile)
Requires:       python3dist(pillow)
Requires:       perl-Image-ExifTool
Requires:       xdg-utils

%description -n python3-%{pypi_name}-git
This application provides a sleek, intuitive graphical interface for managing and launching games from PortProton, Steam, and Epic Games Store. It consolidates your game libraries into a single, user-friendly hub for seamless navigation and organization. Its lightweight structure and cross-platform support deliver a cohesive gaming experience, eliminating the need for multiple launchers. Unique PortProton integration enhances Linux gaming, enabling effortless play of Windows-based titles with minimal setup.

%prep
git clone https://git.linux-gaming.ru/Boria138/PortProtonQt.git

%build
cd %{oname}
%pyproject_wheel

%install
cd %{oname}
%pyproject_install
%pyproject_save_files %{pypi_name}
cp -r build-aux/share %{buildroot}/usr/

%files -n python3-%{pypi_name}-git -f %{pyproject_files}
%{_bindir}/%{pypi_name}
%{_datadir}/icons/hicolor/scalable/apps/ru.linux_gaming.PortProtonQt.svg
%{_metainfodir}/ru.linux_gaming.PortProtonQt.metainfo.xml
%{_datadir}/applications/ru.linux_gaming.PortProtonQt.desktop

%changelog
