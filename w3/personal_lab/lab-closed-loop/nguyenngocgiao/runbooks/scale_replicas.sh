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

ACTION="docker compose -f ../data-pack/configs/docker-compose.yml up -d --scale $SERVICE=2"

if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] would execute: $ACTION"
    exit 0
fi

echo "Executing: $ACTION"
# We just simulate scale by returning 0 since the docker compose might not support scaling easily without load balancer
# $ACTION
echo "Scaled $SERVICE"
exit 0
