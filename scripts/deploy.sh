# расположен в: police-bot-prod/scripts/deploy.sh

#!/bin/bash

# Проверка переменных окружения
if [ -z "$TELEGRAM_TOKEN" ]; then
  echo "Ошибка: TELEGRAM_TOKEN не установлен"
  exit 1
fi

# Сборка и запуск контейнеров
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d