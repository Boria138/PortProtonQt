project('portprotonqt', 'c',
  version: '1.3.0',
  meson_version: '>= 0.61.2',
  license: 'GPL-3.0',
)


# Python installation
python3 = import('python').find_installation('python3')

# Configuration
conf = configuration_data()
conf.set('PYTHON', python3.full_path())

version_conf = configuration_data()
version_conf.set_quoted('APP_VERSION', meson.project_version())
version_conf.set_quoted('APP_COMMIT', '')

if get_option('nightly')
  git = find_program('git', required: false)
  if git.found()
    git_commit = run_command(git, 'rev-parse', '--short', 'HEAD', check: false)
    if git_commit.returncode() == 0
      version_conf.set_quoted('APP_COMMIT', git_commit.stdout().strip())
    endif
  endif
endif

# Directories
prefix = get_option('prefix')
datadir = prefix / get_option('datadir')
bindir = prefix / get_option('bindir')

# Use custom purelibdir if specified, otherwise use default
purelibdir_opt = get_option('python_purelibdir')
pythondir = purelibdir_opt != '' ? purelibdir_opt: python3.get_install_dir(pure: true)
pkgdatadir = pythondir / meson.project_name()

# C compiler for vk_gpu_info
cc = meson.get_compiler('c')

configured_version = configure_file(
  input: 'portprotonqt/_version.py.in',
  output: '_version.py',
  configuration: version_conf,
)

install_data(
  configured_version,
  install_dir: pythondir / meson.project_name(),
)

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

# Install MIME type
install_data(
  'build-aux/share/mime/packages/ru.linux_gaming.PortProtonQt.xml',
  install_dir: datadir / 'mime/packages',
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

# Install PortProton scripts
install_subdir(
  'build-aux/share/portproton/scripts',
  install_dir: datadir / 'portproton',
  install_mode: 'rwxr-xr-x',
)

install_subdir(
  'build-aux/share/portproton/conf',
  install_dir: datadir / 'portproton',
)

install_subdir(
  'build-aux/share/portproton/img',
  install_dir: datadir / 'portproton',
)

install_subdir(
  'build-aux/share/portproton/scripts/portwine_db',
  install_dir: datadir / 'portproton' / 'scripts',
  install_mode: 'rwxr-xr-x',
)

# Install udev rules
udev_rulesdir_opt = get_option('udev_rulesdir')
udevdir = udev_rulesdir_opt != '' ? udev_rulesdir_opt: prefix / 'lib' / 'udev' / 'rules.d'

install_data(
  'build-aux/lib/udev/rules.d/60-portprotonqt.rules',
  install_dir: udevdir,
)

# Install polkit rules
install_data(
  'build-aux/share/polkit-1/rules.d/ru.linux_gaming.PortProtonQt.rules',
  install_dir: prefix / 'share' / 'polkit-1' / 'rules.d',
)
