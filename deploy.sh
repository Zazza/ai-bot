#!/bin/bash
# Деплой ai-bot на VPS
# Использование: ./deploy.sh [--build]

set -e
cd "$(dirname "$0")"

NO_CACHE=""
if [ "$1" = "--build" ]; then
    NO_CACHE="--no-cache"
fi

echo ">>> Pushing to origin..."
git push origin main

echo ">>> Deploying on VPS..."
ssh root@5.35.126.20 "cd /home/mashka/ai-bot && git pull && docker compose down && docker compose build $NO_CACHE && docker compose up -d"

echo ">>> Checking logs..."
sleep 3
ssh root@5.35.126.20 "cd /home/mashka/ai-bot && docker compose logs bot --tail 10"

echo ">>> Done!"
