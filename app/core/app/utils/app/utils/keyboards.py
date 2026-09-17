from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Download", callback_data="menu_download"),
         InlineKeyboardButton(text="👤 My Account", callback_data="menu_account")],
        [InlineKeyboardButton(text="👑 Premium", callback_data="menu_premium"),
         InlineKeyboardButton(text="📊 My Downloads", callback_data="menu_history")],
        [InlineKeyboardButton(text="❓ Tutorial", callback_data="menu_tutorial"),
         InlineKeyboardButton(text="💬 Support", callback_data="menu_support")]
    ])

def download_action(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Start Download", callback_data=f"start_dl|{url}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action")]
    ])
