import os
import time
import httpx
from aiogram import Bot
from aiogram.types import Message
from app.core.config import DOWNLOAD_DIR

def format_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

async def generate_progress_bar(current, total, start_time, action="Downloading"):
    percent = int(current * 100 / total)
    filled = '█' * (percent // 10)
    empty = '░' * (10 - (percent // 10))
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    return f"""
⬇️ **{action}...**
━━━━━━━━━━━━━━ {percent}%
{filled}{empty}

📦 {format_size(current)} / {format_size(total)}
⚡ Speed: {format_size(speed)}/s
⏳ Remaining: {int(eta)} sec
    """

async def download_and_send(bot: Bot, chat_id: int, url: str, file_name: str, status_msg: Message):
    local_path = os.path.join(DOWNLOAD_DIR, file_name)
    start_time = time.time()
    last_update = 0

    try:
        # 1. Download File
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as response:
                total_size = int(response.headers.get("content-length", 0))
                with open(local_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update Progress every 3 seconds to avoid FloodWait
                        if time.time() - last_update > 3:
                            bar = await generate_progress_bar(downloaded, total_size, start_time, "Downloading")
                            await bot.edit_message_text(bar, chat_id, status_msg.message_id)
                            last_update = time.time()

        # 2. Upload to Telegram
        await bot.edit_message_text("📤 **Uploading to Telegram... Please wait.**", chat_id, status_msg.message_id)
        from aiogram.types import FSInputFile
        file = FSInputFile(local_path)
        await bot.send_document(chat_id, document=file, caption=f"✅ **Downloaded:** {file_name}")
        await bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        await bot.edit_message_text(f"❌ **Error occurred:** {str(e)}", chat_id, status_msg.message_id)
    finally:
        # File Cleanup
        if os.path.exists(local_path):
            os.remove(local_path)
