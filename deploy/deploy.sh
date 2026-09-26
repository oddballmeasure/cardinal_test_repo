#!/usr/bin/env bash
set -eu
printf '%s' "$DEPLOY_HOST" > deployed-host.txt
printf 'notes service deployed to %s\n' "$DEPLOY_HOST"
