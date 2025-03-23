import os
from pathlib import Path
from datetime import datetime

try:
    import vdf
except ImportError:
    print("Установите библиотеку vdf: pip install vdf")
    exit(1)

def get_steam_libs(steam_dir):
    libs = set()
    libs_vdf = steam_dir / "steamapps/libraryfolders.vdf"
    
    try:
        with open(libs_vdf, 'r', encoding='utf-8') as f:
            data = vdf.load(f)['libraryfolders']
            for k in data:
                if k.isdigit() and (path := Path(data[k]['path'])):
                    libs.add(path)
    except Exception as e:
        print(f"Ошибка чтения libraryfolders.vdf: {e}")
    
    libs.add(steam_dir)
    return libs

def get_playtime_data(steam_home):
    userdata_dir = steam_home / "userdata"
    play_data = {}

    if not userdata_dir.exists():
        return play_data

    for user_dir in userdata_dir.iterdir():
        localconfig = user_dir / "config/localconfig.vdf"
        if not localconfig.exists():
            continue

        try:
            with open(localconfig, 'r', encoding='utf-8') as f:
                data = vdf.load(f)['UserLocalConfigStore']
                apps = data.get('Software', {}).get('Valve', {}).get('Steam', {}).get('apps', {})

                for appid_str, info in apps.items():
                    try:
                        appid = int(appid_str)
                        last_played = int(info.get('LastPlayed', 0))  # Преобразование в int
                        playtime = int(info.get('Playtime', 0))        # Преобразование в int
                        play_data[appid] = (last_played, playtime)
                    except (ValueError, TypeError) as e:
                        print(f"Ошибка обработки данных для appid {appid_str}: {e}")

        except Exception as e:
            print(f"Ошибка чтения {localconfig}: {e}")

    return play_data

def format_time(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}ч {mins}м" if hours > 0 else f"{mins}м"

def main():
    blacklist_appids = {
        1161040, 1826330, 1493710, 
        1070560, 1391110, 1628350
    }

    steam_home = Path.home() / ".local/share/Steam"
    if not steam_home.exists():
        steam_home = Path.home() / ".steam/steam"  # Проверка альтернативного пути
    if not steam_home.exists():
        print("Каталог Steam не найден!")
        return

    play_data = get_playtime_data(steam_home)
    games = []
    
    for lib in get_steam_libs(steam_home):
        steamapps = lib / "steamapps"
        if not steamapps.exists():
            continue
            
        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                with open(manifest, 'r', encoding='utf-8') as f:
                    app = vdf.load(f)['AppState']
                
                appid = int(app.get('appid', 0))
                if appid in blacklist_appids:
                    continue
                
                if (game_dir := steamapps / "common" / app.get('installdir', '')).exists():
                    last_played, playtime = play_data.get(appid, (0, 0))
                    games.append((app.get('name', f"Unknown ({appid})"), appid, last_played, playtime))
                    
            except Exception as e:
                print(f"Ошибка в {manifest.name}: {e}")

    for name, appid, last_played, playtime in sorted(games, key=lambda x: x[0]):
        last_played_str = datetime.fromtimestamp(last_played).strftime("%Y-%m-%d %H:%M") if last_played else "Никогда"
        print(f"{name} ({appid})")
        print(f"├─ Последний запуск: {last_played_str}")
        print(f"└─ Общее время: {format_time(playtime)}\n")

if __name__ == "__main__":
    main()
