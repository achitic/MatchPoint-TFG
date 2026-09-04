#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
docker compose down
echo "MatchPoint se ha detenido correctamente."
