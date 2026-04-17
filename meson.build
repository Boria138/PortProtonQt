project('portprotonqt', 'c',
  version: '0.1.12',
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

if get_option('build_i586_req_dummy')
  i586_req_dummy_link_args = [
    '-Wl,--no-as-needed',
    '-l:libGL.so.1',
    '-l:libgio-2.0.so.0',
    '-l:libnm.so.0',
    '-l:libnss3.so',
    '-l:libunwind.so.8',
    '-l:libVkLayer_MESA_device_select.so',
    '-l:libnsl.so.1',
    '-l:libvulkan_intel.so',
    '-l:libvulkan_radeon.so',
    '-l:libvulkan_nouveau.so',
  ]

  executable('portprotonqt_i586_req_dummy',
    sources: files('build-aux/i586_req_dummy.c'),
    install: true,
    install_dir: pkgdatadir,
    c_args: ['-std=c99'],
    link_args: i586_req_dummy_link_args,
  )
endif

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

# Install Steam compatibility tool
subdir('build-aux/share/steam/compatibilitytools.d/PortProtonQt')

# Install udev rules
udev_rulesdir_opt = get_option('udev_rulesdir')
udevdir = udev_rulesdir_opt != '' ? udev_rulesdir_opt : prefix / 'lib' / 'udev' / 'rules.d'

install_data(
  'build-aux/lib/udev/rules.d/60-portprotonqt.rules',
  install_dir: udevdir,
)

# Install polkit rules
install_data(
  'build-aux/share/polkit-1/rules.d/ru.linux_gaming.PortProtonQt.rules',
  install_dir: prefix / 'share' / 'polkit-1' / 'rules.d',
)
