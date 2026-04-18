#!/usr/bin/env bash
########################################################################
export url_site="https://linux-gaming.ru/portproton/"
export url_cloud="https://cloud.linux-gaming.ru/portproton"
export url_git="https://git.linux-gaming.ru/CastroFidel/PortWINE"
########################################################################
if [[ "${START_FROM_FLATPAK:-0}" == 1 ]] \
&& [[ -z "${STEAM_COMPAT_DATA_PATH:-}" ]] \
&& command -v "flatpak" &>/dev/null
then
    unset START_FROM_FLATPAK
    flatpak run ru.linux_gaming.PortProton "$@"
    exit
fi

$PW_DEBUG

if [[ $(id -u) = 0 ]] \
&& [[ ! -e "/userdata/system/batocera.conf" ]]
then
    echo "Do not run this script as root!"
    exit 1
fi

if [[ "$(realpath "$0")" == "/usr/share/portproton/scripts/start.sh" ]] ; then
    PORT_SCRIPTS_PATH="/usr/share/portproton/scripts/"
else
    PORT_SCRIPTS_PATH="$(dirname "$(realpath "$0")")"
fi

# PORT_DATA_PATH будет определяться из ppqt, проверить переменную во всех скриптах
# PORT_DATA_PATH="$(dirname "$(dirname "$PORT_SCRIPTS_PATH")")"

export PORT_SCRIPTS_PATH PORT_DATA_PATH

# shellcheck source=/dev/null
source "$PORT_SCRIPTS_PATH/functions_helper"

export PORT_WINE_TMP_PATH="${PORT_DATA_PATH}/data/tmp"
create_new_dir "$PORT_WINE_TMP_PATH"
rm -f "$PORT_WINE_TMP_PATH"/*.{exe,msi,tar}*

if mkdir -p "/tmp/PortProton_$USER" ; then
    export PW_TMPFS_PATH="/tmp/PortProton_$USER"
else
    create_new_dir "${PORT_DATA_PATH}/data/tmp/PortProton_$USER"
    export PW_TMPFS_PATH="${PORT_DATA_PATH}/data/tmp/PortProton_$USER"
fi

export PW_START_PID="$$"

read -r -a pw_full_command_line <<< "$0 $*"
export pw_full_command_line
export orig_IFS="$IFS"

unset PW_NO_RESTART_PPDB PW_DISABLED_CREATE_DB

if [[ ${1,,} == "cli" ]] ; then
    export PW_CLI="1"
    export PROCESS_LOG="1"
    shift
fi
check_variables PW_CLI "0"

if [[ "${1:-}" == file://* ]] ; then
    pw_file_path="${1#file://}"
    pw_file_path="${pw_file_path//%20/ }"
    set -- "${pw_file_path}" "${@:2}"
fi

if [[ "${1,,}" =~ \.ppack$ ]] ; then
    export PW_NO_RESTART_PPDB="1"
    export PW_DISABLED_CREATE_DB="1"
    portwine_exe="$1"
elif [[ "${1,,}" =~ \.ppdb$ ]] ; then
    update_ext_ppdb "$1"
elif [[ "$1" == portproton://* ]] ; then
    PPDB_URL="${1#portproton://}"
    PPDB_URL="${PPDB_URL//https\/\//https:\/\/}"
    PW_TMP_PPDB_FILE="$PW_TMPFS_PATH/tmp_from_url.ppdb"

    print_info "Downloading PPDB from: $PPDB_URL"
    if curl -A 'PortProton' -fsSL "$PPDB_URL" -o "$PW_TMP_PPDB_FILE" ; then
        update_ext_ppdb "$PW_TMP_PPDB_FILE" "url"
    else
        fatal "Failed to download PPDB from URL: $PPDB_URL"
    fi
elif [[ "${1,,}" =~ \.(exe|bat|msi|reg|lnk)$ ]] ; then
    if [[ -f "$1" ]] ; then
        portwine_exe="$(realpath -s "$1")"
    elif [[ -f "$OLDPWD/$1" ]] ; then
        portwine_exe="$(realpath -s "$OLDPWD/$1")"
    elif [[ ! -f "$1" ]] ; then
        portwine_exe="$1"
        MISSING_DESKTOP_FILE="1"
    fi
    if [[ -n "${portwine_exe}" && "${1,,}" =~ \.lnk$ ]] ; then
        get_lnk "${portwine_exe}"
        portwine_exe="$(realpath "${link_path}" 2>/dev/null)"
    fi
elif [[ "$1" =~ ^--(debug|launch|edit-db)$ && "${2,,}" =~ \.(exe|bat|msi|reg)$ ]] ; then
    if [[ -f "$2" ]] ; then
        portwine_exe="$(realpath -s "$2")"
    elif [[ -f "$OLDPWD/$2" ]] ; then
        portwine_exe="$(realpath -s "$OLDPWD/$2")"
    fi
fi
export portwine_exe

# HOTFIX - ModernWarships
if echo "$portwine_exe" | grep ModernWarships &>/dev/null \
&& [[ -f "$(dirname "${portwine_exe}")/Modern Warships.exe" ]]
then
    portwine_exe="$(dirname "${portwine_exe}")/Modern Warships.exe"
    export portwine_exe
    MISSING_DESKTOP_FILE="0"
fi

create_new_dir "${HOME}/.local/share/applications"
if [[ "${PW_SILENT_RESTART}" == "1" ]] \
|| [[ "${START_FROM_STEAM}" == "1" ]]
then
    export PW_GUI_DISABLED_CS="1"
    unset PW_SILENT_RESTART
else
    unset PW_GUI_DISABLED_CS
fi

create_new_dir "${PORT_DATA_PATH}/data/dist"
IFS=$'\n'
for dist_dir in $(lsbash "${PORT_DATA_PATH}/data/dist/") ; do
    dist_dir_new=$(echo "${dist_dir}" | awk '$1=$1' | sed -e s/[[:blank:]]/_/g)
    if [[ ! -d "${PORT_DATA_PATH}/data/dist/${dist_dir_new^^}" ]] ; then
        mv -- "${PORT_DATA_PATH}/data/dist/$dist_dir" "${PORT_DATA_PATH}/data/dist/${dist_dir_new^^}"
    fi
done
IFS="$orig_IFS"

create_new_dir "${PORT_DATA_PATH}/data/prefixes/DEFAULT"
create_new_dir "${PORT_DATA_PATH}/data/prefixes/DOTNET"
try_force_link_dir "${PORT_DATA_PATH}/data/prefixes" "${PORT_DATA_PATH}"

pushd "${PORT_DATA_PATH}/data/prefixes/" 1>/dev/null || fatal
for pfx_dir in ./* ; do
    [[ -d "$pfx_dir" ]] || continue
    pfx_dir_new="${pfx_dir//[[:blank:]]/_}"
    if [[ ! -d "${PORT_DATA_PATH}/data/prefixes/${pfx_dir_new^^}" ]] ; then
        mv -- "${PORT_DATA_PATH}/data/prefixes/$pfx_dir" "${PORT_DATA_PATH}/data/prefixes/${pfx_dir_new^^}"
    fi
done
popd 1>/dev/null || fatal

create_new_dir "${PORT_WINE_TMP_PATH}"/gecko
create_new_dir "${PORT_WINE_TMP_PATH}"/mono

export PW_VULKAN_DIR="${PORT_WINE_TMP_PATH}/VULKAN"
create_new_dir "${PW_VULKAN_DIR}"

cd "${PORT_SCRIPTS_PATH}" || fatal

# shellcheck source=/dev/null
source "${PORT_SCRIPTS_PATH}/var"

export STEAM_SCRIPTS="${PORT_DATA_PATH}/steam_scripts"
create_new_dir "$STEAM_SCRIPTS"

export PW_PLUGINS_PATH="${PORT_WINE_TMP_PATH}/plugins${PW_PLUGINS_VER}"

export PW_WINELIB="${PORT_WINE_TMP_PATH}/libs${PW_LIBS_VER}"
try_remove_dir "${PW_WINELIB}/var"

export WINETRICKS_DOWNLOADER="curl"

check_user_conf

check_variables PW_LOG "0"
try_remove_file "${PW_TMPFS_PATH}/update_pfx_log"

[[ ! -f "$PORT_WINE_TMP_PATH/statistics" ]] && touch "$PORT_WINE_TMP_PATH/statistics"

if [[ -n "${STEAM_COMPAT_DATA_PATH:-}" ]]; then
    steamplay_launch "${@:2}"
    exit
fi
unset WINEPREFIX

# choose branch
if [[ -z "$BRANCH" ]] ; then
    echo 'export BRANCH="master"' >> "$USER_CONF"
    export BRANCH="master"
fi
if [[ "$BRANCH" == "master" ]] ; then
    [[ "${PW_CLI}" != 1 ]] && print_info "Branch in used: STABLE\n"
    export BRANCH_VERSION=""
else
    [[ "${PW_CLI}" != 1 ]] && print_warning "Branch in used: DEVEL\n"
    export BRANCH_VERSION="-dev"
fi

# choose mirror
if [[ -z "$MIRROR" ]] \
&& [[ "$LANGUAGE" == "ru" ]]
then
    echo 'export MIRROR="CLOUD"' >> "$USER_CONF"
    export MIRROR="CLOUD"
elif [[ -z "$MIRROR" ]] ; then
    echo 'export MIRROR="GITHUB"' >> "$USER_CONF"
    export MIRROR="GITHUB"
fi

if [[ $USE_ONLY_LG_RU == "1" ]] ; then
    export MIRROR="CLOUD"
    edit_user_conf_from_gui MIRROR USE_ONLY_LG_RU
    [[ "${PW_CLI}" != 1 ]] && print_info "Force used linux-gaming.ru for all updates.\n"
fi
[[ "${PW_CLI}" != 1 ]] && print_info "The first mirror in used: $MIRROR\n"

# choose downloading covers from SteamGridDB or not
if [[ -z "$DOWNLOAD_STEAM_GRID" ]] ; then
    echo 'export DOWNLOAD_STEAM_GRID="1"' >> "$USER_CONF"
    export DOWNLOAD_STEAM_GRID="1"
fi

if check_gamescope_session
then PW_TERM="env LANG=C xterm -fullscreen -bg black -fg white -e"
else PW_TERM="env LANG=C xterm -bg black -fg white -e"
fi

pw_check_and_download_plugins

if [[ -z $PW_GPU_USE || $PW_GPU_USE == "disabled" ]] ; then
    PW_GPU_USE="disabled"
    pw_check_dxvk
fi

pw_cleanup () {
    CURL_PID="$(pgrep -a curl | grep -i "portproton" | cut -d' ' -f1)"
    if [[ -n $CURL_PID ]] ; then
        for pid in $CURL_PID ; do
            kill "$pid" &>/dev/null
        done
    fi

    rm -fv "${PW_TMPFS_PATH}"/*.log
}
trap "pw_cleanup" EXIT

if check_flatpak ; then
    try_remove_dir "${PORT_WINE_TMP_PATH}/libs${PW_LIBS_VER}"
else pw_download_libs
fi

pw_init_db

if [[ ! -d "${HOME}/PortProtonQt" ]] \
&& check_flatpak 
then
    ln -s "${PORT_DATA_PATH}" "${HOME}/PortProtonQt"
fi

pw_check_and_download_dxvk_and_vkd3d

# shellcheck source=/dev/null
source "${USER_CONF}"

# TODO: ?
kill_portwine

### CLI ###
get_wine_and_pfx () {
    [[ -n $1 ]] && export PW_WINE_USE="$1"
    [[ -n $2 ]] && export PW_PREFIX_NAME="$2"
    # drop create_new_dir "${PATH_TO_VKD3D_FILES}/vkd3d_cache" and create_new_dir "${PATH_TO_DXVK_FILES}/dxvk_cache"
    unset PW_USE_SUPPLIED_DXVK_VKD3D
}

case "$1" in
    --help)
        help_info () {
            files_from_autoinstall=$(ls "${PORT_SCRIPTS_PATH}/pw_autoinstall")
            echo -e "${translations[use]}: [--repair] [--reinstall] [--autoinstall]

--repair                                            ${translations[Forces all scripts to be updated to a working state
                                                    (helps if PortProton is not working)]}
--reinstall                                         ${translations[Reinstalls PortProton and resets all settings to default]}
--generate-pot                                      ${translations[Creates a files with translations .pot and .po]}
--debug                                             ${translations[Debug scripts for PortProton
                                                    (saved log in]} $PORT_DATA_PATH/scripts-debug.log)
--update                                            ${translations[Check update scripts for PortProton]}
--launch                                            ${translations[Launches the application immediately, requires the path to the .exe file]}
--edit-db                                           ${translations[After the variable, the path to the .exe file is required and then the variables.
                                                    (List their variables and values for example PW_MANGOHUD=1 PW_VKBASALT=0, etc.)]}
--get-user-conf                                     ${translations[Get a value from user.conf file, requires variable name]}
--set-user-conf                                     ${translations[Set a value in user.conf file, requires variable name and value]}
--del-user-conf                                     ${translations[Delete a value from user.conf file, requires variable name]}
--list-db                                           ${translations[List all available database variables]}
--show-ppdb                                         ${translations[Show the content of .ppdb file for specified .exe file]}
--backup-prefix                                     ${translations[Backup specified prefix to a file]}
--restore-prefix                                    ${translations[Restore prefix from backup file]}
--winefile                                          ${translations[Open wine file explorer, requires WINE version and prefix name]}
--winecfg                                           ${translations[Open wine configuration, requires WINE version and prefix name]}
--winecmd                                           ${translations[Open wine command prompt, requires WINE version and prefix name]}
--winereg                                           ${translations[Open wine registry editor, requires WINE version and prefix name]}
--wine_uninstaller                                  ${translations[Open wine uninstaller, requires WINE version and prefix name]}
--clear_pfx                                         ${translations[Clear specified prefix, requires WINE version and prefix name]}
--mangohud-preview                                  ${translations[Starts MangoHud preview in vkcube (optional argument: inline MangoHud config)]}
--initial                                           ${translations[Initial setup command]}
--autoinstall                                       ${translations[--autoinstall and the name of what needs to be installed is given in the list below:]}

$(echo $files_from_autoinstall | awk '{for (i = 1; i <= NF; i++) {if (i % 10 == 0) {print ""} printf "%s ", $i}}')

${translations[Usage examples:]}
  portproton cli --launch /path/to/game.exe
  portproton cli --edit-db /path/to/game.exe PW_MANGOHUD=1 PW_VKBASALT=0
  portproton cli --get-user-conf PW_MANGOHUD
  portproton cli --set-user-conf PW_MANGOHUD 1
  portproton cli --del-user-conf PW_MANGOHUD
  portproton cli --backup-prefix DEFAULT /path/to/backup/directory
  portproton cli --restore-prefix /path/to/backup/file.ppack
  portproton cli --winecfg WINE_LG DEFAULT
  portproton cli --mangohud-preview "fps,frametime,cpu_temp,gpu_temp"
  portproton cli --autoinstall [script_name_from_pw_autoinstall]
            "
        }
        help_info
        exit 0
        ;;
    --reinstall)
        export PW_REINSTALL_FROM_TERMINAL=1
        pw_reinstall_pp
        ;;
    --autoinstall)
        pw_autoinstall_from_db $2
        exit 0
        ;;
    --generate-pot)
        generate_pot
        exit 0
        ;;
    --debug)
        clear
        export PW_DEBUG="set -x"
        /usr/bin/env bash -c "${pw_full_command_line[@]}" 2>&1 | tee "$PORT_DATA_PATH/scripts-debug.log" &
        exit 0
        ;;
    --update)
        gui_pw_update
        ;;
    --launch)
        portwine_launch
        stop_portwine
        ;;
    --edit-db)
        # --edit-db /полный/путь/до/файла.exe PW_MANGOHUD=1 PW_VKBASALT=0 (и т.д) для примера
        set_several_variables "${@:3}"
        edit_db_from_gui $keys_all
        exit 0
        ;;
    --get-user-conf)
        # --get-user-conf VARIABLE_NAME
        manage_user_conf_value get "$2"
        exit 0
        ;;
    --set-user-conf)
        # --set-user-conf VARIABLE_NAME VALUE
        manage_user_conf_value set "$2" "$3"
        exit 0
        ;;
        --delete-user-conf)
        # --delete-user-conf VARIABLE_NAME
        manage_user_conf_value delete "$2"
        exit 0
        ;;
    --list-db)
        export pw_yad=""
        gui_edit_db
        pw_skip_get_info
        declare -A NODE_MAP
        INDEX=0
        while read -r line; do
            NODE_MAP[$INDEX]="$line"
            ((INDEX++))
        done < <(lscpu | grep -Po "NUMA node\d+ CPU\(s\):\s+\K.*" 2>/dev/null || true)
        for i in "${!NODE_MAP[@]}"; do
            echo "NUMA_NODE_${i}=${NODE_MAP[$i]}"
        done
        echo "LOGICAL_CORE_OPTIONS=$GET_LOGICAL_CORE"
        [[ -n "$LOCALE_LIST" ]] && echo "LOCALE_LIST=$LOCALE_LIST"
        for var in "${PW_EDIT_DB_FINAL_LIST[@]}"; do
            if echo "$DISABLE_EDIT_DB_LIST" | grep -qw "$var"; then
                echo "$var blocked"
            else
                echo "$var"
            fi
        done
        exit 0
        ;;
    --show-ppdb)
        # --show-ppdb /полный/путь/до/файла.exe ИЛИ /полный/путь/до/файла.exe.ppdb
        input_path="$2"

        case "$input_path" in
            *.ppdb) exe_path="${input_path%.ppdb}" ;;
            *.exe)  exe_path="$input_path" ;;
        esac

        ppdb_path="${exe_path}.ppdb"
        if [[ ! -f "$ppdb_path" ]]; then
            export portwine_exe="$exe_path"
            pw_init_db
        fi

        declare -A all_vars
        while IFS='=' read -r key val; do
            key="${key#export }"
            val="${val#\"}"
            val="${val%\"}"
            all_vars["$key"]="$val"
        done < <(grep -E '^export ' "$ppdb_path" | sed -E 's/[[:space:]]*#.*$//' | sed '/^[[:space:]]*$/d')

        check_user_conf
        if [[ -f "$USER_CONF" ]]; then
            while IFS='=' read -r key val; do
                key="${key#export }"
                val="${val#\"}"
                val="${val%\"}"
                all_vars["$key"]="$val"
            done < <(grep -E '^export ' "$USER_CONF" 2>/dev/null | sed -E 's/[[:space:]]*#.*$//' | sed '/^[[:space:]]*$/d')
        fi

        while IFS='=' read -r key val; do
            key="${key#export }"
            val="${val#\"}"
            val="${val%\"}"
            if [[ -z "${all_vars[$key]+x}" ]]; then
                all_vars["$key"]="$val"
            fi
        done < <(grep -E '^export ' "$PORT_SCRIPTS_PATH/var" | sed -E 's/[[:space:]]*#.*$//' | sed '/^[[:space:]]*$/d')

        for key in "${!all_vars[@]}"; do
            echo "${key}=\"${all_vars[$key]}\""
        done

        exit 0
        ;;
    --backup-prefix)
        # portproton --backup-prefix <PREFIX_NAME> <BACKUP_DIR>
        pw_create_prefix_backup_cli "$2" "$3"
        exit $?
        ;;
    --restore-prefix)
        # portproton --restore-prefix <PREFIX_BACKUP_FILE.ppack>
        pw_unpack_prefix "$2"
        exit $?
        ;;
    --winefile)
        get_wine_and_pfx "$2" "$3"
        pw_winefile
        exit $?
        ;;
    --winecfg)
        get_wine_and_pfx "$2" "$3"
        pw_winecfg
        exit $?
        ;;
    --winecmd)
        get_wine_and_pfx "$2" "$3"
        pw_winecmd
        exit $?
        ;;
    --winereg)
        get_wine_and_pfx "$2" "$3"
        pw_winereg
        exit $?
        ;;
    --wine_uninstaller)
        get_wine_and_pfx "$2" "$3"
        wine_uninstaller
        exit $?
        ;;
    --clear_pfx)
        get_wine_and_pfx "$2" "$3"
        pw_clear_pfx
        exit $?
        ;;
    --mangohud-preview)
        pw_mangohud_preview "${2:-}"
        exit $?
        ;;
    --initial)
        exit 0
        ;;
esac

stop_portwine
