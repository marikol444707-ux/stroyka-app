#!/bin/bash
set -euo pipefail

cd /var/www/stroyka-app
git reset --hard HEAD
git pull --ff-only
echo "HEAD: $(git rev-parse --short HEAD)"
PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py
npm run build
systemctl restart stroyka
systemctl is-active --quiet stroyka
echo "Деплой завершён!"
