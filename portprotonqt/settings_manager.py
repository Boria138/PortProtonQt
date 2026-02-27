def get_toggle_settings():
    """Get predefined toggle settings with descriptions."""
    from portprotonqt.localization import _

    return {
        'PW_MANGOHUD': _("Using FPS and system load monitoring (Turns on and off by the key combination - right Shift + F12)"),
        'PW_MANGOHUD_USER_CONF': _("Forced use of MANGOHUD system settings (GOverlay, etc.)"),
        'PW_VKBASALT': _("Enable vkBasalt by default to improve graphics in games running on Vulkan. (The HOME hotkey disables vkbasalt)"),
        'PW_VKBASALT_USER_CONF': _("Forced use of VKBASALT system settings (GOverlay, etc.)"),
        'PW_DGVOODOO2': _("Enable dgVoodoo2. Forced use all dgVoodoo2 libs (Glide 2.11-3.1, DirectDraw 1-7, Direct3D 2-9) on all 3D API."),
        'PW_GAMESCOPE': _("Super + F : Toggle fullscreen\nSuper + N : Toggle nearest neighbour filtering\nSuper + U : Toggle FSR upscaling\nSuper + Y : Toggle NIS upscaling\nSuper + I : Increase FSR sharpness by 1\nSuper + O : Decrease FSR sharpness by 1\nSuper + S : Take screenshot (currently goes to /tmp/gamescope_DATE.png)\nSuper + G : Toggle keyboard grab\nSuper + C : Update clipboard"),
        'PW_USE_ESYNC': _("Enable in-process synchronization primitives based on eventfd."),
        'PW_USE_FSYNC': _("Enable futex-based in-process synchronization primitives."),
        'PW_USE_NTSYNC': _("Enable in-process synchronization via the Linux ntsync driver."),
        'PW_USE_RAY_TRACING': _("Enable vkd3d support - Ray Tracing"),
        'PW_USE_NVAPI_AND_DLSS': _("Enable DLSS on supported NVIDIA graphics cards"),
        'PW_USE_OPTISCALER': _("Enable OptiScaler (replacement upscaler / frame generator)"),
        'PW_USE_LS_FRAME_GEN': _("Enable Lossless Scaling frame generation (experimental)"),
        'PW_WINE_FULLSCREEN_FSR': _("FSR upscaling in fullscreen with ProtonGE below native resolution"),
        'PW_HIDE_NVIDIA_GPU': _("Disguise all NVIDIA GPU features"),
        'PW_VIRTUAL_DESKTOP': _("Run the application in WINE virtual desktop"),
        'PW_USE_TERMINAL': _("Run the application in a terminal"),
        'PW_USE_GAMEMODE': _("Use system GameMode for performance optimization"),
        'PW_USE_D3D_EXTRAS': _("Enable forced use of third-party DirectX libraries"),
        'PW_FIX_VIDEO_IN_GAME': _("Fix pink-tinted video playback in some games"),
        'PW_REDUCE_PULSE_LATENCY': _("Reduce PulseAudio latency to fix intermittent sound"),
        'PW_USE_US_LAYOUT': _("Force US keyboard layout"),
        'PW_USE_GSTREAMER': _("Use GStreamer for in-game clips (WMF support)"),
        'PW_USE_SHADER_CACHE': _("Use WINE shader caching"),
        'PW_USE_WINE_DXGI': _("Force use of built-in DXGI library"),
        'PW_USE_EAC_AND_BE': _("Enable Easy Anti-Cheat and BattlEye runtimes"),
        'PW_USE_SYSTEM_VK_LAYERS': _("Use system Vulkan layers (MangoHud, vkBasalt, OBS, etc.)"),
        'PW_USE_OBS_VKCAPTURE': _("Enable OBS Studio capture via obs-vkcapture"),
        'PW_DISABLE_COMPOSITING': _("Disable desktop compositing for performance"),
        'PW_USE_RUNTIME': _("Use container launch mode (recommended default)"),
        'PW_DINPUT_PROTOCOL': _("Force DirectInput protocol instead of XInput"),
        'PW_USE_NATIVE_WAYLAND': _("Enable experimental native Wayland support"),
        'PW_USE_DXVK_HDR': _("Enable HDR settings under native Wayland"),
        'PW_USE_GALLIUM_ZINK': _("Use Gallium Zink (OpenGL via Vulkan)"),
        'PW_USE_GALLIUM_NINE': _("Use Gallium Nine (native DirectX 9 for Mesa)"),
        'PW_USE_WINED3D_VULKAN': _("Use WineD3D Vulkan backend (Damavand)"),
        'PW_USE_SUPPLIED_DXVK_VKD3D': _("Use bundled dxvk/vkd3d from Wine/Proton"),
        'PW_USE_SAREK_ASYNC': _("Use async dxvk-sarek (experimental)"),
        'PW_USE_INHIBIT_SLEEP_INFO': _("Prevent the system from going to sleep and disable the screensaver while the game is running")
    }


def get_advanced_settings(disabled_text, logical_core_options, locale_options,
                          numa_nodes, dist_options=None, prefix_options=None):
    """Get advanced settings configuration."""
    from portprotonqt.localization import _
    import shutil

    advanced_settings = []
    if dist_options is None:
        dist_options = []
    if prefix_options is None:
        prefix_options = []

    # 1. Wine Version
    # Add System WINE option if available
    wine_options = dist_options[:]
    if shutil.which('wine') and _('System WINE') not in wine_options:
        wine_options.append(_('System WINE'))

    advanced_settings.append({
        'key': 'PW_WINE_USE',
        'name': _("Wine Version"),
        'description': _("Select the Wine or Proton version to use for this executable."),
        'type': 'combo',
        'options': wine_options,
        'default': ''
    })

    # 2. Prefix Name
    advanced_settings.append({
        'key': 'PW_PREFIX_NAME',
        'name': _("Prefix Name"),
        'description': _("Specify the Wine prefix to run this game with"),
        'type': 'combo',
        'options': prefix_options,
        'default': 'DEFAULT'
    })

    # 3. Vulkan Backend
    vulkan_options = [
        _("Newest"),        # → 6
        _("Stable"),                    # → 2
        ("Sarek"),   # → 1
        ("WINED3D – OpenGL")                 # → 0
    ]

    vulkan_value_map = {
        vulkan_options[0]: "6",
        vulkan_options[1]: "2",
        vulkan_options[2]: "1",
        vulkan_options[3]: "0",
    }

    advanced_settings.append({
        'key': 'PW_VULKAN_USE',
        'name': _("Vulkan Backend"),
        'description': _(
            "Select the DirectX → Vulkan/OpenGL backend:\n\n"
            "• Newest – latest DXVK + VKD3D (best compatibility/performance, requires modern drivers: AMD Mesa 25+, NVIDIA 550.54.14+, Intel Mesa 24.2+)\n"
            "• Stable – older, well-tested DXVK + VKD3D (works on any Vulkan 1.3+ driver)\n"
            "• Sarek – experimental DXVK-Sarek + VKD3D-Sarek (supports older drivers, Vulkan 1.1+)\n"
            "• WINED3D – OpenGL fallback (lowest performance, use only if others fail)"
        ),
        'type': 'combo',
        'options': vulkan_options,
        'default': '6',
        '_value_map': vulkan_value_map
    })

    # 4. Windows version
    advanced_settings.append({
        'key': 'PW_WINDOWS_VER',
        'name': _("Windows version"),
        'description': _("Changing the WINDOWS emulation version may be required to run older games. WINDOWS versions below 10 do not support new games with DirectX 12"),
        'type': 'combo',
        'options': ['11', '10', '7', 'XP'],
        'default': '10'
    })

    # 5. DLL Overrides
    advanced_settings.append({
        'key': 'WINEDLLOVERRIDES',
        'name': _("DLL Overrides"),
        'description': _("Forced to use/disable the library only for the given application.\n\nA brief instruction:\n* libraries are written WITHOUT the .dll file extension\n* libraries are separated by semicolons - ;\n* library=n - use the WINDOWS (third-party) library\n* library=b - use WINE (built-in) library\n* library=n,b - use WINDOWS library and then WINE\n* library=b,n - use WINE library and then WINDOWS\n* library= - disable the use of this library\n\nExample: libglesv2=;d3dx9_36,d3dx9_42=n,b;mfc120=b,n"),
        'type': 'text',
        'default': ''
    })

    # 6. Launch arguments
    advanced_settings.append({
        'key': 'LAUNCH_PARAMETERS',
        'name': _("Launch Arguments"),
        'description': _("Adding an argument after the .exe file, just like you would add an argument in a shortcut on a WINDOWS system.\n\nExample: -dx11 -skipintro 1"),
        'type': 'text',
        'default': ''
    })

    # 7. CPU cores limit
    advanced_settings.append({
        'key': 'PW_WINE_CPU_TOPOLOGY',
        'name': _("CPU Cores Limit"),
        'description': _("Limiting the number of CPU cores is useful for Unity games (It is recommended to set the value equal to 8)"),
        'type': 'combo',
        'options': [disabled_text] + logical_core_options,
        'default': disabled_text
    })

    # 8. OpenGL version
    advanced_settings.append({
        'key': 'PW_MESA_GL_VERSION_OVERRIDE',
        'name': _("OpenGL Version"),
        'description': _("You can select the required OpenGL version, some games require a forced Compatibility Profile (COMP)."),
        'type': 'combo',
        'options': [disabled_text, '4.6COMPAT', '4.5COMPAT', '4.3COMPAT', '4.1COMPAT', '3.3COMPAT', '3.2COMPAT'],
        'default': disabled_text
    })

    # 9. VKD3D feature level
    advanced_settings.append({
        'key': 'PW_VKD3D_FEATURE_LEVEL',
        'name': _("VKD3D Feature Level"),
        'description': _("You can set a forced feature level VKD3D for games on DirectX12"),
        'type': 'combo',
        'options': [disabled_text, '12_2', '12_1', '12_0', '11_1', '11_0'],
        'default': disabled_text
    })

    # 10. Locale
    advanced_settings.append({
        'key': 'PW_LOCALE_SELECT',
        'name': _("Locale"),
        'description': _("Force certain locale for an app. Fixes encoding issues in legacy software"),
        'type': 'combo',
        'options': [disabled_text] + locale_options,
        'default': disabled_text
    })

    # 11. Present mode
    advanced_settings.append({
        'key': 'PW_MESA_VK_WSI_PRESENT_MODE',
        'name': _("Window Mode"),
        'description': _("Window mode (for Vulkan and OpenGL):\nfifo - First in, first out. Limits the frame rate + no tearing. (VSync)\nimmediate - Unlimited frame rate + tearing.\nmailbox - Triple buffering. Unlimited frame rate + no tearing.\nrelaxed - Same as fifo but allows tearing when below the monitors refresh rate."),
        'type': 'combo',
        'options': [disabled_text, 'fifo', 'immediate', 'mailbox', 'relaxed'],
        'default': disabled_text
    })


    # 13. NUMA node
    numa_ids = sorted(numa_nodes.keys())
    numa_options = [disabled_text] + numa_ids if len(numa_ids) > 1 else [disabled_text]
    advanced_settings.append({
        'key': 'PW_CPU_NUMA_NODE_INDEX',
        'name': _("NUMA Node"),
        'description': _("NUMA node for CPU affinity. In multi-core systems, CPUs are split into NUMA nodes, each with its own local memory and cores. Binding a game to a single node reduces memory-access latency and limits costly core-to-core switches."),
        'type': 'combo',
        'options': numa_options,
        'default': disabled_text
    })

    return advanced_settings

# Keys that should be recognized as advanced settings
ADVANCED_SETTING_KEYS = [
    'PW_WINE_USE',
    'PW_PREFIX_NAME',
    'PW_VULKAN_USE',
    'PW_WINDOWS_VER',
    'WINEDLLOVERRIDES',
    'LAUNCH_PARAMETERS',
    'PW_WINE_CPU_TOPOLOGY',
    'PW_MESA_GL_VERSION_OVERRIDE',
    'PW_VKD3D_FEATURE_LEVEL',
    'PW_LOCALE_SELECT',
    'PW_MESA_VK_WSI_PRESENT_MODE',
    'PW_CPU_NUMA_NODE_INDEX',
]
