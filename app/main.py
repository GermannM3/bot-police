from fastapi import FastAPI
from telegram.ext import Application
from app.core.bot import PoliceBot
from app.services.cache import init_redis

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_redis()
    bot = PoliceBot()
    app.telegram_app = await bot.create_app()
    await app.telegram_app.initialize()
    await app.telegram_app.start()
    # Запускаем получение обновлений (polling)
    await app.telegram_app.updater.start_polling()

@app.on_event("shutdown")
async def shutdown():
    # Останавливаем polling при отключении приложения
    await app.telegram_app.updater.stop()
    await app.telegram_app.stop()
    await app.telegram_app.shutdown()

@app.get("/health")
async def health_check():
    return {"status": "ok"}
