#!/usr/bin/env bash
set -euo pipefail

cr=$(printf "\r")
status=0

for file in "$@"; do
    IFS= read -r first_line < "$file" || true

    case "$first_line" in
        "#!"*"$cr")
            echo "$file: trailing <CR> in interpreter: $first_line"
            status=1
            continue
            ;;
    esac

    if ! bash -n "$file"; then
        echo "$file: bash -n syntax check failed"
        status=1
    fi
done

exit "$status"
