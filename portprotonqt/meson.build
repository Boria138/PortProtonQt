# Install Python source files
install_data(
  ['__init__.py',
  'animations.py',
  'app.py',
  'cli.py',
  'config_utils.py',
  'context_menu_manager.py',
  'custom_widgets.py',
  'detail_pages.py',
  'dialogs.py',
  'downloader.py',
  'egs_api.py',
  'game_card.py',
  'game_library_manager.py',
  'get_wine_module.py',
  'howlongtobeat_api.py',
  'image_utils.py',
  'input_manager.py',
  'keyboard_layouts.py',
  'localization.py',
  'logger.py',
  'main_window.py',
  'portproton_api.py',
  'preloader.py',
  'search_utils.py',
  'settings_manager.py',
  'steam_api.py',
  'system_overlay.py',
  'theme_manager.py',
  'theme_security.py',
  'time_utils.py',
  'tray_manager.py',
  'version_utils.py',
  'virtual_keyboard.py'],
  install_dir: pythondir / meson.project_name(),
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

# Install themes
install_subdir(
  'themes',
  install_dir: pythondir / meson.project_name(),
  exclude_directories: ['__pycache__'],
  exclude_files: ['*.pyc'],
)

# Install locales - only .mo files (compiled translations)
# exclude_files doesn't work recursively, so we install each language manually
foreach lang : ['de', 'es', 'pt', 'ru']
  install_data(
    'locales' / lang / 'LC_MESSAGES' / 'portprotonqt.mo',
    install_dir: get_option('localedir') / lang / 'LC_MESSAGES',
  )
endforeach
