# расположен в: police-bot-prod/app/services/cache.py

from redis import asyncio as aioredis
from app.config import Config

redis_client = None

async def init_redis():
    global redis_client
    redis_client = await aioredis.from_url(Config.REDIS_URL, decode_responses=True)

async def get_cache(key):
    return await redis_client.get(key)

async def set_cache(key, value, expire=3600):
    await redis_client.set(key, value, ex=expire)