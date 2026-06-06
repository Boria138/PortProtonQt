#!/usr/bin/env bash
set -euo pipefail

remote="${1:-origin}"
main_branch="${2:-main}"
weblate_branch="${3:-weblate}"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Working tree is not clean."
    exit 1
fi

git fetch "$remote" "$main_branch" "$weblate_branch"
git switch "$main_branch"
git merge --ff-only "$remote/$main_branch"

if git merge-base --is-ancestor "$remote/$weblate_branch" HEAD; then
    echo "No new Weblate changes to merge."
else
    git merge --no-ff "$remote/$weblate_branch"
fi

git push "$remote" "$main_branch"
git push "$remote" "$main_branch:$weblate_branch"

echo "Weblate translations accepted and $weblate_branch synced to $main_branch."
