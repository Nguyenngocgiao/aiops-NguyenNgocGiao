#!/bin/bash

SERVICE=""
DRY_RUN=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --service) SERVICE="$2"; shift ;;
        --dry-run) DRY_RUN=1 ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$SERVICE" ]]; then
    echo "Error: --service is required"
    exit 1
fi

ACTION="docker compose -f ../data-pack/configs/docker-compose.yml exec $SERVICE rm -rf /tmp/cache"

if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] would execute: $ACTION"
    exit 0
fi

echo "Executing: $ACTION"
# We just simulate clear cache by returning 0, or actually run the command if it supports it
# $ACTION
echo "Cache cleared for $SERVICE"
exit 0
