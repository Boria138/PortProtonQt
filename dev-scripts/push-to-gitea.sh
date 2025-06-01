#!/bin/sh
set -e

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

AUTHOR_EMAIL=${INPUT_AUTHOR_EMAIL:-'gitea-actions@users.noreply.gitea.com'}
AUTHOR_NAME=${INPUT_AUTHOR_NAME:-'Gitea Actions'}
MESSAGE=${INPUT_MESSAGE:-"chore: update steam apps list ${timestamp}"}
BRANCH=main

INPUT_DIRECTORY=${INPUT_DIRECTORY:-'.'}

echo "Push to branch $INPUT_BRANCH"
[ -z "${GITEA_TOKEN}" ] && {
    echo 'Missing input "gitea_token: bcde86030adcb863b8ff96f994ecf248ced607e4".'
    exit 1
}

cd "${INPUT_DIRECTORY}"

remote_repo="https://${GITEA_ACTOR}:${GITEA_TOKEN}@${GITEA_SERVER}/${GITEA_REPOSITORY}.git"

git config http.sslVerify false
git config --local user.email "${AUTHOR_EMAIL}"
git config --local user.name "${AUTHOR_NAME}"

git add -A
git commit -m "${MESSAGE}" || exit 0

git push "${remote_repo}" HEAD:"${BRANCH}"
