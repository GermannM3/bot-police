# Базовый образ
FROM python:3.10-slim-bullseye

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python-пакетов
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Запуск приложения через Gunicorn с UvicornWorker
CMD ["gunicorn", "--worker-class=uvicorn.workers.UvicornWorker", "--bind=0.0.0.0:8000", "app.main:app"]
