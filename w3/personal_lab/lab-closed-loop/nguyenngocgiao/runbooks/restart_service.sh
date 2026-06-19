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

# The service name coming from prometheus might have "ronki-" prefix depending on how docker compose names them or we can just use the name directly.
# Wait, docker compose service names in data-pack/configs/docker-compose.yml are frontend, payment-svc, etc.
ACTION="docker compose -f ../data-pack/configs/docker-compose.yml restart $SERVICE"

if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY-RUN] would execute: $ACTION"
    exit 0
fi

echo "Executing: $ACTION"
$ACTION
exit $?
