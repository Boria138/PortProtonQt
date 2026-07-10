#!/usr/bin/env python3
"""Run PortProtonQt against a fake AppImage update server."""

import argparse
import configparser
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class UpdateHandler(http.server.BaseHTTPRequestHandler):
    """Serve fake update metadata and the new AppImage."""

    test_dir = Path()
    server_url = ""
    old_version = "0.1.12"
    new_version = "1.2.0"
    new_appimage_name = "PortProtonQt-1.2.0-x86_64.AppImage"

    def log_message(self, fmt, *args):
        print(f"[server] {fmt % args}")

    def do_GET(self):
        if self.path == "/check":
            self._send_json(self._check_payload())
        elif self.path.endswith(".zsync"):
            self._send_json(self._zsync_payload())
        elif self.path.startswith("/download/"):
            self._send_download()
        else:
            self.send_error(404)

    def _check_payload(self) -> dict:
        zsync_url = f"{self.server_url}/{self.new_appimage_name}.zsync"
        return {
            "update_available": True,
            "new_version": self.new_version,
            "update_info": f"zsync|{zsync_url}",
            "url": zsync_url,
            "new_file_info": {
                "digest_zsync": "fake_digest_abc123",
                "zsync_more_length": 0,
                "blocksize": 0,
                "length": 0,
            },
        }

    def _zsync_payload(self) -> dict:
        return {
            "zsync_version": 1,
            "filename": self.new_appimage_name,
            "urls": [f"{self.server_url}/download/{self.new_appimage_name}"],
            "blocksize": 0,
            "length": 0,
        }

    def _send_download(self) -> None:
        filename = self.path.split("/download/", 1)[1]
        path = self.test_dir / filename
        if not path.exists():
            self.send_error(404, f"Not found: {filename}")
            return
        self._send_file(path)

    def _send_json(self, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_version", nargs="?", default="0.1.12")
    parser.add_argument("new_version", nargs="?", default="1.2.0")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--version", default=None,
                        help="Simulate current app version (e.g. --version 0.1.8)")
    return parser.parse_args()


def write_appimage(path: Path, version: str, updated: bool) -> None:
    marker = "UPDATED test AppImage" if updated else "test AppImage"
    path.write_text(
        "#!/bin/sh\n"
        f"echo 'PortProtonQt v{version} ({marker})'\n"
        f"echo 'VERSION={version}'\n"
        "echo 'APPIMAGE_UPDATE_TEST_MARKER'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def write_config(config_dir: Path, portdata_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    portdata_dir.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config["PortProton"] = {"portdata_path": str(portdata_dir)}
    config["Downloads"] = {
        "auto_appimage_updates": "True",
        "disable_runtime_download": "True",
    }
    with open(config_dir / "PortProtonQt.conf", "w", encoding="utf-8") as config_file:
        config.write(config_file)


def write_fake_tool(bin_dir: Path, server_url: str, new_appimage_name: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    tool = bin_dir / "appimageupdatetool"
    tool.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "import urllib.request\n"
        f"SERVER = {server_url!r}\n"
        f"NEW_NAME = {new_appimage_name!r}\n"
        "\n"
        "def parse_args(argv):\n"
        "    action = None\n"
        "    appimage = None\n"
        "    i = 1\n"
        "    while i < len(argv):\n"
        "        if argv[i] == '-j':\n"
        "            action = 'check'\n"
        "        elif argv[i] == '-Or':\n"
        "            action = 'update'\n"
        "        elif argv[i] == '-u':\n"
        "            i += 1\n"
        "        elif argv[i].endswith('.AppImage'):\n"
        "            appimage = argv[i]\n"
        "        i += 1\n"
        "    return action, appimage\n"
        "\n"
        "def check_update():\n"
        "    response = urllib.request.urlopen(f'{SERVER}/check', timeout=10)\n"
        "    data = json.loads(response.read())\n"
        "    print(json.dumps(data))\n"
        "    sys.stderr.write(f'Update available: {data.get(\"new_version\", \"?\")}\\n')\n"
        "    return 1 if data.get('update_available') else 0\n"
        "\n"
        "def apply_update(appimage):\n"
        "    url = f'{SERVER}/download/{NEW_NAME}'\n"
        "    print(f'Downloading update from {url}...')\n"
        "    response = urllib.request.urlopen(url, timeout=60)\n"
        "    data = response.read()\n"
        "    print(f'Downloaded {len(data)} bytes')\n"
        "    print('Applying update...')\n"
        "    tmp = appimage + '.tmp'\n"
        "    with open(tmp, 'wb') as out_file:\n"
        "        out_file.write(data)\n"
        "    os.chmod(tmp, 0o755)\n"
        "    os.replace(tmp, appimage)\n"
        "    print('Done.')\n"
        "    return 0\n"
        "\n"
        "def main():\n"
        "    action, appimage = parse_args(sys.argv)\n"
        "    if not appimage or not os.path.isfile(appimage):\n"
        "        sys.stderr.write(f'Error: AppImage not found: {appimage}\\n')\n"
        "        return 2\n"
        "    if action == 'check':\n"
        "        return check_update()\n"
        "    if action == 'update':\n"
        "        return apply_update(appimage)\n"
        "    sys.stderr.write('Unknown action\\n')\n"
        "    return 2\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)
    return tool


def start_server(args: argparse.Namespace, test_dir: Path, new_appimage_name: str):
    server = http.server.HTTPServer(("127.0.0.1", args.port), UpdateHandler)
    server_url = f"http://127.0.0.1:{server.server_port}"
    UpdateHandler.test_dir = test_dir
    UpdateHandler.server_url = server_url
    UpdateHandler.old_version = args.old_version
    UpdateHandler.new_version = args.new_version
    UpdateHandler.new_appimage_name = new_appimage_name
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server_url


def python_command() -> str:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_gui(env: dict[str, str]) -> int:
    proc = subprocess.Popen(
        [python_command(), "-m", "portprotonqt.app"],
        cwd=str(REPO_ROOT),
        env=env,
    )
    return proc.wait()


def main() -> None:
    args = parse_args()
    if args.version:
        args.old_version = args.version
    test_dir = Path(tempfile.mkdtemp(prefix="ppqt-appimage-update-"))
    bin_dir = test_dir / "bin"
    config_dir = test_dir / "config"
    cache_dir = test_dir / "cache"
    data_dir = test_dir / "data"
    portdata_dir = test_dir / "portdata"
    old_appimage = test_dir / f"PortProtonQt-{args.old_version}-x86_64.AppImage"
    new_appimage_name = f"PortProtonQt-{args.new_version}-x86_64.AppImage"
    new_appimage = test_dir / new_appimage_name
    server = None

    try:
        write_config(config_dir, portdata_dir)
        write_appimage(old_appimage, args.old_version, updated=False)
        write_appimage(new_appimage, args.new_version, updated=True)
        server, server_url = start_server(args, test_dir, new_appimage_name)
        tool_path = write_fake_tool(bin_dir, server_url, new_appimage_name)

        env = os.environ.copy()
        env["APPIMAGE"] = str(old_appimage)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["XDG_CONFIG_HOME"] = str(config_dir)
        env["XDG_CACHE_HOME"] = str(cache_dir)
        env["XDG_DATA_HOME"] = str(data_dir)
        env["PORTPROTONQT_VERSION"] = args.old_version

        print("=== AppImage update GUI test ===")
        print(f"Test dir       : {test_dir}")
        print(f"Old AppImage   : {old_appimage}")
        print(f"New AppImage   : {new_appimage}")
        print(f"Fake tool      : {tool_path}")
        print(f"HTTP server    : {server_url}")
        print(f"Config         : {config_dir / 'PortProtonQt.conf'}")
        print("")
        print("In GUI: wait for the update dialog, press Update, watch progress.")
        print("After success, old AppImage should be replaced by the new file.")
        print("")

        raise SystemExit(run_gui(env))
    finally:
        if server is not None:
            server.shutdown()
        if args.keep:
            print(f"Keeping test dir: {test_dir}")
        else:
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
