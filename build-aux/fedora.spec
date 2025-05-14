%global pypi_name portprotonqt
%global pypi_version 0.1.0
%global oname PortProtonQt

Name:           python-%{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
Summary:        A modern GUI for PortProton project

License:        MIT
URL:            https://github.com/Boria138/PortProtonQt
Source0:        %{url}/archive/%{version}/%{oname}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-wheel
BuildRequires:  python3-pip
BuildRequires:  python3-build
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3dist(setuptools)

%description
%{summary}

%package -n     python3-%{pypi_name}
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

%description -n python3-%{pypi_name}
PortProtonQt is a modern graphical user interface for the PortProton project,
designed to simplify the management and launching of games using Wine and Proton.

%prep
%autosetup -p1 -n %{oname}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{pypi_name}

%files -n python3-%{pypi_name} -f %{pyproject_files}
%{_bindir}/%{pypi_name}

%changelog
