# Install Python source files
install_data(
  ['__init__.py',
  'animations.py',
  'app.py',
  'cli.py',
  'config_utils.py',
  'context_menu_manager.py',
  'custom_widgets.py',
  'dialogs.py',
  'downloader.py',
  'egs_api.py',
  'game_card.py',
  'game_library_manager.py',
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
  'system_overlay.py',
  'theme_manager.py',
  'theme_security.py',
  'time_utils.py',
  'tray_manager.py',
  'version_utils.py',
  'virtual_keyboard.py'],
  install_dir: pythondir / meson.project_name(),
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

# Install locales - only .mo files (compiled translations)
# exclude_files doesn't work recursively, so we install each language manually
foreach lang : ['de', 'es', 'pt', 'ru']
  install_data(
    'locales' / lang / 'LC_MESSAGES' / 'portprotonqt.mo',
    install_dir: get_option('localedir') / lang / 'LC_MESSAGES',
  )
endforeach
