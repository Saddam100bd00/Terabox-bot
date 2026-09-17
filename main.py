import os
import time
import asyncio
import logging
import re
import httpx
from datetime import datetime
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Aiogram Imports
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties

# Database Imports (Added 'select' for correct DB queries)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# FastAPI & Uvicorn for Render Web Server
from fastapi import FastAPI
import uvicorn

# ================= 1. CONFIGURATION =================
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "Premium_buy_admin")
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
Send me any valid TeraBox share link, and I will download the video/file for you directly to Telegram.

🆓 **Free Users:** 5 Downloads/Day
👑 **Premium Users:** Unlimited + Queue Priority

👨‍💻 Support: @{support}
"""

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Download", callback_data="menu_download"),
         InlineKeyboardButton(text="👤 My Account", callback_data="menu_account")],
        [InlineKeyboardButton(text="💬 Support", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")]
    ])

def download_action(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Start Download", callback_data=f"start_dl|{url}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action")]
    ])

# ================= 4. TERABOX SERVICE =================
TERABOX_REGEX = re.compile(r'https?://(?:www\.)?(terabox\.com|teraboxapp\.com|terasharelink\.com|1024tera\.com|teraboxlink\.com)/[a-zA-Z0-9_-]+')

async def is_valid_terabox_link(url: str) -> bool:
    return bool(TERABOX_REGEX.search(url))

async def fetch_media_info(url: str):
    """
    (MOCK IMPLEMENTATION) - Replace with real TeraBox API later.
    """
    return {
        "ok": True,
        "file_name": "Terabox_Video.mp4",
        "file_size": 50 * 1024 * 1024, # 50 MB Example
        "download_url": "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_50mb.mp4",
        "is_video": True
    }

# ================= 5. DOWNLOADER SERVICE =================
def format_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size} B"

async def generate_progress_bar(current, total, start_time):
    percent = int(current * 100 / total) if total > 0 else 0
    filled = '█' * (percent // 10)
    empty = '░' * (10 - (percent // 10))
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    return f"⬇️ **Downloading...**\n━━━━━━━━━━━━━━ {percent}%\n{filled}{empty}\n\n📦 {format_size(current)} / {format_size(total)}\n⚡ Speed: {format_size(speed)}/s\n⏳ Remaining: {int(eta)} sec"

async def download_and_send(bot: Bot, chat_id: int, url: str, file_name: str, status_msg: types.Message):
    local_path = os.path.join(DOWNLOAD_DIR, file_name)
    start_time = time.time()
    last_update = 0

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as response:
                total_size = int(response.headers.get("content-length", 0))
                with open(local_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes():
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
        await bot.send_document(chat_id, document=file, caption=f"✅ **Downloaded:** {file_name}")
        await bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        await bot.edit_message_text(f"❌ **Error occurred:** {str(e)}", chat_id, status_msg.message_id)
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

# ================= 6. TELEGRAM HANDLERS =================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Fixed DB Error: Now correctly checks if user exists before saving
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
            
    await message.answer(WELCOME_TEXT.format(support=SUPPORT_USERNAME), reply_markup=main_menu())

# Added Missing Button Handlers
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
        return await message.answer("❌ **Invalid Link!**\nPlease send a valid TeraBox share link.")

    msg = await message.answer("🔍 **Validating and Analyzing Media... ⏳**")
    info = await fetch_media_info(url)
    
    if not info.get("ok"):
        return await msg.edit_text("❌ Failed to fetch file information.")

    if info["file_size"] > MAX_FILE_SIZE_BYTES:
        return await msg.edit_text("❌ **File Too Large!**\nMaximum supported file size is 2GB.")

    text = f"✅ **Media Found!**\n🎬 Name: `{info['file_name']}`\n📦 Size: {format_size(info['file_size'])}\n\nChoose an option below:"
    await msg.edit_text(text, reply_markup=download_action(info['download_url']))

@dp.callback_query(F.data.startswith("start_dl|"))
async def process_download(callback: types.CallbackQuery):
    url = callback.data.split("|")[1]
    await callback.message.edit_text("⏳ **Download Started...**")
    asyncio.create_task(download_and_send(bot, callback.message.chat.id, url, "TeraBox_File.mp4", callback.message))
    await callback.answer()

@dp.callback_query(F.data == "cancel_action")
async def cancel_dl(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Action Cancelled.")
    await callback.answer()

# ================= 7. FASTAPI SERVER FOR RENDER =================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logging.info("Initializing Database...")
    await init_db()
    logging.info("Starting Telegram Bot...")
    asyncio.create_task(dp.start_polling(bot))
    yield
    # --- Shutdown ---
    logging.info("Shutting down bot...")
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "TeraBox Premium Bot is Running perfectly! 🚀"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
