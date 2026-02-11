project('portprotonqt', 'c',
  version: '0.1.10',
  meson_version: '>= 0.61.2',
  license: 'GPL-3.0',
)


# Python installation
python3 = import('python').find_installation('python3')

# Configuration
conf = configuration_data()
conf.set('PYTHON', python3.full_path())

# Directories
prefix = get_option('prefix')
datadir = prefix / get_option('datadir')
bindir = prefix / get_option('bindir')

# Use custom purelibdir if specified, otherwise use default
purelibdir_opt = get_option('python_purelibdir')
pythondir = purelibdir_opt != '' ? purelibdir_opt : join_paths(prefix, python3.get_path('purelib'))
pkgdatadir = pythondir / meson.project_name()

# C compiler for vk_gpu_info
cc = meson.get_compiler('c')

# Install Python package
subdir('portprotonqt')

# Install entry point script
configured_portprotonqt = configure_file(
  input: 'build-aux/portprotonqt',
  output: 'portprotonqt-script',
  configuration: conf,
)

install_data(configured_portprotonqt,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
  rename: 'portprotonqt',
)

# Build and install vk_gpu_info executable
vk_gpu_info_sources = files('build-aux/vk_gpu_info.c')
vk_gpu_info_deps = [dependency('vulkan', required: true)]

executable('vk_gpu_info',
  sources: vk_gpu_info_sources,
  dependencies: vk_gpu_info_deps,
  install: true,
  install_dir: bindir,
  c_args: ['-std=c99'],
)

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
udev = dependency('udev', required: false)
udevdir = udev.found() ? udev.get_variable(pkgconfig: 'udevdir') / 'rules.d' : prefix / get_option('libdir') / 'udev/rules.d'

install_data(
  'build-aux/lib/udev/rules.d/60-portprotonqt.rules',
  install_dir: udevdir,
)
