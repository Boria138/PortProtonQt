# Install Python source files
install_data(
  ['__init__.py',
   'app.py',
   'cli.py',
   'context_menu_manager.py',
   'custom_widgets.py',
   'dialogs.py',
   'disc_image_utils.py',
   'downloader.py',
   'easyterm.py',

  'game_card.py',
  'game_library_manager.py',
  'howlongtobeat_api.py',
  'image_utils.py',
  'icon_extractor.py',
  'input_manager.py',
  'keyboard_layouts.py',
  'localization.py',
  'logger.py',
  'main_window.py',
  'port_data_path_selector.py',
  'portproton_api.py',
  'preloader.py',
  'qt_utils.py',
  'search_utils.py',
  'settings_manager.py',
  'theme_manager.py',
  'theme_security.py',
  'time_utils.py',
  'tray_manager.py',
  'version_utils.py',
  'virtual_keyboard.py'],
  install_dir: pythondir / meson.project_name(),
)

# Install animations package
install_data(
  ['animations/__init__.py',
   'animations/detail_page.py',
   'animations/game_card.py',
   'animations/virtual_keyboard.py',
  ],
  install_dir: pythondir / meson.project_name() / 'animations',
)

# Install steam_api package
install_data(
  ['steam_api/__init__.py',
   'steam_api/utils.py',
   'steam_api/cache.py',
   'steam_api/api.py',
   'steam_api/shortcuts.py',
  ],
  install_dir: pythondir / meson.project_name() / 'steam_api',
)

# Install dialogs package
install_data(
  ['dialogs/__init__.py',
   'dialogs/base.py',
   'dialogs/dialog_utils.py',
   'dialogs/file_explorer.py',
   'dialogs/winetricks_dialog.py',
   'dialogs/settings_dialog.py',
   'dialogs/settings_mangohud.py',
   'dialogs/settings_gamescope.py',
   'dialogs/proton_manager.py',
   'dialogs/wine_loader.py',
   'dialogs/wine_downloader.py',
   'dialogs/wine_extractor.py',
  ],
  install_dir: pythondir / meson.project_name() / 'dialogs',
)

# Install detail_pages package
install_data(
  ['detail_pages/__init__.py',
   'detail_pages/widgets.py',
   'detail_pages/utils.py',
  ],
  install_dir: pythondir / meson.project_name() / 'detail_pages',
)

# Install system_manager package
install_data(
  ['system_manager/__init__.py',
   'system_manager/audio.py',
   'system_manager/bluetooth.py',
   'system_manager/common.py',
   'system_manager/network.py',
   'system_manager/storage.py',
  ],
  install_dir: pythondir / meson.project_name() / 'system_manager',
)

# Install tabs package
install_data(
  ['tabs/__init__.py',
   'tabs/control_hints.py',
   'tabs/system_tab.py',
   'tabs/workers.py',
  ],
  install_dir: pythondir / meson.project_name() / 'tabs',
)

# Install debug_utils package
install_data(
  ['debug_utils/__init__.py',
   'debug_utils/debug_log_manager.py',
   'debug_utils/env_utils.py',
   'debug_utils/game_debug.py',
   'debug_utils/gpu_info.py',
   'debug_utils/log_processor.py',
   'debug_utils/system_info.py',
   'debug_utils/xorg_utils.py',
  ],
  install_dir: pythondir / meson.project_name() / 'debug_utils',
)

# Install scripts_utils package
install_data(
  ['scripts_utils/__init__.py',
   'scripts_utils/idle_inhibit.py',
   'scripts_utils/power_profiles.py',
   'scripts_utils/shortcut_tools.py',
  ],
  install_dir: pythondir / meson.project_name() / 'scripts_utils',
)

# Install config package
install_data(
  ['config/__init__.py',
   'config/base.py',
   'config/ui.py',
   'config/game.py',
   'config/cache.py',
   'config/gamepad.py',
   'config/proxy.py',
   'config/display.py',
   'config/window.py',
   'config/favorites.py',
   'config/portproton.py',
   'config/validators.py',
  ],
  install_dir: pythondir / meson.project_name() / 'config',
)

# Install themes
install_subdir(
  'themes',
  install_dir: pythondir / meson.project_name(),
  exclude_directories: ['__pycache__'],
  exclude_files: ['*.pyc'],
)

# Install terminal schemes
install_subdir(
  'terminal_schemes',
  install_dir: pythondir / meson.project_name(),
)

# Compile and install locales from .po files
msgfmt = find_program('msgfmt', required: true)
foreach lang : ['de', 'es', 'pt', 'ru', 'zh_Hans']
  mo_target = configure_file(
    input: 'locales' / lang / 'LC_MESSAGES' / 'portprotonqt.po',
    output: lang + '_portprotonqt.mo',
    command: [msgfmt, '@INPUT@', '-o', '@OUTPUT@'],
  )
  install_data(
    mo_target,
    rename: 'portprotonqt.mo',
    install_dir: get_option('localedir') / lang / 'LC_MESSAGES',
    install_tag: 'i18n'
  )
endforeach
