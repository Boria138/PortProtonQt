"""Debug utilities package for system information and log management."""

from portprotonqt.debug_utils.gpu_info import (
    get_gpu_list,
    get_selectable_gpu_entries,
    get_selectable_gpu_list,
    get_cached_vk_gpu_info,
    get_graphics_info_detailed,
)

from portprotonqt.debug_utils.system_info import (
    get_os_info,
    get_cpu_info,
    get_ram_info,
    get_ram_info_detailed,
    get_desktop_environment,
    get_locale_info,
    get_locale_available,
    get_libc_version,
    get_program_bit_depth,
    get_filesystem_info,
    generate_system_info,
)

from portprotonqt.debug_utils.game_debug import (
    get_ppdb_content,
    get_user_overrides,
    get_prefix_name,
    get_winetricks_log,
)

from portprotonqt.debug_utils.env_utils import (
    get_file_content,
    get_portproton_env,
    get_runtime_status,
    get_vulkan_use_info,
    get_wine_version,
    get_d3d_extras_status,
)

from portprotonqt.debug_utils.log_processor import (
    process_portproton_log,
)

from portprotonqt.debug_utils.debug_log_manager import (
    DebugLogManager,
)

from portprotonqt.debug_utils.xorg_utils import (
    get_xorg_version,
    decode_xorg_release,
)

__all__ = [
    "get_gpu_list",
    "get_selectable_gpu_entries",
    "get_selectable_gpu_list",
    "get_cached_vk_gpu_info",
    "get_graphics_info_detailed",
    "get_os_info",
    "get_cpu_info",
    "get_ram_info",
    "get_ram_info_detailed",
    "get_desktop_environment",
    "get_locale_info",
    "get_locale_available",
    "get_libc_version",
    "get_program_bit_depth",
    "get_filesystem_info",
    "get_ppdb_content",
    "get_user_overrides",
    "get_prefix_name",
    "get_winetricks_log",
    "generate_system_info",
    "get_file_content",
    "get_portproton_env",
    "get_runtime_status",
    "get_vulkan_use_info",
    "get_wine_version",
    "get_d3d_extras_status",
    "process_portproton_log",
    "DebugLogManager",
    "get_xorg_version",
    "decode_xorg_release",
]
