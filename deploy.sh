#!/bin/bash
cd /var/www/stroyka-app
git reset --hard HEAD
git pull
npm run build
sed -i 's/"user": "nikolas"/"user": "stroyka"/g' /var/www/stroyka-app/backend/main.py
sed -i 's/"password": "password"/"password": "password123"/g' /var/www/stroyka-app/backend/main.py
systemctl restart stroyka
echo "Деплой завершён!"
