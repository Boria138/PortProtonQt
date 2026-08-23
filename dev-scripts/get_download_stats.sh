#!/bin/bash
set -euo pipefail

GITHUB_REPOS=("Boria138/PortProtonQt" "linux-gaming-ru/PortProtonQt")
GITEA_REPO="Linux-Gaming/PortProtonQt"
GITEA_URL="https://git.linux-gaming.ru"

jq_total='[.[].assets[] | select(.name | test("\\.(zsync|sha256)$|steam-compat") | not) | .download_count] | add // 0'

echo "=== PortProtonQt Download Stats ==="
echo

echo "--- GitHub (${GITHUB_REPOS[*]}) ---"
GH_RAW=$(for repo in "${GITHUB_REPOS[@]}"; do
    curl -sf "https://api.github.com/repos/${repo}/releases?per_page=100"
done | jq -s 'add')
GH_COUNT=$(echo "$GH_RAW" | jq "$jq_total")
GH_RELEASES=$(echo "$GH_RAW" | jq 'length')
echo "Releases: $GH_RELEASES"
echo "Total downloads: $GH_COUNT"
echo
echo "Per release:"
echo "$GH_RAW" | jq -r '.[] | "\n  \(.tag_name) (\(.published_at)):" as $header | $header, (.assets[] | select(.name | test("\\.(zsync|sha256)$|steam-compat") | not) | "    \(.name): \(.download_count)")'
echo

echo "--- Gitea (${GITEA_REPO}) ---"
GIT_RAW=$(curl -sf "${GITEA_URL}/api/v1/repos/${GITEA_REPO}/releases?limit=50")
GIT_COUNT=$(echo "$GIT_RAW" | jq "$jq_total")
GIT_RELEASES=$(echo "$GIT_RAW" | jq 'length')
echo "Releases: $GIT_RELEASES"
echo "Total downloads: $GIT_COUNT"
echo
echo "Per release:"
echo "$GIT_RAW" | jq -r '.[] | "\n  \(.tag_name) (\(.created_at)):" as $header | $header, (.assets[] | select(.name | test("\\.(zsync|sha256)$|steam-compat") | not) | "    \(.name): \(.download_count)")'
echo

TOTAL=$((GH_COUNT + GIT_COUNT))
echo "========================"
echo "GitHub total:  $GH_COUNT"
echo "Gitea total:   $GIT_COUNT"
echo "Grand total:   $TOTAL"
echo
echo "--- Top downloads (by file) ---"
jq_filter_top='[.[].assets[] | select(.name | test("\\.(zsync|sha256)$|steam-compat") | not)] | group_by(.name) | map({name: .[0].name, total: (map(.download_count) | add)}) | sort_by(-.total) | .[:15] | .[] | "  \(.total)\t\(.name)"'
echo "GitHub:"
echo "$GH_RAW" | jq -r "$jq_filter_top"
echo
echo "Gitea:"
echo "$GIT_RAW" | jq -r "$jq_filter_top"
echo
echo "--- Top downloads (by type) ---"
jq_type='[.[].assets[] | select(.name | test("\\.(zsync|sha256)$|steam-compat") | not)] | map({type: (.name | split(".") | last | if test("^AppImage$") then "AppImage" elif test("^deb$") then "deb" elif test("^rpm$") then "rpm" elif test("^zst$") then "pkg.tar.zst" else "other" end), downloads: .download_count}) | group_by(.type) | map({type: .[0].type, total: (map(.downloads) | add)}) | sort_by(-.total) | .[] | "  \(.type): \(.total)"'
echo "GitHub:"
echo "$GH_RAW" | jq -r "$jq_type"
echo
echo "Gitea:"
echo "$GIT_RAW" | jq -r "$jq_type"

if [[ "${CI:-}" != "true" ]]; then
    echo
    echo "Local run: README update and commit skipped"
    exit 0
fi

sed -i "s|-[0-9]*-green?style=flat-square|-$TOTAL-green?style=flat-square|g" README.md README.ru.md
echo
echo "Badge updated: $TOTAL"

git diff --quiet README.md README.ru.md && { echo "No changes to commit"; exit 0; }

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

git config http.sslVerify false
git config --local user.email "gitea-actions@users.noreply.gitea.com"
git config --local user.name "Gitea Actions"

git add README.md README.ru.md
git commit -m "chore: download stats ${timestamp}"
remote_repo="https://${GITEA_ACTOR}:${GITEA_TOKEN}@${GITEA_SERVER}/${GITEA_REPOSITORY}.git"
git push "${remote_repo}" HEAD:main
echo "Pushed to Gitea"
