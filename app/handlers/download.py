from aiogram import Router, F, types
from app.services.terabox import is_valid_terabox_link, fetch_media_info
from app.services.downloader import download_and_send
from app.utils.keyboards import download_action
from app.utils.texts import INVALID_LINK
from app.core.config import MAX_FILE_SIZE_BYTES

router = Router()

@router.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    url = message.text
    if not await is_valid_terabox_link(url):
        return await message.answer(INVALID_LINK)

    msg = await message.answer("🔍 **Validating and Analyzing Media... ⏳**")
    
    info = await fetch_media_info(url)
    if not info.get("ok"):
        return await msg.edit_text("❌ Failed to fetch file information.")

    if info["file_size"] > MAX_FILE_SIZE_BYTES:
        return await msg.edit_text("❌ **File Too Large!**\nMaximum supported file size is 2GB.")

    size_mb = info['file_size'] / (1024 * 1024)
    text = f"""
✅ **Media Found!**
🎬 Name: `{info['file_name']}`
📦 Size: {size_mb:.2f} MB

Choose an option below:
    """
    # Safe callback data hack (storing URL temporary or using a short ID is better in production)
    # For demo, we assume the direct link is passed
    await msg.edit_text(text, reply_markup=download_action(info['download_url']))

@router.callback_query(F.data.startswith("start_dl|"))
async def process_download(callback: types.CallbackQuery):
    url = callback.data.split("|")[1]
    await callback.message.edit_text("⏳ **Added to Queue...**")
    # In a real app, send to asyncio.Queue here. Calling directly for structure demonstration:
    await download_and_send(callback.bot, callback.message.chat.id, url, "TeraBox_File.mp4", callback.message)
