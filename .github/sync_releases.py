#!/usr/bin/env python3
import urllib.request
import json
import subprocess
import os
import sys

GITEA_API_URL = "https://git.linux-gaming.ru/api/v1/repos/Linux-Gaming/PortProtonQt/releases"

def get_gitea_releases():
    req = urllib.request.Request(
        GITEA_API_URL, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def get_github_releases():
    try:
        res = subprocess.run(
            ["gh", "release", "list", "--limit", "1000", "--json", "tagName"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(res.stdout)
        return {item["tagName"] for item in data}
    except Exception as e:
        print(f"Error fetching GitHub releases: {e}", file=sys.stderr)
        return set()

def download_file(url, local_filename):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as resp, open(local_filename, "wb") as f:
        while True:
            chunk = resp.read(16 * 1024 * 1024)  # 16MB buffer
            if not chunk:
                break
            f.write(chunk)

def main():
    print("Fetching releases from Gitea...")
    try:
        gitea_releases = get_gitea_releases()
    except Exception as e:
        print(f"Failed to fetch Gitea releases: {e}", file=sys.stderr)
        sys.exit(1)

    print("Fetching releases from GitHub...")
    github_releases = get_github_releases()

    # Process releases from oldest to newest to preserve chronological order on GitHub
    gitea_releases.reverse()

    for release in gitea_releases:
        tag = release["tag_name"]
        if tag in github_releases:
            print(f"Release '{tag}' already exists on GitHub. Skipping.")
            continue

        print(f"Syncing release '{tag}'...")
        name = release.get("name") or tag
        body = release.get("body") or ""
        prerelease = release.get("prerelease", False)
        draft = release.get("draft", False)
        
        downloaded_files = []
        assets = release.get("assets", [])
        for asset in assets:
            asset_name = asset["name"]
            download_url = asset["browser_download_url"]
            print(f"  Downloading asset: {asset_name}...")
            try:
                download_file(download_url, asset_name)
                downloaded_files.append(asset_name)
            except Exception as e:
                print(f"  Failed to download asset {asset_name}: {e}", file=sys.stderr)

        # Create release on GitHub via GitHub CLI
        cmd = ["gh", "release", "create", tag]
        cmd.extend(downloaded_files)
        cmd.extend(["--title", name, "--notes", body])
        
        if prerelease:
            cmd.append("--prerelease")
        if draft:
            cmd.append("--draft")

        print(f"  Creating GitHub release for '{tag}'...")
        try:
            subprocess.run(cmd, check=True)
            print(f"  Successfully synced release '{tag}'!")
        except subprocess.CalledProcessError as e:
            print(f"  Failed to create GitHub release '{tag}': {e}", file=sys.stderr)
        
        # Clean up downloaded assets
        for file in downloaded_files:
            try:
                os.remove(file)
            except OSError:
                pass

if __name__ == "__main__":
    main()
