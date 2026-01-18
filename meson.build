project('portprotonqt',
  version: '0.1.10',
  meson_version: '>= 0.61.2',
  license: 'GPL-3.0',
)

# Project directories
prefix = get_option('prefix')
datadir = prefix / get_option('datadir')
bindir = prefix / get_option('bindir')

# Python module for site-packages path
python = import('python')
python3 = python.find_installation('python3')
pythondir = join_paths(prefix, python3.get_path('purelib'))

python_libdir = get_option('python_libdir')
if python_libdir == ''
  python_installdir = pythondir
else
  python_installdir = python_libdir
endif

pkgdatadir = python_installdir / meson.project_name()

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())

# Install Python package
subdir('portprotonqt')

# Install entry point script with proper name to avoid conflict in build directory
configured_portprotonqt = configure_file(
  input: 'build-aux/portprotonqt',
  output: 'portprotonqt-script',
  configuration: conf,
)

# Install the configured script with the correct name
install_data(configured_portprotonqt,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
  rename: 'portprotonqt')

# Install desktop file
install_data(
  'build-aux/share/applications/ru.linux_gaming.PortProtonQt.desktop',
  install_dir: datadir / 'applications',
)

# Install icon
install_data(
  'build-aux/share/icons/hicolor/scalable/apps/ru.linux_gaming.PortProtonQt.svg',
  install_dir: datadir / 'icons/hicolor/scalable/apps',
)

# Install metainfo
install_data(
  'build-aux/share/metainfo/ru.linux_gaming.PortProtonQt.metainfo.xml',
  install_dir: datadir / 'metainfo',
)

# Install bash completion
install_data(
  'build-aux/share/bash-completion/completions/portprotonqt',
  install_dir: datadir / 'bash-completion/completions',
)

# Install udev rules
udevdir = get_option('udevdir')
if udevdir == ''
  udev = dependency('udev', required: false)
  if udev.found()
    udevdir = udev.get_variable(pkgconfig: 'udevdir') / 'rules.d'
  else
    udevdir = prefix / get_option('libdir') / 'udev/rules.d'
  endif
endif

install_data(
  'build-aux/lib/udev/rules.d/60-portprotonqt.rules',
  install_dir: udevdir,
)
