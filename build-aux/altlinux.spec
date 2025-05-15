%define pypi_name portprotonqt

Name: python3-module-portprotonqt
Version: 0.1.0
Release: alt1

Summary: A modern GUI for PortProton project
License: MIT
Group: Games/Other

Url: https://github.com/Boria138/PortProtonQt
# Source-url: https://github.com/Boria138/PortProtonQt/archive/refs/tags/%version.tar.gz
Source: %name-%version.tar

BuildRequires(pre): rpm-build-python3
BuildRequires: python3-devel python3-module-setuptools python3-module-wheel

Requires: qt6-svg

BuildArch: noarch

%description
%summary

%prep
%setup

%build
%pyproject_build

%install
%pyproject_install

%files
%_bindir/portprotonqt
%python3_sitelibdir/%pypi_name/
%python3_sitelibdir/%{pyproject_distinfo %pypi_name}
