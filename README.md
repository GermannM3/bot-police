# расположен в корне: police-bot-prod/README.md

# Police Bot Production

Производственная версия Telegram-бота для модерации чатов.

## Описание

Проект реализован с использованием FastAPI, Gunicorn с UvicornWorker, и Telegram API. В проекте также настроено кэширование через Redis, мониторинг с Prometheus и обратный прокси Nginx.

## Структура проекта

docker-compose -f docker-compose.prod.yml up --build
