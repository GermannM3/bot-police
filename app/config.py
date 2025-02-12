# расположен в: police-bot-prod/app/config.py

import os

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    MODEL_PATH = "cointegrated/rubert-tiny-toxicity"

config = Config()