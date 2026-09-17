import os
import time
import asyncio
import logging
import re
import httpx
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Aiogram Imports
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties

# Database Imports
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# FastAPI & Uvicorn for Render Web Server
from fastapi import FastAPI
import uvicorn

# ================= 1. CONFIGURATION =================
load_dotenv()

MAIN_BOT_TOKEN = "8500215028:AAGi3CUatThSfpfBW1fbyJN80T99fTmc7KE" 
OWNER_ID = 8701368956
OWNER_USERNAME = "Premium_buy_admin"

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///terabox.db")

try:
    MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_GB", 2)) * 1024 * 1024 * 1024
except:
    MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)

# ================= 2. DATABASE MODELS =================
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    username = Column(String, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ================= 3. TEXTS & KEYBOARDS =================
WELCOME_TEXT = """
✨ **Welcome to Premium TeraBox Downloader!** ✨
━━━━━━━━━━━━━━━━━━━━
Send me any valid TeraBox share link, and I will download the actual video/file for you directly to Telegram!

🆓 **Free Users:** 5 Downloads/Day
👑 **Premium Users:** Unlimited + Queue Priority

👨‍💻 Support: @{support}
"""

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Download", callback_data="menu_download"),
         InlineKeyboardButton(text="👤 My Account", callback_data="menu_account")],
        [InlineKeyboardButton(text="💬 Support", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

def download_action(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Start Download", callback_data=f"start_dl|{url}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action")]
    ])

# ================= 4. REAL TERABOX SCRAPER (RAPID API) =================
async def is_valid_terabox_link(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def find_link(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("http"):
                if k.lower() in ["url", "download_url", "downloadlink", "link", "fast download", "hd video", "dlink", "direct_link"]:
                    return v
        for k, v in obj.items():
            res = find_link(v)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_link(item)
            if res: return res
    return None

def find_title(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ["title", "file_name", "name", "filename"]:
                if isinstance(v, str) and v != "":
                    return v
        for k, v in obj.items():
            res = find_title(v)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_title(item)
            if res: return res
    return "TeraBox_Video.mp4"

async def fetch_media_info(url: str):
    """
    RapidAPI Terabox Downloader API
    """
    api_url = "https://terabox-downloader-direct-download-link-generator.p.rapidapi.com/fetch"
    
    payload = {"url": url}
    headers = {
        "x-rapidapi-key": "81612a03f7msh9343986d4544d64p1f3741jsn3e7c72cdbfc8",
        "x-rapidapi-host": "terabox-downloader-direct-download-link-generator.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Note: This specific API uses POST request
            response = await client.post(api_url, json=payload, headers=headers)
            
            if response.status_code != 200:
                logging.error(f"RapidAPI Error: {response.text}")
                return {"ok": False}
                
            data = response.json()
            
            download_url = find_link(data)
            file_name = find_title(data)

            if download_url:
                if not file_name.endswith(".mp4"):
                    file_name += ".mp4"
                    
                return {
                    "ok": True,
                    "file_name": file_name,
                    "file_size": 250 * 1024 * 1024, # Assuming ~250MB
                    "download_url": download_url,
                    "is_video": True
                }
    except Exception as e:
        logging.error(f"RapidAPI Failed: {e}")
            
    return {"ok": False}

# ================= 5. DOWNLOADER SERVICE =================
def format_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size} B"

async def generate_progress_bar(current, total, start_time):
    total = total if total > 0 else current + (10 * 1024 * 1024) 
    percent = int(current * 100 / total) if total > 0 else 0
    percent = min(percent, 100) 
    
    filled = '█' * (percent // 10)
    empty = '░' * (10 - (percent // 10))
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    
    return f"⬇️ **Downloading...**\n━━━━━━━━━━━━━━ {percent}%\n{filled}{empty}\n\n📦 Downloaded: {format_size(current)}\n⚡ Speed: {format_size(speed)}/s"

async def download_and_send(bot: Bot, chat_id: int, direct_url: str, file_name: str, status_msg: types.Message):
    local_path = os.path.join(DOWNLOAD_DIR, file_name)
    start_time = time.time()
    last_update = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=None, follow_redirects=True, headers=headers) as client:
            async with client.stream("GET", direct_url) as response:
                total_size = int(response.headers.get("content-length", 0))
                with open(local_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes(chunk_size=1024*1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if time.time() - last_update > 3:
                            bar = await generate_progress_bar(downloaded, total_size, start_time)
                            try:
                                await bot.edit_message_text(bar, chat_id, status_msg.message_id)
                            except: pass
                            last_update = time.time()

        await bot.edit_message_text("📤 **Uploading to Telegram... Please wait.**", chat_id, status_msg.message_id)
        
        file = FSInputFile(local_path)
        await bot.send_video(chat_id, video=file, caption=f"✅ **Downloaded Successfully!**\n🎬 `{file_name}`")
        await bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        await bot.edit_message_text(f"❌ **Download Error:** API is overloaded or link is dead.\nPlease try again later.", chat_id, status_msg.message_id)
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

# ================= 6. TELEGRAM HANDLERS =================
bot = Bot(token=MAIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    try:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if not user:
                new_user = User(telegram_id=message.from_user.id, username=message.from_user.username)
                session.add(new_user)
                await session.commit()
    except Exception as e:
        logging.error(f"Database error: {e}")
            
    await message.answer(WELCOME_TEXT.format(support=OWNER_USERNAME), reply_markup=main_menu())

@dp.callback_query(F.data == "menu_download")
async def handle_menu_download(callback: types.CallbackQuery):
    await callback.message.reply("🔗 **Please send me a valid TeraBox share link to download.**")
    await callback.answer()

@dp.callback_query(F.data == "menu_account")
async def handle_menu_account(callback: types.CallbackQuery):
    acc_text = f"👤 **Your Account Details**\n━━━━━━━━━━━━━━━━━━━━\n🆔 **ID:** `{callback.from_user.id}`\n⭐ **Status:** Free User\n\n_(Premium features and stats coming soon!)_"
    await callback.message.reply(acc_text)
    await callback.answer()

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    url = message.text
    if not await is_valid_terabox_link(url):
        return await message.answer("❌ **Invalid Link!**\nPlease send a valid link starting with http.")

    msg = await message.answer("🔍 **Validating and Analyzing Media with RapidAPI... ⏳**")
    
    info = await fetch_media_info(url)
    
    if not info.get("ok"):
        return await msg.edit_text("❌ **Failed to fetch video!**\nThe API server might be busy or the link is private/expired. Try again later.")

    safe_name = info['file_name'].replace('_', '\\_').replace('[', '').replace(']', '')
    text = f"✅ **Media Found!**\n🎬 Name: `{safe_name}`\n\nChoose an option below:"
    
    # Save the direct URL properly
    await msg.edit_text(text, reply_markup=download_action(url))

@dp.callback_query(F.data.startswith("start_dl|"))
async def process_download(callback: types.CallbackQuery):
    url = callback.data.split("|", 1)[1]
    await callback.message.edit_text("⏳ **Extracting direct link & Starting Download...**")
    
    info = await fetch_media_info(url)
    if not info.get("ok"):
        await callback.message.edit_text("❌ **Failed to start download!** Server busy.")
        return
        
    direct_url = info["download_url"]
    file_name = info["file_name"]
    
    asyncio.create_task(download_and_send(bot, callback.message.chat.id, direct_url, file_name, callback.message))
    await callback.answer()

@dp.callback_query(F.data == "cancel_action")
async def cancel_dl(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Action Cancelled.")
    await callback.answer()

# ================= 7. FASTAPI SERVER FOR RENDER =================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Initializing Database...")
    await init_db()
    logging.info("Starting Telegram Bot...")
    asyncio.create_task(dp.start_polling(bot))
    yield
    logging.info("Shutting down bot...")
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "TeraBox Premium Bot is Running perfectly! 🚀"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
