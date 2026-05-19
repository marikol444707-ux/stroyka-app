#!/bin/bash
cd /var/www/stroyka-app
git reset --hard HEAD
git pull
npm run build
systemctl restart stroyka
echo "Деплой завершён!"
