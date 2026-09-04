#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Falta Docker. Instala Docker Desktop o Docker Engine y vuelve a intentarlo."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker no esta iniciado. Arrancalo y vuelve a intentarlo."
  exit 1
fi

echo "Preparando MatchPoint. La primera vez puede tardar varios minutos..."
docker compose up --build -d --wait

url="http://localhost"
if command -v open >/dev/null 2>&1; then
  open "$url"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$url" >/dev/null 2>&1 &
else
  echo "Abre $url en tu navegador."
fi

echo "MatchPoint esta disponible en $url"
