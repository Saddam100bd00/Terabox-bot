import asyncio
import logging
from aiogram import Bot, Dispatcher
from fastapi import FastAPI
import uvicorn

from app.core.config import BOT_TOKEN
from app.core.database import init_db
from app.handlers import user, download

# Setup Logging
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# Include Routers
dp.include_router(user.router)
dp.include_router(download.router)

# Web Server for Render/VPS Health Check
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "TeraBox Bot is Running successfully 🚀"}

async def start_bot():
    await init_db()
    logging.info("Starting Telegram Bot Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Create background loop for Bot
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    
    # Run FastAPI server for Docker/Render port binding
    uvicorn.run(app, host="0.0.0.0", port=8000)
