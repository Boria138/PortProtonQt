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
  'debug_utils.py',
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
